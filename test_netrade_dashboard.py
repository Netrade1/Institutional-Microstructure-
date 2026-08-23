from __future__ import annotations

import argparse
import itertools
import math
import unittest
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
from pandas.tseries.offsets import BDay


try:
    import matplotlib.pyplot as plt
except ImportError:  # pragma: no cover - plotting is optional in test environments
    plt = None


try:
    import yfinance as yf
except ImportError:  # pragma: no cover - data fetch can be mocked in tests
    yf = None


@dataclass
class StrategyParams:
    ema_fast: int = 20
    ema_slow: int = 50
    sma_trend: int = 200
    rsi_len: int = 14
    rsi_min: float = 40.0
    rsi_max: float = 70.0
    volume_sma: int = 20
    volume_mult: float = 0.8
    atr_len: int = 14
    atr_min: float = 0.01
    atr_max: float = 0.04
    trail_pct: float = 0.08
    hard_stop_pct: float = 0.12
    profit_target_pct: float = 0.15
    risk_pct: float = 0.02
    slippage_pct: float = 0.0002  # 0.02%


OPTIMIZATION_GRID = {"rsi_min": [35.0, 40.0, 45.0], "rsi_max": [65.0, 70.0], "trail_pct": [0.06, 0.08, 0.1]}


def _rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _atr(df: pd.DataFrame, period: int) -> pd.Series:
    prev_close = df["Close"].shift(1)
    tr = pd.concat(
        [
            (df["High"] - df["Low"]).abs(),
            (df["High"] - prev_close).abs(),
            (df["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def fetch_ohlcv(symbol: str, start: str, end: str) -> pd.DataFrame:
    if yf is None:
        raise ImportError("yfinance is required for live data fetch. Install with `pip install yfinance`.")
    data = yf.download(symbol, start=start, end=end, auto_adjust=True, actions=True, progress=False)
    if data.empty:
        raise ValueError(f"No data returned for {symbol} between {start} and {end}.")
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    required = {"Open", "High", "Low", "Close", "Volume"}
    if not required.issubset(set(data.columns)):
        raise ValueError(f"Missing required columns. Found {list(data.columns)}")
    data = data.sort_index().copy()
    # Mon-Fri business-day approximation; exchange-specific holidays are not explicitly modeled.
    business_idx = pd.date_range(data.index.min(), data.index.max(), freq=BDay())
    data = data.reindex(business_idx)
    ohlc = ["Open", "High", "Low", "Close"]
    data[ohlc] = data[ohlc].ffill()
    data["Volume"] = data["Volume"].fillna(0)
    return data


def load_csv_ohlcv(path: str) -> pd.DataFrame:
    if not path:
        raise ValueError("CSV path cannot be empty.")
    if not Path(path).exists():
        raise FileNotFoundError(f"CSV path does not exist: {path}")
    df = pd.read_csv(path, parse_dates=True, index_col=0).sort_index()
    required = {"Open", "High", "Low", "Close", "Volume"}
    if not required.issubset(set(df.columns)):
        raise ValueError(f"CSV must include columns: {sorted(required)}")
    return df


def add_indicators(df: pd.DataFrame, p: StrategyParams) -> pd.DataFrame:
    out = df.copy()
    out["ema_fast"] = out["Close"].ewm(span=p.ema_fast, adjust=False).mean()
    out["ema_slow"] = out["Close"].ewm(span=p.ema_slow, adjust=False).mean()
    out["sma_trend"] = out["Close"].rolling(p.sma_trend).mean()
    out["rsi"] = _rsi(out["Close"], p.rsi_len)
    out["atr"] = _atr(out, p.atr_len)
    out["vol_sma"] = out["Volume"].rolling(p.volume_sma).mean()
    out["atr_ratio"] = out["atr"] / out["Close"]
    return out


def _cross_up(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a > b) & (a.shift(1) <= b.shift(1))


def _cross_down(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a < b) & (a.shift(1) >= b.shift(1))


def generate_signals(df: pd.DataFrame, p: StrategyParams) -> pd.DataFrame:
    out = df.copy()
    out["entry_signal"] = (
        _cross_up(out["ema_fast"], out["ema_slow"])
        & out["rsi"].between(p.rsi_min, p.rsi_max, inclusive="both")
        & (out["Close"] > out["sma_trend"])
        & (out["Volume"] >= p.volume_mult * out["vol_sma"])
        & out["atr_ratio"].between(p.atr_min, p.atr_max, inclusive="both")
    )
    out["exit_cross"] = _cross_down(out["ema_fast"], out["ema_slow"])
    return out


def _max_drawdown(equity: pd.Series) -> float:
    roll_max = equity.cummax()
    dd = equity / roll_max - 1.0
    return float(dd.min())


def _annualized_sharpe(returns: pd.Series) -> float:
    if returns.std(ddof=0) == 0:
        return 0.0
    return float((returns.mean() / returns.std(ddof=0)) * np.sqrt(252))


def _cagr(equity: pd.Series) -> float:
    if equity.empty or len(equity) < 2 or equity.iloc[0] <= 0:
        return 0.0
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    if years <= 0:
        return 0.0
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1)


def backtest(df: pd.DataFrame, p: StrategyParams, initial_capital: float = 100_000) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, float]]:
    data = generate_signals(add_indicators(df, p), p).dropna().copy()
    if data.empty:
        raise ValueError("Not enough data after indicator warm-up.")

    equity = initial_capital
    shares = 0
    entry_price = np.nan
    highest_close = np.nan
    trades: List[Dict[str, object]] = []
    equity_curve: List[Dict[str, object]] = []

    for dt, row in data.iterrows():
        close = float(row["Close"])
        mark_to_market = equity + shares * close

        if shares == 0 and bool(row["entry_signal"]):
            stop_distance = close * p.hard_stop_pct
            risk_budget = mark_to_market * p.risk_pct
            qty_risk = math.floor(risk_budget / stop_distance) if stop_distance > 0 else 0
            qty_afford = math.floor(mark_to_market / (close * (1 + p.slippage_pct))) if close > 0 else 0
            qty = int(max(0, min(qty_risk, qty_afford)))
            if qty > 0:
                fill = close * (1 + p.slippage_pct)
                shares = qty
                entry_price = fill
                highest_close = close
                equity -= qty * fill
                trades.append({"entry_date": dt, "entry_price": fill, "shares": qty})

        elif shares > 0:
            highest_close = max(highest_close, close)
            trail_stop = highest_close * (1 - p.trail_pct)
            hard_stop = entry_price * (1 - p.hard_stop_pct)
            profit_target = entry_price * (1 + p.profit_target_pct)

            exit_reason = None
            if close < trail_stop:
                exit_reason = "trailing_stop"
            elif bool(row["exit_cross"]):
                exit_reason = "ema_cross_down"
            elif close < hard_stop:
                exit_reason = "hard_stop"
            elif close > profit_target:
                exit_reason = "profit_target"

            if exit_reason is not None:
                fill = close * (1 - p.slippage_pct)
                equity += shares * fill
                trade = trades[-1]
                trade["exit_date"] = dt
                trade["exit_price"] = fill
                trade["exit_reason"] = exit_reason
                pnl = (fill - float(trade["entry_price"])) * int(trade["shares"])
                trade["pnl"] = pnl
                shares = 0
                entry_price = np.nan
                highest_close = np.nan

        total_equity = equity + shares * close
        equity_curve.append({"date": dt, "equity": total_equity, "close": close, "position": shares})

    if shares > 0:
        close = float(data.iloc[-1]["Close"])
        fill = close * (1 - p.slippage_pct)
        equity += shares * fill
        trade = trades[-1]
        trade["exit_date"] = data.index[-1]
        trade["exit_price"] = fill
        trade["exit_reason"] = "end_of_test"
        trade["pnl"] = (fill - float(trade["entry_price"])) * int(trade["shares"])
        shares = 0
        equity_curve[-1]["equity"] = equity
        equity_curve[-1]["position"] = 0

    eq_df = pd.DataFrame(equity_curve).set_index("date")
    trades_df = pd.DataFrame(trades)

    closed = trades_df.dropna(subset=["pnl"]).copy() if not trades_df.empty else pd.DataFrame(columns=["pnl"])
    gross_profit = float(closed.loc[closed["pnl"] > 0, "pnl"].sum()) if not closed.empty else 0.0
    gross_loss = float(closed.loc[closed["pnl"] < 0, "pnl"].sum()) if not closed.empty else 0.0
    returns = eq_df["equity"].pct_change().fillna(0.0)
    win_rate = float((closed["pnl"] > 0).mean()) if not closed.empty else 0.0

    merged = data.join(eq_df[["equity"]], how="left")
    merged["equity"] = merged["equity"].ffill().fillna(initial_capital)
    merged["drawdown"] = merged["equity"] / merged["equity"].cummax() - 1.0

    if gross_loss < 0:
        profit_factor = float(gross_profit / abs(gross_loss))
    elif gross_profit > 0:
        profit_factor = float("inf")
    else:
        profit_factor = 0.0

    metrics = {
        "trades": int(len(closed)),
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown": _max_drawdown(merged["equity"]),
        "sharpe": _annualized_sharpe(returns),
        "cagr": _cagr(merged["equity"]),
        "total_return": float(merged["equity"].iloc[-1] / merged["equity"].iloc[0] - 1.0),
    }
    return merged, trades_df, metrics


def plot_results(data: pd.DataFrame, trades: pd.DataFrame, metrics: Dict[str, float], title: str) -> None:
    if plt is None:
        print("matplotlib is not available; skipping plots.")
        return
    fig, (ax_price, ax_equity, ax_dd) = plt.subplots(3, 1, figsize=(14, 11), sharex=True, gridspec_kw={"height_ratios": [2, 1, 1]})
    ax_price.plot(data.index, data["Close"], label="Close", color="black", linewidth=1.0)
    ax_price.plot(data.index, data["ema_fast"], label="EMA Fast", color="teal", linewidth=1.0)
    ax_price.plot(data.index, data["ema_slow"], label="EMA Slow", color="orange", linewidth=1.0)
    ax_price.plot(data.index, data["sma_trend"], label="SMA Trend", color="blue", linewidth=1.0)

    if not trades.empty:
        entries = trades.dropna(subset=["entry_date"])
        exits = trades.dropna(subset=["exit_date"])
        ax_price.scatter(entries["entry_date"], entries["entry_price"], marker="^", color="green", s=35, label="Entry")
        ax_price.scatter(exits["exit_date"], exits["exit_price"], marker="v", color="red", s=35, label="Exit")
    ax_price.legend(loc="upper left")
    ax_price.set_title(title)

    eq = data["equity"]
    ax_equity.plot(eq.index, eq.values, color="navy", label="Equity")
    ax_equity.legend(loc="upper left")

    dd = eq / eq.cummax() - 1.0
    ax_dd.fill_between(dd.index, dd.values, 0, color="firebrick", alpha=0.4)
    ax_dd.set_ylabel("Drawdown")

    profit_factor_text = "inf (no losses)" if not np.isfinite(metrics["profit_factor"]) else f"{metrics['profit_factor']:.2f}"
    perf_text = (
        f"Trades: {metrics['trades']}\n"
        f"Win rate: {metrics['win_rate']:.2%}\n"
        f"Profit factor: {profit_factor_text}\n"
        f"Max DD: {metrics['max_drawdown']:.2%}\n"
        f"Sharpe: {metrics['sharpe']:.2f}\n"
        f"CAGR: {metrics['cagr']:.2%}"
    )
    ax_price.text(0.99, 0.02, perf_text, transform=ax_price.transAxes, va="bottom", ha="right", bbox={"boxstyle": "round", "fc": "white", "alpha": 0.8})
    plt.tight_layout()
    plt.show()


def optimize_parameters(df: pd.DataFrame, base: StrategyParams, grid: Dict[str, Iterable]) -> pd.DataFrame:
    keys = list(grid.keys())
    values = [list(grid[k]) for k in keys]
    rows = []
    for combo in itertools.product(*values):
        params = StrategyParams(**{**asdict(base), **dict(zip(keys, combo))})
        _, _, m = backtest(df, params)
        row = {k: v for k, v in zip(keys, combo)}
        row.update(m)
        rows.append(row)
    out = pd.DataFrame(rows).sort_values(["profit_factor", "sharpe"], ascending=False)
    return out


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trading strategy backtest dashboard")
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--initial-capital", dest="initial_capital", type=float, default=100_000)
    parser.add_argument("--plot", action="store_true", help="Render equity/drawdown charts")
    parser.add_argument("--optimize", action="store_true", help="Run small parameter grid search")
    parser.add_argument("--csv", help="Path to local OHLCV CSV with Open/High/Low/Close/Volume columns")
    return parser.parse_args(argv)


def run_cli(args: argparse.Namespace) -> int:
    if args.csv:
        df = load_csv_ohlcv(args.csv)
    else:
        try:
            df = fetch_ohlcv(args.symbol, args.start, args.end)
        except Exception as exc:
            raise RuntimeError(
                f"Data fetch failed for {args.symbol}. Use --csv for offline backtests. Original error: {exc}"
            ) from exc
    params = StrategyParams()
    data, trades, metrics = backtest(df, params, initial_capital=args.initial_capital)

    print(f"Symbol: {args.symbol} | Timeframe: Daily | Period: {args.start} -> {args.end}")
    for k in ["trades", "win_rate", "profit_factor", "max_drawdown", "sharpe", "cagr", "total_return"]:
        v = metrics[k]
        if isinstance(v, float) and not np.isfinite(v):
            print(f"{k:>14}: inf (no losing trades)")
            continue
        if k in {"win_rate", "max_drawdown", "cagr", "total_return"}:
            print(f"{k:>14}: {v:.2%}")
        else:
            print(f"{k:>14}: {v:.4f}" if isinstance(v, float) else f"{k:>14}: {v}")

    if args.optimize:
        optim = optimize_parameters(df, params, OPTIMIZATION_GRID)
        print("\nTop optimization rows:")
        print(optim.head(10).to_string(index=False))

    if args.plot:
        plot_results(data, trades, metrics, title=f"{args.symbol} Strategy Backtest")
    return 0


class StrategySignalTests(unittest.TestCase):
    def setUp(self) -> None:
        idx = pd.date_range("2020-01-01", periods=320, freq="B")
        close = pd.Series(np.linspace(100, 140, len(idx)), index=idx)
        close.iloc[250:260] += np.linspace(-8, 14, 10)
        close.iloc[260:280] += 8
        self.df = pd.DataFrame(
            {
                "Open": close * 0.999,
                "High": close * 1.005,
                "Low": close * 0.995,
                "Close": close,
                "Volume": 1_000_000,
            },
            index=idx,
        )

    def test_indicator_columns_present(self) -> None:
        out = add_indicators(self.df, StrategyParams())
        for col in ["ema_fast", "ema_slow", "sma_trend", "rsi", "atr", "vol_sma", "atr_ratio"]:
            self.assertIn(col, out.columns)

    def test_signal_generation_has_expected_fields(self) -> None:
        out = generate_signals(add_indicators(self.df, StrategyParams()), StrategyParams())
        self.assertIn("entry_signal", out.columns)
        self.assertIn("exit_cross", out.columns)
        self.assertTrue(out["entry_signal"].dtype == bool)

    def test_backtest_metrics_keys(self) -> None:
        _, trades, metrics = backtest(self.df, StrategyParams())
        self.assertIn("profit_factor", metrics)
        self.assertIn("max_drawdown", metrics)
        self.assertIn("sharpe", metrics)
        self.assertIn("trades", metrics)
        self.assertIsInstance(trades, pd.DataFrame)

    def test_hard_stop_position_sizing_not_overlevered(self) -> None:
        p = StrategyParams(hard_stop_pct=0.12, risk_pct=0.02)
        data = generate_signals(add_indicators(self.df, p), p).dropna()
        row = data.iloc[0]
        close = float(row["Close"])
        equity = 100_000
        stop_distance = close * p.hard_stop_pct
        qty_risk = math.floor((equity * p.risk_pct) / stop_distance)
        qty_afford = math.floor(equity / (close * (1 + p.slippage_pct)))
        qty = min(qty_risk, qty_afford)
        self.assertLessEqual(qty * close, equity)


if __name__ == "__main__":
    raise SystemExit(run_cli(parse_args()))
