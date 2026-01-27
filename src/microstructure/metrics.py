"""
Microstructure Metrics
Calculates various market microstructure metrics and measures
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict


class MicrostructureMetrics:
    """
    Calculates market microstructure metrics including spread measures,
    price impact, liquidity metrics, and information metrics.
    """
    
    @staticmethod
    def calculate_quoted_spread(bid: float, ask: float) -> float:
        """
        Calculate quoted (nominal) spread.
        
        Args:
            bid: Best bid price
            ask: Best ask price
            
        Returns:
            Quoted spread
        """
        return ask - bid
    
    @staticmethod
    def calculate_relative_spread(bid: float, ask: float) -> float:
        """
        Calculate relative (percentage) spread.
        
        Args:
            bid: Best bid price
            ask: Best ask price
            
        Returns:
            Relative spread as percentage
        """
        mid_price = (bid + ask) / 2
        return ((ask - bid) / mid_price) * 100
    
    @staticmethod
    def calculate_effective_spread(trade_price: float, mid_price: float, side: str) -> float:
        """
        Calculate effective spread for a trade.
        
        Args:
            trade_price: Actual trade price
            mid_price: Mid-quote at time of trade
            side: Trade side ('buy' or 'sell')
            
        Returns:
            Effective spread in basis points
        """
        if side.lower() == 'buy':
            spread = (trade_price - mid_price) / mid_price
        else:
            spread = (mid_price - trade_price) / mid_price
        
        return spread * 10000  # Convert to basis points
    
    @staticmethod
    def calculate_realized_spread(
        trade_price: float, 
        mid_price_at_trade: float,
        mid_price_later: float,
        side: str
    ) -> float:
        """
        Calculate realized spread (measure of adverse selection).
        
        Args:
            trade_price: Actual trade price
            mid_price_at_trade: Mid-quote at time of trade
            mid_price_later: Mid-quote at later time
            side: Trade side ('buy' or 'sell')
            
        Returns:
            Realized spread in basis points
        """
        if side.lower() == 'buy':
            spread = (trade_price - mid_price_later) / mid_price_at_trade
        else:
            spread = (mid_price_later - trade_price) / mid_price_at_trade
        
        return spread * 10000
    
    @staticmethod
    def calculate_price_impact(
        mid_price_before: float,
        mid_price_after: float,
        side: str
    ) -> float:
        """
        Calculate permanent price impact of a trade.
        
        Args:
            mid_price_before: Mid-quote before trade
            mid_price_after: Mid-quote after trade
            side: Trade side ('buy' or 'sell')
            
        Returns:
            Price impact in basis points
        """
        if side.lower() == 'buy':
            impact = (mid_price_after - mid_price_before) / mid_price_before
        else:
            impact = (mid_price_before - mid_price_after) / mid_price_before
        
        return impact * 10000
    
    @staticmethod
    def calculate_roll_measure(returns: pd.Series) -> float:
        """
        Calculate Roll's measure of effective spread from returns.
        
        Args:
            returns: Series of price returns
            
        Returns:
            Roll's measure estimate
        """
        # Roll's measure: spread = 2 * sqrt(-Cov(r_t, r_{t-1}))
        cov = returns.autocorr(lag=1)
        
        if cov < 0:
            return 2 * np.sqrt(-cov)
        else:
            return 0.0  # Roll's measure undefined for positive autocorrelation
    
    @staticmethod
    def calculate_amihud_illiquidity(
        returns: pd.Series,
        volumes: pd.Series
    ) -> float:
        """
        Calculate Amihud's (2002) illiquidity measure.
        
        Args:
            returns: Series of daily returns
            volumes: Series of daily dollar volumes
            
        Returns:
            Amihud illiquidity ratio
        """
        illiquidity = (np.abs(returns) / volumes).mean()
        return illiquidity * 1e6  # Scale for readability
    
    @staticmethod
    def calculate_kyle_lambda(
        price_changes: pd.Series,
        signed_volumes: pd.Series
    ) -> float:
        """
        Calculate Kyle's lambda (price impact coefficient).
        
        Args:
            price_changes: Series of price changes
            signed_volumes: Series of signed volumes (positive for buys)
            
        Returns:
            Kyle's lambda coefficient
        """
        # Run regression: ΔP = λ * Q + ε
        if len(price_changes) == len(signed_volumes) and len(price_changes) > 1:
            std_volume = np.std(signed_volumes)
            
            if std_volume <= 1e-8:
                return 0.0
            
            coef = np.corrcoef(signed_volumes, price_changes)[0, 1]
            std_price = np.std(price_changes)
            
            return coef * (std_price / std_volume)
        
        return 0.0
    
    @staticmethod
    def calculate_pin(
        buys: int,
        sells: int,
        alpha: float = 0.5,
        delta: float = 0.5
    ) -> float:
        """
        Calculate Probability of Informed Trading (PIN).
        Simplified version using buy-sell imbalance.
        
        Args:
            buys: Number of buy trades
            sells: Number of sell trades
            alpha: Probability of information event
            delta: Probability that information is good news
            
        Returns:
            Estimated PIN
        """
        total_trades = buys + sells
        if total_trades == 0:
            return 0.0
        
        imbalance = abs(buys - sells) / total_trades
        
        # Simplified PIN estimate based on order flow imbalance
        pin = alpha * imbalance
        
        return min(pin, 1.0)
    
    @staticmethod
    def calculate_order_flow_toxicity(
        vwap: float,
        mid_price: float
    ) -> float:
        """
        Calculate order flow toxicity (VPIN-style measure).
        
        Args:
            vwap: Volume-weighted average price
            mid_price: Mid-quote price
            
        Returns:
            Toxicity measure
        """
        if mid_price > 0:
            return abs((vwap - mid_price) / mid_price)
        return 0.0
    
    @staticmethod
    def calculate_market_depth(
        bid_depth: float,
        ask_depth: float,
        mid_price: float
    ) -> Dict[str, float]:
        """
        Calculate market depth metrics.
        
        Args:
            bid_depth: Total bid volume
            ask_depth: Total ask volume
            mid_price: Mid-quote price
            
        Returns:
            Dictionary with depth metrics
        """
        total_depth = bid_depth + ask_depth
        
        return {
            'total_depth': total_depth,
            'bid_depth': bid_depth,
            'ask_depth': ask_depth,
            'depth_imbalance': (bid_depth - ask_depth) / total_depth if total_depth > 0 else 0.0,
            'depth_ratio': bid_depth / ask_depth if ask_depth > 1e-8 else float('inf'),
            'dollar_depth': total_depth * mid_price
        }
    
    @staticmethod
    def calculate_volatility_metrics(returns: pd.Series) -> Dict[str, float]:
        """
        Calculate various volatility metrics.
        
        Args:
            returns: Series of returns
            
        Returns:
            Dictionary with volatility metrics
        """
        return {
            'std_dev': returns.std(),
            'variance': returns.var(),
            'realized_volatility': np.sqrt(np.sum(returns ** 2)),
            'mean_absolute_deviation': returns.abs().mean(),
            'downside_deviation': returns[returns < 0].std(),
            'skewness': returns.skew(),
            'kurtosis': returns.kurtosis()
        }
    
    @staticmethod
    def calculate_information_share(
        price_series: pd.Series,
        returns_series: pd.Series
    ) -> float:
        """
        Calculate information share (contribution to price discovery).
        
        Args:
            price_series: Series of prices
            returns_series: Series of returns
            
        Returns:
            Information share estimate
        """
        # Simplified information share based on variance contribution
        total_variance = returns_series.var()
        
        if total_variance <= 1e-8:
            return 0.0
        
        # Calculate how much of the total variance is explained
        explained_variance = returns_series.abs().mean()
        return explained_variance / np.sqrt(total_variance)
