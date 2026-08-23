"""
data_intake/models.py – Canonical data models for all incoming market data.

Every feed adapter normalises raw exchange/broker data into these structures
before it reaches the order book engine. This decouples feed-specific formats
from all downstream processing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Quote:
    """Level 1 NBBO quote snapshot."""
    symbol: str
    bid_price: float
    bid_size: float
    ask_price: float
    ask_size: float
    timestamp_ns: int = field(default_factory=lambda: time.time_ns())
    feed: str = "unknown"

    @property
    def spread(self) -> float:
        return round(self.ask_price - self.bid_price, 6)

    @property
    def mid_price(self) -> float:
        return round((self.bid_price + self.ask_price) / 2, 6)

    @property
    def microprice(self) -> float:
        """Weighted mid-price – pulls toward the thinner side of the book."""
        total = self.bid_size + self.ask_size
        if total == 0:
            return self.mid_price
        return round(
            (self.bid_price * self.ask_size + self.ask_price * self.bid_size) / total, 6
        )


@dataclass
class L2Level:
    """A single price level on one side of the order book."""
    price: float
    size: float


@dataclass
class OrderBookSnapshot:
    """Full Level 2 order book snapshot at a point in time."""
    symbol: str
    bids: list[L2Level]          # sorted descending by price
    asks: list[L2Level]          # sorted ascending by price
    timestamp_ns: int = field(default_factory=lambda: time.time_ns())
    feed: str = "unknown"
    sequence: Optional[int] = None

    @property
    def best_bid(self) -> Optional[L2Level]:
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> Optional[L2Level]:
        return self.asks[0] if self.asks else None

    @property
    def spread(self) -> float:
        if self.best_bid and self.best_ask:
            return round(self.best_ask.price - self.best_bid.price, 6)
        return float("nan")

    @property
    def mid_price(self) -> float:
        if self.best_bid and self.best_ask:
            return round((self.best_bid.price + self.best_ask.price) / 2, 6)
        return float("nan")

    def total_bid_depth(self, levels: int = 10) -> float:
        return sum(lvl.size for lvl in self.bids[:levels])

    def total_ask_depth(self, levels: int = 10) -> float:
        return sum(lvl.size for lvl in self.asks[:levels])


@dataclass
class Trade:
    """A single time-and-sales print."""
    symbol: str
    price: float
    size: float
    side: str                    # "buy" | "sell" | "unknown"
    timestamp_ns: int = field(default_factory=lambda: time.time_ns())
    feed: str = "unknown"
    conditions: list[str] = field(default_factory=list)

    @property
    def is_buy_aggressor(self) -> bool:
        return self.side == "buy"

    @property
    def notional(self) -> float:
        return round(self.price * self.size, 2)


@dataclass
class FeedHealthReport:
    """Data-quality report produced by the Data Integrity Agent."""
    feed: str
    symbol: str
    quality_score: float         # 0.0 – 1.0
    latency_ms: float
    missing_ticks: int
    stale_quote: bool
    bad_ticks: int
    gap_detected: bool
    timestamp_ns: int = field(default_factory=lambda: time.time_ns())
    notes: list[str] = field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        return (
            self.quality_score >= 0.80
            and not self.stale_quote
            and not self.gap_detected
            and self.latency_ms < 2000
        )
