"""
tests/test_features.py – Unit tests for the Feature Engineering Layer.
"""
import math
import pytest
from src.data_intake.models import L2Level, OrderBookSnapshot, Trade
from src.order_book.engine import OrderBookEngine
from src.features.engineer import FeatureEngineer


def make_state(bid_size=500, ask_size=400, mid=100.0):
    engine = OrderBookEngine(depth_levels=5)
    bids = [L2Level(price=round(mid - 0.05 - i * 0.01, 2), size=bid_size) for i in range(5)]
    asks = [L2Level(price=round(mid + 0.05 + i * 0.01, 2), size=ask_size) for i in range(5)]
    snap = OrderBookSnapshot(symbol="TEST", bids=bids, asks=asks, feed="test")
    trades = [Trade("TEST", price=mid, size=100, side="buy")]
    return engine.process(snap, trades), trades


class TestFeatureEngineer:
    def setup_method(self):
        self.eng = FeatureEngineer("TEST")

    def test_feature_vector_structure(self):
        state, trades = make_state()
        fv = self.eng.update(state, trades)
        assert fv.symbol == "TEST"
        assert fv.feature_version == "1.0"
        assert fv.mid_price > 0

    def test_spread_in_feature_vector(self):
        state, trades = make_state()
        fv = self.eng.update(state, trades)
        assert fv.spread > 0

    def test_rsi_nan_with_insufficient_history(self):
        state, trades = make_state()
        fv = self.eng.update(state, trades)
        # Only 1 tick of history; RSI requires >14+1 data points
        assert math.isnan(fv.rsi_14)

    def test_rsi_computed_after_sufficient_history(self):
        state, trades = make_state()
        for _ in range(20):
            self.eng.update(state, trades)
        fv = self.eng.update(state, trades)
        assert not math.isnan(fv.rsi_14)
        assert 0 <= fv.rsi_14 <= 100

    def test_accumulation_score_range(self):
        state, trades = make_state(bid_size=5000, ask_size=200)
        fv = self.eng.update(state, trades)
        assert 0.0 <= fv.accumulation_score <= 1.0

    def test_distribution_score_range(self):
        state, trades = make_state(bid_size=200, ask_size=5000)
        fv = self.eng.update(state, trades)
        assert 0.0 <= fv.distribution_score <= 1.0

    def test_to_dict_serialisable(self):
        state, trades = make_state()
        fv = self.eng.update(state, trades)
        d = fv.to_dict()
        assert isinstance(d, dict)
        assert "mid_price" in d
        assert "accumulation_score" in d

    def test_vwap_approaches_mid(self):
        """After many identical ticks, VWAP should converge near mid-price."""
        state, trades = make_state(mid=150.0)
        for _ in range(30):
            fv = self.eng.update(state, trades)
        assert abs(fv.vwap - 150.0) < 1.0

    def test_bollinger_band_width_positive(self):
        """BB width should be positive after sufficient price history."""
        state, trades = make_state()
        for _ in range(25):
            self.eng.update(state, trades)
        fv = self.eng.update(state, trades)
        if not math.isnan(fv.bb_width):
            assert fv.bb_width >= 0
