"""Institutional-grade indicator helpers for strategy parity across environments."""

from __future__ import annotations

import pandas as pd


def _validate_index(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame index must be a DatetimeIndex for session-aware indicators.")
    return df


def vwap(df: pd.DataFrame, price_col: str = "close", volume_col: str = "volume") -> pd.Series:
    """Session-anchored VWAP using cumulative price*volume / cumulative volume."""
    _validate_index(df)
    session = df.index.normalize()
    pv = df[price_col] * df[volume_col]
    return pv.groupby(session).cumsum() / df[volume_col].groupby(session).cumsum().replace(0, pd.NA)


def twap(df: pd.DataFrame, price_col: str = "close") -> pd.Series:
    """Session-anchored TWAP using cumulative average of price."""
    _validate_index(df)
    session = df.index.normalize()
    cumulative_price = df[price_col].groupby(session).cumsum()
    session_count = df.groupby(session).cumcount() + 1
    return cumulative_price / session_count


def rvol(volume: pd.Series, lookback: int = 20) -> pd.Series:
    """Relative volume versus rolling mean volume."""
    return volume / volume.rolling(lookback, min_periods=1).mean().replace(0, pd.NA)


def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    """Wilder RSI with exponentially smoothed gains/losses."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def obv(df: pd.DataFrame, close_col: str = "close", volume_col: str = "volume") -> pd.Series:
    """On-balance volume cumulative flow."""
    close = df[close_col]
    direction = close.diff().fillna(0).apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    return (direction * df[volume_col]).cumsum()


def obv_sma(obv_series: pd.Series, length: int = 20) -> pd.Series:
    return obv_series.rolling(length, min_periods=1).mean()


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD line, signal line, and histogram."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame(
        {
            "macd_line": macd_line,
            "macd_signal": signal_line,
            "macd_hist": histogram,
        },
        index=series.index,
    )


def bearish_divergence(price: pd.Series, oscillator: pd.Series, lookback: int = 5) -> pd.Series:
    """Bearish divergence proxy: higher price high vs lower oscillator high over lookback."""
    return (price > price.shift(lookback)) & (oscillator < oscillator.shift(lookback))


def bullish_divergence(price: pd.Series, oscillator: pd.Series, lookback: int = 5) -> pd.Series:
    """Bullish divergence proxy: lower price low vs higher oscillator low over lookback."""
    return (price < price.shift(lookback)) & (oscillator > oscillator.shift(lookback))
