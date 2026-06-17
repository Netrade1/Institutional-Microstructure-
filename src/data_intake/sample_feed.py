"""
data_intake/sample_feed.py – Synthetic / replay feed for development and testing.

Generates realistic-looking Level 2 order book snapshots and trade prints
without requiring live API credentials. All downstream code is feed-agnostic
and works identically with real feeds.

Usage:
    feed = SampleFeedAdapter(symbol="NVDA", base_price=500.0)
    async for snapshot, trades in feed.stream():
        process(snapshot, trades)
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import AsyncIterator

from src.data_intake.models import L2Level, OrderBookSnapshot, Quote, Trade


class SampleFeedAdapter:
    """
    Deterministic-ish synthetic market data generator.

    Simulates a random-walk mid-price with realistic spread and depth dynamics,
    including occasional absorption, sweep, stacking, and pulling events.
    """

    def __init__(
        self,
        symbol: str = "AAPL",
        base_price: float = 185.0,
        tick_size: float = 0.01,
        depth_levels: int = 10,
        interval_ms: int = 250,
        seed: int | None = None,
    ) -> None:
        self.symbol = symbol
        self.tick_size = tick_size
        self.depth_levels = depth_levels
        self.interval_ms = interval_ms
        self._price = base_price
        self._rng = random.Random(seed)
        self._sequence = 0

    # ── Public interface ──────────────────────────────────────────────────────

    async def stream(
        self, max_ticks: int | None = None
    ) -> AsyncIterator[tuple[OrderBookSnapshot, list[Trade]]]:
        """Yield (OrderBookSnapshot, list[Trade]) at configured interval."""
        tick = 0
        while max_ticks is None or tick < max_ticks:
            self._evolve_price()
            snapshot = self._build_snapshot()
            trades = self._generate_trades()
            yield snapshot, trades
            tick += 1
            await asyncio.sleep(self.interval_ms / 1000.0)

    def get_snapshot(self) -> OrderBookSnapshot:
        """Synchronous single snapshot, useful for testing."""
        self._evolve_price()
        return self._build_snapshot()

    def get_quote(self) -> Quote:
        snap = self._build_snapshot()
        bb = snap.best_bid
        ba = snap.best_ask
        return Quote(
            symbol=self.symbol,
            bid_price=bb.price if bb else self._price - self.tick_size,
            bid_size=bb.size if bb else 100,
            ask_price=ba.price if ba else self._price + self.tick_size,
            ask_size=ba.size if ba else 100,
            feed="sample",
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _evolve_price(self) -> None:
        """Random walk with occasional regime shifts."""
        drift = self._rng.gauss(0, 0.03)
        # Occasional momentum burst or mean-reversion
        if self._rng.random() < 0.05:
            drift += self._rng.choice([-0.15, 0.15])
        self._price = round(
            max(self._price + drift, self.tick_size), 2
        )

    def _build_snapshot(self) -> OrderBookSnapshot:
        self._sequence += 1
        spread_ticks = self._rng.randint(1, 4)
        half_spread = (spread_ticks * self.tick_size) / 2
        best_bid = round(self._price - half_spread, 2)
        best_ask = round(self._price + half_spread, 2)

        bids: list[L2Level] = []
        asks: list[L2Level] = []

        for i in range(self.depth_levels):
            bid_price = round(best_bid - i * self.tick_size * self._rng.uniform(1, 3), 2)
            ask_price = round(best_ask + i * self.tick_size * self._rng.uniform(1, 3), 2)

            # Occasional stacking (large size at a level)
            bid_size = self._rng.randint(100, 800)
            ask_size = self._rng.randint(100, 800)
            if i == 0 and self._rng.random() < 0.1:
                bid_size = self._rng.randint(2000, 8000)  # stacking event
            if i == 1 and self._rng.random() < 0.08:
                ask_size = self._rng.randint(2000, 8000)  # ask wall

            bids.append(L2Level(price=bid_price, size=bid_size))
            asks.append(L2Level(price=ask_price, size=ask_size))

        return OrderBookSnapshot(
            symbol=self.symbol,
            bids=bids,
            asks=asks,
            timestamp_ns=time.time_ns(),
            feed="sample",
            sequence=self._sequence,
        )

    def _generate_trades(self) -> list[Trade]:
        """Produce 0–5 trade prints per tick."""
        trades: list[Trade] = []
        n = self._rng.choices([0, 1, 2, 3, 4, 5], weights=[30, 35, 20, 8, 5, 2])[0]

        for _ in range(n):
            side = self._rng.choice(["buy", "sell"])
            price_offset = self._rng.uniform(0, 0.03)
            price = round(
                self._price + (price_offset if side == "buy" else -price_offset), 2
            )
            size = self._rng.randint(10, 500)
            # Occasional large institutional-size print
            if self._rng.random() < 0.03:
                size = self._rng.randint(1000, 10000)

            trades.append(
                Trade(
                    symbol=self.symbol,
                    price=price,
                    size=size,
                    side=side,
                    timestamp_ns=time.time_ns(),
                    feed="sample",
                )
            )
        return trades
