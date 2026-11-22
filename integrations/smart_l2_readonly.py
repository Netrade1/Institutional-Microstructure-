"""Read-only Level 2 event adapter. No broker execution capability.

This module is an integration boundary, not a market-data provider.
Provider normalization must establish event-time and receive-time provenance.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json

class FeedRejected(ValueError):
    pass

def number(value):
    try:
        v = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise FeedRejected("invalid decimal") from exc
    if not v.is_finite():
        raise FeedRejected("nonfinite decimal")
    return v

@dataclass(frozen=True)
class BookMetrics:
    bid: Decimal
    ask: Decimal
    imbalance: Decimal
    microprice: Decimal

class ReadOnlyBook:
    """A minimal contiguous-sequence MBP adapter, defaulting to NO_DATA."""
    def __init__(self, symbol: str, max_age_ns: int = 1_000_000_000):
        self.symbol = symbol
        self.max_age_ns = max_age_ns
        self.reset()

    def reset(self):
        self.bids, self.asks = {}, {}
        self.sequence = None
        self.quote_time_ns = None
        self.healthy = False
        self.trades = set()
        self.cvd = Decimal(0)
        self.turnover = Decimal(0)
        self.volume = Decimal(0)

    @staticmethod
    def _levels(rows):
        result = {}
        for p, q in rows:
            p, q = number(p), number(q)
            if p <= 0 or q < 0 or p in result:
                raise FeedRejected("invalid or duplicate level")
            result[p] = q
        return result

    @staticmethod
    def _validate_book(bids, asks):
        if not bids or not asks or max(bids) >= min(asks):
            raise FeedRejected("empty or crossed book")

    def ingest(self, event: dict):
        try:
            if event.get("symbol") != self.symbol:
                raise FeedRejected("symbol mismatch")
            ts = event["ts_ns"]
            rx = event["received_ns"]
            if type(ts) is not int or type(rx) is not int or ts < 0 or rx < ts:
                raise FeedRejected("invalid event/receive timestamps")
            kind = event["type"]
            if kind == "snapshot":
                seq = event["seq"]
                if type(seq) is not int or seq < 0:
                    raise FeedRejected("invalid sequence")
                bids = {p:q for p,q in self._levels(event["bids"]).items() if q}
                asks = {p:q for p,q in self._levels(event["asks"]).items() if q}
                self._validate_book(bids, asks)
                self.bids, self.asks = bids, asks
                self.sequence, self.quote_time_ns = seq, ts
                self.healthy = True
            elif kind == "delta":
                if not self.healthy or event["seq"] != self.sequence + 1:
                    raise FeedRejected("missing snapshot or sequence gap")
                if ts < self.quote_time_ns:
                    raise FeedRejected("quote timestamp regression")
                bids, asks = self.bids.copy(), self.asks.copy()
                for dest, key in ((bids,"bids"),(asks,"asks")):
                    for p,q in self._levels(event.get(key, [])).items():
                        if q: dest[p] = q
                        else: dest.pop(p, None)
                self._validate_book(bids, asks)
                self.bids, self.asks = bids, asks
                self.sequence, self.quote_time_ns = event["seq"], ts
            elif kind == "trade":
                if not self.healthy or ts < self.quote_time_ns or ts - self.quote_time_ns > self.max_age_ns:
                    raise FeedRejected("unsynchronized quote")
                trade_id = str(event["trade_id"])
                if trade_id in self.trades:
                    raise FeedRejected("duplicate trade")
                price, qty = number(event["price"]), number(event["size"])
                if price <= 0 or qty <= 0:
                    raise FeedRejected("invalid trade")
                bid, ask = max(self.bids), min(self.asks)
                if bid < price < ask:
                    raise FeedRejected("unclassified trade")
                sign = 1 if price >= ask else -1
                self.cvd += sign * qty
                self.turnover += price * qty
                self.volume += qty
                self.trades.add(trade_id)
            else:
                raise FeedRejected("unknown event")
            return self.metrics(rx)
        except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
            self.healthy = False
            raise FeedRejected(str(exc)) from exc

    def metrics(self, now_ns: int):
        if not self.healthy or self.quote_time_ns is None or now_ns < self.quote_time_ns or now_ns - self.quote_time_ns > self.max_age_ns:
            return {"status":"NO_DATA", "paper_only":True}
        bid, ask = max(self.bids), min(self.asks)
        bs, az = self.bids[bid], self.asks[ask]
        result = BookMetrics(bid, ask, (bs-az)/(bs+az), (ask*bs+bid*az)/(bs+az))
        return {"status":"RESEARCH_ONLY", "paper_only":True,
                "bid":str(result.bid), "ask":str(result.ask),
                "obi":str(result.imbalance), "microprice":str(result.microprice),
                "cvd":str(self.cvd),
                "vwap":str(self.turnover/self.volume) if self.volume else None}

def canonical_event_hash(event):
    return sha256(json.dumps(event, sort_keys=True, separators=(",",":"), allow_nan=False).encode()).hexdigest()
