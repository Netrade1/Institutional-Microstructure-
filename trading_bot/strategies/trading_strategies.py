"""
Trading Strategies - AI-powered trading logic
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Trading signal types"""
    BUY = 1
    SELL = -1
    HOLD = 0


class TradingSignal:
    """Represents a trading signal"""
    
    def __init__(self, symbol: str, signal: SignalType, confidence: float, 
                 price: float, timestamp: pd.Timestamp):
        self.symbol = symbol
        self.signal = signal
        self.confidence = confidence
        self.price = price
        self.timestamp = timestamp
        
    def __repr__(self):
        return f"Signal({self.symbol}, {self.signal.name}, confidence={self.confidence:.2f}, price={self.price})"


class MLTradingStrategy:
    """ML-based trading strategy using ensemble predictions"""
    
    def __init__(self, model, threshold: float = 0.02):
        self.model = model
        self.threshold = threshold  # Minimum price change to trigger signal
        
    def generate_signals(self, data: pd.DataFrame, predictions: np.ndarray) -> List[TradingSignal]:
        """Generate trading signals based on ML predictions"""
        signals = []
        
        current_price = data['Close'].iloc[-1]
        predicted_price = predictions[-1]
        
        # Calculate expected return
        expected_return = (predicted_price - current_price) / current_price
        
        # Calculate confidence based on prediction certainty
        confidence = min(abs(expected_return) / self.threshold, 1.0)
        
        # Generate signal
        if expected_return > self.threshold:
            signal = SignalType.BUY
        elif expected_return < -self.threshold:
            signal = SignalType.SELL
        else:
            signal = SignalType.HOLD
        
        trading_signal = TradingSignal(
            symbol=data.name if hasattr(data, 'name') else 'UNKNOWN',
            signal=signal,
            confidence=confidence,
            price=current_price,
            timestamp=data.index[-1]
        )
        
        signals.append(trading_signal)
        return signals


class TechnicalStrategy:
    """Technical analysis-based strategy"""
    
    @staticmethod
    def generate_signals(data: pd.DataFrame) -> List[TradingSignal]:
        """Generate signals based on technical indicators"""
        signals = []
        
        # Get latest indicators
        rsi = data['RSI'].iloc[-1]
        macd = data['MACD'].iloc[-1]
        macd_signal = data['MACD_Signal'].iloc[-1]
        bb_upper = data['BB_Upper'].iloc[-1]
        bb_lower = data['BB_Lower'].iloc[-1]
        close = data['Close'].iloc[-1]
        
        # Signal logic
        signal = SignalType.HOLD
        confidence = 0.5
        
        # RSI-based signals
        if rsi < 30:  # Oversold
            signal = SignalType.BUY
            confidence = min((30 - rsi) / 30, 1.0)
        elif rsi > 70:  # Overbought
            signal = SignalType.SELL
            confidence = min((rsi - 70) / 30, 1.0)
        
        # MACD crossover
        if macd > macd_signal and signal != SignalType.SELL:
            signal = SignalType.BUY
            confidence = max(confidence, 0.6)
        elif macd < macd_signal and signal != SignalType.BUY:
            signal = SignalType.SELL
            confidence = max(confidence, 0.6)
        
        # Bollinger Bands
        if close < bb_lower:
            signal = SignalType.BUY
            confidence = max(confidence, 0.7)
        elif close > bb_upper:
            signal = SignalType.SELL
            confidence = max(confidence, 0.7)
        
        trading_signal = TradingSignal(
            symbol=data.name if hasattr(data, 'name') else 'UNKNOWN',
            signal=signal,
            confidence=confidence,
            price=close,
            timestamp=data.index[-1]
        )
        
        return [trading_signal]


class HybridStrategy:
    """Combines ML and Technical strategies for robust trading"""
    
    def __init__(self, ml_strategy: MLTradingStrategy, ml_weight: float = 0.7):
        self.ml_strategy = ml_strategy
        self.technical_strategy = TechnicalStrategy()
        self.ml_weight = ml_weight
        self.technical_weight = 1 - ml_weight
        
    def generate_signals(self, data: pd.DataFrame, predictions: np.ndarray) -> TradingSignal:
        """Generate hybrid signals combining ML and technical analysis"""
        
        # Get signals from both strategies
        ml_signals = self.ml_strategy.generate_signals(data, predictions)
        tech_signals = self.technical_strategy.generate_signals(data)
        
        ml_signal = ml_signals[0]
        tech_signal = tech_signals[0]
        
        # Combine signals with weights
        ml_value = ml_signal.signal.value * ml_signal.confidence * self.ml_weight
        tech_value = tech_signal.signal.value * tech_signal.confidence * self.technical_weight
        
        combined_value = ml_value + tech_value
        combined_confidence = (
            ml_signal.confidence * self.ml_weight + 
            tech_signal.confidence * self.technical_weight
        )
        
        # Determine final signal
        if combined_value > 0.2:
            final_signal = SignalType.BUY
        elif combined_value < -0.2:
            final_signal = SignalType.SELL
        else:
            final_signal = SignalType.HOLD
        
        return TradingSignal(
            symbol=data.name if hasattr(data, 'name') else 'UNKNOWN',
            signal=final_signal,
            confidence=combined_confidence,
            price=data['Close'].iloc[-1],
            timestamp=data.index[-1]
        )


class StrategyBacktester:
    """Backtesting framework for trading strategies"""
    
    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = []
        
    def backtest(self, data: pd.DataFrame, signals: List[TradingSignal]) -> Dict:
        """Run backtest on historical data"""
        self.capital = self.initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = [self.capital]
        
        for signal in signals:
            if signal.signal == SignalType.BUY and signal.confidence > 0.5:
                # Buy logic
                position_size = self.capital * 0.1  # 10% of capital
                shares = position_size / signal.price
                
                if signal.symbol not in self.positions:
                    self.positions[signal.symbol] = {
                        'shares': shares,
                        'entry_price': signal.price,
                        'entry_time': signal.timestamp
                    }
                    self.capital -= position_size
                    self.trades.append({
                        'action': 'BUY',
                        'symbol': signal.symbol,
                        'price': signal.price,
                        'shares': shares,
                        'timestamp': signal.timestamp
                    })
                    
            elif signal.signal == SignalType.SELL and signal.symbol in self.positions:
                # Sell logic
                position = self.positions[signal.symbol]
                proceeds = position['shares'] * signal.price
                profit = proceeds - (position['shares'] * position['entry_price'])
                
                self.capital += proceeds
                self.trades.append({
                    'action': 'SELL',
                    'symbol': signal.symbol,
                    'price': signal.price,
                    'shares': position['shares'],
                    'profit': profit,
                    'timestamp': signal.timestamp
                })
                del self.positions[signal.symbol]
            
            # Update equity curve
            total_equity = self.capital
            for pos in self.positions.values():
                total_equity += pos['shares'] * signal.price
            self.equity_curve.append(total_equity)
        
        # Calculate metrics
        total_return = (self.equity_curve[-1] - self.initial_capital) / self.initial_capital
        max_drawdown = self._calculate_max_drawdown()
        sharpe_ratio = self._calculate_sharpe_ratio()
        
        results = {
            'initial_capital': self.initial_capital,
            'final_capital': self.equity_curve[-1],
            'total_return': total_return,
            'num_trades': len(self.trades),
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'equity_curve': self.equity_curve
        }
        
        logger.info(f"Backtest Results: Return={total_return:.2%}, Sharpe={sharpe_ratio:.2f}, Max DD={max_drawdown:.2%}")
        return results
    
    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown"""
        equity = np.array(self.equity_curve)
        running_max = np.maximum.accumulate(equity)
        drawdown = (equity - running_max) / running_max
        return abs(drawdown.min())
    
    def _calculate_sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio"""
        if len(self.equity_curve) < 2:
            return 0.0
        
        returns = np.diff(self.equity_curve) / self.equity_curve[:-1]
        excess_returns = returns - (risk_free_rate / 252)  # Daily risk-free rate
        
        if len(excess_returns) == 0 or np.std(excess_returns) == 0:
            return 0.0
        
        return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
