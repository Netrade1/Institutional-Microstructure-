"""
Market Data Fetcher
Fetches real-time and historical market data from various sources
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
import requests
import json


class MarketDataFetcher:
    """
    Fetches market data from various sources including exchanges and data providers.
    Supports both real-time and historical data retrieval.
    """
    
    def __init__(self, api_key: Optional[str] = None, data_source: str = "simulated"):
        """
        Initialize the market data fetcher.
        
        Args:
            api_key: API key for data provider (if required)
            data_source: Data source to use ('simulated', 'alpha_vantage', 'polygon', etc.)
        """
        self.api_key = api_key
        self.data_source = data_source
        self.base_urls = {
            'alpha_vantage': 'https://www.alphavantage.co/query',
            'polygon': 'https://api.polygon.io',
        }
    
    def get_quote(self, symbol: str) -> Dict:
        """
        Get real-time quote for a symbol.
        
        Args:
            symbol: Trading symbol (e.g., 'AAPL', 'MSFT')
            
        Returns:
            Dictionary with quote data including bid, ask, last, volume
        """
        if self.data_source == "simulated":
            return self._generate_simulated_quote(symbol)
        else:
            raise NotImplementedError(f"Data source {self.data_source} not yet implemented")
    
    def get_historical_data(
        self, 
        symbol: str, 
        start_date: Union[str, datetime], 
        end_date: Union[str, datetime],
        interval: str = '1D'
    ) -> pd.DataFrame:
        """
        Get historical OHLCV data for a symbol.
        
        Args:
            symbol: Trading symbol
            start_date: Start date for historical data
            end_date: End date for historical data
            interval: Data interval ('1m', '5m', '1h', '1D', etc.)
            
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        if self.data_source == "simulated":
            return self._generate_simulated_historical_data(symbol, start_date, end_date, interval)
        else:
            raise NotImplementedError(f"Data source {self.data_source} not yet implemented")
    
    def get_tick_data(self, symbol: str, num_ticks: int = 100) -> pd.DataFrame:
        """
        Get tick-level data for a symbol.
        
        Args:
            symbol: Trading symbol
            num_ticks: Number of ticks to retrieve
            
        Returns:
            DataFrame with columns: timestamp, price, size, side
        """
        if self.data_source == "simulated":
            return self._generate_simulated_tick_data(symbol, num_ticks)
        else:
            raise NotImplementedError(f"Data source {self.data_source} not yet implemented")
    
    def _generate_simulated_quote(self, symbol: str) -> Dict:
        """Generate simulated real-time quote data"""
        base_price = hash(symbol) % 500 + 50
        spread = base_price * 0.001
        
        return {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'bid': round(base_price - spread/2, 2),
            'ask': round(base_price + spread/2, 2),
            'last': round(base_price + np.random.uniform(-spread, spread), 2),
            'volume': int(np.random.uniform(100000, 10000000)),
            'bid_size': int(np.random.uniform(100, 10000)),
            'ask_size': int(np.random.uniform(100, 10000)),
        }
    
    def _generate_simulated_historical_data(
        self, 
        symbol: str, 
        start_date: Union[str, datetime], 
        end_date: Union[str, datetime],
        interval: str
    ) -> pd.DataFrame:
        """Generate simulated historical OHLCV data"""
        if isinstance(start_date, str):
            start_date = pd.to_datetime(start_date)
        if isinstance(end_date, str):
            end_date = pd.to_datetime(end_date)
        
        # Generate date range based on interval
        if interval == '1D':
            dates = pd.date_range(start=start_date, end=end_date, freq='D')
        elif interval == '1h':
            dates = pd.date_range(start=start_date, end=end_date, freq='H')
        elif interval == '5m':
            dates = pd.date_range(start=start_date, end=end_date, freq='5min')
        else:
            dates = pd.date_range(start=start_date, end=end_date, freq='D')
        
        base_price = hash(symbol) % 500 + 50
        
        # Generate price series with random walk
        returns = np.random.normal(0.0002, 0.02, len(dates))
        prices = base_price * np.exp(np.cumsum(returns))
        
        data = []
        for i, date in enumerate(dates):
            open_price = prices[i]
            high_price = open_price * (1 + abs(np.random.normal(0, 0.01)))
            low_price = open_price * (1 - abs(np.random.normal(0, 0.01)))
            close_price = open_price * (1 + np.random.normal(0, 0.005))
            volume = int(np.random.uniform(100000, 10000000))
            
            data.append({
                'timestamp': date,
                'open': round(open_price, 2),
                'high': round(high_price, 2),
                'low': round(low_price, 2),
                'close': round(close_price, 2),
                'volume': volume
            })
        
        return pd.DataFrame(data)
    
    def _generate_simulated_tick_data(self, symbol: str, num_ticks: int) -> pd.DataFrame:
        """Generate simulated tick-level data"""
        base_price = hash(symbol) % 500 + 50
        spread = base_price * 0.001
        
        data = []
        current_time = datetime.now()
        
        for i in range(num_ticks):
            tick_time = current_time - timedelta(seconds=(num_ticks - i))
            price = base_price + np.random.normal(0, spread)
            size = int(np.random.uniform(10, 1000))
            side = np.random.choice(['buy', 'sell'])
            
            data.append({
                'timestamp': tick_time,
                'price': round(price, 2),
                'size': size,
                'side': side
            })
        
        return pd.DataFrame(data)
    
    def get_order_book_snapshot(self, symbol: str, depth: int = 10) -> Dict:
        """
        Get order book snapshot for a symbol.
        
        Args:
            symbol: Trading symbol
            depth: Number of price levels to retrieve on each side
            
        Returns:
            Dictionary with 'bids' and 'asks' lists of [price, size] pairs
        """
        if self.data_source == "simulated":
            return self._generate_simulated_order_book(symbol, depth)
        else:
            raise NotImplementedError(f"Data source {self.data_source} not yet implemented")
    
    def _generate_simulated_order_book(self, symbol: str, depth: int) -> Dict:
        """Generate simulated order book snapshot"""
        base_price = hash(symbol) % 500 + 50
        spread = base_price * 0.001
        tick_size = 0.01
        
        bids = []
        asks = []
        
        for i in range(depth):
            bid_price = round(base_price - spread/2 - i * tick_size, 2)
            bid_size = int(np.random.uniform(100, 5000))
            bids.append([bid_price, bid_size])
            
            ask_price = round(base_price + spread/2 + i * tick_size, 2)
            ask_size = int(np.random.uniform(100, 5000))
            asks.append([ask_price, ask_size])
        
        return {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'bids': bids,
            'asks': asks
        }
