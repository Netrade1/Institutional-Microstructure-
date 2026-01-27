"""
Example: Technical Indicators
Demonstrates technical indicator calculations
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.market_data.data_fetcher import MarketDataFetcher
from src.indicators.technical_indicators import TechnicalIndicators
from datetime import datetime, timedelta


def main():
    print("=" * 60)
    print("Technical Indicators Example")
    print("=" * 60)
    
    # Fetch historical data
    fetcher = MarketDataFetcher(data_source="simulated")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    
    data = fetcher.get_historical_data("AAPL", start_date, end_date, interval='1D')
    
    indicators = TechnicalIndicators()
    
    # Example 1: Moving Averages
    print("\n1. Moving Averages:")
    print("-" * 40)
    sma_20 = indicators.sma(data['close'], 20)
    ema_20 = indicators.ema(data['close'], 20)
    print(f"Latest Close: ${data['close'].iloc[-1]:.2f}")
    print(f"SMA(20): ${sma_20.iloc[-1]:.2f}")
    print(f"EMA(20): ${ema_20.iloc[-1]:.2f}")
    
    # Example 2: RSI
    print("\n2. Relative Strength Index (RSI):")
    print("-" * 40)
    rsi = indicators.rsi(data['close'], 14)
    latest_rsi = rsi.iloc[-1]
    print(f"RSI(14): {latest_rsi:.2f}")
    if latest_rsi > 70:
        print("Signal: Overbought")
    elif latest_rsi < 30:
        print("Signal: Oversold")
    else:
        print("Signal: Neutral")
    
    # Example 3: MACD
    print("\n3. MACD:")
    print("-" * 40)
    macd_line, signal_line, histogram = indicators.macd(data['close'])
    print(f"MACD Line: {macd_line.iloc[-1]:.4f}")
    print(f"Signal Line: {signal_line.iloc[-1]:.4f}")
    print(f"Histogram: {histogram.iloc[-1]:.4f}")
    if histogram.iloc[-1] > 0:
        print("Signal: Bullish")
    else:
        print("Signal: Bearish")
    
    # Example 4: Bollinger Bands
    print("\n4. Bollinger Bands:")
    print("-" * 40)
    upper, middle, lower = indicators.bollinger_bands(data['close'], 20, 2.0)
    print(f"Upper Band: ${upper.iloc[-1]:.2f}")
    print(f"Middle Band: ${middle.iloc[-1]:.2f}")
    print(f"Lower Band: ${lower.iloc[-1]:.2f}")
    print(f"Current Price: ${data['close'].iloc[-1]:.2f}")
    
    # Example 5: ATR
    print("\n5. Average True Range (ATR):")
    print("-" * 40)
    atr = indicators.atr(data['high'], data['low'], data['close'], 14)
    print(f"ATR(14): ${atr.iloc[-1]:.2f}")
    
    # Example 6: Stochastic
    print("\n6. Stochastic Oscillator:")
    print("-" * 40)
    k, d = indicators.stochastic(data['high'], data['low'], data['close'])
    print(f"%K: {k.iloc[-1]:.2f}")
    print(f"%D: {d.iloc[-1]:.2f}")
    
    # Example 7: OBV
    print("\n7. On-Balance Volume (OBV):")
    print("-" * 40)
    obv = indicators.obv(data['close'], data['volume'])
    print(f"OBV: {obv.iloc[-1]:,.0f}")
    
    # Example 8: VWAP
    print("\n8. Volume Weighted Average Price (VWAP):")
    print("-" * 40)
    vwap = indicators.vwap(data['high'], data['low'], data['close'], data['volume'])
    print(f"VWAP: ${vwap.iloc[-1]:.2f}")
    print(f"Current Price: ${data['close'].iloc[-1]:.2f}")


if __name__ == "__main__":
    main()
