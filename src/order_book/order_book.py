"""
Order Book
Represents and analyzes the limit order book
"""

import pandas as pd
import numpy as np
from typing import List, Tuple, Dict, Optional
from datetime import datetime


class OrderBook:
    """
    Represents a limit order book with bid and ask sides.
    Provides methods for order book analysis and manipulation.
    """
    
    def __init__(self, symbol: str):
        """
        Initialize an order book for a symbol.
        
        Args:
            symbol: Trading symbol
        """
        self.symbol = symbol
        self.bids: List[Tuple[float, int]] = []  # [(price, size), ...]
        self.asks: List[Tuple[float, int]] = []  # [(price, size), ...]
        self.timestamp = None
    
    def update(self, bids: List[List], asks: List[List]):
        """
        Update the order book with new bid and ask levels.
        
        Args:
            bids: List of [price, size] pairs for bids (sorted high to low)
            asks: List of [price, size] pairs for asks (sorted low to high)
        """
        self.bids = [(price, size) for price, size in bids]
        self.asks = [(price, size) for price, size in asks]
        self.timestamp = datetime.now()
        
        # Sort to ensure correct ordering
        self.bids.sort(key=lambda x: x[0], reverse=True)
        self.asks.sort(key=lambda x: x[0])
    
    def get_best_bid(self) -> Optional[Tuple[float, int]]:
        """Get the best (highest) bid price and size"""
        return self.bids[0] if self.bids else None
    
    def get_best_ask(self) -> Optional[Tuple[float, int]]:
        """Get the best (lowest) ask price and size"""
        return self.asks[0] if self.asks else None
    
    def get_mid_price(self) -> Optional[float]:
        """Calculate the mid price between best bid and ask"""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        
        if best_bid and best_ask:
            return (best_bid[0] + best_ask[0]) / 2
        return None
    
    def get_spread(self) -> Optional[float]:
        """Calculate the bid-ask spread"""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        
        if best_bid and best_ask:
            return best_ask[0] - best_bid[0]
        return None
    
    def get_relative_spread(self) -> Optional[float]:
        """Calculate the relative (percentage) spread"""
        spread = self.get_spread()
        mid_price = self.get_mid_price()
        
        if spread is not None and mid_price and mid_price > 0:
            return (spread / mid_price) * 100
        return None
    
    def get_depth(self, side: str, levels: int = 5) -> float:
        """
        Calculate the depth (total volume) for a given side.
        
        Args:
            side: 'bid' or 'ask'
            levels: Number of price levels to include
            
        Returns:
            Total volume at the specified levels
        """
        if side.lower() == 'bid':
            return sum(size for _, size in self.bids[:levels])
        elif side.lower() == 'ask':
            return sum(size for _, size in self.asks[:levels])
        return 0.0
    
    def get_imbalance(self, levels: int = 5) -> Optional[float]:
        """
        Calculate order book imbalance.
        
        Args:
            levels: Number of price levels to include
            
        Returns:
            Imbalance ratio between -1 (all asks) and 1 (all bids)
        """
        bid_depth = self.get_depth('bid', levels)
        ask_depth = self.get_depth('ask', levels)
        
        total_depth = bid_depth + ask_depth
        if total_depth > 0:
            return (bid_depth - ask_depth) / total_depth
        return None
    
    def get_weighted_mid_price(self, levels: int = 5) -> Optional[float]:
        """
        Calculate volume-weighted mid price.
        
        Args:
            levels: Number of price levels to include
            
        Returns:
            Volume-weighted mid price
        """
        bid_depth = self.get_depth('bid', levels)
        ask_depth = self.get_depth('ask', levels)
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        
        if best_bid and best_ask and (bid_depth + ask_depth) > 0:
            return (best_bid[0] * ask_depth + best_ask[0] * bid_depth) / (bid_depth + ask_depth)
        return None
    
    def calculate_vwap(self, side: str, volume: int) -> Optional[float]:
        """
        Calculate VWAP for a market order of given volume.
        
        Args:
            side: 'buy' or 'sell'
            volume: Order volume
            
        Returns:
            Volume-weighted average price for the order
        """
        if side.lower() == 'buy':
            levels = self.asks
        elif side.lower() == 'sell':
            levels = self.bids
        else:
            return None
        
        remaining_volume = volume
        total_cost = 0.0
        
        for price, size in levels:
            if remaining_volume <= 0:
                break
            
            fill_volume = min(remaining_volume, size)
            total_cost += price * fill_volume
            remaining_volume -= fill_volume
        
        if remaining_volume > 0:
            # Not enough liquidity
            return None
        
        return total_cost / volume
    
    def get_market_impact(self, side: str, volume: int) -> Optional[float]:
        """
        Estimate market impact of a market order.
        
        Args:
            side: 'buy' or 'sell'
            volume: Order volume
            
        Returns:
            Price impact in basis points
        """
        vwap = self.calculate_vwap(side, volume)
        mid_price = self.get_mid_price()
        
        if vwap and mid_price and mid_price > 0:
            if side.lower() == 'buy':
                impact = (vwap - mid_price) / mid_price
            else:
                impact = (mid_price - vwap) / mid_price
            
            return impact * 10000  # Convert to basis points
        return None
    
    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert order book to a DataFrame for analysis.
        
        Returns:
            DataFrame with bid and ask levels
        """
        max_levels = max(len(self.bids), len(self.asks))
        
        data = []
        for i in range(max_levels):
            row = {'level': i}
            
            if i < len(self.bids):
                row['bid_price'] = self.bids[i][0]
                row['bid_size'] = self.bids[i][1]
            else:
                row['bid_price'] = None
                row['bid_size'] = None
            
            if i < len(self.asks):
                row['ask_price'] = self.asks[i][0]
                row['ask_size'] = self.asks[i][1]
            else:
                row['ask_price'] = None
                row['ask_size'] = None
            
            data.append(row)
        
        return pd.DataFrame(data)
    
    def __repr__(self) -> str:
        """String representation of the order book"""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        spread = self.get_spread()
        
        return (f"OrderBook(symbol={self.symbol}, "
                f"best_bid={best_bid}, best_ask={best_ask}, "
                f"spread={spread:.4f})" if spread else 
                f"OrderBook(symbol={self.symbol}, empty)")
