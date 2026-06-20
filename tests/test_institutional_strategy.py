import unittest

import pandas as pd

from indicators.institutional_indicators import macd, obv, rvol, twap, vwap
from test_netrade_dashboard import StrategyParams, compute_indicators, run_backtest


class InstitutionalIndicatorTests(unittest.TestCase):
    @staticmethod
    def sample_df() -> pd.DataFrame:
        idx = pd.date_range("2024-01-01 09:30:00", periods=120, freq="min")
        close = pd.Series(range(100, 220), index=idx, dtype=float)
        data = pd.DataFrame(
            {
                "open": close - 0.5,
                "high": close + 1,
                "low": close - 1,
                "close": close,
                "volume": [1000 + (i % 25) * 50 for i in range(120)],
            },
            index=idx,
        )
        return data

    def test_vwap_twap_session_anchored(self) -> None:
        df = self.sample_df()
        v = vwap(df)
        t = twap(df)
        self.assertFalse(v.isna().all())
        self.assertFalse(t.isna().all())
        self.assertAlmostEqual(float(t.iloc[0]), float(df["close"].iloc[0]), places=6)

    def test_obv_and_macd_columns_exist(self) -> None:
        df = self.sample_df()
        obv_series = obv(df)
        macd_df = macd(df["close"])
        self.assertEqual(len(obv_series), len(df))
        self.assertTrue({"macd_line", "macd_signal", "macd_hist"}.issubset(set(macd_df.columns)))

    def test_compute_indicators_has_required_signals(self) -> None:
        df = self.sample_df()
        out = compute_indicators(df, StrategyParams())
        required = {
            "vwap",
            "twap",
            "rvol",
            "rsi_7",
            "rsi_14",
            "rsi_21",
            "obv",
            "obv_sma",
            "macd_line",
            "macd_signal",
            "macd_hist",
            "entry_long",
            "exit_signal",
        }
        self.assertTrue(required.issubset(set(out.columns)))
        self.assertTrue((rvol(df["volume"], 20) > 0).all())

    def test_run_backtest_returns_metrics_and_counter(self) -> None:
        df = self.sample_df()
        _, metrics, counter = run_backtest(df)
        self.assertIn("profit_factor", metrics)
        self.assertIn("max_drawdown_pct", metrics)
        self.assertIn("entry_macd", counter)
        self.assertIn("exit_vwap", counter)


if __name__ == "__main__":
    unittest.main()
