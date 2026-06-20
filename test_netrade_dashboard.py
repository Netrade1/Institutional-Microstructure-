"""Institutional-grade backtest harness aligned with Pine strategy logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from indicators.institutional_indicators import (
    bearish_divergence,
    macd,
    obv,
    obv_sma,
    rsi,
    rvol,
    twap,
    vwap,
)


@dataclass(frozen=True)
class StrategyParams:
    ema_fast: int = 20
    ema_slow: int = 50
    sma_trend: int = 200
    rvol_lookback: int = 20
    rvol_threshold: float = 1.2
    rsi_fast: int = 7
    rsi_mid: int = 14
    rsi_slow: int = 21
    rsi_min: float = 40
    rsi_max: float = 70
    obv_sma_len: int = 20
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    divergence_lookback: int = 5
    hard_stop_pct: float = 0.12
    profit_target_pct: float = 0.15
    trailing_stop_pct: float = 0.08
    risk_per_trade: float = 0.02


def compute_indicators(df: pd.DataFrame, params: StrategyParams) -> pd.DataFrame:
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    data = df.copy()
    data = data.sort_index()

    data["ema_fast"] = data["close"].ewm(span=params.ema_fast, adjust=False).mean()
    data["ema_slow"] = data["close"].ewm(span=params.ema_slow, adjust=False).mean()
    data["sma_trend"] = data["close"].rolling(params.sma_trend, min_periods=1).mean()

    data["vwap"] = vwap(data)
    data["twap"] = twap(data)
    data["rvol"] = rvol(data["volume"], params.rvol_lookback)

    data["rsi_7"] = rsi(data["close"], params.rsi_fast)
    data["rsi_14"] = rsi(data["close"], params.rsi_mid)
    data["rsi_21"] = rsi(data["close"], params.rsi_slow)

    data["obv"] = obv(data)
    data["obv_sma"] = obv_sma(data["obv"], params.obv_sma_len)

    macd_df = macd(data["close"], params.macd_fast, params.macd_slow, params.macd_signal)
    data = pd.concat([data, macd_df], axis=1)

    data["rsi_bear_div"] = bearish_divergence(data["close"], data["rsi_14"], params.divergence_lookback)
    data["macd_bear_div"] = bearish_divergence(data["close"], data["macd_hist"], params.divergence_lookback)
    data["obv_bear_div"] = bearish_divergence(data["close"], data["obv"], params.divergence_lookback)

    data["entry_long"] = (
        (data["ema_fast"] > data["ema_slow"])
        & (data["rsi_14"].between(params.rsi_min, params.rsi_max, inclusive="both"))
        & (data["close"] > data["sma_trend"])
        & (data["close"] > data["vwap"])
        & (data["rvol"] > params.rvol_threshold)
        & (data["obv"] > data["obv_sma"])
        & (data["macd_hist"] > 0)
        & (data["macd_line"] > data["macd_signal"])
        & (~data["rsi_bear_div"].fillna(False))
    )

    data["exit_momentum"] = (data["macd_hist"] < 0) & (data["macd_line"] < data["macd_signal"])
    data["exit_trend"] = data["ema_fast"] < data["ema_slow"]
    data["exit_vwap"] = data["close"] < data["vwap"]
    data["exit_obv"] = data["obv"] < data["obv_sma"]
    data["exit_signal"] = data[["exit_momentum", "exit_trend", "exit_vwap", "exit_obv"]].any(axis=1)

    return data


def _max_drawdown(equity_curve: pd.Series) -> float:
    peak = equity_curve.cummax()
    drawdown = (equity_curve / peak) - 1
    return float(drawdown.min()) if not drawdown.empty else 0.0


def _profit_factor(pnls: List[float]) -> float:
    gross_profit = sum(x for x in pnls if x > 0)
    gross_loss = abs(sum(x for x in pnls if x < 0))
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def run_backtest(
    df: pd.DataFrame,
    params: StrategyParams | None = None,
    initial_capital: float = 100_000.0,
    slippage_bps: float = 5.0,
    commission_bps: float = 1.0,
) -> Tuple[pd.DataFrame, Dict[str, float], Dict[str, int]]:
    params = params or StrategyParams()
    data = compute_indicators(df, params)

    equity = initial_capital
    cash = initial_capital
    shares = 0.0
    entry_price = np.nan
    peak_price = np.nan

    trades: List[Dict[str, float]] = []
    equity_curve: List[float] = []
    signal_counter: Dict[str, int] = {
        "entry_trend": 0,
        "entry_vwap": 0,
        "entry_rvol": 0,
        "entry_obv": 0,
        "entry_macd": 0,
        "exit_momentum": 0,
        "exit_trend": 0,
        "exit_vwap": 0,
        "exit_obv": 0,
        "exit_stop": 0,
        "exit_target": 0,
        "exit_trailing": 0,
    }

    slip_mult_buy = 1 + slippage_bps / 10_000
    slip_mult_sell = 1 - slippage_bps / 10_000
    fee_mult = commission_bps / 10_000

    for ts, row in data.iterrows():
        close = float(row["close"])

        if shares <= 0 and bool(row["entry_long"]):
            stop_price = close * (1 - params.hard_stop_pct)
            risk_per_share = max(close - stop_price, 1e-9)
            risk_budget = equity * params.risk_per_trade
            target_shares = risk_budget / risk_per_share
            affordable_shares = cash / (close * slip_mult_buy)
            shares = max(0.0, min(target_shares, affordable_shares))
            if shares > 0:
                fill = close * slip_mult_buy
                fees = fill * shares * fee_mult
                cash -= (fill * shares + fees)
                entry_price = fill
                peak_price = fill
                signal_counter["entry_trend"] += 1
                signal_counter["entry_vwap"] += 1
                signal_counter["entry_rvol"] += 1
                signal_counter["entry_obv"] += 1
                signal_counter["entry_macd"] += 1

        elif shares > 0:
            peak_price = max(peak_price, close)
            hard_stop = entry_price * (1 - params.hard_stop_pct)
            target = entry_price * (1 + params.profit_target_pct)
            trailing = peak_price * (1 - params.trailing_stop_pct)

            stop_hit = close <= hard_stop
            target_hit = close >= target
            trailing_hit = close <= trailing
            exit_signal = bool(row["exit_signal"])

            should_exit = stop_hit or target_hit or trailing_hit or exit_signal
            if should_exit:
                fill = close * slip_mult_sell
                fees = fill * shares * fee_mult
                proceeds = fill * shares - fees
                cash += proceeds
                pnl = (fill - entry_price) * shares - fees
                trades.append(
                    {
                        "timestamp": ts,
                        "entry_price": float(entry_price),
                        "exit_price": float(fill),
                        "shares": float(shares),
                        "pnl": float(pnl),
                    }
                )

                if stop_hit:
                    signal_counter["exit_stop"] += 1
                if target_hit:
                    signal_counter["exit_target"] += 1
                if trailing_hit:
                    signal_counter["exit_trailing"] += 1
                if bool(row["exit_momentum"]):
                    signal_counter["exit_momentum"] += 1
                if bool(row["exit_trend"]):
                    signal_counter["exit_trend"] += 1
                if bool(row["exit_vwap"]):
                    signal_counter["exit_vwap"] += 1
                if bool(row["exit_obv"]):
                    signal_counter["exit_obv"] += 1

                shares = 0.0
                entry_price = np.nan
                peak_price = np.nan

        position_value = shares * close
        equity = cash + position_value
        equity_curve.append(equity)

    data["equity"] = equity_curve

    pnls = [t["pnl"] for t in trades]
    returns = data["equity"].pct_change().fillna(0)

    metrics = {
        "initial_capital": initial_capital,
        "ending_equity": float(data["equity"].iloc[-1]) if not data.empty else initial_capital,
        "total_return_pct": (float(data["equity"].iloc[-1]) / initial_capital - 1) * 100 if not data.empty else 0.0,
        "trade_count": float(len(trades)),
        "win_rate_pct": (sum(1 for p in pnls if p > 0) / len(pnls) * 100) if pnls else 0.0,
        "profit_factor": _profit_factor(pnls),
        "max_drawdown_pct": _max_drawdown(data["equity"]) * 100 if not data.empty else 0.0,
        "sharpe_daily": float(np.sqrt(252) * returns.mean() / returns.std()) if returns.std() > 0 else 0.0,
    }

    return data, metrics, signal_counter


def plot_dashboard(data: pd.DataFrame) -> None:
    """Plot strategy dashboard with institutional indicators."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(5, 1, figsize=(14, 16), sharex=True)

    axes[0].plot(data.index, data["close"], label="Close", color="black", linewidth=1)
    axes[0].plot(data.index, data["vwap"], label="VWAP", color="cyan")
    axes[0].plot(data.index, data["twap"], label="TWAP", color="deepskyblue")
    axes[0].set_title("Price vs VWAP/TWAP")
    axes[0].legend(loc="upper left")

    axes[1].plot(data.index, data["rvol"], label="RVOL", color="purple")
    axes[1].axhline(1.2, linestyle="--", color="gray", label="RVOL Threshold")
    axes[1].set_title("Relative Volume")
    axes[1].legend(loc="upper left")

    axes[2].plot(data.index, data["rsi_7"], label="RSI 7", alpha=0.7)
    axes[2].plot(data.index, data["rsi_14"], label="RSI 14", linewidth=1.5)
    axes[2].plot(data.index, data["rsi_21"], label="RSI 21", alpha=0.7)
    axes[2].axhline(70, linestyle="--", color="red")
    axes[2].axhline(30, linestyle="--", color="green")
    axes[2].set_title("Multi-Timeframe RSI")
    axes[2].legend(loc="upper left")

    axes[3].plot(data.index, data["obv"], label="OBV", color="green")
    axes[3].plot(data.index, data["obv_sma"], label="OBV SMA(20)", color="red")
    axes[3].set_title("OBV Accumulation/Distribution")
    axes[3].legend(loc="upper left")

    axes[4].bar(data.index, data["macd_hist"], label="MACD Hist", color="gray")
    axes[4].plot(data.index, data["macd_line"], label="MACD", color="blue")
    axes[4].plot(data.index, data["macd_signal"], label="Signal", color="orange")
    axes[4].axhline(0, color="black", linewidth=0.8)
    axes[4].set_title("Advanced MACD")
    axes[4].legend(loc="upper left")

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    # This module is designed to be imported in tests or fed with prepared OHLCV data.
    print("Load OHLCV data into a DataFrame and call run_backtest(df).")
