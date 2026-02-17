"""
Data Module - Market data fetching and feature engineering
Provides data acquisition and technical indicator calculation
"""
import pandas as pd
import numpy as np
import yfinance as yf
from typing import Dict, List, Tuple
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MarketDataFetcher:
    """Fetches market data from various sources"""
    
    def __init__(self, symbols: List[str], interval: str = '1h', history_days: int = 365):
        """
        Initialize market data fetcher
        
        Args:
            symbols: List of trading symbols (e.g., ['BTC/USDT', 'AAPL'])
            interval: Data interval (e.g., '1h', '1d')
            history_days: Number of days of historical data
        """
        self.symbols = symbols
        self.interval = interval
        self.history_days = history_days
        logger.info(f"MarketDataFetcher initialized for {len(symbols)} symbols")
    
    def fetch_all(self) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for all symbols
        
        Returns:
            Dictionary mapping symbol to DataFrame with OHLCV data
        """
        data = {}
        for symbol in self.symbols:
            try:
                df = self.fetch_symbol(symbol)
                if df is not None and len(df) > 0:
                    data[symbol] = df
                    logger.info(f"Fetched {len(df)} records for {symbol}")
            except Exception as e:
                logger.error(f"Error fetching data for {symbol}: {e}")
        
        return data
    
    def fetch_symbol(self, symbol: str) -> pd.DataFrame:
        """
        Fetch data for a single symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            DataFrame with OHLCV columns
        """
        try:
            # Convert symbol format for yfinance (BTC/USDT -> BTC-USD)
            yf_symbol = self._convert_symbol_format(symbol)
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=self.history_days)
            
            # Fetch data from yfinance
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(start=start_date, end=end_date, interval=self._convert_interval())
            
            # Standardize column names
            df = df.rename(columns={
                'Open': 'Open',
                'High': 'High',
                'Low': 'Low',
                'Close': 'Close',
                'Volume': 'Volume'
            })
            
            # Select only OHLCV columns
            df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")
            return pd.DataFrame()
    
    def _convert_symbol_format(self, symbol: str) -> str:
        """Convert trading symbol to yfinance format"""
        # Handle crypto pairs
        if '/' in symbol:
            base, quote = symbol.split('/')
            if quote == 'USDT':
                return f"{base}-USD"
            return f"{base}-{quote}"
        # Handle stock symbols
        return symbol
    
    def _convert_interval(self) -> str:
        """Convert interval format to yfinance format"""
        interval_map = {
            '1h': '1h',
            '1d': '1d',
            '1m': '1m',
            '5m': '5m',
            '15m': '15m',
            '30m': '30m',
            '1wk': '1wk'
        }
        return interval_map.get(self.interval, '1d')


class FeatureEngineering:
    """Feature engineering for trading data"""
    
    @staticmethod
    def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """
        Add technical indicators to OHLCV data
        
        Args:
            df: DataFrame with OHLCV columns
            
        Returns:
            DataFrame with additional technical indicator columns
        """
        df = df.copy()
        
        # Moving Averages
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
        df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
        
        # RSI (Relative Strength Index)
        df['RSI'] = FeatureEngineering._calculate_rsi(df['Close'])
        
        # MACD
        df['MACD'] = df['EMA_12'] - df['EMA_26']
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
        
        # Bollinger Bands
        df['BB_Middle'] = df['Close'].rolling(window=20).mean()
        bb_std = df['Close'].rolling(window=20).std()
        df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
        df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
        
        # Volume indicators
        df['Volume_MA'] = df['Volume'].rolling(window=20).mean()
        df['Volume_Ratio'] = df['Volume'] / df['Volume_MA']
        
        # Volatility
        df['Returns'] = df['Close'].pct_change()
        df['Volatility'] = df['Returns'].rolling(window=20).std()
        
        # ATR (Average True Range)
        df['ATR'] = FeatureEngineering._calculate_atr(df)
        
        # Rate of Change
        df['ROC'] = df['Close'].pct_change(periods=10)
        
        # Stochastic Oscillator
        df['Stoch_K'], df['Stoch_D'] = FeatureEngineering._calculate_stochastic(df)
        
        return df
    
    @staticmethod
    def _calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def _calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        atr = true_range.rolling(window=period).mean()
        
        return atr
    
    @staticmethod
    def _calculate_stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> Tuple[pd.Series, pd.Series]:
        """Calculate Stochastic Oscillator"""
        low_min = df['Low'].rolling(window=k_period).min()
        high_max = df['High'].rolling(window=k_period).max()
        
        stoch_k = 100 * ((df['Close'] - low_min) / (high_max - low_min))
        stoch_d = stoch_k.rolling(window=d_period).mean()
        
        return stoch_k, stoch_d
    
    @staticmethod
    def create_sequences(data: np.ndarray, lookback: int) -> Tuple[np.ndarray, np.ndarray]:
        """
        Create sequences for LSTM training
        
        Args:
            data: Input data array
            lookback: Number of time steps to look back
            
        Returns:
            Tuple of (X sequences, y targets)
        """
        X, y = [], []
        
        for i in range(lookback, len(data)):
            X.append(data[i-lookback:i])
            # Predict next close price (assuming close is first feature)
            y.append(data[i, 0] if len(data.shape) > 1 else data[i])
        
        return np.array(X), np.array(y)
