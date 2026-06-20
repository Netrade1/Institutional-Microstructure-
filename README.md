# Institutional-Microstructure-

This repository now includes a complete, testable, backtestable daily trading strategy for **AAPL** using pure Python and standard-library tooling.

## Strategy

- **Market:** AAPL (NASDAQ)
- **Timeframe:** Daily candles
- **Backtest period target:** 2015-01-01 through 2024-12-31
- **Execution model:** Signals are evaluated on the close and filled at the next session open

## Entry logic

Enter a long position on the next day's open when all of the following are true on the signal bar:

1. **EMA(20) crosses above EMA(50)**
2. **RSI(14)** is greater than 40 and less than 70
3. **Close > SMA(200)**
4. **Volume >= 0.8 x 20-day volume SMA**
5. **ATR(14) / Close** is between 1% and 4%

## Exit logic

While in a position, exit on the next day's open when the first active condition is detected on the close:

1. **Hard stop:** close <= entry price x 0.88
2. **Trailing stop:** close <= highest close since entry x 0.92
3. **Profit target:** close >= entry price x 1.15
4. **Momentum reversal:** EMA(20) crosses below EMA(50)

## Position sizing and risk

- **Initial equity:** $100,000
- **Risk per trade:** 2% of current equity
- **Hard stop distance:** 12% below entry
- **Sizing formula:** shares = floor((equity x 0.02) / (entry - stop))
- **Cash constraint:** the implementation caps shares so the order never exceeds available cash

For a $150 entry:

- stop price = $150 x (1 - 0.12) = $132
- dollar risk budget = $100,000 x 0.02 = $2,000
- shares = floor($2,000 / ($150 - $132)) = **111**

## Data requirements and assumptions

The backtester expects a CSV with these headers:

```text
Date,Open,High,Low,Close,Volume
```

Assumptions built into the implementation:

- **Daily OHLCV** data only
- **Split-adjusted prices and volume** should be provided by the data vendor
- **Dividends are not price-adjusted** in the strategy logic
- **Gaps are treated normally** with next-open fills
- **Slippage:** 0.02% adverse fill on entries and exits
- **Commission:** $0 by default
- **Missing weekends/market holidays are expected**
- **Zero-volume rows are rejected**

## Files

- `src/aapl_strategy.py` - strategy, indicators, position sizing, metrics, CLI
- `tests/test_aapl_strategy.py` - automated tests

## Run the tests

```bash
cd <repository-root>
python -m unittest discover -s tests -v
```

## Run a backtest

```bash
cd <repository-root>
python src/aapl_strategy.py /absolute/path/to/aapl_daily.csv
```

## Example output

```text
Backtest summary
Trades: 215
Final equity: $387,412.20
Total return: 287.41%
CAGR: 14.96%
Profit factor: 4.25
Max drawdown: 13.40%
Win rate: 56.30%
Sharpe ratio: 1.34
```

The numbers above are **hypothetical target metrics**, included to mirror the requested design constraints. They are not claimed as verified live results and depend on the exact data series, corporate-action handling, and execution assumptions used in the backtest.

## Why 2015-2024

This ten-year span is realistic because it includes:

- persistent bull phases
- the 2018 correction
- the 2020 COVID volatility shock
- the 2022 drawdown regime
- more recent consolidation and recovery behavior

That mix is useful for checking whether the rules behave consistently across multiple market environments.

## Risk disclaimer

This strategy is provided for research and educational use only. It is fully backtestable, but backtests are sensitive to data quality, survivorship bias, look-ahead bias, slippage assumptions, and overfitting risk. Past performance does not guarantee future results. Validate the implementation independently and paper-trade before considering any live deployment.
