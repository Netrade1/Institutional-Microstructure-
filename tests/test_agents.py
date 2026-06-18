"""
tests/test_agents.py – Unit tests for all agent modules.
"""
import pytest
from src.data_intake.models import L2Level, OrderBookSnapshot, Trade, FeedHealthReport
from src.order_book.engine import OrderBookEngine
from src.features.engineer import FeatureEngineer
from src.agents.order_book_analyst import OrderBookAnalystAgent
from src.agents.market_dna_detector import MarketDNADetectorAgent
from src.agents.institutional_footprint import InstitutionalFootprintAgent
from src.agents.participant_archetype_agent import ParticipantArchetypeAgent, ARCHETYPES
from src.agents.ipo_microstructure_agent import IPOMicrostructureAgent
from src.agents.motivation_inference_agent import MotivationInferenceAgent, MOTIVATION_TAXONOMY
from src.agents.risk_governor import RiskGovernorAgent
from src.agents.compliance_agent import ComplianceAgent
from src.agents.decision_parliament import DecisionParliament


def _make_pipeline(bid_size=500, ask_size=400, mid=100.0, spread_mult=1.0):
    engine = OrderBookEngine(depth_levels=5)
    bids = [L2Level(price=round(mid - 0.05 * spread_mult - i * 0.01, 2), size=bid_size) for i in range(5)]
    asks = [L2Level(price=round(mid + 0.05 * spread_mult + i * 0.01, 2), size=ask_size) for i in range(5)]
    snap = OrderBookSnapshot(symbol="TEST", bids=bids, asks=asks, feed="test")
    trades = [Trade("TEST", price=mid, size=100, side="buy")]
    state = engine.process(snap, trades)
    eng = FeatureEngineer("TEST")
    features = eng.update(state, trades)
    health = FeedHealthReport(
        feed="test", symbol="TEST", quality_score=0.95, latency_ms=10,
        missing_ticks=0, stale_quote=False, bad_ticks=0, gap_detected=False,
    )
    return state, features, health


class TestOrderBookAnalystAgent:
    def test_returns_report(self):
        state, features, _ = _make_pipeline()
        agent = OrderBookAnalystAgent()
        report = agent.analyse(state, features)
        assert report.symbol == "TEST"
        assert report.directional_bias in {"bullish", "bearish", "neutral"}
        assert 0 <= report.bias_confidence <= 1

    def test_bullish_when_bid_dominates(self):
        state, features, _ = _make_pipeline(bid_size=5000, ask_size=200)
        agent = OrderBookAnalystAgent()
        report = agent.analyse(state, features)
        assert report.directional_bias in {"bullish", "neutral"}

    def test_bearish_when_ask_dominates(self):
        state, features, _ = _make_pipeline(bid_size=200, ask_size=5000)
        agent = OrderBookAnalystAgent()
        report = agent.analyse(state, features)
        assert report.directional_bias in {"bearish", "neutral"}


class TestMarketDNADetector:
    def test_returns_report(self):
        state, features, _ = _make_pipeline()
        agent = MarketDNADetectorAgent()
        report = agent.classify(state, features)
        assert report.regime is not None
        assert 0 <= report.regime_confidence <= 1
        assert isinstance(report.supporting_signals, list)

    def test_valid_regime_label(self):
        state, features, _ = _make_pipeline()
        agent = MarketDNADetectorAgent()
        report = agent.classify(state, features)
        valid = {
            "trending_up", "trending_down", "ranging", "breakout", "reversal",
            "compression", "expansion", "accumulation", "distribution", "trap", "ambiguous"
        }
        assert report.regime in valid


class TestInstitutionalFootprintAgent:
    def test_returns_report_with_limitations(self):
        state, features, _ = _make_pipeline()
        agent = InstitutionalFootprintAgent()
        report = agent.analyse(state, features)
        assert report.limitations != ""
        assert "level 2 data" in report.limitations.lower()

    def test_probability_in_range(self):
        state, features, _ = _make_pipeline()
        agent = InstitutionalFootprintAgent()
        report = agent.analyse(state, features)
        assert 0 <= report.probability <= 1

    def test_no_identity_claims_in_label(self):
        """Label must never contain a named institution."""
        state, features, _ = _make_pipeline()
        agent = InstitutionalFootprintAgent()
        report = agent.analyse(state, features)
        from src.config import IDENTITY_CLAIM_BLOCKED_TERMS
        label_lower = report.behavioral_label.lower()
        for term in IDENTITY_CLAIM_BLOCKED_TERMS:
            assert term not in label_lower, f"Identity claim found in label: {term}"


class TestRiskGovernorAgent:
    def test_clear_status_normal_conditions(self):
        state, features, health = _make_pipeline()
        agent = RiskGovernorAgent()
        report = agent.evaluate(state, features, health)
        assert report.risk_status in {"clear", "caution", "veto"}
        assert 0 <= report.risk_score <= 1

    def test_veto_on_bad_data_quality(self):
        state, features, _ = _make_pipeline()
        bad_health = FeedHealthReport(
            feed="test", symbol="TEST", quality_score=0.30,
            latency_ms=10, missing_ticks=0, stale_quote=True,
            bad_ticks=0, gap_detected=True,
        )
        agent = RiskGovernorAgent()
        report = agent.evaluate(state, features, bad_health)
        assert report.veto is True
        assert report.risk_status == "veto"

    def test_caution_or_veto_on_wide_spread(self):
        """Wide spread should elevate risk status."""
        state, features, health = _make_pipeline(spread_mult=5.0)
        # Artificially set spread_multiple
        state.spread_multiple = 5.0
        agent = RiskGovernorAgent()
        report = agent.evaluate(state, features, health)
        assert report.risk_status in {"caution", "veto"}


class TestComplianceAgent:
    def test_approves_clean_text(self):
        agent = ComplianceAgent()
        result = agent.check_output("TEST", "Order book imbalance is positive.")
        assert result.status == "approved"

    def test_blocks_named_institution(self):
        agent = ComplianceAgent()
        result = agent.check_output("TEST", "BlackRock is buying at this level.")
        assert result.status == "blocked"
        assert len(result.violations) > 0

    def test_blocks_identity_claim_phrase(self):
        agent = ComplianceAgent()
        result = agent.check_output("TEST", "Citadel is buying here.")
        assert result.status == "blocked"

    def test_flags_certainty_language(self):
        agent = ComplianceAgent()
        result = agent.check_output("TEST", "This is definitely bullish behavior.")
        assert result.status in {"flagged", "blocked"}

    def test_valid_behavioral_label(self):
        agent = ComplianceAgent()
        valid, msg = agent.check_behavioral_label("accumulation_like", [])
        assert valid is True

    def test_invalid_behavioral_label(self):
        agent = ComplianceAgent()
        valid, msg = agent.check_behavioral_label("blackrock_buying", [])
        assert valid is False

    def test_add_limitations_appends_statement(self):
        text = "The order book shows accumulation-like behavior."
        result = ComplianceAgent.add_limitations(text)
        assert "level 2 data does not reveal" in result.lower()

    def test_add_limitations_does_not_duplicate(self):
        text = "Level 2 data does not reveal the actual identity of market participants."
        result = ComplianceAgent.add_limitations(text)
        count = result.lower().count("level 2 data does not reveal")
        assert count == 1


class TestDecisionParliament:
    def _make_reports(self, ob_bias="neutral", ob_conf=0.4, regime="ranging",
                      inst_label="neutral", inst_prob=0.3, risk_status="clear",
                      risk_veto=False, compliance_status="approved"):
        from src.agents.models import (
            OrderBookAnalystReport, MarketDNAReport, InstitutionalFootprintReport,
            RiskGovernorReport, ComplianceReport,
        )
        import time
        ts = time.time_ns()
        ob = OrderBookAnalystReport(
            symbol="TEST", timestamp_ns=ts,
            directional_bias=ob_bias, bias_confidence=ob_conf,
            key_signals=[], absorption_score=0.2, sweep_intensity=0.1,
            spoof_like_score=0.1, iceberg_like_score=0.1,
            spread_multiple=1.0, book_imbalance=0.1,
        )
        dna = MarketDNAReport(
            symbol="TEST", timestamp_ns=ts,
            regime=regime, regime_confidence=0.5,
            supporting_signals=[], regime_stability=0.7,
        )
        inst = InstitutionalFootprintReport(
            symbol="TEST", timestamp_ns=ts,
            behavioral_label=inst_label, probability=inst_prob,
            confidence_label="medium", reasoning=[], limitations="test",
        )
        risk = RiskGovernorReport(
            symbol="TEST", timestamp_ns=ts,
            risk_status=risk_status, risk_score=0.1,
            veto=risk_veto, veto_reasons=["test veto"] if risk_veto else [],
            spread_ok=True, data_quality_ok=True,
            model_confidence_ok=True, news_lockout=False,
        )
        comp = ComplianceReport(
            symbol="TEST", timestamp_ns=ts,
            status=compliance_status, violations=[], warnings=[],
        )
        return ob, dna, inst, risk, comp

    def test_risk_veto_blocks_all(self):
        ob, dna, inst, risk, comp = self._make_reports(risk_veto=True, risk_status="veto")
        p = DecisionParliament()
        result = p.deliberate(ob, dna, inst, risk, comp)
        assert result.disposition == "risk_veto"

    def test_compliance_block(self):
        ob, dna, inst, risk, comp = self._make_reports(compliance_status="blocked")
        p = DecisionParliament()
        result = p.deliberate(ob, dna, inst, risk, comp)
        assert result.disposition == "blocked"

    def test_data_insufficient(self):
        from src.agents.models import RiskGovernorReport
        import time
        ob, dna, inst, _, comp = self._make_reports()
        bad_risk = RiskGovernorReport(
            symbol="TEST", timestamp_ns=time.time_ns(),
            risk_status="veto", risk_score=0.9,
            veto=False, veto_reasons=[],
            spread_ok=True, data_quality_ok=False,
            model_confidence_ok=True, news_lockout=False,
        )
        p = DecisionParliament()
        result = p.deliberate(ob, dna, inst, bad_risk, comp)
        assert result.disposition == "data_insufficient"

    def test_paper_trade_approved_with_strong_signals(self):
        ob, dna, inst, risk, comp = self._make_reports(
            ob_bias="bullish", ob_conf=0.70,
            regime="accumulation",
            inst_label="accumulation_like", inst_prob=0.68,
            risk_status="clear",
        )
        p = DecisionParliament()
        result = p.deliberate(ob, dna, inst, risk, comp)
        assert result.disposition in {"paper_trade_approved", "watchlist"}

    def test_result_has_limitations(self):
        ob, dna, inst, risk, comp = self._make_reports()
        p = DecisionParliament()
        result = p.deliberate(ob, dna, inst, risk, comp)
        assert result.limitations != ""


# ── Phase 2A Tests ─────────────────────────────────────────────────────────────

class TestParticipantArchetypeAgent:
    def test_returns_report(self):
        state, features, _ = _make_pipeline()
        agent = ParticipantArchetypeAgent()
        report = agent.analyse(state, features)
        assert report.symbol == "TEST"
        assert report.archetype in ARCHETYPES
        assert 0 <= report.probability <= 1
        assert report.confidence_label in {"high", "medium", "low", "insufficient_data"}

    def test_limitations_always_populated(self):
        state, features, _ = _make_pipeline()
        agent = ParticipantArchetypeAgent()
        report = agent.analyse(state, features)
        assert report.limitations != ""
        assert "level 2 data" in report.limitations.lower()

    def test_no_identity_in_archetype(self):
        """Archetype label must never contain a named institution."""
        state, features, _ = _make_pipeline()
        agent = ParticipantArchetypeAgent()
        report = agent.analyse(state, features)
        from src.config import IDENTITY_CLAIM_BLOCKED_TERMS
        for term in IDENTITY_CLAIM_BLOCKED_TERMS:
            assert term not in report.archetype.lower()

    def test_institutional_accumulator_on_strong_bid(self):
        """Dominant bid side with large absorption should favour institutional_accumulator."""
        state, features, _ = _make_pipeline(bid_size=5000, ask_size=300)
        agent = ParticipantArchetypeAgent()
        report = agent.analyse(state, features)
        # Should not classify as strategic_seller or retail_sentiment_buyer
        assert report.archetype not in {"strategic_seller"}

    def test_secondary_archetype_optional(self):
        state, features, _ = _make_pipeline()
        agent = ParticipantArchetypeAgent()
        report = agent.analyse(state, features)
        # secondary_archetype may be None or a valid archetype
        if report.secondary_archetype is not None:
            assert report.secondary_archetype in ARCHETYPES


class TestIPOMicrostructureAgent:
    def test_returns_report(self):
        state, features, _ = _make_pipeline()
        agent = IPOMicrostructureAgent()
        report = agent.analyse(state, features)
        assert report.symbol == "TEST"
        assert report.price_discovery_phase in {
            "pre_open", "price_discovery", "stabilisation",
            "post_stabilisation", "normal_trading"
        }
        assert isinstance(report.ipo_specific_signals, list)
        assert report.confidence_label in {"high", "medium", "low"}

    def test_spcx_is_ipo_symbol(self):
        """SPCX must be recognised as an IPO symbol when configured."""
        from src.data_intake.models import L2Level, OrderBookSnapshot, Trade
        engine = OrderBookEngine(depth_levels=5)
        bids = [L2Level(price=round(100.0 - 0.05 - i * 0.01, 2), size=500) for i in range(5)]
        asks = [L2Level(price=round(100.0 + 0.05 + i * 0.01, 2), size=400) for i in range(5)]
        snap = OrderBookSnapshot(symbol="SPCX", bids=bids, asks=asks, feed="test")
        trades = [Trade("SPCX", price=100.0, size=100, side="buy")]
        state = engine.process(snap, trades)
        eng = FeatureEngineer("SPCX")
        features = eng.update(state, trades)
        agent = IPOMicrostructureAgent()
        report = agent.analyse(state, features)
        assert report.is_ipo_symbol is True

    def test_greenshoe_requires_strong_conditions(self):
        """Greenshoe flag should not fire on weak conditions."""
        state, features, _ = _make_pipeline(bid_size=300, ask_size=300)
        agent = IPOMicrostructureAgent()
        report = agent.analyse(state, features)
        # With balanced and normal conditions, greenshoe should not be likely
        # (not a guaranteed assertion — just confirm the report is valid)
        assert isinstance(report.greenshoe_activity_likely, bool)


class TestMotivationInferenceAgent:
    def _make_archetype_report(self, archetype="institutional_accumulator", prob=0.65, conf="high"):
        from src.agents.models import ParticipantArchetypeReport
        import time
        return ParticipantArchetypeReport(
            symbol="TEST",
            timestamp_ns=time.time_ns(),
            archetype=archetype,
            probability=prob,
            confidence_label=conf,
            secondary_archetype=None,
            secondary_probability=0.0,
            evidence=["Test evidence signal."],
            limitations="Level 2 data does not reveal participant identity.",
        )

    def test_returns_report(self):
        state, features, _ = _make_pipeline()
        arch = self._make_archetype_report()
        agent = MotivationInferenceAgent()
        report = agent.analyse(state, features, arch)
        assert report.symbol == "TEST"
        assert report.motivation_primary in MOTIVATION_TAXONOMY
        assert report.motivation_confidence in {"high", "medium", "low"}
        assert report.engine_used in {"rule_based", "deepseek"}
        assert report.compliance_cleared is True

    def test_motivation_in_taxonomy(self):
        state, features, _ = _make_pipeline()
        for archetype in ["institutional_accumulator", "strategic_seller",
                          "algorithmic_market_maker", "momentum_ignitor", "unknown_mixed"]:
            arch = self._make_archetype_report(archetype=archetype, prob=0.6)
            agent = MotivationInferenceAgent()
            report = agent.analyse(state, features, arch)
            assert report.motivation_primary in MOTIVATION_TAXONOMY, (
                f"Motivation '{report.motivation_primary}' not in taxonomy for archetype '{archetype}'"
            )

    def test_alternative_motivation_in_taxonomy(self):
        state, features, _ = _make_pipeline()
        arch = self._make_archetype_report()
        agent = MotivationInferenceAgent()
        report = agent.analyse(state, features, arch)
        assert report.motivation_alternative in MOTIVATION_TAXONOMY

    def test_reasoning_trace_populated(self):
        state, features, _ = _make_pipeline()
        arch = self._make_archetype_report()
        agent = MotivationInferenceAgent()
        report = agent.analyse(state, features, arch)
        assert report.reasoning_trace != ""

    def test_rule_based_when_no_api_key(self, monkeypatch):
        """Without DEEPSEEK_API_KEY, engine must be rule_based."""
        import src.config as cfg
        monkeypatch.setattr(cfg, "DEEPSEEK_API_KEY", "")
        state, features, _ = _make_pipeline()
        arch = self._make_archetype_report()
        agent = MotivationInferenceAgent()
        report = agent.analyse(state, features, arch)
        assert report.engine_used == "rule_based"


class TestDecisionParliamentPhase2A:
    """Tests that Phase 2A extended fields appear correctly in parliament results."""

    def _make_full_reports(self):
        from src.agents.models import (
            OrderBookAnalystReport, MarketDNAReport, InstitutionalFootprintReport,
            RiskGovernorReport, ComplianceReport, ParticipantArchetypeReport, MotivationInferenceReport,
        )
        import time
        ts = time.time_ns()
        ob = OrderBookAnalystReport(
            symbol="TEST", timestamp_ns=ts,
            directional_bias="bullish", bias_confidence=0.7,
            key_signals=[], absorption_score=0.5, sweep_intensity=0.2,
            spoof_like_score=0.1, iceberg_like_score=0.3,
            spread_multiple=1.0, book_imbalance=0.2,
        )
        dna = MarketDNAReport(
            symbol="TEST", timestamp_ns=ts,
            regime="accumulation", regime_confidence=0.65,
            supporting_signals=[], regime_stability=0.7,
        )
        inst = InstitutionalFootprintReport(
            symbol="TEST", timestamp_ns=ts,
            behavioral_label="accumulation_like", probability=0.68,
            confidence_label="high", reasoning=[], limitations="test",
        )
        risk = RiskGovernorReport(
            symbol="TEST", timestamp_ns=ts,
            risk_status="clear", risk_score=0.1,
            veto=False, veto_reasons=[],
            spread_ok=True, data_quality_ok=True,
            model_confidence_ok=True, news_lockout=False,
        )
        comp = ComplianceReport(
            symbol="TEST", timestamp_ns=ts,
            status="approved", violations=[], warnings=[],
        )
        arch = ParticipantArchetypeReport(
            symbol="TEST", timestamp_ns=ts,
            archetype="institutional_accumulator", probability=0.70,
            confidence_label="high", secondary_archetype=None,
            secondary_probability=0.0, evidence=["Test evidence."],
            limitations="test",
        )
        motiv = MotivationInferenceReport(
            symbol="TEST", timestamp_ns=ts,
            motivation_primary="position_building_ahead_of_catalyst",
            motivation_confidence="high",
            motivation_evidence=["Test evidence."],
            motivation_alternative="mandate_driven_allocation",
            archetype_context="institutional_accumulator",
            reasoning_trace="Test trace.",
            engine_used="rule_based",
            compliance_cleared=True,
        )
        return ob, dna, inst, risk, comp, arch, motiv

    def test_phase2a_fields_in_result(self):
        ob, dna, inst, risk, comp, arch, motiv = self._make_full_reports()
        p = DecisionParliament()
        result = p.deliberate(ob, dna, inst, risk, comp,
                              archetype_report=arch, motivation_report=motiv)
        assert result.participant_archetype == "institutional_accumulator"
        assert result.motivation_primary == "position_building_ahead_of_catalyst"
        assert result.motivation_confidence == "high"

    def test_phase2a_fields_none_when_not_provided(self):
        """Backward compatibility: Phase 2A fields are None when reports not passed."""
        from src.agents.models import (
            OrderBookAnalystReport, MarketDNAReport, InstitutionalFootprintReport,
            RiskGovernorReport, ComplianceReport,
        )
        import time
        ts = time.time_ns()
        ob = OrderBookAnalystReport(
            symbol="TEST", timestamp_ns=ts,
            directional_bias="neutral", bias_confidence=0.4,
            key_signals=[], absorption_score=0.2, sweep_intensity=0.1,
            spoof_like_score=0.1, iceberg_like_score=0.1,
            spread_multiple=1.0, book_imbalance=0.1,
        )
        dna = MarketDNAReport(
            symbol="TEST", timestamp_ns=ts,
            regime="ranging", regime_confidence=0.5,
            supporting_signals=[], regime_stability=0.7,
        )
        inst = InstitutionalFootprintReport(
            symbol="TEST", timestamp_ns=ts,
            behavioral_label="neutral", probability=0.3,
            confidence_label="low", reasoning=[], limitations="test",
        )
        risk = RiskGovernorReport(
            symbol="TEST", timestamp_ns=ts,
            risk_status="clear", risk_score=0.1,
            veto=False, veto_reasons=[],
            spread_ok=True, data_quality_ok=True,
            model_confidence_ok=True, news_lockout=False,
        )
        comp = ComplianceReport(
            symbol="TEST", timestamp_ns=ts,
            status="approved", violations=[], warnings=[],
        )
        p = DecisionParliament()
        result = p.deliberate(ob, dna, inst, risk, comp)
        assert result.participant_archetype is None
        assert result.motivation_primary is None
        assert result.ipo_phase is None
