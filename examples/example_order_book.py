"""
Example: Order Book Analysis
Demonstrates order book analysis and microstructure metrics
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.market_data.data_fetcher import MarketDataFetcher
from src.order_book.order_book import OrderBook
from src.microstructure.metrics import MicrostructureMetrics


def main():
    print("=" * 60)
    print("Order Book Analysis Example")
    print("=" * 60)
    
    # Fetch order book data
    fetcher = MarketDataFetcher(data_source="simulated")
    ob_data = fetcher.get_order_book_snapshot("MSFT", depth=10)
    
    # Create order book object
    order_book = OrderBook("MSFT")
    order_book.update(ob_data['bids'], ob_data['asks'])
    
    # Example 1: Basic order book metrics
    print("\n1. Basic Order Book Metrics:")
    print("-" * 40)
    best_bid = order_book.get_best_bid()
    best_ask = order_book.get_best_ask()
    print(f"Best Bid: ${best_bid[0]:.2f} x {best_bid[1]}")
    print(f"Best Ask: ${best_ask[0]:.2f} x {best_ask[1]}")
    print(f"Mid Price: ${order_book.get_mid_price():.2f}")
    print(f"Spread: ${order_book.get_spread():.4f}")
    print(f"Relative Spread: {order_book.get_relative_spread():.4f}%")
    
    # Example 2: Market depth
    print("\n2. Market Depth:")
    print("-" * 40)
    bid_depth = order_book.get_depth('bid', levels=5)
    ask_depth = order_book.get_depth('ask', levels=5)
    print(f"Bid Depth (5 levels): {bid_depth:,}")
    print(f"Ask Depth (5 levels): {ask_depth:,}")
    print(f"Order Book Imbalance: {order_book.get_imbalance(5):.4f}")
    print(f"Weighted Mid Price: ${order_book.get_weighted_mid_price(5):.2f}")
    
    # Example 3: Market impact estimation
    print("\n3. Market Impact Estimation:")
    print("-" * 40)
    volume = 1000
    buy_vwap = order_book.calculate_vwap('buy', volume)
    sell_vwap = order_book.calculate_vwap('sell', volume)
    buy_impact = order_book.get_market_impact('buy', volume)
    sell_impact = order_book.get_market_impact('sell', volume)
    
    print(f"For {volume} shares:")
    print(f"  Buy VWAP: ${buy_vwap:.2f}")
    print(f"  Buy Impact: {buy_impact:.2f} bps")
    print(f"  Sell VWAP: ${sell_vwap:.2f}")
    print(f"  Sell Impact: {sell_impact:.2f} bps")
    
    # Example 4: Microstructure metrics
    print("\n4. Microstructure Metrics:")
    print("-" * 40)
    metrics = MicrostructureMetrics()
    quoted_spread = metrics.calculate_quoted_spread(best_bid[0], best_ask[0])
    relative_spread = metrics.calculate_relative_spread(best_bid[0], best_ask[0])
    
    print(f"Quoted Spread: ${quoted_spread:.4f}")
    print(f"Relative Spread: {relative_spread:.4f}%")
    
    # Calculate depth metrics
    depth_metrics = metrics.calculate_market_depth(
        bid_depth, ask_depth, order_book.get_mid_price()
    )
    print(f"Total Depth: {depth_metrics['total_depth']:,}")
    print(f"Depth Imbalance: {depth_metrics['depth_imbalance']:.4f}")
    print(f"Dollar Depth: ${depth_metrics['dollar_depth']:,.2f}")
    
    # Example 5: Order book DataFrame
    print("\n5. Order Book DataFrame:")
    print("-" * 40)
    df = order_book.to_dataframe()
    print(df.head())


if __name__ == "__main__":
    main()
