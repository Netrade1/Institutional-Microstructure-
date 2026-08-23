"""
tests/test_orchestrator.py – Integration tests for the full pipeline.
"""
import asyncio
import pytest
from src.data_intake.sample_feed import SampleFeedAdapter
from src.orchestrator import Orchestrator


class TestOrchestrator:
    def setup_method(self):
        self.orch = Orchestrator("AAPL")
        self.feed = SampleFeedAdapter("AAPL", base_price=185.0, seed=42)

    def teardown_method(self):
        self.orch.close()

    def _run_ticks(self, n=10):
        snap = self.feed.get_snapshot()
        for _ in range(n):
            trades = self.feed._generate_trades()
            snap = self.feed.get_snapshot()
            result = self.orch.process(snap, trades)
        return result

    def test_pipeline_runs(self):
        result = self._run_ticks(5)
        assert result is not None
        assert result.symbol == "AAPL"

    def test_disposition_is_valid(self):
        result = self._run_ticks(10)
        valid = {
            "research_approved", "watchlist", "paper_trade_approved",
            "human_review", "rejected", "risk_veto", "data_insufficient", "blocked",
        }
        assert result.disposition in valid

    def test_compliance_always_present(self):
        result = self._run_ticks(5)
        assert result.compliance_status in {"approved", "flagged", "blocked"}

    def test_limitations_always_in_result(self):
        result = self._run_ticks(5)
        assert result.limitations != ""
        assert "level 2 data" in result.limitations.lower()

    def test_chat_responds(self):
        self._run_ticks(5)
        response = self.orch.chat("help")
        assert response.text != ""

    def test_chat_analyze(self):
        self._run_ticks(10)
        response = self.orch.chat("analyze AAPL")
        assert "AAPL" in response.text or "microstructure" in response.text.lower()

    def test_chat_compliance_gate(self):
        """Chatbot must not deliver responses naming institutions."""
        self._run_ticks(5)
        # The compliance gate should block any attempt to inject institution names
        response = self.orch.chat("is BlackRock buying AAPL?")
        # The response should either be blocked or not contain the assertion
        assert "blackrock is buying" not in response.text.lower()

    def test_no_live_trading_default(self):
        """Execution mode must be paper by default."""
        from src.config import LIVE_MODE_ENABLED
        assert LIVE_MODE_ENABLED is False


class TestSampleFeed:
    def test_stream_async(self):
        async def _run():
            feed = SampleFeedAdapter("TEST", base_price=100.0, seed=1)
            count = 0
            async for snap, trades in feed.stream(max_ticks=5):
                assert snap.symbol == "TEST"
                assert snap.best_bid is not None
                assert snap.best_ask is not None
                count += 1
            return count
        count = asyncio.run(_run())
        assert count == 5

    def test_snapshot_has_depth(self):
        feed = SampleFeedAdapter("TEST", base_price=100.0)
        snap = feed.get_snapshot()
        assert len(snap.bids) > 0
        assert len(snap.asks) > 0
        assert snap.best_bid.price < snap.best_ask.price  # bid < ask (no crossed book)
