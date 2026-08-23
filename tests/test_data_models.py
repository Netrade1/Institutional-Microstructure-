"""
tests/test_data_models.py – Unit tests for canonical data models.
"""
import time
import pytest
from src.data_intake.models import Quote, L2Level, OrderBookSnapshot, Trade, FeedHealthReport


def make_snapshot(bids=None, asks=None):
    bids = bids or [L2Level(price=100.0, size=500), L2Level(price=99.9, size=300)]
    asks = asks or [L2Level(price=100.1, size=400), L2Level(price=100.2, size=200)]
    return OrderBookSnapshot(symbol="TEST", bids=bids, asks=asks, feed="test")


class TestQuote:
    def test_spread(self):
        q = Quote("TEST", bid_price=100.0, bid_size=100, ask_price=100.1, ask_size=200)
        assert abs(q.spread - 0.1) < 1e-9

    def test_mid_price(self):
        q = Quote("TEST", bid_price=100.0, bid_size=100, ask_price=100.2, ask_size=100)
        assert abs(q.mid_price - 100.1) < 1e-9

    def test_microprice_pulls_toward_thin_side(self):
        # Ask is thinner → microprice should be above mid
        q = Quote("TEST", bid_price=100.0, bid_size=1000, ask_price=100.2, ask_size=100)
        assert q.microprice > q.mid_price


class TestOrderBookSnapshot:
    def test_spread(self):
        snap = make_snapshot()
        assert abs(snap.spread - 0.1) < 1e-9

    def test_mid_price(self):
        snap = make_snapshot()
        assert abs(snap.mid_price - 100.05) < 1e-9

    def test_total_bid_depth(self):
        snap = make_snapshot()
        assert snap.total_bid_depth() == 800

    def test_best_bid_ask(self):
        snap = make_snapshot()
        assert snap.best_bid.price == 100.0
        assert snap.best_ask.price == 100.1

    def test_empty_book(self):
        snap = OrderBookSnapshot(symbol="TEST", bids=[], asks=[], feed="test")
        assert snap.best_bid is None
        assert snap.best_ask is None


class TestTrade:
    def test_notional(self):
        t = Trade("TEST", price=100.0, size=500, side="buy")
        assert t.notional == 50000.0

    def test_is_buy_aggressor(self):
        t = Trade("TEST", price=100.0, size=100, side="buy")
        assert t.is_buy_aggressor is True
        t2 = Trade("TEST", price=100.0, size=100, side="sell")
        assert t2.is_buy_aggressor is False


class TestFeedHealthReport:
    def test_healthy(self):
        h = FeedHealthReport(
            feed="test", symbol="TEST", quality_score=0.95, latency_ms=50,
            missing_ticks=0, stale_quote=False, bad_ticks=0, gap_detected=False,
        )
        assert h.is_healthy is True

    def test_stale_is_unhealthy(self):
        h = FeedHealthReport(
            feed="test", symbol="TEST", quality_score=0.95, latency_ms=50,
            missing_ticks=0, stale_quote=True, bad_ticks=0, gap_detected=False,
        )
        assert h.is_healthy is False
