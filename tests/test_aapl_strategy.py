import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aapl_strategy import (  # noqa: E402
    Bar,
    StrategyConfig,
    atr,
    backtest_strategy,
    calculate_position_size,
    ema,
    load_ohlcv_csv,
    rsi,
    sma,
)


class IndicatorTests(unittest.TestCase):
    def test_sma_computes_expected_average(self):
        values = [1, 2, 3, 4, 5]
        self.assertEqual(sma(values, 3), [None, None, 2.0, 3.0, 4.0])

    def test_ema_seeds_with_period_average(self):
        values = [10, 11, 12, 13, 14, 15]
        result = ema(values, 3)
        self.assertEqual(result[:2], [None, None])
        self.assertAlmostEqual(result[2], 11.0)
        self.assertGreater(result[-1], result[-2])

    def test_rsi_stays_bounded(self):
        values = [100, 101, 102, 101, 103, 104, 103, 105, 106, 107, 106, 108, 109, 110, 111, 112]
        result = rsi(values, 14)
        self.assertIsNone(result[13])
        self.assertIsNotNone(result[14])
        self.assertGreaterEqual(result[14], 0.0)
        self.assertLessEqual(result[14], 100.0)

    def test_atr_positive_after_warmup(self):
        bars = [
            Bar(datetime(2024, 1, 1) + timedelta(days=index), 100 + index, 102 + index, 99 + index, 101 + index, 1_000_000)
            for index in range(20)
        ]
        result = atr(bars, 14)
        self.assertIsNone(result[13])
        self.assertGreater(result[14], 0.0)


class PositionSizingTests(unittest.TestCase):
    def test_position_size_uses_two_percent_risk(self):
        config = StrategyConfig(initial_cash=100_000, risk_per_trade=0.02, hard_stop_pct=0.12)
        shares = calculate_position_size(100_000, 150.0, config)
        self.assertEqual(shares, 111)


class BacktestTests(unittest.TestCase):
    def test_backtest_executes_profit_target_trade(self):
        bars = []
        start = datetime(2020, 1, 1)

        for index in range(220):
            if index < 170:
                close = 100 + (index * 0.05)
            elif index < 200:
                close = 108 + ((index - 170) * 0.8)
            elif index == 200:
                close = 132
            elif index == 201:
                close = 136
            else:
                close = 160

            open_price = close * 0.998
            bars.append(
                Bar(
                    date=start + timedelta(days=index),
                    open=open_price,
                    high=close * 1.01,
                    low=close * 0.99,
                    close=close,
                    volume=2_000_000,
                )
            )

        result = backtest_strategy(bars)
        self.assertGreaterEqual(result.trade_count, 1)
        self.assertTrue(any(trade.exit_reason in {"profit_target", "end_of_test"} for trade in result.trades))
        self.assertGreater(result.final_equity, 100_000)

    def test_csv_loader_rejects_zero_volume(self):
        csv_path = Path(__file__).resolve().parent / "bad_data.csv"
        csv_path.write_text(
            "Date,Open,High,Low,Close,Volume\n"
            "2024-01-02,100,101,99,100,0\n",
            encoding="utf-8",
        )
        with self.assertRaises(ValueError):
            load_ohlcv_csv(csv_path)
        csv_path.unlink()


if __name__ == "__main__":
    unittest.main()
