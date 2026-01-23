"""
Risk Management System - Controls trading risk and portfolio allocation
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents a trading position"""
    symbol: str
    shares: float
    entry_price: float
    current_price: float
    
    @property
    def value(self) -> float:
        return self.shares * self.current_price
    
    @property
    def profit_loss(self) -> float:
        return (self.current_price - self.entry_price) * self.shares
    
    @property
    def profit_loss_pct(self) -> float:
        return (self.current_price - self.entry_price) / self.entry_price


class Portfolio:
    """Portfolio management and tracking"""
    
    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.trade_history = []
        
    def add_position(self, symbol: str, shares: float, price: float):
        """Add or update a position"""
        if symbol in self.positions:
            # Average in
            pos = self.positions[symbol]
            total_shares = pos.shares + shares
            avg_price = (pos.entry_price * pos.shares + price * shares) / total_shares
            self.positions[symbol] = Position(symbol, total_shares, avg_price, price)
        else:
            self.positions[symbol] = Position(symbol, shares, price, price)
        
        self.cash -= shares * price
        self.trade_history.append({
            'action': 'BUY',
            'symbol': symbol,
            'shares': shares,
            'price': price
        })
        logger.info(f"Added position: {symbol}, {shares} shares @ ${price:.2f}")
    
    def remove_position(self, symbol: str, shares: Optional[float] = None):
        """Remove or reduce a position"""
        if symbol not in self.positions:
            logger.warning(f"Position {symbol} not found")
            return
        
        pos = self.positions[symbol]
        shares_to_sell = shares if shares else pos.shares
        
        if shares_to_sell >= pos.shares:
            # Close entire position
            self.cash += pos.shares * pos.current_price
            self.trade_history.append({
                'action': 'SELL',
                'symbol': symbol,
                'shares': pos.shares,
                'price': pos.current_price,
                'profit': pos.profit_loss
            })
            del self.positions[symbol]
            logger.info(f"Closed position: {symbol}, profit: ${pos.profit_loss:.2f}")
        else:
            # Partial close
            self.cash += shares_to_sell * pos.current_price
            pos.shares -= shares_to_sell
            self.trade_history.append({
                'action': 'SELL',
                'symbol': symbol,
                'shares': shares_to_sell,
                'price': pos.current_price
            })
            logger.info(f"Reduced position: {symbol}, sold {shares_to_sell} shares")
    
    def update_prices(self, prices: Dict[str, float]):
        """Update current prices for all positions"""
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol].current_price = price
    
    @property
    def total_value(self) -> float:
        """Total portfolio value"""
        positions_value = sum(pos.value for pos in self.positions.values())
        return self.cash + positions_value
    
    @property
    def total_profit_loss(self) -> float:
        """Total profit/loss across all positions"""
        return sum(pos.profit_loss for pos in self.positions.values())
    
    @property
    def total_return(self) -> float:
        """Total return percentage"""
        return (self.total_value - self.initial_capital) / self.initial_capital
    
    def get_position_weights(self) -> Dict[str, float]:
        """Get position weights in portfolio"""
        total = self.total_value
        return {symbol: pos.value / total for symbol, pos in self.positions.items()}


class RiskManager:
    """Manages trading risk and position sizing"""
    
    def __init__(self, max_position_size: float = 0.2, stop_loss: float = 0.02,
                 take_profit: float = 0.05, max_daily_loss: float = 0.05,
                 max_portfolio_risk: float = 0.15):
        self.max_position_size = max_position_size
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.max_daily_loss = max_daily_loss
        self.max_portfolio_risk = max_portfolio_risk
        self.daily_start_value = None
        
    def calculate_position_size(self, capital: float, confidence: float, 
                                volatility: float = 0.02) -> float:
        """Calculate position size based on risk parameters"""
        # Kelly Criterion with adjustments
        win_rate = 0.5 + (confidence - 0.5) * 0.5  # Map confidence to win rate
        avg_win = self.take_profit
        avg_loss = self.stop_loss
        
        kelly = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
        kelly = max(0, min(kelly, self.max_position_size))
        
        # Adjust for volatility
        risk_adjusted = kelly * (0.02 / volatility) if volatility > 0 else kelly * 0.5
        
        # Apply maximum position size limit
        final_size = min(risk_adjusted, self.max_position_size)
        
        return capital * final_size
    
    def should_stop_loss(self, position: Position) -> bool:
        """Check if stop loss should be triggered"""
        return position.profit_loss_pct <= -self.stop_loss
    
    def should_take_profit(self, position: Position) -> bool:
        """Check if take profit should be triggered"""
        return position.profit_loss_pct >= self.take_profit
    
    def check_daily_loss_limit(self, portfolio: Portfolio) -> bool:
        """Check if daily loss limit exceeded"""
        if self.daily_start_value is None:
            self.daily_start_value = portfolio.total_value
            return False
        
        daily_loss = (portfolio.total_value - self.daily_start_value) / self.daily_start_value
        return daily_loss <= -self.max_daily_loss
    
    def reset_daily_tracking(self, portfolio: Portfolio):
        """Reset daily tracking (call at start of trading day)"""
        self.daily_start_value = portfolio.total_value
    
    def check_portfolio_risk(self, portfolio: Portfolio) -> bool:
        """Check if portfolio risk is within limits"""
        positions_value = sum(pos.value for pos in portfolio.positions.values())
        total_value = portfolio.total_value
        
        if total_value == 0:
            return True
        
        exposure = positions_value / total_value
        return exposure <= (1 - self.max_portfolio_risk)
    
    def validate_trade(self, portfolio: Portfolio, symbol: str, 
                      position_size: float, confidence: float) -> tuple[bool, str]:
        """Validate if trade should be executed"""
        
        # Check daily loss limit
        if self.check_daily_loss_limit(portfolio):
            return False, "Daily loss limit exceeded"
        
        # Check if position size is within limits
        max_allowed = portfolio.total_value * self.max_position_size
        if position_size > max_allowed:
            return False, f"Position size exceeds limit (max: ${max_allowed:.2f})"
        
        # Check portfolio risk
        if not self.check_portfolio_risk(portfolio):
            return False, "Portfolio risk limit exceeded"
        
        # Check confidence threshold
        if confidence < 0.5:
            return False, "Insufficient confidence"
        
        # Check available cash
        if position_size > portfolio.cash:
            return False, "Insufficient cash"
        
        return True, "Trade validated"
    
    def manage_positions(self, portfolio: Portfolio) -> List[str]:
        """Check all positions and return symbols that need action"""
        actions = []
        
        for symbol, position in portfolio.positions.items():
            if self.should_stop_loss(position):
                actions.append(f"STOP_LOSS:{symbol}")
                logger.warning(f"Stop loss triggered for {symbol}")
            elif self.should_take_profit(position):
                actions.append(f"TAKE_PROFIT:{symbol}")
                logger.info(f"Take profit triggered for {symbol}")
        
        return actions


class PortfolioOptimizer:
    """Optimizes portfolio allocation using modern portfolio theory"""
    
    @staticmethod
    def calculate_optimal_weights(returns: pd.DataFrame, risk_free_rate: float = 0.02) -> Dict[str, float]:
        """Calculate optimal portfolio weights using mean-variance optimization"""
        mean_returns = returns.mean()
        cov_matrix = returns.cov()
        
        num_assets = len(returns.columns)
        
        # Simple equal-weight for now (can be enhanced with optimization libraries)
        weights = {symbol: 1.0 / num_assets for symbol in returns.columns}
        
        return weights
    
    @staticmethod
    def calculate_var(returns: np.ndarray, confidence_level: float = 0.95) -> float:
        """Calculate Value at Risk (VaR)"""
        return np.percentile(returns, (1 - confidence_level) * 100)
    
    @staticmethod
    def calculate_cvar(returns: np.ndarray, confidence_level: float = 0.95) -> float:
        """Calculate Conditional Value at Risk (CVaR)"""
        var = PortfolioOptimizer.calculate_var(returns, confidence_level)
        return returns[returns <= var].mean()
