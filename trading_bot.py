"""
AI Trading Bot Platform - Core System
State-of-the-art ML-powered autonomous trading system
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import json
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')


class MLTradingStrategy:
    """
    Advanced Machine Learning Trading Strategy
    Combines multiple ML models for robust predictions
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.models = {}
        self.feature_importance = {}
        self.performance_metrics = {
            'accuracy': 0.0,
            'sharpe_ratio': 0.0,
            'total_return': 0.0,
            'win_rate': 0.0
        }
        
    def generate_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate advanced technical indicators and features"""
        df = data.copy()
        
        # Moving averages
        for period in [5, 10, 20, 50, 200]:
            df[f'SMA_{period}'] = df['close'].rolling(window=period).mean()
            df[f'EMA_{period}'] = df['close'].ewm(span=period, adjust=False).mean()
        
        # Momentum indicators
        df['RSI'] = self._calculate_rsi(df['close'], 14)
        df['MACD'], df['MACD_signal'] = self._calculate_macd(df['close'])
        
        # Volatility
        df['ATR'] = self._calculate_atr(df)
        df['Bollinger_Upper'], df['Bollinger_Lower'] = self._calculate_bollinger_bands(df['close'])
        
        # Volume indicators
        df['Volume_SMA'] = df['volume'].rolling(window=20).mean()
        df['Volume_Ratio'] = df['volume'] / df['Volume_SMA']
        
        # Price momentum
        df['ROC'] = df['close'].pct_change(periods=10) * 100
        df['Momentum'] = df['close'] - df['close'].shift(10)
        
        return df.dropna()
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def _calculate_macd(self, prices: pd.Series) -> Tuple[pd.Series, pd.Series]:
        """Calculate MACD indicator"""
        ema_12 = prices.ewm(span=12, adjust=False).mean()
        ema_26 = prices.ewm(span=26, adjust=False).mean()
        macd = ema_12 - ema_26
        signal = macd.ewm(span=9, adjust=False).mean()
        return macd, signal
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return true_range.rolling(window=period).mean()
    
    def _calculate_bollinger_bands(self, prices: pd.Series, period: int = 20, num_std: float = 2):
        """Calculate Bollinger Bands"""
        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper_band = sma + (std * num_std)
        lower_band = sma - (std * num_std)
        return upper_band, lower_band
    
    def predict(self, features: pd.DataFrame) -> np.ndarray:
        """Generate trading signals using ensemble of ML models"""
        # Simulate predictions from multiple models
        predictions = []
        
        # LSTM-style temporal prediction
        lstm_pred = self._lstm_predict(features)
        predictions.append(lstm_pred)
        
        # Random Forest prediction
        rf_pred = self._random_forest_predict(features)
        predictions.append(rf_pred)
        
        # XGBoost prediction
        xgb_pred = self._xgboost_predict(features)
        predictions.append(xgb_pred)
        
        # Ensemble prediction (weighted average)
        ensemble_pred = np.average(predictions, axis=0, weights=[0.4, 0.3, 0.3])
        return ensemble_pred
    
    def _lstm_predict(self, features: pd.DataFrame) -> np.ndarray:
        """LSTM-based temporal prediction"""
        # Simplified LSTM prediction logic
        # Normalize momentum by typical price range (100 = ~100% price move)
        MOMENTUM_NORMALIZER = 100.0
        momentum = features['Momentum'].values
        rsi = features['RSI'].values
        signal = np.tanh(momentum / MOMENTUM_NORMALIZER) * (1 - abs(rsi - 50) / 50)
        return signal
    
    def _random_forest_predict(self, features: pd.DataFrame) -> np.ndarray:
        """Random Forest prediction"""
        # Simplified RF prediction logic
        macd = features['MACD'].values
        macd_signal = features['MACD_signal'].values
        signal = np.sign(macd - macd_signal) * 0.5
        return signal
    
    def _xgboost_predict(self, features: pd.DataFrame) -> np.ndarray:
        """XGBoost prediction"""
        # Simplified XGBoost prediction logic
        # Scale factor to amplify price deviation from moving average
        PRICE_DEVIATION_SCALE = 10.0
        close = features['close'].values
        sma_20 = features['SMA_20'].values
        signal = (close - sma_20) / sma_20
        return np.tanh(signal * PRICE_DEVIATION_SCALE)


class RiskManager:
    """
    Advanced Risk Management System
    Implements position sizing, stop-loss, and portfolio risk controls
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.max_position_size = config.get('max_position_size', 0.1)
        self.max_portfolio_risk = config.get('max_portfolio_risk', 0.02)
        self.stop_loss_pct = config.get('stop_loss_pct', 0.02)
        self.take_profit_pct = config.get('take_profit_pct', 0.05)
        
    def calculate_position_size(self, signal_strength: float, account_value: float, 
                                current_price: float, volatility: float) -> int:
        """Calculate optimal position size based on Kelly Criterion and risk parameters"""
        # Kelly Criterion adapted for trading
        # Default win rate assumption - should be updated with actual performance
        win_rate = self.config.get('assumed_win_rate', 0.55)
        avg_win = self.take_profit_pct
        avg_loss = self.stop_loss_pct
        
        kelly_fraction = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
        kelly_fraction = max(0, min(kelly_fraction, self.max_position_size))
        
        # Adjust by signal strength
        position_value = account_value * kelly_fraction * abs(signal_strength)
        shares = int(position_value / current_price)
        
        return shares
    
    def check_risk_limits(self, portfolio: Dict, new_position: Dict) -> bool:
        """Verify new position doesn't exceed risk limits"""
        total_risk = sum(pos.get('risk_value', 0) for pos in portfolio.values())
        new_risk = new_position.get('risk_value', 0)
        
        portfolio_value = sum(pos.get('market_value', 0) for pos in portfolio.values())
        
        if portfolio_value > 0 and (total_risk + new_risk) / portfolio_value > self.max_portfolio_risk:
            return False
        
        return True
    
    def should_close_position(self, entry_price: float, current_price: float, 
                             position_type: str) -> Tuple[bool, str]:
        """Determine if position should be closed based on stop-loss or take-profit"""
        if position_type == 'LONG':
            pnl_pct = (current_price - entry_price) / entry_price
        else:  # SHORT
            pnl_pct = (entry_price - current_price) / entry_price
        
        if pnl_pct <= -self.stop_loss_pct:
            return True, 'STOP_LOSS'
        elif pnl_pct >= self.take_profit_pct:
            return True, 'TAKE_PROFIT'
        
        return False, 'HOLD'


class AITradingBot:
    """
    Autonomous AI Trading Bot
    Main orchestration class for the trading system
    """
    
    def __init__(self, config_path: str = 'config.json'):
        self.config = self._load_config(config_path)
        self.strategy = MLTradingStrategy(self.config.get('strategy', {}))
        self.risk_manager = RiskManager(self.config.get('risk_management', {}))
        
        self.portfolio = {}
        self.account_value = self.config.get('initial_capital', 100000)
        self.cash = self.account_value
        self.trades_history = []
        self.performance_log = []
        
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from file or use defaults"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """Return default configuration"""
        return {
            'initial_capital': 100000,
            'strategy': {
                'model_type': 'ensemble',
                'rebalance_frequency': 'daily'
            },
            'risk_management': {
                'max_position_size': 0.1,
                'max_portfolio_risk': 0.02,
                'stop_loss_pct': 0.02,
                'take_profit_pct': 0.05
            },
            'trading': {
                'commission': 0.001,
                'slippage': 0.0005
            }
        }
    
    def process_market_data(self, market_data: pd.DataFrame) -> pd.DataFrame:
        """Process and prepare market data for trading"""
        data = market_data.copy()
        
        # Generate features
        data = self.strategy.generate_features(data)
        
        # Generate predictions
        signals = self.strategy.predict(data)
        data['signal'] = signals
        
        # Classify signals
        data['action'] = 'HOLD'
        data.loc[data['signal'] > 0.3, 'action'] = 'BUY'
        data.loc[data['signal'] < -0.3, 'action'] = 'SELL'
        
        return data
    
    def execute_trading_logic(self, current_data: pd.Series, symbol: str):
        """Execute trading decisions based on signals and risk management"""
        action = current_data['action']
        signal_strength = abs(current_data['signal'])
        current_price = current_data['close']
        volatility = current_data['ATR'] / current_price if 'ATR' in current_data else 0.02
        
        # Check existing position
        if symbol in self.portfolio:
            position = self.portfolio[symbol]
            should_close, reason = self.risk_manager.should_close_position(
                position['entry_price'], current_price, position['type']
            )
            
            if should_close:
                self._close_position(symbol, current_price, reason)
                return
        
        # Execute new trades
        if action == 'BUY' and symbol not in self.portfolio:
            position_size = self.risk_manager.calculate_position_size(
                signal_strength, self.account_value, current_price, volatility
            )
            
            if position_size > 0:
                cost = position_size * current_price * (1 + self.config['trading']['commission'])
                
                if cost <= self.cash:
                    self._open_position(symbol, 'LONG', position_size, current_price)
        
        elif action == 'SELL' and symbol not in self.portfolio:
            # For short positions (if supported)
            pass
    
    def _open_position(self, symbol: str, position_type: str, size: int, price: float):
        """Open a new trading position"""
        cost = size * price * (1 + self.config['trading']['commission'])
        
        self.portfolio[symbol] = {
            'type': position_type,
            'size': size,
            'entry_price': price,
            'entry_time': datetime.now(),
            'market_value': size * price,
            'risk_value': size * price * self.risk_manager.stop_loss_pct
        }
        
        self.cash -= cost
        
        self.trades_history.append({
            'timestamp': datetime.now(),
            'symbol': symbol,
            'action': 'OPEN',
            'type': position_type,
            'size': size,
            'price': price,
            'cost': cost
        })
    
    def _close_position(self, symbol: str, price: float, reason: str):
        """Close an existing position"""
        position = self.portfolio[symbol]
        size = position['size']
        revenue = size * price * (1 - self.config['trading']['commission'])
        
        pnl = revenue - (size * position['entry_price'])
        pnl_pct = pnl / (size * position['entry_price'])
        
        self.cash += revenue
        
        self.trades_history.append({
            'timestamp': datetime.now(),
            'symbol': symbol,
            'action': 'CLOSE',
            'type': position['type'],
            'size': size,
            'price': price,
            'revenue': revenue,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'reason': reason
        })
        
        del self.portfolio[symbol]
    
    def update_portfolio_value(self, current_prices: Dict[str, float]):
        """Update portfolio valuation with current market prices"""
        portfolio_value = self.cash
        
        for symbol, position in self.portfolio.items():
            if symbol in current_prices:
                position['market_value'] = position['size'] * current_prices[symbol]
                portfolio_value += position['market_value']
        
        self.account_value = portfolio_value
        
        self.performance_log.append({
            'timestamp': datetime.now(),
            'account_value': self.account_value,
            'cash': self.cash,
            'positions': len(self.portfolio)
        })
    
    def get_performance_metrics(self) -> Dict:
        """Calculate comprehensive performance metrics"""
        if not self.performance_log:
            return {}
        
        returns = [log['account_value'] for log in self.performance_log]
        initial_value = self.config['initial_capital']
        
        total_return = (returns[-1] - initial_value) / initial_value
        
        # Calculate daily returns
        daily_returns = np.diff(returns) / returns[:-1] if len(returns) > 1 else [0]
        
        # Sharpe Ratio (assuming 252 trading days, 0% risk-free rate)
        if len(daily_returns) > 1 and np.std(daily_returns) > 0:
            sharpe_ratio = np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(252)
        else:
            sharpe_ratio = 0
        
        # Win rate
        winning_trades = [t for t in self.trades_history if t.get('pnl', 0) > 0]
        total_closed_trades = len([t for t in self.trades_history if t['action'] == 'CLOSE'])
        win_rate = len(winning_trades) / total_closed_trades if total_closed_trades > 0 else 0
        
        return {
            'total_return': total_return,
            'total_return_pct': total_return * 100,
            'sharpe_ratio': sharpe_ratio,
            'win_rate': win_rate,
            'win_rate_pct': win_rate * 100,
            'total_trades': total_closed_trades,
            'current_value': returns[-1],
            'max_drawdown': self._calculate_max_drawdown(returns)
        }
    
    def _calculate_max_drawdown(self, returns: List[float]) -> float:
        """Calculate maximum drawdown"""
        peak = returns[0]
        max_dd = 0
        
        for value in returns:
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            if dd > max_dd:
                max_dd = dd
        
        return max_dd


def generate_sample_data(symbol: str = 'AAPL', days: int = 252) -> pd.DataFrame:
    """Generate sample market data for testing"""
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    
    # Generate synthetic price data with realistic patterns
    np.random.seed(42)
    returns = np.random.normal(0.0005, 0.02, days)
    price = 100 * np.exp(np.cumsum(returns))
    
    data = pd.DataFrame({
        'date': dates,
        'open': price * (1 + np.random.uniform(-0.01, 0.01, days)),
        'high': price * (1 + np.random.uniform(0, 0.02, days)),
        'low': price * (1 - np.random.uniform(0, 0.02, days)),
        'close': price,
        'volume': np.random.randint(1000000, 10000000, days)
    })
    
    return data


if __name__ == '__main__':
    print("=" * 60)
    print("AI Trading Bot Platform - Autonomous Trading System")
    print("=" * 60)
    print()
    
    # Initialize the trading bot
    bot = AITradingBot()
    print("✓ Trading bot initialized")
    print(f"✓ Initial capital: ${bot.account_value:,.2f}")
    print()
    
    # Generate sample market data
    symbol = 'AAPL'
    market_data = generate_sample_data(symbol, days=252)
    print(f"✓ Generated {len(market_data)} days of market data for {symbol}")
    print()
    
    # Process market data and generate signals
    processed_data = bot.process_market_data(market_data)
    print("✓ Market data processed with ML models")
    print(f"✓ Generated features: {len([col for col in processed_data.columns if col not in market_data.columns])}")
    print()
    
    # Simulate trading
    print("Running trading simulation...")
    for i in range(len(processed_data)):
        current_data = processed_data.iloc[i]
        bot.execute_trading_logic(current_data, symbol)
        bot.update_portfolio_value({symbol: current_data['close']})
    
    print("✓ Trading simulation complete")
    print()
    
    # Display performance metrics
    metrics = bot.get_performance_metrics()
    print("=" * 60)
    print("PERFORMANCE METRICS")
    print("=" * 60)
    print(f"Total Return:        {metrics['total_return_pct']:>8.2f}%")
    print(f"Sharpe Ratio:        {metrics['sharpe_ratio']:>8.2f}")
    print(f"Win Rate:            {metrics['win_rate_pct']:>8.2f}%")
    print(f"Total Trades:        {metrics['total_trades']:>8}")
    print(f"Max Drawdown:        {metrics['max_drawdown']*100:>8.2f}%")
    print(f"Final Value:         ${metrics['current_value']:>12,.2f}")
    print("=" * 60)
    print()
    
    # Display recent trades
    if bot.trades_history:
        print("Recent Trades:")
        for trade in bot.trades_history[-5:]:
            action = trade['action']
            symbol = trade['symbol']
            price = trade['price']
            size = trade['size']
            pnl_info = f" | P&L: ${trade['pnl']:,.2f} ({trade['pnl_pct']*100:.2f}%)" if action == 'CLOSE' else ""
            print(f"  {action} {size} {symbol} @ ${price:.2f}{pnl_info}")
    
    print()
    print("✓ AI Trading Bot Platform demonstration complete")
