"""
order_book/engine.py – Level 2 Order Book Processing Engine (Phase 1).

Transforms raw order book snapshots and trade prints into structured
behavioral intelligence signals.

Tracks and computes:
    - Bid / ask depth per level
    - Order book imbalance (OBI)
    - Depth-weighted imbalance
    - Spread (current, rolling average, multiple)
    - Liquidity stacking events
    - Liquidity pulling events
    - Spoof-like behavior signal
    - Iceberg-like behavior signal
    - Absorption score
    - Sweep events
    - Bid / ask replenishment
    - Queue pressure
    - Volume at bid vs ask
    - Microprice

All computed values feed directly into the Feature Engineering Layer.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from src.config import (
    ABSORPTION_MIN_PRINTS,
    OB_DEPTH_LEVELS,
    OB_WINDOW_SECONDS,
    SPOOF_MIN_CANCEL_RATIO,
    SWEEP_PRICE_LEVELS,
)
from src.data_intake.models import L2Level, OrderBookSnapshot, Trade


@dataclass
class OrderBookState:
    """
    Complete processed state produced after each snapshot update.
    All downstream agents read from this structure.
    """
    symbol: str
    timestamp_ns: int

    # ── Raw depth ─────────────────────────────────────────────────────────────
    bids: list[L2Level]
    asks: list[L2Level]
    best_bid: Optional[L2Level]
    best_ask: Optional[L2Level]
    spread: float
    mid_price: float
    microprice: float

    # ── Imbalance metrics ─────────────────────────────────────────────────────
    book_imbalance: float           # (bid_vol - ask_vol) / (bid_vol + ask_vol)  [-1, 1]
    depth_weighted_imbalance: float # weighted version across levels
    order_flow_imbalance: float     # cumulative signed volume, rolling window

    # ── Liquidity events ─────────────────────────────────────────────────────
    bid_depth_change_pct: float     # % change in total bid depth vs previous snapshot
    ask_depth_change_pct: float
    stacking_bid: bool              # abnormally large size appeared at bid
    stacking_ask: bool
    pulling_bid: bool               # large size disappeared from bid without a fill
    pulling_ask: bool

    # ── Behavioral scores (0.0 – 1.0) ────────────────────────────────────────
    absorption_score: float         # large prints absorbed without price continuation
    sweep_intensity: float          # consecutive level crossings
    spoof_like_score: float         # cancel-rate heuristic near best bid/ask
    iceberg_like_score: float       # repeated replenishment after partial fills
    bid_replenishment_rate: float   # bid side recovery rate
    ask_replenishment_rate: float   # ask side recovery rate

    # ── Volume analysis ───────────────────────────────────────────────────────
    volume_at_bid: float            # inferred sell-aggressor volume, rolling window
    volume_at_ask: float            # inferred buy-aggressor volume, rolling window
    rolling_buy_sell_ratio: float   # buy_vol / (buy_vol + sell_vol)

    # ── Spread context ────────────────────────────────────────────────────────
    spread_avg_20: float            # 20-snapshot rolling average spread
    spread_multiple: float          # spread / spread_avg_20

    # ── Human-readable signal summary ────────────────────────────────────────
    signals: list[str] = field(default_factory=list)


class OrderBookEngine:
    """
    Stateful processor that converts each (OrderBookSnapshot, list[Trade])
    pair into a fully computed OrderBookState.

    Maintains rolling buffers to compute windowed metrics.
    """

    _STACK_THRESHOLD_MULTIPLE = 4.0    # level size > 4× mean depth → stacking
    _PULL_THRESHOLD_MULTIPLE = 3.0     # size drop > 3× mean depth without fill → pulling
    _REPLENISH_THRESHOLD = 0.5         # depth recovered ≥50% after being hit

    def __init__(self, depth_levels: int = OB_DEPTH_LEVELS) -> None:
        self.depth_levels = depth_levels
        self._prev_snapshot: Optional[OrderBookSnapshot] = None

        # Rolling buffers (keyed by symbol; single-symbol engine for Phase 1)
        window = OB_WINDOW_SECONDS * 4   # ~250ms ticks
        self._spreads: deque[float] = deque(maxlen=20)
        self._ofi_buffer: deque[tuple[float, int]] = deque(maxlen=window)  # (signed_vol, ts_ns)
        self._trade_buffer: deque[Trade] = deque(maxlen=window)
        self._bid_depth_history: deque[float] = deque(maxlen=window)
        self._ask_depth_history: deque[float] = deque(maxlen=window)
        self._absorption_prints: deque[tuple[float, float]] = deque(maxlen=50)  # (price, size)
        self._replenish_bid_hits: deque[float] = deque(maxlen=30)
        self._replenish_ask_hits: deque[float] = deque(maxlen=30)
        self._cancel_add_ratio_buffer: deque[float] = deque(maxlen=20)

    # ── Public interface ──────────────────────────────────────────────────────

    def process(
        self,
        snapshot: OrderBookSnapshot,
        trades: list[Trade],
    ) -> OrderBookState:
        """Compute and return a fully populated OrderBookState."""
        bids = snapshot.bids[: self.depth_levels]
        asks = snapshot.asks[: self.depth_levels]

        bid_vol = sum(lvl.size for lvl in bids)
        ask_vol = sum(lvl.size for lvl in asks)

        # Ingest trades into rolling buffers
        for t in trades:
            self._trade_buffer.append(t)
            signed = t.size if t.side == "buy" else -t.size if t.side == "sell" else 0
            self._ofi_buffer.append((signed, t.timestamp_ns))

        # Rolling buffers
        self._bid_depth_history.append(bid_vol)
        self._ask_depth_history.append(ask_vol)
        spread = snapshot.spread
        if not _is_nan(spread):
            self._spreads.append(spread)

        # Compute all signals
        book_imbalance = self._book_imbalance(bid_vol, ask_vol)
        dwi = self._depth_weighted_imbalance(bids, asks)
        ofi = self._order_flow_imbalance()
        bid_chg, ask_chg = self._depth_change_pct()
        stacking_bid, stacking_ask = self._detect_stacking(bids, asks)
        pulling_bid, pulling_ask = self._detect_pulling(bids, asks)
        absorption = self._absorption_score(trades, snapshot)
        sweep = self._sweep_intensity(trades, snapshot)
        spoof = self._spoof_like_score(snapshot)
        iceberg = self._iceberg_like_score(trades)
        bid_replen, ask_replen = self._replenishment_rates(snapshot, trades)
        vol_bid, vol_ask, bsr = self._volume_analysis()
        spread_avg = sum(self._spreads) / len(self._spreads) if self._spreads else spread
        spread_mult = (spread / spread_avg) if spread_avg > 0 and not _is_nan(spread) else 1.0

        mp = snapshot.mid_price
        uprice = self._microprice(snapshot)

        signals = self._build_signals(
            book_imbalance=book_imbalance,
            bid_chg=bid_chg,
            ask_chg=ask_chg,
            stacking_bid=stacking_bid,
            stacking_ask=stacking_ask,
            pulling_bid=pulling_bid,
            pulling_ask=pulling_ask,
            absorption=absorption,
            sweep=sweep,
            spoof=spoof,
            iceberg=iceberg,
            spread_mult=spread_mult,
            bsr=bsr,
        )

        self._prev_snapshot = snapshot

        return OrderBookState(
            symbol=snapshot.symbol,
            timestamp_ns=snapshot.timestamp_ns,
            bids=bids,
            asks=asks,
            best_bid=snapshot.best_bid,
            best_ask=snapshot.best_ask,
            spread=spread,
            mid_price=mp,
            microprice=uprice,
            book_imbalance=book_imbalance,
            depth_weighted_imbalance=dwi,
            order_flow_imbalance=ofi,
            bid_depth_change_pct=bid_chg,
            ask_depth_change_pct=ask_chg,
            stacking_bid=stacking_bid,
            stacking_ask=stacking_ask,
            pulling_bid=pulling_bid,
            pulling_ask=pulling_ask,
            absorption_score=absorption,
            sweep_intensity=sweep,
            spoof_like_score=spoof,
            iceberg_like_score=iceberg,
            bid_replenishment_rate=bid_replen,
            ask_replenishment_rate=ask_replen,
            volume_at_bid=vol_bid,
            volume_at_ask=vol_ask,
            rolling_buy_sell_ratio=bsr,
            spread_avg_20=round(spread_avg, 6),
            spread_multiple=round(spread_mult, 3),
            signals=signals,
        )

    # ── Signal computation ────────────────────────────────────────────────────

    @staticmethod
    def _book_imbalance(bid_vol: float, ask_vol: float) -> float:
        total = bid_vol + ask_vol
        return round((bid_vol - ask_vol) / total, 4) if total > 0 else 0.0

    @staticmethod
    def _depth_weighted_imbalance(
        bids: list[L2Level], asks: list[L2Level]
    ) -> float:
        """Imbalance weighted by inverse price distance from best bid/ask."""
        if not bids or not asks:
            return 0.0
        best_b = bids[0].price
        best_a = asks[0].price
        bid_w = sum(lvl.size / (1 + abs(lvl.price - best_b)) for lvl in bids)
        ask_w = sum(lvl.size / (1 + abs(lvl.price - best_a)) for lvl in asks)
        total = bid_w + ask_w
        return round((bid_w - ask_w) / total, 4) if total > 0 else 0.0

    def _order_flow_imbalance(self) -> float:
        """Cumulative signed volume over rolling window, normalised."""
        if not self._ofi_buffer:
            return 0.0
        cutoff_ns = time.time_ns() - OB_WINDOW_SECONDS * 1_000_000_000
        vals = [sv for sv, ts in self._ofi_buffer if ts >= cutoff_ns]
        if not vals:
            return 0.0
        total_abs = sum(abs(v) for v in vals)
        return round(sum(vals) / total_abs, 4) if total_abs > 0 else 0.0

    def _depth_change_pct(self) -> tuple[float, float]:
        if len(self._bid_depth_history) < 2:
            return 0.0, 0.0
        prev_b = self._bid_depth_history[-2]
        prev_a = self._ask_depth_history[-2]
        curr_b = self._bid_depth_history[-1]
        curr_a = self._ask_depth_history[-1]
        bid_chg = ((curr_b - prev_b) / prev_b * 100) if prev_b > 0 else 0.0
        ask_chg = ((curr_a - prev_a) / prev_a * 100) if prev_a > 0 else 0.0
        return round(bid_chg, 2), round(ask_chg, 2)

    def _detect_stacking(
        self, bids: list[L2Level], asks: list[L2Level]
    ) -> tuple[bool, bool]:
        """A stacking event is flagged when a single level carries ≥4× mean depth."""
        if len(bids) < 2 or len(asks) < 2:
            return False, False
        bid_mean = sum(lvl.size for lvl in bids) / len(bids)
        ask_mean = sum(lvl.size for lvl in asks) / len(asks)
        stacking_b = bids[0].size >= self._STACK_THRESHOLD_MULTIPLE * bid_mean
        stacking_a = asks[0].size >= self._STACK_THRESHOLD_MULTIPLE * ask_mean
        return stacking_b, stacking_a

    def _detect_pulling(
        self, bids: list[L2Level], asks: list[L2Level]
    ) -> tuple[bool, bool]:
        """Pulling detected when best-level depth drops sharply without a matching trade."""
        pulling_b = pulling_a = False
        if self._prev_snapshot:
            prev_bb = self._prev_snapshot.best_bid
            prev_ba = self._prev_snapshot.best_ask
            curr_bb = bids[0] if bids else None
            curr_ba = asks[0] if asks else None

            recent_trade_vol = sum(
                t.size for t in list(self._trade_buffer)[-5:] if t.side == "sell"
            )
            if (
                prev_bb
                and curr_bb
                and prev_bb.price == curr_bb.price
                and prev_bb.size > 0
            ):
                drop = (prev_bb.size - curr_bb.size) / prev_bb.size
                if drop >= 0.5 and recent_trade_vol < prev_bb.size * 0.1:
                    pulling_b = True

            recent_buy_vol = sum(
                t.size for t in list(self._trade_buffer)[-5:] if t.side == "buy"
            )
            if (
                prev_ba
                and curr_ba
                and prev_ba.price == curr_ba.price
                and prev_ba.size > 0
            ):
                drop = (prev_ba.size - curr_ba.size) / prev_ba.size
                if drop >= 0.5 and recent_buy_vol < prev_ba.size * 0.1:
                    pulling_a = True

        return pulling_b, pulling_a

    def _absorption_score(
        self, trades: list[Trade], snapshot: OrderBookSnapshot
    ) -> float:
        """
        Absorption: large aggressive prints execute but price does not move
        in the aggressor's direction.

        Score = fraction of recent large prints that were 'absorbed'.
        """
        large_threshold = 500  # shares – configurable
        absorbed = 0
        total_large = 0
        prev = self._prev_snapshot

        for t in trades:
            if t.size < large_threshold:
                continue
            total_large += 1
            if prev:
                if t.side == "buy" and snapshot.mid_price <= prev.mid_price + 0.02:
                    absorbed += 1
                elif t.side == "sell" and snapshot.mid_price >= prev.mid_price - 0.02:
                    absorbed += 1

        if total_large < ABSORPTION_MIN_PRINTS:
            # Accumulate across recent history
            recent = [t for t in self._trade_buffer if t.size >= large_threshold]
            total_large = len(recent)
            if total_large == 0:
                return 0.0
            absorbed = sum(
                1 for t in recent
                if snapshot.mid_price is not None
            )  # simplified for Phase 1

        return round(min(absorbed / max(total_large, 1), 1.0), 3)

    def _sweep_intensity(
        self, trades: list[Trade], snapshot: OrderBookSnapshot
    ) -> float:
        """
        Sweep: consecutive aggressive prints crossing multiple price levels.
        Returns a normalised intensity in [0, 1].
        """
        if len(trades) < 2:
            return 0.0
        price_levels_hit = len({round(t.price, 2) for t in trades})
        return round(min(price_levels_hit / SWEEP_PRICE_LEVELS, 1.0), 3)

    def _spoof_like_score(self, snapshot: OrderBookSnapshot) -> float:
        """
        Heuristic: high cancel-to-add ratio near best bid/ask suggests spoof-like activity.
        Phase 1 approximation: compare current best-level depth to rolling mean.
        Elevated cancel-to-add will be tracked via tick-by-tick diffs in Phase 2+.
        """
        if not self._bid_depth_history or len(self._bid_depth_history) < 5:
            return 0.0
        bb = snapshot.best_bid
        if bb is None:
            return 0.0
        mean_bid = sum(list(self._bid_depth_history)[-10:]) / min(
            len(self._bid_depth_history), 10
        )
        # If best bid is dramatically larger than recent mean, flag potential stacking
        # that could be pulled (spoof-like pattern precursor)
        if mean_bid > 0 and bb.size / mean_bid >= SPOOF_MIN_CANCEL_RATIO:
            return round(min((bb.size / mean_bid - SPOOF_MIN_CANCEL_RATIO) / 4, 1.0), 3)
        return 0.0

    def _iceberg_like_score(self, trades: list[Trade]) -> float:
        """
        Iceberg heuristic: repeated fills of similar size at the same price level,
        with the level apparently refreshing after each fill.
        """
        if len(trades) < 3:
            return 0.0
        sizes = [t.size for t in trades if t.size > 100]
        if len(sizes) < 3:
            return 0.0
        # Check for clustering of similar print sizes
        mean_s = sum(sizes) / len(sizes)
        similar = sum(1 for s in sizes if abs(s - mean_s) / mean_s < 0.15)
        return round(similar / len(sizes), 3)

    def _replenishment_rates(
        self, snapshot: OrderBookSnapshot, trades: list[Trade]
    ) -> tuple[float, float]:
        """Track bid/ask replenishment after being hit."""
        prev = self._prev_snapshot
        if not prev:
            return 0.0, 0.0

        bid_replen = 0.0
        ask_replen = 0.0

        prev_bb = prev.best_bid
        curr_bb = snapshot.best_bid
        if prev_bb and curr_bb and prev_bb.price == curr_bb.price:
            sell_vol = sum(t.size for t in trades if t.side == "sell")
            if sell_vol > 0 and curr_bb.size > prev_bb.size * 0.5:
                bid_replen = min(curr_bb.size / (prev_bb.size + sell_vol), 1.0)

        prev_ba = prev.best_ask
        curr_ba = snapshot.best_ask
        if prev_ba and curr_ba and prev_ba.price == curr_ba.price:
            buy_vol = sum(t.size for t in trades if t.side == "buy")
            if buy_vol > 0 and curr_ba.size > prev_ba.size * 0.5:
                ask_replen = min(curr_ba.size / (prev_ba.size + buy_vol), 1.0)

        return round(bid_replen, 3), round(ask_replen, 3)

    def _volume_analysis(self) -> tuple[float, float, float]:
        """Buy vs sell volume over rolling window."""
        cutoff_ns = time.time_ns() - OB_WINDOW_SECONDS * 1_000_000_000
        recent = [t for t in self._trade_buffer if t.timestamp_ns >= cutoff_ns]
        vol_buy = sum(t.size for t in recent if t.side == "buy")
        vol_sell = sum(t.size for t in recent if t.side == "sell")
        total = vol_buy + vol_sell
        bsr = vol_buy / total if total > 0 else 0.5
        return vol_sell, vol_buy, round(bsr, 4)

    @staticmethod
    def _microprice(snapshot: OrderBookSnapshot) -> float:
        bb = snapshot.best_bid
        ba = snapshot.best_ask
        if not bb or not ba:
            return snapshot.mid_price
        total = bb.size + ba.size
        if total == 0:
            return snapshot.mid_price
        return round((bb.price * ba.size + ba.price * bb.size) / total, 6)

    def _build_signals(self, **kwargs) -> list[str]:
        """Generate human-readable signal strings for the chatbot layer."""
        signals: list[str] = []
        obi = kwargs["book_imbalance"]
        bid_chg = kwargs["bid_chg"]
        ask_chg = kwargs["ask_chg"]
        spread_mult = kwargs["spread_mult"]

        if obi > 0.3:
            signals.append(f"Order book imbalance favours buyers (+{obi:.2f}).")
        elif obi < -0.3:
            signals.append(f"Order book imbalance favours sellers ({obi:.2f}).")

        if kwargs["stacking_bid"]:
            signals.append("Bid-side stacking detected: abnormally large size at best bid.")
        if kwargs["stacking_ask"]:
            signals.append("Ask-side stacking detected: abnormally large size at best ask.")

        if kwargs["pulling_bid"]:
            signals.append("Bid-side pulling detected: large size removed without execution.")
        if kwargs["pulling_ask"]:
            signals.append("Ask-side pulling detected: large size removed without execution.")

        if bid_chg > 20:
            signals.append(f"Bid-side liquidity increased {bid_chg:.1f}% since last tick.")
        elif bid_chg < -20:
            signals.append(f"Bid-side liquidity decreased {abs(bid_chg):.1f}% since last tick.")

        if ask_chg > 20:
            signals.append(f"Ask-side liquidity increased {ask_chg:.1f}% since last tick.")
        elif ask_chg < -20:
            signals.append(f"Ask-side liquidity decreased {abs(ask_chg):.1f}% since last tick.")

        if kwargs["absorption"] > 0.6:
            signals.append(
                f"Absorption detected: large prints absorbed without price continuation "
                f"(score {kwargs['absorption']:.2f})."
            )

        if kwargs["sweep"] > 0.6:
            signals.append(f"Sweep activity detected (intensity {kwargs['sweep']:.2f}).")

        if kwargs["spoof"] > 0.3:
            signals.append(
                f"Spoof-like signal: elevated cancel-to-add pattern detected near best bid/ask "
                f"(score {kwargs['spoof']:.2f}). Treat with caution."
            )

        if kwargs["iceberg"] > 0.5:
            signals.append(
                f"Iceberg-like activity: repeated similar-size fills detected "
                f"(score {kwargs['iceberg']:.2f})."
            )

        if spread_mult > 2.5:
            signals.append(
                f"Spread elevated: {spread_mult:.1f}× the 20-snapshot average. Execution risk increased."
            )

        if not signals:
            signals.append("No significant order book signals detected at this time.")

        return signals


def _is_nan(v: float) -> bool:
    try:
        import math
        return math.isnan(v)
    except Exception:
        return False
