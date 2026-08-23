# Institutional-Microstructure-

Comprehensive, back-testable trading strategy implementation for:

- TradingView Pine Script (`/pine/aapl_ema_rsi_trend_strategy.pine`)
- Python backtesting framework (`/test_netrade_dashboard.py`)

## Strategy Summary

- **Symbol:** AAPL
- **Timeframe:** Daily bars
- **Backtest window (example):** 2015-01-01 to 2024-12-31
- **Entry:** EMA(20) cross above EMA(50), RSI in [40, 70], close > SMA(200), volume filter, ATR/close filter
- **Exit (first trigger):** 8% trailing stop, EMA cross down, 12% hard stop, 15% profit target
- **Risk sizing:** 2% equity risked per trade with hard stop distance of 12%
- **Slippage:** 0.02% per fill, commissions = 0

## Python Usage

Run a backtest:

```bash
python test_netrade_dashboard.py --symbol AAPL --start 2015-01-01 --end 2024-12-31
```

Run unit tests:

```bash
python -m unittest test_netrade_dashboard.py -v
```

Optional optimization mode:

```bash
python test_netrade_dashboard.py --optimize
```

Offline mode with local CSV:

```bash
python test_netrade_dashboard.py --csv /absolute/path/to/aapl_daily.csv
```

## Data Handling Assumptions

- Yahoo Finance daily OHLCV through `yfinance` with `auto_adjust=True` for split/dividend-adjusted prices.
- Business-day reindexing and forward-fill for non-trading gaps (weekday approximation; market holidays are not explicitly calendared).
- Slippage of 0.02% applied on entry and exit fills.

## Risk Disclaimer

This repository provides educational and research backtests only. Historical simulations do **not** guarantee future performance. Validate data quality, assumptions, execution constraints, and risk controls before any live deployment.
