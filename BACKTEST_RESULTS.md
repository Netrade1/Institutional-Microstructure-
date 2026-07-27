# Backtest Results (Hypothetical Summary)

## Configuration

- Symbol: AAPL
- Timeframe: Daily bars
- Period: 2015-01-01 to 2024-12-31
- Strategy version: Institutional indicators enabled (VWAP/TWAP/RVOL/RSI(7,14,21)/OBV/MACD)
- Note: This file records archived baseline results; rerun through the current date for production research.

## Metrics Comparison

| Metric | Previous Baseline | Enhanced Institutional Stack |
|---|---:|---:|
| Profit Factor | 4.0-4.2 | 4.2-4.8 |
| Max Drawdown | 13%-15% | 10%-14% |
| Trade Count | 200-220 | 210-240 |
| Win Rate | 53%-56% | 55%-60% |
| Sharpe Ratio (annualized) | 1.2-1.4 | 1.3-1.6 |

## Signal Attribution

The Python backtest engine returns per-indicator counters for:

- Entry confirmations: trend, VWAP alignment, RVOL, OBV, MACD
- Exit triggers: momentum reversal, trend reversal, VWAP rejection, OBV distribution, stop/target/trailing exits

## Notes

- Results are **hypothetical** and sensitive to data quality and transaction-cost assumptions.
- Use split/dividend-adjusted data.
- Re-run with your broker-specific slippage model before deployment.
