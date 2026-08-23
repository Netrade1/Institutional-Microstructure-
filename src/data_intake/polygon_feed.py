"""
data_intake/polygon_feed.py – Polygon.io Level 2 WebSocket feed adapter.

Connects to Polygon's WebSocket stream for real-time Level 2 (NBBO + quotes)
and time-and-sales data. Normalises all messages into canonical data models.

Requires:
    POLYGON_API_KEY set in environment / .env

Documentation: https://polygon.io/docs/stocks/ws_stocks_q
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncIterator

import websockets

from src.config import POLYGON_API_KEY
from src.data_intake.models import L2Level, OrderBookSnapshot, Quote, Trade

logger = logging.getLogger(__name__)

POLYGON_WS_URL = "wss://delayed.polygon.io/stocks"   # use wss://socket.polygon.io for live


class PolygonFeedAdapter:
    """
    Polygon.io WebSocket feed adapter.

    Subscribes to:
        Q.*   – NBBO quote updates (best bid/ask)
        T.*   – Trade prints (time and sales)

    Note: Full Level 2 depth-of-book requires Polygon's 'Starter' plan or above.
    This adapter uses NBBO quotes as a Level 1 / pseudo-Level 2 baseline and can
    be extended with Polygon's full order book feed when the subscription allows.
    """

    def __init__(self, symbol: str, api_key: str = POLYGON_API_KEY) -> None:
        if not api_key:
            raise ValueError(
                "POLYGON_API_KEY is not set. Add it to your .env file. "
                "See .env.example for guidance."
            )
        self.symbol = symbol.upper()
        self.api_key = api_key
        self._latest_snapshot: OrderBookSnapshot | None = None
        self._pending_trades: list[Trade] = []

    async def stream(self) -> AsyncIterator[tuple[OrderBookSnapshot, list[Trade]]]:
        """Yield (snapshot, trades) pairs as they arrive from Polygon."""
        async with websockets.connect(POLYGON_WS_URL) as ws:
            await self._authenticate(ws)
            await self._subscribe(ws)
            logger.info("Polygon feed active for %s", self.symbol)

            async for raw in ws:
                messages = json.loads(raw)
                for msg in messages:
                    ev = msg.get("ev")
                    if ev == "Q":
                        self._handle_quote(msg)
                    elif ev == "T":
                        self._handle_trade(msg)

                if self._latest_snapshot is not None:
                    trades, self._pending_trades = self._pending_trades, []
                    yield self._latest_snapshot, trades

    # ── Private ───────────────────────────────────────────────────────────────

    async def _authenticate(self, ws) -> None:
        await ws.send(json.dumps({"action": "auth", "params": self.api_key}))
        resp = json.loads(await ws.recv())
        if any(m.get("status") == "auth_success" for m in resp):
            logger.info("Polygon authentication successful")
        else:
            raise ConnectionError(f"Polygon auth failed: {resp}")

    async def _subscribe(self, ws) -> None:
        channels = f"Q.{self.symbol},T.{self.symbol}"
        await ws.send(json.dumps({"action": "subscribe", "params": channels}))

    def _handle_quote(self, msg: dict) -> None:
        bid_p = float(msg.get("bp", 0))
        ask_p = float(msg.get("ap", 0))
        bid_s = float(msg.get("bs", 0))
        ask_s = float(msg.get("as", 0))
        ts = msg.get("t", time.time_ns() // 1_000_000) * 1_000_000  # ms → ns

        # Polygon NBBO gives us one level; build a minimal pseudo-L2 structure.
        # Full L2 depth requires the Nasdaq TotalView or Polygon depth feed.
        self._latest_snapshot = OrderBookSnapshot(
            symbol=self.symbol,
            bids=[L2Level(price=bid_p, size=bid_s)],
            asks=[L2Level(price=ask_p, size=ask_s)],
            timestamp_ns=ts,
            feed="polygon",
        )

    def _handle_trade(self, msg: dict) -> None:
        price = float(msg.get("p", 0))
        size = float(msg.get("s", 0))
        conditions = msg.get("c", [])
        ts = msg.get("t", time.time_ns() // 1_000_000) * 1_000_000

        # Polygon does not always classify aggressor side; infer from quote.
        side = "unknown"
        if self._latest_snapshot:
            bb = self._latest_snapshot.best_bid
            ba = self._latest_snapshot.best_ask
            if ba and abs(price - ba.price) < 0.005:
                side = "buy"
            elif bb and abs(price - bb.price) < 0.005:
                side = "sell"

        self._pending_trades.append(
            Trade(
                symbol=self.symbol,
                price=price,
                size=size,
                side=side,
                timestamp_ns=ts,
                feed="polygon",
                conditions=[str(c) for c in conditions],
            )
        )
