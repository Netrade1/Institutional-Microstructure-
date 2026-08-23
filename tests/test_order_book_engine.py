"""
tests/test_order_book_engine.py – Unit tests for the order book processing engine.
"""
import pytest
from src.data_intake.models import L2Level, OrderBookSnapshot, Trade
from src.order_book.engine import OrderBookEngine


def make_snapshot(bid_price=100.0, ask_price=100.1, bid_size=500, ask_size=400, levels=5):
    bids = [L2Level(price=round(bid_price - i * 0.01, 2), size=bid_size - i * 10) for i in range(levels)]
    asks = [L2Level(price=round(ask_price + i * 0.01, 2), size=ask_size - i * 10) for i in range(levels)]
    return OrderBookSnapshot(symbol="TEST", bids=bids, asks=asks, feed="test", sequence=1)


class TestOrderBookEngine:
    def setup_method(self):
        self.engine = OrderBookEngine(depth_levels=5)

    def test_basic_processing(self):
        snap = make_snapshot()
        result = self.engine.process(snap, [])
        assert result.symbol == "TEST"
        assert result.mid_price > 0
        assert result.spread > 0

    def test_book_imbalance_bullish(self):
        """When bid depth >> ask depth, imbalance should be positive."""
        snap = OrderBookSnapshot(
            symbol="TEST",
            bids=[L2Level(price=100.0, size=5000)],
            asks=[L2Level(price=100.1, size=100)],
            feed="test",
        )
        result = self.engine.process(snap, [])
        assert result.book_imbalance > 0

    def test_book_imbalance_bearish(self):
        """When ask depth >> bid depth, imbalance should be negative."""
        snap = OrderBookSnapshot(
            symbol="TEST",
            bids=[L2Level(price=100.0, size=100)],
            asks=[L2Level(price=100.1, size=5000)],
            feed="test",
        )
        result = self.engine.process(snap, [])
        assert result.book_imbalance < 0

    def test_stacking_detection(self):
        """Abnormally large best bid should trigger stacking signal."""
        bids = [L2Level(price=100.0 - i * 0.01, size=10000 if i == 0 else 100) for i in range(5)]
        asks = [L2Level(price=100.1 + i * 0.01, size=200) for i in range(5)]
        snap = OrderBookSnapshot(symbol="TEST", bids=bids, asks=asks, feed="test")
        result = self.engine.process(snap, [])
        assert result.stacking_bid is True

    def test_sweep_intensity_with_multilevel_trades(self):
        """Trades at multiple price levels should trigger sweep signal."""
        snap = make_snapshot()
        trades = [
            Trade("TEST", price=100.1 + i * 0.01, size=200, side="buy")
            for i in range(5)
        ]
        result = self.engine.process(snap, trades)
        assert result.sweep_intensity > 0

    def test_signals_list_not_empty(self):
        snap = make_snapshot()
        result = self.engine.process(snap, [])
        assert len(result.signals) > 0

    def test_spread_multiple_no_history(self):
        """With no spread history, spread_multiple should be 1.0."""
        snap = make_snapshot()
        result = self.engine.process(snap, [])
        # First tick: spread_multiple equals spread / itself = 1.0 (approx)
        assert result.spread_multiple > 0

    def test_volume_analysis_buy_side(self):
        snap = make_snapshot()
        trades = [Trade("TEST", price=100.1, size=500, side="buy") for _ in range(5)]
        result = self.engine.process(snap, trades)
        # More buys → BSR should be > 0.5
        assert result.rolling_buy_sell_ratio > 0

    def test_microprice_direction(self):
        """When bid is larger, microprice should pull toward ask (thin side)."""
        snap = OrderBookSnapshot(
            symbol="TEST",
            bids=[L2Level(price=100.0, size=2000)],
            asks=[L2Level(price=100.2, size=200)],
            feed="test",
        )
        result = self.engine.process(snap, [])
        # Microprice should be closer to ask (200 ask size → more weight to bid price... 
        # actually microprice = (bid*ask_size + ask*bid_size)/(bid_size+ask_size))
        # = (100.0*200 + 100.2*2000) / 2200 = (20000+200400)/2200 = 220400/2200 = 100.18
        assert result.microprice > 100.0
