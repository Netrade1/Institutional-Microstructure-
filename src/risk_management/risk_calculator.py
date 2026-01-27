"""
Risk Calculator
Calculates various risk metrics and position sizing
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional


# Constants
TRADING_DAYS_PER_YEAR = 252


class RiskCalculator:
    """
    Calculates risk metrics and helps with position sizing and risk management.
    """
    
    @staticmethod
    def calculate_var(
        returns: pd.Series,
        confidence_level: float = 0.95,
        method: str = 'historical'
    ) -> float:
        """
        Calculate Value at Risk (VaR).
        
        Args:
            returns: Series of returns
            confidence_level: Confidence level (e.g., 0.95 for 95%)
            method: Calculation method ('historical', 'parametric', 'monte_carlo')
            
        Returns:
            VaR value
        """
        if method == 'historical':
            return np.percentile(returns, (1 - confidence_level) * 100)
        
        elif method == 'parametric':
            mean = returns.mean()
            std = returns.std()
            z_score = np.abs(np.percentile(np.random.standard_normal(10000), 
                                          (1 - confidence_level) * 100))
            return mean - z_score * std
        
        else:
            raise ValueError(f"Unknown VaR method: {method}")
    
    @staticmethod
    def calculate_cvar(
        returns: pd.Series,
        confidence_level: float = 0.95
    ) -> float:
        """
        Calculate Conditional Value at Risk (CVaR/Expected Shortfall).
        
        Args:
            returns: Series of returns
            confidence_level: Confidence level
            
        Returns:
            CVaR value
        """
        var = RiskCalculator.calculate_var(returns, confidence_level)
        cvar = returns[returns <= var].mean()
        
        return cvar
    
    @staticmethod
    def calculate_sharpe_ratio(
        returns: pd.Series,
        risk_free_rate: float = 0.02
    ) -> float:
        """
        Calculate Sharpe Ratio.
        
        Args:
            returns: Series of returns
            risk_free_rate: Risk-free rate (annualized)
            
        Returns:
            Sharpe ratio
        """
        excess_returns = returns - risk_free_rate / TRADING_DAYS_PER_YEAR  # Assume daily returns
        
        if returns.std() > 1e-8:  # Add minimum threshold
            return np.sqrt(TRADING_DAYS_PER_YEAR) * (excess_returns.mean() / returns.std())
        return 0.0
    
    @staticmethod
    def calculate_sortino_ratio(
        returns: pd.Series,
        risk_free_rate: float = 0.02
    ) -> float:
        """
        Calculate Sortino Ratio (uses downside deviation).
        
        Args:
            returns: Series of returns
            risk_free_rate: Risk-free rate (annualized)
            
        Returns:
            Sortino ratio
        """
        excess_returns = returns - risk_free_rate / TRADING_DAYS_PER_YEAR
        downside_returns = returns[returns < 0]
        
        if len(downside_returns) > 0 and downside_returns.std() > 1e-8:  # Add minimum threshold
            downside_deviation = downside_returns.std()
            return np.sqrt(TRADING_DAYS_PER_YEAR) * (excess_returns.mean() / downside_deviation)
        return 0.0
    
    @staticmethod
    def calculate_max_drawdown(prices: pd.Series) -> Dict[str, float]:
        """
        Calculate maximum drawdown.
        
        Args:
            prices: Series of prices or portfolio values
            
        Returns:
            Dictionary with max drawdown information
        """
        cumulative_max = prices.cummax()
        drawdown = (prices - cumulative_max) / cumulative_max
        max_drawdown = drawdown.min()
        
        max_dd_idx = drawdown.idxmin()
        peak_idx = prices[:max_dd_idx].idxmax()
        
        return {
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown * 100,
            'peak_date': peak_idx,
            'trough_date': max_dd_idx,
            'recovery_date': None  # Would need to calculate if price recovers
        }
    
    @staticmethod
    def calculate_position_size(
        account_value: float,
        risk_per_trade: float,
        entry_price: float,
        stop_loss_price: float,
        contract_size: float = 1.0
    ) -> int:
        """
        Calculate position size based on risk management rules.
        
        Args:
            account_value: Total account value
            risk_per_trade: Risk per trade as decimal (e.g., 0.02 for 2%)
            entry_price: Entry price
            stop_loss_price: Stop loss price
            contract_size: Size of one contract/share
            
        Returns:
            Position size (number of shares/contracts)
        """
        risk_amount = account_value * risk_per_trade
        price_risk = abs(entry_price - stop_loss_price)
        
        if price_risk <= 0:
            raise ValueError("Stop loss price must be different from entry price")
        
        position_size = int(risk_amount / (price_risk * contract_size))
        return max(position_size, 0)
    
    @staticmethod
    def calculate_kelly_criterion(
        win_rate: float,
        avg_win: float,
        avg_loss: float
    ) -> float:
        """
        Calculate Kelly Criterion for position sizing.
        
        Args:
            win_rate: Probability of winning (0-1)
            avg_win: Average win amount
            avg_loss: Average loss amount
            
        Returns:
            Kelly percentage (fraction of capital to risk)
        """
        if avg_loss <= 0:
            raise ValueError("Average loss must be positive")
        
        win_loss_ratio = avg_win / avg_loss
        kelly = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
        return max(0, min(kelly, 1))  # Constrain between 0 and 1
    
    @staticmethod
    def calculate_beta(
        asset_returns: pd.Series,
        market_returns: pd.Series
    ) -> float:
        """
        Calculate beta (systematic risk).
        
        Args:
            asset_returns: Series of asset returns
            market_returns: Series of market returns
            
        Returns:
            Beta coefficient
        """
        covariance = asset_returns.cov(market_returns)
        market_variance = market_returns.var()
        
        if market_variance <= 1e-8:
            raise ValueError("Market returns have zero or near-zero variance")
        
        return covariance / market_variance
    
    @staticmethod
    def calculate_portfolio_metrics(
        weights: Dict[str, float],
        returns: pd.DataFrame,
        covariance_matrix: Optional[pd.DataFrame] = None
    ) -> Dict:
        """
        Calculate portfolio-level risk metrics.
        
        Args:
            weights: Dictionary of asset weights
            returns: DataFrame of asset returns
            covariance_matrix: Optional pre-calculated covariance matrix
            
        Returns:
            Dictionary with portfolio metrics
        """
        weight_array = np.array([weights.get(col, 0) for col in returns.columns])
        
        # Portfolio return
        portfolio_return = (returns.mean() * weight_array).sum()
        
        # Portfolio variance and volatility
        if covariance_matrix is None:
            covariance_matrix = returns.cov()
        
        portfolio_variance = np.dot(weight_array, np.dot(covariance_matrix, weight_array))
        portfolio_volatility = np.sqrt(portfolio_variance)
        
        # Portfolio VaR
        portfolio_returns = (returns * weight_array).sum(axis=1)
        var_95 = RiskCalculator.calculate_var(portfolio_returns, 0.95)
        cvar_95 = RiskCalculator.calculate_cvar(portfolio_returns, 0.95)
        
        return {
            'expected_return': portfolio_return * TRADING_DAYS_PER_YEAR,  # Annualized
            'volatility': portfolio_volatility * np.sqrt(TRADING_DAYS_PER_YEAR),  # Annualized
            'var_95': var_95,
            'cvar_95': cvar_95,
            'sharpe_ratio': RiskCalculator.calculate_sharpe_ratio(portfolio_returns)
        }
    
    @staticmethod
    def calculate_risk_adjusted_return(
        returns: pd.Series,
        risk_free_rate: float = 0.02
    ) -> Dict[str, float]:
        """
        Calculate various risk-adjusted return metrics.
        
        Args:
            returns: Series of returns
            risk_free_rate: Risk-free rate
            
        Returns:
            Dictionary with risk-adjusted metrics
        """
        total_return = (1 + returns).prod() - 1
        annualized_return = (1 + total_return) ** (TRADING_DAYS_PER_YEAR / len(returns)) - 1
        
        return {
            'total_return': total_return,
            'annualized_return': annualized_return,
            'sharpe_ratio': RiskCalculator.calculate_sharpe_ratio(returns, risk_free_rate),
            'sortino_ratio': RiskCalculator.calculate_sortino_ratio(returns, risk_free_rate),
            'volatility': returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR),
            'var_95': RiskCalculator.calculate_var(returns, 0.95),
            'cvar_95': RiskCalculator.calculate_cvar(returns, 0.95)
        }
