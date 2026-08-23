"""
Unit tests for the AI Trading Bot
"""
import unittest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from trading_bot.data import MarketDataFetcher, FeatureEngineering
from trading_bot.models import LSTMModel, RandomForestModel, XGBoostModel
from trading_bot.strategies import SignalType, TradingSignal, MLTradingStrategy
from trading_bot.risk import Portfolio, RiskManager, Position


class TestDataFetcher(unittest.TestCase):
    """Test data fetching and feature engineering"""
    
    def test_feature_engineering(self):
        """Test feature creation"""
        # Create sample data
        dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
        data = pd.DataFrame({
            'Open': np.random.uniform(100, 110, 100),
            'High': np.random.uniform(110, 120, 100),
            'Low': np.random.uniform(90, 100, 100),
            'Close': np.random.uniform(100, 110, 100),
            'Volume': np.random.uniform(1000000, 2000000, 100)
        }, index=dates)
        
        # Add features
        df_features = FeatureEngineering.add_technical_indicators(data)
        
        # Check that features were added
        self.assertIn('SMA_20', df_features.columns)
        self.assertIn('RSI', df_features.columns)
        self.assertIn('MACD', df_features.columns)
        
    def test_sequence_creation(self):
        """Test sequence creation for LSTM"""
        data = np.random.rand(100, 5)
        X, y = FeatureEngineering.create_sequences(data, lookback=10)
        
        self.assertEqual(X.shape[0], 90)  # 100 - 10
        self.assertEqual(X.shape[1], 10)  # lookback
        self.assertEqual(len(y), 90)


class TestModels(unittest.TestCase):
    """Test ML models"""
    
    def setUp(self):
        """Setup test data"""
        self.X = np.random.rand(100, 60, 5)
        self.y = np.random.rand(100)
        self.X_flat = np.random.rand(100, 10)
        
    def test_lstm_model(self):
        """Test LSTM model"""
        model = LSTMModel(lookback=60, features=5)
        model.build_model(units=10, dropout=0.1)
        
        self.assertIsNotNone(model.model)
        
    def test_random_forest(self):
        """Test Random Forest model"""
        model = RandomForestModel(n_estimators=10)
        model.train(self.X_flat, self.y)
        
        predictions = model.predict(self.X_flat)
        self.assertEqual(len(predictions), len(self.y))
        
    def test_xgboost(self):
        """Test XGBoost model"""
        model = XGBoostModel(n_estimators=10)
        model.train(self.X_flat, self.y)
        
        predictions = model.predict(self.X_flat)
        self.assertEqual(len(predictions), len(self.y))


class TestStrategies(unittest.TestCase):
    """Test trading strategies"""
    
    def test_signal_creation(self):
        """Test signal creation"""
        signal = TradingSignal(
            symbol='TEST',
            signal=SignalType.BUY,
            confidence=0.8,
            price=100.0,
            timestamp=pd.Timestamp.now()
        )
        
        self.assertEqual(signal.symbol, 'TEST')
        self.assertEqual(signal.signal, SignalType.BUY)
        self.assertEqual(signal.confidence, 0.8)


class TestRiskManagement(unittest.TestCase):
    """Test risk management"""
    
    def test_portfolio_creation(self):
        """Test portfolio initialization"""
        portfolio = Portfolio(initial_capital=100000)
        
        self.assertEqual(portfolio.cash, 100000)
        self.assertEqual(portfolio.total_value, 100000)
        
    def test_position_management(self):
        """Test adding and removing positions"""
        portfolio = Portfolio(initial_capital=100000)
        
        # Add position
        portfolio.add_position('TEST', shares=10, price=100)
        
        self.assertEqual(len(portfolio.positions), 1)
        self.assertEqual(portfolio.cash, 99000)  # 100000 - 1000
        
        # Remove position
        portfolio.positions['TEST'].current_price = 110
        portfolio.remove_position('TEST')
        
        self.assertEqual(len(portfolio.positions), 0)
        self.assertEqual(portfolio.cash, 100100)  # Made $100 profit
        
    def test_risk_manager(self):
        """Test risk manager"""
        rm = RiskManager(max_position_size=0.2, stop_loss=0.02)
        portfolio = Portfolio(100000)
        
        # Test position sizing
        size = rm.calculate_position_size(100000, confidence=0.7)
        self.assertLessEqual(size, 20000)  # Max 20% of capital
        
        # Test stop loss
        pos = Position('TEST', 10, 100, 95)
        self.assertTrue(rm.should_stop_loss(pos))
        
        # Test take profit
        pos2 = Position('TEST', 10, 100, 106)
        self.assertTrue(rm.should_take_profit(pos2))


class TestPortfolio(unittest.TestCase):
    """Test portfolio functionality"""
    
    def test_profit_loss_calculation(self):
        """Test P/L calculations"""
        pos = Position('TEST', shares=10, entry_price=100, current_price=110)
        
        self.assertEqual(pos.value, 1100)
        self.assertEqual(pos.profit_loss, 100)
        self.assertEqual(pos.profit_loss_pct, 0.1)
        
    def test_portfolio_return(self):
        """Test total return calculation"""
        portfolio = Portfolio(initial_capital=100000)
        portfolio.add_position('TEST', 10, 100)
        
        # Update price
        portfolio.update_prices({'TEST': 110})
        
        # Check return
        expected_value = 99000 + 1100  # cash + position value
        self.assertEqual(portfolio.total_value, expected_value)


if __name__ == '__main__':
    unittest.main()
