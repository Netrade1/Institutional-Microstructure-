# Institutional-Microstructure-

Institutional-grade strategy package with aligned Pine Script and Python backtest logic.

## Strategy Scope

- **Market:** U.S. equities (example: AAPL)
- **Primary template timeframe:** Daily OHLCV (2015-2024 baseline window; extend to latest data for live research refreshes)
- **Core model:** EMA trend + RSI regime + institutional confirmation stack

## Institutional Indicators Added

- **VWAP:** session-anchored cumulative `sum(price*volume) / sum(volume)`
- **TWAP:** session-anchored cumulative `sum(price) / count`
- **RVOL:** `volume / SMA(volume, lookback)`
- **RSI (7/14/21):** multi-horizon confirmation with divergence checks
- **OBV + OBV SMA(20):** accumulation/distribution filter
- **Advanced MACD (12/26/9):** line, signal, histogram, divergence proxy, zero-line context

## Enhanced Entry Logic

Long entries require all of:

1. EMA(20) > EMA(50)
2. RSI(14) in [40, 70]
3. Close > SMA(200)
4. Close > VWAP
5. RVOL > 1.2
6. OBV > OBV_SMA(20)
7. MACD histogram > 0 and MACD line > signal line
8. No bearish RSI divergence

## Enhanced Exit Logic

Exit when any of the following triggers:

- EMA(20) < EMA(50)
- MACD histogram < 0 and MACD < signal
- Price crosses below VWAP
- OBV crosses below OBV_SMA(20)
- Hard stop, trailing stop, or profit target

## Files

- `strategies/aapl_daily_ema_rsi_strategy.pine` – full Pine Script strategy
- `indicators/institutional_indicators.py` – reusable indicator calculations
- `test_netrade_dashboard.py` – Python backtest engine + metrics + plotting
- `tests/test_institutional_strategy.py` – focused unit tests
- `BACKTEST_RESULTS.md` – baseline vs enhanced strategy summary

## Data Requirements for Backtesting

Use OHLCV with adjusted prices to account for **splits/dividends**. Recommended assumptions:

- Session-aware timestamps (DatetimeIndex)
- Gaps handled via bar-to-bar execution (no look-ahead)
- Slippage: 5 bps default
- Commission: 1 bp default

## Run Tests

```bash
python -m unittest discover -s tests -v
```

## Risk Disclaimer

This repository is for research and educational use only. Historical or hypothetical backtest performance is not a guarantee of future results. Validate data quality, transaction-cost assumptions, and execution constraints before any real-money deployment.
