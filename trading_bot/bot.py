"""
Main Trading Bot - Autonomous AI Trading System
Orchestrates data fetching, ML predictions, strategy execution, and risk management
"""
import yaml
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
import logging
from datetime import datetime

from trading_bot.data import MarketDataFetcher, FeatureEngineering
from trading_bot.models import EnsembleModel
from trading_bot.strategies import HybridStrategy, MLTradingStrategy, SignalType
from trading_bot.risk import Portfolio, RiskManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AITradingBot:
    """Autonomous AI Trading Bot with ML models and risk management"""
    
    def __init__(self, config_path: str = 'config.yaml'):
        """Initialize the trading bot"""
        logger.info("Initializing AI Trading Bot...")
        
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Initialize components
        self.symbols = self.config['trading']['symbols']
        self.data_fetcher = MarketDataFetcher(
            symbols=self.symbols,
            interval=self.config['data']['interval'],
            history_days=self.config['data']['history_days']
        )
        
        self.portfolio = Portfolio(self.config['trading']['initial_capital'])
        self.risk_manager = RiskManager(
            max_position_size=self.config['trading']['max_position_size'],
            stop_loss=self.config['trading']['stop_loss'],
            take_profit=self.config['trading']['take_profit'],
            max_daily_loss=self.config['risk']['max_daily_loss'],
            max_portfolio_risk=self.config['risk']['max_portfolio_risk']
        )
        
        self.ensemble_model = EnsembleModel()
        self.strategy = None
        self.is_trained = False
        
        logger.info("Trading Bot initialized successfully")
    
    def fetch_and_prepare_data(self) -> Dict[str, pd.DataFrame]:
        """Fetch and prepare market data with features"""
        logger.info("Fetching market data...")
        raw_data = self.data_fetcher.fetch_all()
        
        prepared_data = {}
        for symbol, df in raw_data.items():
            # Add technical indicators
            df_features = FeatureEngineering.add_technical_indicators(df)
            df_features = df_features.dropna()
            
            if len(df_features) > 100:  # Ensure enough data
                prepared_data[symbol] = df_features
                logger.info(f"Prepared {len(df_features)} records for {symbol}")
        
        return prepared_data
    
    def train_models(self, data: Dict[str, pd.DataFrame]):
        """Train ML models on historical data"""
        logger.info("Training ML models...")
        
        # Use first symbol for training (can be enhanced to use multiple)
        symbol = list(data.keys())[0]
        df = data[symbol]
        
        # Prepare features for training
        feature_cols = ['Close', 'Volume', 'SMA_20', 'SMA_50', 'RSI', 'MACD', 
                       'BB_Upper', 'BB_Lower', 'Volume_Ratio', 'Volatility']
        feature_cols = [col for col in feature_cols if col in df.columns]
        
        # Scale and prepare data
        from sklearn.preprocessing import MinMaxScaler
        scaler = MinMaxScaler()
        scaled_data = scaler.fit_transform(df[feature_cols].values)
        
        # Create sequences for LSTM
        lookback = self.config['ml']['lookback_period']
        X_lstm, y = FeatureEngineering.create_sequences(scaled_data, lookback)
        
        # Prepare features for tree models
        X_features = scaled_data[lookback:]
        
        # Train ensemble
        self.ensemble_model.train(X_lstm, X_features, y)
        
        # Initialize strategy
        ml_strategy = MLTradingStrategy(self.ensemble_model)
        self.strategy = HybridStrategy(ml_strategy)
        
        self.is_trained = True
        logger.info("Models trained successfully")
    
    def generate_predictions(self, data: pd.DataFrame) -> np.ndarray:
        """Generate predictions for given data"""
        if not self.is_trained:
            raise ValueError("Models not trained. Call train_models() first.")
        
        # Prepare features
        feature_cols = ['Close', 'Volume', 'SMA_20', 'SMA_50', 'RSI', 'MACD',
                       'BB_Upper', 'BB_Lower', 'Volume_Ratio', 'Volatility']
        feature_cols = [col for col in feature_cols if col in data.columns]
        
        from sklearn.preprocessing import MinMaxScaler
        scaler = MinMaxScaler()
        scaled_data = scaler.fit_transform(data[feature_cols].values)
        
        # Create sequences
        lookback = self.config['ml']['lookback_period']
        X_lstm, _ = FeatureEngineering.create_sequences(scaled_data, lookback)
        X_features = scaled_data[lookback:]
        
        # Generate predictions
        predictions = self.ensemble_model.predict(X_lstm, X_features)
        
        return predictions
    
    def execute_trading_cycle(self, data: Dict[str, pd.DataFrame]):
        """Execute one trading cycle: analyze, signal, trade"""
        logger.info("Executing trading cycle...")
        
        # Reset daily tracking
        self.risk_manager.reset_daily_tracking(self.portfolio)
        
        # Process each symbol
        for symbol, df in data.items():
            try:
                # Generate predictions
                predictions = self.generate_predictions(df)
                
                # Generate trading signal
                df.name = symbol  # Add symbol name to dataframe
                signal = self.strategy.generate_signals(df, predictions)
                
                logger.info(f"Signal for {symbol}: {signal}")
                
                # Execute trade based on signal
                self._execute_signal(signal)
                
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
        
        # Manage existing positions
        self._manage_positions()
        
        # Log portfolio status
        self._log_portfolio_status()
    
    def _execute_signal(self, signal):
        """Execute trade based on signal"""
        if signal.signal == SignalType.BUY and signal.confidence > 0.6:
            # Calculate position size
            volatility = 0.02  # Simplified, should be calculated from data
            position_size = self.risk_manager.calculate_position_size(
                self.portfolio.cash, signal.confidence, volatility
            )
            
            # Validate trade
            valid, message = self.risk_manager.validate_trade(
                self.portfolio, signal.symbol, position_size, signal.confidence
            )
            
            if valid:
                shares = position_size / signal.price
                self.portfolio.add_position(signal.symbol, shares, signal.price)
                logger.info(f"Executed BUY: {signal.symbol}, {shares:.2f} shares @ ${signal.price:.2f}")
            else:
                logger.warning(f"Trade rejected: {message}")
        
        elif signal.signal == SignalType.SELL and signal.symbol in self.portfolio.positions:
            # Sell position
            self.portfolio.remove_position(signal.symbol)
            logger.info(f"Executed SELL: {signal.symbol}")
    
    def _manage_positions(self):
        """Manage existing positions (stop loss, take profit)"""
        actions = self.risk_manager.manage_positions(self.portfolio)
        
        for action in actions:
            action_type, symbol = action.split(':')
            if action_type in ['STOP_LOSS', 'TAKE_PROFIT']:
                self.portfolio.remove_position(symbol)
                logger.info(f"Position closed: {symbol} ({action_type})")
    
    def _log_portfolio_status(self):
        """Log current portfolio status"""
        logger.info("="*50)
        logger.info("Portfolio Status:")
        logger.info(f"Total Value: ${self.portfolio.total_value:,.2f}")
        logger.info(f"Cash: ${self.portfolio.cash:,.2f}")
        logger.info(f"Total P/L: ${self.portfolio.total_profit_loss:,.2f}")
        logger.info(f"Total Return: {self.portfolio.total_return:.2%}")
        logger.info(f"Open Positions: {len(self.portfolio.positions)}")
        
        for symbol, pos in self.portfolio.positions.items():
            logger.info(f"  {symbol}: {pos.shares:.2f} shares, P/L: ${pos.profit_loss:.2f} ({pos.profit_loss_pct:.2%})")
        logger.info("="*50)
    
    def run(self, train: bool = True, cycles: int = 1):
        """Run the trading bot"""
        logger.info(f"Starting AI Trading Bot (train={train}, cycles={cycles})")
        
        # Fetch and prepare data
        data = self.fetch_and_prepare_data()
        
        if not data:
            logger.error("No data available. Exiting.")
            return
        
        # Train models if needed
        if train:
            self.train_models(data)
        
        # Execute trading cycles
        for cycle in range(cycles):
            logger.info(f"\n{'='*60}")
            logger.info(f"Trading Cycle {cycle + 1}/{cycles}")
            logger.info(f"{'='*60}\n")
            
            # Refresh data for live trading (in practice, fetch latest data)
            if cycle > 0:
                data = self.fetch_and_prepare_data()
            
            # Execute trading
            self.execute_trading_cycle(data)
        
        logger.info("Trading bot execution completed")
        return self.portfolio
    
    def get_performance_metrics(self) -> Dict:
        """Get performance metrics"""
        return {
            'total_value': self.portfolio.total_value,
            'total_return': self.portfolio.total_return,
            'num_trades': len(self.portfolio.trade_history),
            'num_positions': len(self.portfolio.positions),
            'cash': self.portfolio.cash
        }


if __name__ == "__main__":
    # Run the trading bot
    bot = AITradingBot()
    portfolio = bot.run(train=True, cycles=1)
    
    print("\n" + "="*60)
    print("Final Results:")
    print("="*60)
    metrics = bot.get_performance_metrics()
    for key, value in metrics.items():
        print(f"{key}: {value}")
