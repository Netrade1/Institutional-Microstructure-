"""
features/engineer.py – Feature Engineering Layer (Phase 1).

Produces a named, versioned feature vector from each OrderBookState.
This vector is the primary input to Phase 2 machine learning models.

Feature groups:
    1. Core order book features
    2. Technical indicator features (VWAP, RVOL, RSI, ATR, MACD, BB)
    3. Behavioral composite scores

All features are returned as a FeatureVector dataclass and also as a
flat dict suitable for serialisation (pandas, Parquet, model inference).
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Optional

from src.config import FEATURE_WINDOWS, RSI_PERIOD, ATR_PERIOD
from src.data_intake.models import Trade
from src.order_book.engine import OrderBookState


FEATURE_VERSION = "1.0"


@dataclass
class FeatureVector:
    """
    Complete ML-ready feature vector produced at each tick.
    All values are float. NaN indicates unavailable / insufficient history.
    """
    # ── Metadata ──────────────────────────────────────────────────────────────
    feature_version: str
    symbol: str
    timestamp_ns: int

    # ── Core order book features ──────────────────────────────────────────────
    bid_ask_imbalance: float
    depth_weighted_imbalance: float
    spread: float
    mid_price: float
    microprice: float
    microprice_bias: float          # microprice - mid_price (signed pressure)
    order_flow_imbalance: float
    bid_depth_change_pct: float
    ask_depth_change_pct: float
    absorption_score: float
    sweep_intensity: float
    spoof_like_score: float
    iceberg_like_score: float
    bid_replenishment_rate: float
    ask_replenishment_rate: float
    volume_at_bid: float
    volume_at_ask: float
    rolling_buy_sell_ratio: float
    spread_multiple: float
    stacking_bid: float             # bool encoded as 0/1
    stacking_ask: float
    pulling_bid: float
    pulling_ask: float

    # ── Multi-window OBI deltas ───────────────────────────────────────────────
    obi_5s: float
    obi_10s: float
    obi_30s: float
    ofi_5s: float
    ofi_30s: float

    # ── Technical indicators ──────────────────────────────────────────────────
    vwap: float
    vwap_deviation: float           # (mid - vwap) / vwap
    rvol: float                     # relative volume vs 20-bar average
    rsi_14: float
    atr_14: float
    macd_line: float
    macd_signal: float
    macd_histogram: float
    bb_upper: float
    bb_lower: float
    bb_width: float
    bb_pct_b: float                 # %B: position within Bollinger Bands
    obv: float                      # on-balance volume
    ma_slope_5: float               # slope of 5-bar MA
    ma_slope_20: float

    # ── Behavioral composite scores ───────────────────────────────────────────
    accumulation_score: float       # composite: OBI + absorption + replenishment + VWAP support
    distribution_score: float       # composite: negative OBI + ask stacking + fading
    institutional_footprint_prob: float
    momentum_ignition_risk: float
    liquidity_trap_risk: float
    breakout_confirmation_score: float
    false_breakout_prob: float      # placeholder until ML model available

    def to_dict(self) -> dict:
        return asdict(self)

    def to_flat_dict(self) -> dict[str, float | str | int]:
        """Flatten for pandas / Parquet storage."""
        return self.to_dict()


class FeatureEngineer:
    """
    Stateful feature engineer.

    Maintains rolling price/volume/indicator history per symbol.
    Call update() after each (OrderBookState, list[Trade]) pair.
    """

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self._mid_prices: deque[float] = deque(maxlen=200)
        self._volumes: deque[float] = deque(maxlen=200)
        self._highs: deque[float] = deque(maxlen=200)
        self._lows: deque[float] = deque(maxlen=200)
        self._closes: deque[float] = deque(maxlen=200)
        self._obi_ts: deque[tuple[float, int]] = deque(maxlen=500)   # (obi, ts_ns)
        self._ofi_ts: deque[tuple[float, int]] = deque(maxlen=500)
        self._vwap_num: float = 0.0     # cumulative price × volume
        self._vwap_den: float = 0.0     # cumulative volume
        self._obv: float = 0.0
        self._prev_mid: Optional[float] = None
        self._avg_vol_20: deque[float] = deque(maxlen=20)

    # ── Public ────────────────────────────────────────────────────────────────

    def update(
        self,
        state: OrderBookState,
        trades: list[Trade],
    ) -> FeatureVector:
        """Ingest new state and trades; return updated FeatureVector."""
        mp = state.mid_price
        trade_vol = sum(t.size for t in trades)
        trade_value = sum(t.price * t.size for t in trades)

        # Update OHLCV-like rolling series
        self._mid_prices.append(mp)
        self._closes.append(mp)
        self._highs.append(max((t.price for t in trades), default=mp))
        self._lows.append(min((t.price for t in trades), default=mp))
        self._volumes.append(trade_vol)
        self._avg_vol_20.append(trade_vol)

        # VWAP
        self._vwap_num += trade_value
        self._vwap_den += trade_vol
        vwap = (self._vwap_num / self._vwap_den) if self._vwap_den > 0 else mp
        vwap_dev = ((mp - vwap) / vwap) if vwap > 0 else 0.0

        # OBV
        if self._prev_mid is not None:
            if mp > self._prev_mid:
                self._obv += trade_vol
            elif mp < self._prev_mid:
                self._obv -= trade_vol
        self._prev_mid = mp

        # Relative volume
        avg_vol = sum(self._avg_vol_20) / len(self._avg_vol_20) if self._avg_vol_20 else 1
        rvol = trade_vol / avg_vol if avg_vol > 0 else 1.0

        # Technical indicators
        rsi = self._rsi(list(self._closes), RSI_PERIOD)
        atr = self._atr(
            list(self._highs), list(self._lows), list(self._closes), ATR_PERIOD
        )
        macd_l, macd_s, macd_h = self._macd(list(self._closes))
        bb_u, bb_l, bb_w, bb_pctb = self._bollinger(list(self._closes))
        ma5 = self._ma_slope(list(self._closes), 5)
        ma20 = self._ma_slope(list(self._closes), 20)

        # Windowed OBI / OFI
        self._obi_ts.append((state.book_imbalance, state.timestamp_ns))
        self._ofi_ts.append((state.order_flow_imbalance, state.timestamp_ns))
        obi_5, obi_10, obi_30 = self._windowed_mean(self._obi_ts, [5, 10, 30])
        ofi_5, ofi_30 = self._windowed_mean(self._ofi_ts, [5, 30])[:2]

        # Behavioral composite scores
        accum = self._accumulation_score(state, vwap_dev)
        distrib = self._distribution_score(state, vwap_dev)
        inst_prob = self._institutional_footprint_prob(state, accum, distrib)
        mig_risk = self._momentum_ignition_risk(state, rvol)
        lt_risk = self._liquidity_trap_risk(state, atr)
        bo_score = self._breakout_confirmation_score(state, rvol)
        fb_prob = self._false_breakout_prob(state)  # heuristic placeholder

        return FeatureVector(
            feature_version=FEATURE_VERSION,
            symbol=self.symbol,
            timestamp_ns=state.timestamp_ns,
            # Core OB
            bid_ask_imbalance=state.book_imbalance,
            depth_weighted_imbalance=state.depth_weighted_imbalance,
            spread=state.spread,
            mid_price=state.mid_price,
            microprice=state.microprice,
            microprice_bias=round(state.microprice - state.mid_price, 6),
            order_flow_imbalance=state.order_flow_imbalance,
            bid_depth_change_pct=state.bid_depth_change_pct,
            ask_depth_change_pct=state.ask_depth_change_pct,
            absorption_score=state.absorption_score,
            sweep_intensity=state.sweep_intensity,
            spoof_like_score=state.spoof_like_score,
            iceberg_like_score=state.iceberg_like_score,
            bid_replenishment_rate=state.bid_replenishment_rate,
            ask_replenishment_rate=state.ask_replenishment_rate,
            volume_at_bid=state.volume_at_bid,
            volume_at_ask=state.volume_at_ask,
            rolling_buy_sell_ratio=state.rolling_buy_sell_ratio,
            spread_multiple=state.spread_multiple,
            stacking_bid=float(state.stacking_bid),
            stacking_ask=float(state.stacking_ask),
            pulling_bid=float(state.pulling_bid),
            pulling_ask=float(state.pulling_ask),
            # Multi-window
            obi_5s=obi_5,
            obi_10s=obi_10,
            obi_30s=obi_30,
            ofi_5s=ofi_5,
            ofi_30s=ofi_30,
            # Technical
            vwap=round(vwap, 4),
            vwap_deviation=round(vwap_dev, 6),
            rvol=round(rvol, 4),
            rsi_14=rsi,
            atr_14=atr,
            macd_line=macd_l,
            macd_signal=macd_s,
            macd_histogram=macd_h,
            bb_upper=bb_u,
            bb_lower=bb_l,
            bb_width=bb_w,
            bb_pct_b=bb_pctb,
            obv=round(self._obv, 2),
            ma_slope_5=ma5,
            ma_slope_20=ma20,
            # Behavioral
            accumulation_score=accum,
            distribution_score=distrib,
            institutional_footprint_prob=inst_prob,
            momentum_ignition_risk=mig_risk,
            liquidity_trap_risk=lt_risk,
            breakout_confirmation_score=bo_score,
            false_breakout_prob=fb_prob,
        )

    # ── Indicator implementations ─────────────────────────────────────────────

    @staticmethod
    def _rsi(closes: list[float], period: int) -> float:
        if len(closes) < period + 1:
            return float("nan")
        gains, losses = [], []
        for i in range(1, len(closes)):
            chg = closes[i] - closes[i - 1]
            gains.append(max(chg, 0))
            losses.append(max(-chg, 0))
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 4)

    @staticmethod
    def _atr(
        highs: list[float], lows: list[float], closes: list[float], period: int
    ) -> float:
        if len(closes) < period + 1:
            return float("nan")
        trs = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            trs.append(tr)
        return round(sum(trs[-period:]) / period, 6)

    @staticmethod
    def _ema(data: list[float], period: int) -> list[float]:
        if not data:
            return []
        k = 2 / (period + 1)
        ema = [data[0]]
        for v in data[1:]:
            ema.append(v * k + ema[-1] * (1 - k))
        return ema

    def _macd(
        self, closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9
    ) -> tuple[float, float, float]:
        if len(closes) < slow + signal:
            return float("nan"), float("nan"), float("nan")
        ema_fast = self._ema(closes, fast)
        ema_slow = self._ema(closes, slow)
        macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
        macd_signal = self._ema(macd_line, signal)
        if not macd_signal:
            return float("nan"), float("nan"), float("nan")
        ml = round(macd_line[-1], 6)
        ms = round(macd_signal[-1], 6)
        return ml, ms, round(ml - ms, 6)

    @staticmethod
    def _bollinger(closes: list[float], period: int = 20, std_dev: float = 2.0):
        if len(closes) < period:
            return float("nan"), float("nan"), float("nan"), float("nan")
        window = closes[-period:]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        std = math.sqrt(variance)
        upper = round(mean + std_dev * std, 4)
        lower = round(mean - std_dev * std, 4)
        width = round(upper - lower, 6)
        last = closes[-1]
        pct_b = round((last - lower) / width, 4) if width > 0 else 0.5
        return upper, lower, width, pct_b

    @staticmethod
    def _ma_slope(closes: list[float], period: int) -> float:
        if len(closes) < period + 1:
            return float("nan")
        ma_now = sum(closes[-period:]) / period
        ma_prev = sum(closes[-(period + 1):-1]) / period
        return round(ma_now - ma_prev, 6)

    @staticmethod
    def _windowed_mean(
        buffer: deque[tuple[float, int]], windows_s: list[int]
    ) -> list[float]:
        now = time.time_ns()
        results = []
        for w in windows_s:
            cutoff = now - w * 1_000_000_000
            vals = [v for v, ts in buffer if ts >= cutoff]
            results.append(round(sum(vals) / len(vals), 4) if vals else float("nan"))
        return results

    # ── Behavioral composite scores ───────────────────────────────────────────

    @staticmethod
    def _accumulation_score(state: OrderBookState, vwap_dev: float) -> float:
        score = 0.0
        if state.book_imbalance > 0.2:
            score += 0.25
        if state.absorption_score > 0.5:
            score += 0.25
        if state.bid_replenishment_rate > 0.3:
            score += 0.20
        if vwap_dev > -0.002:          # price near or above VWAP
            score += 0.15
        if state.order_flow_imbalance > 0.1:
            score += 0.15
        return round(min(score, 1.0), 3)

    @staticmethod
    def _distribution_score(state: OrderBookState, vwap_dev: float) -> float:
        score = 0.0
        if state.book_imbalance < -0.2:
            score += 0.25
        if state.stacking_ask:
            score += 0.25
        if vwap_dev < 0.002:           # price near or below VWAP
            score += 0.15
        if state.order_flow_imbalance < -0.1:
            score += 0.20
        if state.ask_replenishment_rate > 0.3:
            score += 0.15
        return round(min(score, 1.0), 3)

    @staticmethod
    def _institutional_footprint_prob(
        state: OrderBookState, accum: float, distrib: float
    ) -> float:
        """
        Combined probability that observed activity resembles institutional-style
        participation (either accumulation or distribution style).

        All outputs from this score MUST be accompanied by the compliance limitations
        statement in any user-facing response.
        """
        base = max(accum, distrib)
        if state.iceberg_like_score > 0.4:
            base += 0.10
        if state.absorption_score > 0.6:
            base += 0.08
        return round(min(base, 1.0), 3)

    @staticmethod
    def _momentum_ignition_risk(state: OrderBookState, rvol: float) -> float:
        score = 0.0
        if state.sweep_intensity > 0.5:
            score += 0.4
        if rvol > 2.0:
            score += 0.3
        if state.spoof_like_score > 0.3:
            score += 0.3
        return round(min(score, 1.0), 3)

    @staticmethod
    def _liquidity_trap_risk(state: OrderBookState, atr: float) -> float:
        score = 0.0
        if state.spread_multiple > 2.0:
            score += 0.4
        if not math.isnan(atr) and atr > 0 and state.spread > atr * 0.1:
            score += 0.3
        if state.pulling_bid or state.pulling_ask:
            score += 0.3
        return round(min(score, 1.0), 3)

    @staticmethod
    def _breakout_confirmation_score(state: OrderBookState, rvol: float) -> float:
        score = 0.0
        if state.sweep_intensity > 0.4:
            score += 0.3
        if rvol > 1.5:
            score += 0.3
        if state.book_imbalance > 0.3:
            score += 0.2
        if state.absorption_score < 0.3:   # low absorption = price can move
            score += 0.2
        return round(min(score, 1.0), 3)

    @staticmethod
    def _false_breakout_prob(state: OrderBookState) -> float:
        """Heuristic placeholder – Phase 2 will replace with trained classifier."""
        score = 0.0
        if state.spoof_like_score > 0.3:
            score += 0.4
        if state.pulling_bid or state.pulling_ask:
            score += 0.3
        if state.spread_multiple > 2.0:
            score += 0.3
        return round(min(score, 1.0), 3)
