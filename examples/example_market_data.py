"""
Example: Market Data Fetching
Demonstrates how to fetch and analyze market data
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.market_data.data_fetcher import MarketDataFetcher
from datetime import datetime, timedelta
import pandas as pd


def main():
    print("=" * 60)
    print("Market Data Fetching Example")
    print("=" * 60)
    
    # Initialize market data fetcher
    fetcher = MarketDataFetcher(data_source="simulated")
    
    # Example 1: Get real-time quote
    print("\n1. Real-time Quote:")
    print("-" * 40)
    quote = fetcher.get_quote("AAPL")
    print(f"Symbol: {quote['symbol']}")
    print(f"Bid: ${quote['bid']:.2f} x {quote['bid_size']}")
    print(f"Ask: ${quote['ask']:.2f} x {quote['ask_size']}")
    print(f"Last: ${quote['last']:.2f}")
    print(f"Volume: {quote['volume']:,}")
    
    # Example 2: Get historical data
    print("\n2. Historical Data (Last 30 days):")
    print("-" * 40)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    historical = fetcher.get_historical_data("AAPL", start_date, end_date, interval='1D')
    print(historical.head())
    print(f"\nTotal rows: {len(historical)}")
    
    # Example 3: Get tick data
    print("\n3. Tick Data (Last 10 ticks):")
    print("-" * 40)
    ticks = fetcher.get_tick_data("AAPL", num_ticks=10)
    print(ticks)
    
    # Example 4: Get order book snapshot
    print("\n4. Order Book Snapshot:")
    print("-" * 40)
    order_book = fetcher.get_order_book_snapshot("AAPL", depth=5)
    print(f"Symbol: {order_book['symbol']}")
    print(f"Timestamp: {order_book['timestamp']}")
    print("\nBids:")
    for price, size in order_book['bids']:
        print(f"  ${price:.2f} x {size}")
    print("\nAsks:")
    for price, size in order_book['asks']:
        print(f"  ${price:.2f} x {size}")


if __name__ == "__main__":
    main()
