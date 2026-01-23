"""
Data Pipeline for AI Trading Bot
Handles real-time and historical market data processing
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json


class MarketDataPipeline:
    """
    Market Data Processing Pipeline
    Handles data ingestion, cleaning, and feature engineering
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.data_cache = {}
        self.last_update = {}
    
    def fetch_historical_data(self, symbol: str, start_date: str, 
                             end_date: str) -> pd.DataFrame:
        """
        Fetch historical market data
        In production, this would connect to data providers (Alpha Vantage, Yahoo Finance, etc.)
        """
        # Simulate data fetching
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        days = (end - start).days
        
        return self._generate_realistic_data(symbol, days, start)
    
    def fetch_realtime_data(self, symbol: str) -> Dict:
        """
        Fetch real-time market data
        In production, this would use WebSocket or REST API
        """
        # Simulate real-time data
        price = 100 + np.random.normal(0, 5)
        
        return {
            'symbol': symbol,
            'timestamp': datetime.now(),
            'price': price,
            'bid': price - 0.01,
            'ask': price + 0.01,
            'volume': np.random.randint(100, 10000),
            'open': price * 0.99,
            'high': price * 1.01,
            'low': price * 0.98,
            'close': price
        }
    
    def _generate_realistic_data(self, symbol: str, days: int, 
                                 start_date: pd.Timestamp) -> pd.DataFrame:
        """Generate realistic synthetic market data"""
        dates = pd.date_range(start=start_date, periods=days, freq='D')
        
        # Generate price with trend and noise
        np.random.seed(hash(symbol) % 2**32)
        trend = np.linspace(0, 0.2, days)
        noise = np.random.normal(0, 0.02, days)
        returns = trend / days + noise
        
        base_price = 100
        prices = base_price * np.exp(np.cumsum(returns))
        
        # Generate OHLCV data
        data = pd.DataFrame({
            'date': dates,
            'symbol': symbol,
            'open': prices * (1 + np.random.uniform(-0.01, 0.01, days)),
            'high': prices * (1 + np.random.uniform(0, 0.02, days)),
            'low': prices * (1 - np.random.uniform(0, 0.02, days)),
            'close': prices,
            'volume': np.random.randint(1000000, 10000000, days)
        })
        
        # Ensure high is highest and low is lowest
        data['high'] = data[['open', 'high', 'close']].max(axis=1)
        data['low'] = data[['open', 'low', 'close']].min(axis=1)
        
        return data
    
    def clean_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Clean and validate market data"""
        df = data.copy()
        
        # Remove duplicates
        df = df.drop_duplicates(subset=['date'], keep='last')
        
        # Handle missing values
        df = df.ffill().bfill()
        
        # Validate price data
        df = df[df['close'] > 0]
        df = df[df['volume'] > 0]
        
        # Sort by date
        df = df.sort_values('date').reset_index(drop=True)
        
        return df
    
    def add_time_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Add time-based features"""
        df = data.copy()
        
        df['day_of_week'] = pd.to_datetime(df['date']).dt.dayofweek
        df['month'] = pd.to_datetime(df['date']).dt.month
        df['quarter'] = pd.to_datetime(df['date']).dt.quarter
        
        # Trading session features
        df['is_monday'] = (df['day_of_week'] == 0).astype(int)
        df['is_friday'] = (df['day_of_week'] == 4).astype(int)
        
        return df
    
    def calculate_returns(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate various return metrics"""
        df = data.copy()
        
        # Simple returns
        df['returns'] = df['close'].pct_change()
        
        # Log returns
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        
        # Multi-period returns
        for period in [5, 10, 20]:
            df[f'returns_{period}d'] = df['close'].pct_change(periods=period)
        
        return df
    
    def detect_market_regime(self, data: pd.DataFrame) -> pd.DataFrame:
        """Detect market regime (trending, ranging, volatile)"""
        df = data.copy()
        
        # Calculate volatility
        df['volatility'] = df['returns'].rolling(window=20).std()
        
        # Calculate trend strength (ADX-like)
        df['trend_strength'] = abs(df['close'].rolling(window=20).mean() - 
                                   df['close'].rolling(window=5).mean()) / df['close']
        
        # Classify regime
        vol_threshold = df['volatility'].quantile(0.7)
        trend_threshold = df['trend_strength'].quantile(0.6)
        
        df['regime'] = 'RANGING'
        df.loc[df['volatility'] > vol_threshold, 'regime'] = 'VOLATILE'
        df.loc[df['trend_strength'] > trend_threshold, 'regime'] = 'TRENDING'
        
        return df
    
    def process_pipeline(self, symbol: str, start_date: str, 
                        end_date: str) -> pd.DataFrame:
        """Execute complete data processing pipeline"""
        # Fetch data
        data = self.fetch_historical_data(symbol, start_date, end_date)
        
        # Clean data
        data = self.clean_data(data)
        
        # Add features
        data = self.add_time_features(data)
        data = self.calculate_returns(data)
        data = self.detect_market_regime(data)
        
        # Cache data
        self.data_cache[symbol] = data
        self.last_update[symbol] = datetime.now()
        
        return data
    
    def export_data(self, symbol: str, output_path: str):
        """Export processed data to file"""
        if symbol in self.data_cache:
            data = self.data_cache[symbol]
            data.to_csv(output_path, index=False)
            return True
        return False
    
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get latest price from cache or fetch"""
        if symbol in self.data_cache:
            return self.data_cache[symbol]['close'].iloc[-1]
        return None


class DataValidator:
    """
    Data Quality Validation
    Ensures data integrity and quality
    """
    
    @staticmethod
    def validate_ohlc(data: pd.DataFrame) -> Dict[str, any]:
        """Validate OHLC data consistency"""
        issues = []
        
        # Check high >= low
        invalid_range = data[data['high'] < data['low']]
        if len(invalid_range) > 0:
            issues.append(f"Found {len(invalid_range)} rows where high < low")
        
        # Check high >= open, close
        invalid_high = data[(data['high'] < data['open']) | (data['high'] < data['close'])]
        if len(invalid_high) > 0:
            issues.append(f"Found {len(invalid_high)} rows where high < open/close")
        
        # Check low <= open, close
        invalid_low = data[(data['low'] > data['open']) | (data['low'] > data['close'])]
        if len(invalid_low) > 0:
            issues.append(f"Found {len(invalid_low)} rows where low > open/close")
        
        # Check for negative prices
        negative_prices = data[(data['open'] <= 0) | (data['high'] <= 0) | 
                              (data['low'] <= 0) | (data['close'] <= 0)]
        if len(negative_prices) > 0:
            issues.append(f"Found {len(negative_prices)} rows with negative/zero prices")
        
        return {
            'valid': len(issues) == 0,
            'total_rows': len(data),
            'issues': issues
        }
    
    @staticmethod
    def check_missing_data(data: pd.DataFrame) -> Dict[str, any]:
        """Check for missing data"""
        missing = data.isnull().sum()
        
        return {
            'has_missing': missing.sum() > 0,
            'missing_by_column': missing[missing > 0].to_dict(),
            'total_missing': missing.sum()
        }
    
    @staticmethod
    def detect_outliers(data: pd.DataFrame, column: str = 'returns', 
                       threshold: float = 3.0) -> pd.DataFrame:
        """Detect outliers using z-score method"""
        if column not in data.columns:
            return pd.DataFrame()
        
        mean = data[column].mean()
        std = data[column].std()
        
        z_scores = np.abs((data[column] - mean) / std)
        outliers = data[z_scores > threshold]
        
        return outliers


if __name__ == '__main__':
    print("=" * 60)
    print("Market Data Pipeline - Testing")
    print("=" * 60)
    print()
    
    # Initialize pipeline
    pipeline = MarketDataPipeline()
    print("✓ Data pipeline initialized")
    print()
    
    # Process data for multiple symbols
    symbols = ['AAPL', 'GOOGL', 'MSFT']
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    
    for symbol in symbols:
        print(f"Processing {symbol}...")
        data = pipeline.process_pipeline(symbol, start_date, end_date)
        print(f"  ✓ Fetched {len(data)} days of data")
        print(f"  ✓ Latest price: ${data['close'].iloc[-1]:.2f}")
        print(f"  ✓ Market regime: {data['regime'].iloc[-1]}")
        
        # Validate data
        validator = DataValidator()
        validation = validator.validate_ohlc(data)
        
        if validation['valid']:
            print(f"  ✓ Data validation passed")
        else:
            print(f"  ⚠ Data validation issues: {validation['issues']}")
        print()
    
    print("=" * 60)
    print("✓ Data pipeline testing complete")
