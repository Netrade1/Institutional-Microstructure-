from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean, pstdev
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class Bar:
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class StrategyConfig:
    initial_cash: float = 100_000.0
    risk_per_trade: float = 0.02
    fast_ema_period: int = 20
    slow_ema_period: int = 50
    rsi_period: int = 14
    atr_period: int = 14
    long_sma_period: int = 200
    volume_sma_period: int = 20
    min_volume_ratio: float = 0.8
    min_atr_ratio: float = 0.01
    max_atr_ratio: float = 0.04
    trailing_stop_pct: float = 0.08
    hard_stop_pct: float = 0.12
    profit_target_pct: float = 0.15
    entry_rsi_min: float = 40.0
    entry_rsi_max: float = 70.0
    slippage_pct: float = 0.0002
    commission_per_trade: float = 0.0


@dataclass(frozen=True)
class Trade:
    entry_date: datetime
    exit_date: datetime
    entry_price: float
    exit_price: float
    shares: int
    pnl: float
    return_pct: float
    exit_reason: str


@dataclass(frozen=True)
class BacktestResult:
    trades: List[Trade]
    equity_curve: List[float]
    drawdown_curve: List[float]
    profit_factor: float
    max_drawdown_pct: float
    win_rate_pct: float
    sharpe_ratio: float
    cagr_pct: float
    total_return_pct: float
    trade_count: int
    final_equity: float


def load_ohlcv_csv(path: str | Path) -> List[Bar]:
    rows: List[Bar] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"Date", "Open", "High", "Low", "Close", "Volume"}
        if not required.issubset(reader.fieldnames or set()):
            raise ValueError(f"CSV must contain columns: {sorted(required)}")

        for raw in reader:
            volume = float(raw["Volume"])
            if volume <= 0:
                raise ValueError(f"Volume must be positive on {raw['Date']}")
            rows.append(
                Bar(
                    date=datetime.fromisoformat(raw["Date"]),
                    open=float(raw["Open"]),
                    high=float(raw["High"]),
                    low=float(raw["Low"]),
                    close=float(raw["Close"]),
                    volume=volume,
                )
            )

    if not rows:
        raise ValueError("CSV contains no rows")

    rows.sort(key=lambda bar: bar.date)

    for current, nxt in zip(rows, rows[1:]):
        if current.date == nxt.date:
            raise ValueError(f"Duplicate date found: {current.date.date()}")
        if min(current.open, current.high, current.low, current.close) <= 0:
            raise ValueError(f"Prices must be positive on {current.date.date()}")
        if current.high < max(current.open, current.close, current.low):
            raise ValueError(f"High must be the session maximum on {current.date.date()}")
        if current.low > min(current.open, current.close, current.high):
            raise ValueError(f"Low must be the session minimum on {current.date.date()}")

    last = rows[-1]
    if min(last.open, last.high, last.low, last.close) <= 0:
        raise ValueError(f"Prices must be positive on {last.date.date()}")
    if last.high < max(last.open, last.close, last.low):
        raise ValueError(f"High must be the session maximum on {last.date.date()}")
    if last.low > min(last.open, last.close, last.high):
        raise ValueError(f"Low must be the session minimum on {last.date.date()}")

    return rows


def sma(values: List[float], period: int) -> List[Optional[float]]:
    result: List[Optional[float]] = [None] * len(values)
    if period <= 0:
        raise ValueError("period must be positive")
    running_total = 0.0
    for index, value in enumerate(values):
        running_total += value
        if index >= period:
            running_total -= values[index - period]
        if index >= period - 1:
            result[index] = running_total / period
    return result


def ema(values: List[float], period: int) -> List[Optional[float]]:
    result: List[Optional[float]] = [None] * len(values)
    if period <= 0:
        raise ValueError("period must be positive")
    if len(values) < period:
        return result
    seed = sum(values[:period]) / period
    multiplier = 2 / (period + 1)
    result[period - 1] = seed
    previous = seed
    for index in range(period, len(values)):
        previous = (values[index] - previous) * multiplier + previous
        result[index] = previous
    return result


def rsi(values: List[float], period: int) -> List[Optional[float]]:
    result: List[Optional[float]] = [None] * len(values)
    if period <= 0:
        raise ValueError("period must be positive")
    if len(values) <= period:
        return result

    gains: List[float] = []
    losses: List[float] = []
    for index in range(1, len(values)):
        delta = values[index] - values[index - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    result[period] = 100.0 if avg_loss == 0 else 100 - (100 / (1 + (avg_gain / avg_loss)))

    for index in range(period + 1, len(values)):
        gain = gains[index - 1]
        loss = losses[index - 1]
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
        result[index] = 100.0 if avg_loss == 0 else 100 - (100 / (1 + (avg_gain / avg_loss)))
    return result


def atr(bars: List[Bar], period: int) -> List[Optional[float]]:
    result: List[Optional[float]] = [None] * len(bars)
    if period <= 0:
        raise ValueError("period must be positive")
    if len(bars) <= period:
        return result

    true_ranges: List[float] = []
    for index, bar in enumerate(bars):
        if index == 0:
            true_range = bar.high - bar.low
        else:
            previous_close = bars[index - 1].close
            true_range = max(
                bar.high - bar.low,
                abs(bar.high - previous_close),
                abs(bar.low - previous_close),
            )
        true_ranges.append(true_range)

    first_atr = sum(true_ranges[1 : period + 1]) / period
    result[period] = first_atr
    previous = first_atr
    for index in range(period + 1, len(bars)):
        previous = ((previous * (period - 1)) + true_ranges[index]) / period
        result[index] = previous
    return result


def calculate_position_size(equity: float, entry_price: float, config: StrategyConfig) -> int:
    stop_price = entry_price * (1 - config.hard_stop_pct)
    risk_per_share = entry_price - stop_price
    if risk_per_share <= 0:
        return 0
    risk_budget = equity * config.risk_per_trade
    shares_by_risk = int(risk_budget // risk_per_share)
    shares_by_cash = int(equity // entry_price)
    return max(0, min(shares_by_risk, shares_by_cash))


def _crossed_above(series_a: List[Optional[float]], series_b: List[Optional[float]], index: int) -> bool:
    if index <= 0:
        return False
    a_now, b_now = series_a[index], series_b[index]
    a_prev, b_prev = series_a[index - 1], series_b[index - 1]
    return all(value is not None for value in (a_now, b_now, a_prev, b_prev)) and a_prev <= b_prev and a_now > b_now


def _crossed_below(series_a: List[Optional[float]], series_b: List[Optional[float]], index: int) -> bool:
    if index <= 0:
        return False
    a_now, b_now = series_a[index], series_b[index]
    a_prev, b_prev = series_a[index - 1], series_b[index - 1]
    return all(value is not None for value in (a_now, b_now, a_prev, b_prev)) and a_prev >= b_prev and a_now < b_now


def backtest_strategy(bars: List[Bar], config: StrategyConfig | None = None) -> BacktestResult:
    config = config or StrategyConfig()
    closes = [bar.close for bar in bars]
    volumes = [bar.volume for bar in bars]
    ema_fast = ema(closes, config.fast_ema_period)
    ema_slow = ema(closes, config.slow_ema_period)
    rsi_values = rsi(closes, config.rsi_period)
    sma_long = sma(closes, config.long_sma_period)
    atr_values = atr(bars, config.atr_period)
    volume_sma = sma(volumes, config.volume_sma_period)

    cash = config.initial_cash
    shares = 0
    entry_price = 0.0
    peak_close = 0.0
    entry_date: Optional[datetime] = None
    equity_curve: List[float] = []
    trades: List[Trade] = []
    pending_entry = False
    pending_exit_reason: Optional[str] = None

    for index, bar in enumerate(bars):
        if pending_exit_reason and shares > 0:
            fill_price = bar.open * (1 - config.slippage_pct)
            proceeds = (fill_price * shares) - config.commission_per_trade
            cash += proceeds
            pnl = (fill_price - entry_price) * shares - (2 * config.commission_per_trade)
            trades.append(
                Trade(
                    entry_date=entry_date or bar.date,
                    exit_date=bar.date,
                    entry_price=entry_price,
                    exit_price=fill_price,
                    shares=shares,
                    pnl=pnl,
                    return_pct=((fill_price / entry_price) - 1) * 100,
                    exit_reason=pending_exit_reason,
                )
            )
            shares = 0
            entry_price = 0.0
            peak_close = 0.0
            entry_date = None
            pending_exit_reason = None

        if pending_entry and shares == 0:
            fill_price = bar.open * (1 + config.slippage_pct)
            size = calculate_position_size(cash, fill_price, config)
            total_cost = (fill_price * size) + config.commission_per_trade
            if size > 0 and total_cost <= cash:
                shares = size
                cash -= total_cost
                entry_price = fill_price
                peak_close = bar.close
                entry_date = bar.date
            pending_entry = False

        equity_curve.append(cash + (shares * bar.close))

        if index == len(bars) - 1:
            continue

        if shares == 0:
            atr_value = atr_values[index]
            sma_value = sma_long[index]
            volume_avg = volume_sma[index]
            rsi_value = rsi_values[index]
            if None in (atr_value, sma_value, volume_avg, rsi_value):
                continue
            volatility_ratio = atr_value / bar.close if bar.close else math.inf
            entry_signal = all(
                (
                    _crossed_above(ema_fast, ema_slow, index),
                    config.entry_rsi_min < rsi_value < config.entry_rsi_max,
                    bar.close > sma_value,
                    bar.volume >= volume_avg * config.min_volume_ratio,
                    config.min_atr_ratio <= volatility_ratio <= config.max_atr_ratio,
                )
            )
            if entry_signal:
                pending_entry = True
        else:
            peak_close = max(peak_close, bar.close)
            if bar.close <= entry_price * (1 - config.hard_stop_pct):
                pending_exit_reason = "hard_stop"
            elif bar.close <= peak_close * (1 - config.trailing_stop_pct):
                pending_exit_reason = "trailing_stop"
            elif bar.close >= entry_price * (1 + config.profit_target_pct):
                pending_exit_reason = "profit_target"
            elif _crossed_below(ema_fast, ema_slow, index):
                pending_exit_reason = "ema_cross_down"

    if shares > 0:
        final_bar = bars[-1]
        fill_price = final_bar.close * (1 - config.slippage_pct)
        cash += (fill_price * shares) - config.commission_per_trade
        pnl = (fill_price - entry_price) * shares - (2 * config.commission_per_trade)
        trades.append(
            Trade(
                entry_date=entry_date or final_bar.date,
                exit_date=final_bar.date,
                entry_price=entry_price,
                exit_price=fill_price,
                shares=shares,
                pnl=pnl,
                return_pct=((fill_price / entry_price) - 1) * 100,
                exit_reason="end_of_test",
            )
        )
        equity_curve[-1] = cash

    drawdown_curve = _drawdown_curve(equity_curve)
    return BacktestResult(
        trades=trades,
        equity_curve=equity_curve,
        drawdown_curve=drawdown_curve,
        profit_factor=_profit_factor(trades),
        max_drawdown_pct=abs(min(drawdown_curve, default=0.0)) * 100,
        win_rate_pct=_win_rate(trades),
        sharpe_ratio=_sharpe_ratio(equity_curve),
        cagr_pct=_cagr(equity_curve, bars),
        total_return_pct=((equity_curve[-1] / config.initial_cash) - 1) * 100 if equity_curve else 0.0,
        trade_count=len(trades),
        final_equity=equity_curve[-1] if equity_curve else config.initial_cash,
    )


def _drawdown_curve(equity_curve: Iterable[float]) -> List[float]:
    peak = 0.0
    drawdowns: List[float] = []
    for equity in equity_curve:
        peak = max(peak, equity)
        drawdowns.append(0.0 if peak == 0 else (equity / peak) - 1)
    return drawdowns


def _profit_factor(trades: List[Trade]) -> float:
    gross_profit = sum(max(trade.pnl, 0.0) for trade in trades)
    gross_loss = abs(sum(min(trade.pnl, 0.0) for trade in trades))
    return math.inf if gross_loss == 0 and gross_profit > 0 else (gross_profit / gross_loss if gross_loss else 0.0)


def _win_rate(trades: List[Trade]) -> float:
    if not trades:
        return 0.0
    return (sum(1 for trade in trades if trade.pnl > 0) / len(trades)) * 100


def _sharpe_ratio(equity_curve: List[float]) -> float:
    if len(equity_curve) < 2:
        return 0.0
    returns = [(equity_curve[index] / equity_curve[index - 1]) - 1 for index in range(1, len(equity_curve)) if equity_curve[index - 1] > 0]
    if len(returns) < 2:
        return 0.0
    volatility = pstdev(returns)
    return 0.0 if volatility == 0 else (mean(returns) / volatility) * math.sqrt(252)


def _cagr(equity_curve: List[float], bars: List[Bar]) -> float:
    if not equity_curve or len(bars) < 2 or equity_curve[0] <= 0:
        return 0.0
    days = max((bars[-1].date - bars[0].date).days, 1)
    years = days / 365.25
    return ((equity_curve[-1] / equity_curve[0]) ** (1 / years) - 1) * 100 if years > 0 else 0.0


def format_summary(result: BacktestResult) -> str:
    return "\n".join(
        [
            "Backtest summary",
            f"Trades: {result.trade_count}",
            f"Final equity: ${result.final_equity:,.2f}",
            f"Total return: {result.total_return_pct:.2f}%",
            f"CAGR: {result.cagr_pct:.2f}%",
            f"Profit factor: {result.profit_factor:.2f}",
            f"Max drawdown: {result.max_drawdown_pct:.2f}%",
            f"Win rate: {result.win_rate_pct:.2f}%",
            f"Sharpe ratio: {result.sharpe_ratio:.2f}",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest the AAPL daily EMA + RSI strategy against OHLCV CSV data.")
    parser.add_argument("csv_path", help="CSV file with Date, Open, High, Low, Close, Volume columns.")
    args = parser.parse_args()

    bars = load_ohlcv_csv(args.csv_path)
    result = backtest_strategy(bars)
    print(format_summary(result))


if __name__ == "__main__":
    main()
