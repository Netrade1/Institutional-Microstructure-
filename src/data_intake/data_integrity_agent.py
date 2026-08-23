"""
data_intake/data_integrity_agent.py – Data Integrity Agent (Phase 1).

Monitors incoming snapshots and trade streams for:
  - Stale quotes (no update within threshold)
  - Bad ticks (price outliers)
  - Missing data (gaps in sequence numbers)
  - Feed latency
  - Zero-size quotes

Produces a FeedHealthReport that downstream agents consume before processing.
A failing health check can halt or flag downstream processing.
"""

from __future__ import annotations

import statistics
import time
from collections import deque

from src.data_intake.models import FeedHealthReport, OrderBookSnapshot, Trade


class DataIntegrityAgent:
    """
    Stateful feed monitor.

    Call check() after each (snapshot, trades) pair.  The returned
    FeedHealthReport is passed to the audit ledger and the agentic
    orchestration layer.
    """

    STALE_THRESHOLD_MS = 5_000       # quote older than 5s → stale
    PRICE_OUTLIER_SIGMA = 5.0        # prints > 5 σ from rolling mean → bad tick
    PRICE_HISTORY_SIZE = 200         # rolling window for outlier detection
    MAX_LATENCY_MS = 2_000           # >2 s feed lag → degraded health

    def __init__(self) -> None:
        self._last_ts_ns: int | None = None
        self._prev_sequence: int | None = None
        self._price_history: deque[float] = deque(maxlen=self.PRICE_HISTORY_SIZE)
        self._latency_samples: deque[float] = deque(maxlen=50)

    # ── Public ────────────────────────────────────────────────────────────────

    def check(
        self,
        snapshot: OrderBookSnapshot,
        trades: list[Trade],
    ) -> FeedHealthReport:
        now_ns = time.time_ns()
        notes: list[str] = []
        bad_ticks = 0
        gap_detected = False

        # ── Staleness ────────────────────────────────────────────────────────
        stale = False
        if self._last_ts_ns is not None:
            age_ms = (now_ns - snapshot.timestamp_ns) / 1e6
            if age_ms > self.STALE_THRESHOLD_MS:
                stale = True
                notes.append(f"Stale quote: {age_ms:.0f}ms old")
        self._last_ts_ns = snapshot.timestamp_ns

        # ── Sequence gap ─────────────────────────────────────────────────────
        if snapshot.sequence is not None:
            if self._prev_sequence is not None and snapshot.sequence != self._prev_sequence + 1:
                gap_detected = True
                notes.append(
                    f"Sequence gap: expected {self._prev_sequence + 1}, got {snapshot.sequence}"
                )
            self._prev_sequence = snapshot.sequence

        # ── Latency estimate ─────────────────────────────────────────────────
        latency_ms = (now_ns - snapshot.timestamp_ns) / 1e6
        self._latency_samples.append(latency_ms)
        avg_latency = statistics.mean(self._latency_samples)
        if avg_latency > self.MAX_LATENCY_MS:
            notes.append(f"High feed latency: avg {avg_latency:.0f}ms")

        # ── Bad tick detection ────────────────────────────────────────────────
        for trade in trades:
            self._price_history.append(trade.price)
            if len(self._price_history) >= 30:
                mu = statistics.mean(self._price_history)
                sigma = statistics.pstdev(self._price_history)
                if sigma > 0 and abs(trade.price - mu) > self.PRICE_OUTLIER_SIGMA * sigma:
                    bad_ticks += 1
                    notes.append(
                        f"Bad tick: price {trade.price} is {abs(trade.price - mu)/sigma:.1f}σ from mean"
                    )

        # ── Zero-size quote check ─────────────────────────────────────────────
        missing_ticks = 0
        if snapshot.best_bid and snapshot.best_bid.size == 0:
            missing_ticks += 1
            notes.append("Zero-size best bid")
        if snapshot.best_ask and snapshot.best_ask.size == 0:
            missing_ticks += 1
            notes.append("Zero-size best ask")

        # ── Quality score ─────────────────────────────────────────────────────
        quality = 1.0
        if stale:
            quality -= 0.30
        if gap_detected:
            quality -= 0.20
        if bad_ticks > 0:
            quality -= min(0.20, bad_ticks * 0.05)
        if avg_latency > self.MAX_LATENCY_MS:
            quality -= 0.15
        if missing_ticks > 0:
            quality -= 0.10
        quality = max(0.0, round(quality, 3))

        return FeedHealthReport(
            feed=snapshot.feed,
            symbol=snapshot.symbol,
            quality_score=quality,
            latency_ms=round(avg_latency, 2),
            missing_ticks=missing_ticks,
            stale_quote=stale,
            bad_ticks=bad_ticks,
            gap_detected=gap_detected,
            timestamp_ns=now_ns,
            notes=notes,
        )
