"""
Technical Indicators
Common technical analysis indicators for trading
"""

import pandas as pd
import numpy as np
from typing import Optional, Tuple


class TechnicalIndicators:
    """
    Calculates technical indicators commonly used in trading.
    """
    
    @staticmethod
    def sma(prices: pd.Series, period: int) -> pd.Series:
        """
        Calculate Simple Moving Average.
        
        Args:
            prices: Series of prices
            period: Lookback period
            
        Returns:
            Series of SMA values
        """
        return prices.rolling(window=period).mean()
    
    @staticmethod
    def ema(prices: pd.Series, period: int) -> pd.Series:
        """
        Calculate Exponential Moving Average.
        
        Args:
            prices: Series of prices
            period: Lookback period
            
        Returns:
            Series of EMA values
        """
        return prices.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculate Relative Strength Index.
        
        Args:
            prices: Series of prices
            period: Lookback period (default 14)
            
        Returns:
            Series of RSI values (0-100)
        """
        delta = prices.diff()
        
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        # Handle division by zero
        with np.errstate(divide='ignore', invalid='ignore'):
            rs = gain / loss
            rs = rs.replace([np.inf, -np.inf], 100)  # If loss is 0, RSI = 100
            rs = rs.fillna(0)
        
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def macd(
        prices: pd.Series,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate MACD (Moving Average Convergence Divergence).
        
        Args:
            prices: Series of prices
            fast_period: Fast EMA period (default 12)
            slow_period: Slow EMA period (default 26)
            signal_period: Signal line period (default 9)
            
        Returns:
            Tuple of (MACD line, Signal line, Histogram)
        """
        fast_ema = TechnicalIndicators.ema(prices, fast_period)
        slow_ema = TechnicalIndicators.ema(prices, slow_period)
        
        macd_line = fast_ema - slow_ema
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    @staticmethod
    def bollinger_bands(
        prices: pd.Series,
        period: int = 20,
        std_dev: float = 2.0
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate Bollinger Bands.
        
        Args:
            prices: Series of prices
            period: Lookback period (default 20)
            std_dev: Number of standard deviations (default 2.0)
            
        Returns:
            Tuple of (Upper band, Middle band, Lower band)
        """
        middle_band = prices.rolling(window=period).mean()
        standard_deviation = prices.rolling(window=period).std()
        
        upper_band = middle_band + (standard_deviation * std_dev)
        lower_band = middle_band - (standard_deviation * std_dev)
        
        return upper_band, middle_band, lower_band
    
    @staticmethod
    def atr(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14
    ) -> pd.Series:
        """
        Calculate Average True Range.
        
        Args:
            high: Series of high prices
            low: Series of low prices
            close: Series of close prices
            period: Lookback period (default 14)
            
        Returns:
            Series of ATR values
        """
        high_low = high - low
        high_close = (high - close.shift()).abs()
        low_close = (low - close.shift()).abs()
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()
        
        return atr
    
    @staticmethod
    def stochastic(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14,
        smooth_k: int = 3,
        smooth_d: int = 3
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Calculate Stochastic Oscillator.
        
        Args:
            high: Series of high prices
            low: Series of low prices
            close: Series of close prices
            period: Lookback period (default 14)
            smooth_k: %K smoothing period (default 3)
            smooth_d: %D smoothing period (default 3)
            
        Returns:
            Tuple of (%K line, %D line)
        """
        lowest_low = low.rolling(window=period).min()
        highest_high = high.rolling(window=period).max()
        
        # Handle division by zero when price range is zero
        price_range = highest_high - lowest_low
        with np.errstate(divide='ignore', invalid='ignore'):
            k_percent = 100 * ((close - lowest_low) / price_range)
            k_percent = k_percent.replace([np.inf, -np.inf], np.nan)
        
        k_smooth = k_percent.rolling(window=smooth_k).mean()
        d_smooth = k_smooth.rolling(window=smooth_d).mean()
        
        return k_smooth, d_smooth
    
    @staticmethod
    def adx(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14
    ) -> pd.Series:
        """
        Calculate Average Directional Index.
        
        Args:
            high: Series of high prices
            low: Series of low prices
            close: Series of close prices
            period: Lookback period (default 14)
            
        Returns:
            Series of ADX values
        """
        # Calculate +DM and -DM
        high_diff = high.diff()
        low_diff = -low.diff()
        
        plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
        minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)
        
        # Calculate True Range
        tr = TechnicalIndicators.atr(high, low, close, 1)
        
        # Calculate smoothed +DI and -DI
        atr_period = tr.rolling(window=period).sum()
        
        # Handle division by zero
        with np.errstate(divide='ignore', invalid='ignore'):
            plus_di = 100 * (plus_dm.rolling(window=period).sum() / atr_period)
            minus_di = 100 * (minus_dm.rolling(window=period).sum() / atr_period)
            
            # Calculate DX
            di_sum = plus_di + minus_di
            dx = 100 * (plus_di - minus_di).abs() / di_sum
            dx = dx.replace([np.inf, -np.inf], np.nan)
        
        adx = dx.rolling(window=period).mean()
        
        return adx
    
    @staticmethod
    def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        """
        Calculate On-Balance Volume.
        
        Args:
            close: Series of close prices
            volume: Series of volumes
            
        Returns:
            Series of OBV values
        """
        direction = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
        obv = (direction * volume).cumsum()
        
        return obv
    
    @staticmethod
    def vwap(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        volume: pd.Series
    ) -> pd.Series:
        """
        Calculate Volume Weighted Average Price.
        
        Args:
            high: Series of high prices
            low: Series of low prices
            close: Series of close prices
            volume: Series of volumes
            
        Returns:
            Series of VWAP values
        """
        typical_price = (high + low + close) / 3
        vwap = (typical_price * volume).cumsum() / volume.cumsum()
        
        return vwap
    
    @staticmethod
    def cci(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 20
    ) -> pd.Series:
        """
        Calculate Commodity Channel Index.
        
        Args:
            high: Series of high prices
            low: Series of low prices
            close: Series of close prices
            period: Lookback period (default 20)
            
        Returns:
            Series of CCI values
        """
        typical_price = (high + low + close) / 3
        sma = typical_price.rolling(window=period).mean()
        mad = typical_price.rolling(window=period).apply(
            lambda x: np.abs(x - x.mean()).mean()
        )
        
        # Handle division by zero when MAD is zero
        with np.errstate(divide='ignore', invalid='ignore'):
            cci = (typical_price - sma) / (0.015 * mad)
            cci = cci.replace([np.inf, -np.inf], np.nan)
        
        return cci
    
    @staticmethod
    def momentum(prices: pd.Series, period: int = 10) -> pd.Series:
        """
        Calculate Momentum indicator.
        
        Args:
            prices: Series of prices
            period: Lookback period (default 10)
            
        Returns:
            Series of momentum values
        """
        return prices.diff(period)
    
    @staticmethod
    def roc(prices: pd.Series, period: int = 10) -> pd.Series:
        """
        Calculate Rate of Change.
        
        Args:
            prices: Series of prices
            period: Lookback period (default 10)
            
        Returns:
            Series of ROC values (percentage)
        """
        # Handle division by zero
        with np.errstate(divide='ignore', invalid='ignore'):
            roc = ((prices - prices.shift(period)) / prices.shift(period)) * 100
            roc = roc.replace([np.inf, -np.inf], np.nan)
        
        return roc
