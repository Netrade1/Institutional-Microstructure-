"""
agents/decision_parliament.py – Decision Parliament (Phase 1).

Collects all agent assessments and produces a final disposition.

Disposition hierarchy:
    data_insufficient → (always first if data quality fails)
    risk_veto         → (Risk Governor veto)
    blocked           → (Compliance violation)
    human_review      → (conflicting high-confidence signals)
    paper_trade_approved → (all clear, sufficient evidence)
    watchlist         → (soft signals, insufficient conviction)
    research_approved → (analysis only, no execution context)
    rejected          → (no actionable signal)
"""

from __future__ import annotations

from src.agents.models import (
    ComplianceReport,
    DecisionParliamentResult,
    InstitutionalFootprintReport,
    MarketDNAReport,
    OrderBookAnalystReport,
    RiskGovernorReport,
)
from src.config import COMPLIANCE_LIMITATIONS_STATEMENT


class DecisionParliament:
    """
    Multi-agent voting and disposition engine.
    """

    def deliberate(
        self,
        ob_report: OrderBookAnalystReport,
        dna_report: MarketDNAReport,
        inst_report: InstitutionalFootprintReport,
        risk_report: RiskGovernorReport,
        compliance_report: ComplianceReport,
    ) -> DecisionParliamentResult:

        symbol = ob_report.symbol
        ts = ob_report.timestamp_ns

        # ── Gate 1: Data quality ──────────────────────────────────────────────
        if not risk_report.data_quality_ok:
            return self._result(
                symbol, ts, "data_insufficient",
                "Data quality check failed. Feed reliability is insufficient for analysis.",
                ob_report, dna_report, inst_report, risk_report, compliance_report,
            )

        # ── Gate 2: Compliance block ──────────────────────────────────────────
        if compliance_report.status == "blocked":
            return self._result(
                symbol, ts, "blocked",
                f"Output blocked by Compliance Agent: {'; '.join(compliance_report.violations)}",
                ob_report, dna_report, inst_report, risk_report, compliance_report,
            )

        # ── Gate 3: Risk veto ─────────────────────────────────────────────────
        if risk_report.veto:
            return self._result(
                symbol, ts, "risk_veto",
                f"Risk Governor veto: {'; '.join(risk_report.veto_reasons)}",
                ob_report, dna_report, inst_report, risk_report, compliance_report,
            )

        # ── Compute aggregate conviction ──────────────────────────────────────
        bullish_votes = 0
        bearish_votes = 0
        total_confidence = 0.0

        if ob_report.directional_bias == "bullish":
            bullish_votes += 1
            total_confidence += ob_report.bias_confidence
        elif ob_report.directional_bias == "bearish":
            bearish_votes += 1
            total_confidence += ob_report.bias_confidence

        if inst_report.behavioral_label == "accumulation_like":
            bullish_votes += 1
            total_confidence += inst_report.probability
        elif inst_report.behavioral_label == "distribution_like":
            bearish_votes += 1
            total_confidence += inst_report.probability

        regime_supports_action = dna_report.regime in {
            "accumulation", "breakout", "compression", "distribution"
        }
        if regime_supports_action:
            total_confidence += dna_report.regime_confidence * 0.5

        avg_confidence = total_confidence / max(bullish_votes + bearish_votes, 1)

        # ── Gate 4: Conflicting signals at high confidence ────────────────────
        if bullish_votes >= 1 and bearish_votes >= 1 and avg_confidence > 0.55:
            return self._result(
                symbol, ts, "human_review",
                "Conflicting high-confidence signals from Order Book Analyst and "
                "Institutional Footprint Agent. Human review recommended.",
                ob_report, dna_report, inst_report, risk_report, compliance_report,
            )

        # ── Gate 5: Paper trade approval ─────────────────────────────────────
        dominant_votes = max(bullish_votes, bearish_votes)
        if (
            dominant_votes >= 2
            and avg_confidence >= 0.55
            and risk_report.risk_status == "clear"
            and regime_supports_action
            and compliance_report.status == "approved"
        ):
            direction = "bullish" if bullish_votes > bearish_votes else "bearish"
            return self._result(
                symbol, ts, "paper_trade_approved",
                f"Multiple agents converge on {direction} view with sufficient confidence. "
                f"Risk Governor clear. Paper trade approved (no live execution).",
                ob_report, dna_report, inst_report, risk_report, compliance_report,
            )

        # ── Gate 6: Watchlist ─────────────────────────────────────────────────
        if dominant_votes >= 1 and avg_confidence >= 0.40:
            return self._result(
                symbol, ts, "watchlist",
                "Signal is present but conviction is insufficient for execution. "
                "Setup added to watchlist for further monitoring.",
                ob_report, dna_report, inst_report, risk_report, compliance_report,
            )

        # ── Default: Research only ────────────────────────────────────────────
        return self._result(
            symbol, ts, "research_approved",
            "Analysis complete. No actionable trade setup detected at this time. "
            "Research output delivered.",
            ob_report, dna_report, inst_report, risk_report, compliance_report,
        )

    @staticmethod
    def _result(
        symbol: str,
        ts: int,
        disposition: str,
        reasoning: str,
        ob: OrderBookAnalystReport,
        dna: MarketDNAReport,
        inst: InstitutionalFootprintReport,
        risk: RiskGovernorReport,
        compliance: ComplianceReport,
    ) -> DecisionParliamentResult:
        human_exp = (
            f"Symbol: {symbol} | Regime: {dna.regime} (confidence {dna.regime_confidence:.0%}) | "
            f"Order book bias: {ob.directional_bias} ({ob.bias_confidence:.0%}) | "
            f"Behavioral pattern: {inst.behavioral_label} ({inst.probability:.0%}, {inst.confidence_label} confidence) | "
            f"Risk status: {risk.risk_status} | "
            f"Disposition: {disposition.replace('_', ' ').upper()}. "
            f"{reasoning}"
        )
        return DecisionParliamentResult(
            symbol=symbol,
            timestamp_ns=ts,
            disposition=disposition,
            reasoning=reasoning,
            ob_analyst_vote=ob.directional_bias,
            ob_analyst_confidence=ob.bias_confidence,
            dna_regime=dna.regime,
            dna_confidence=dna.regime_confidence,
            inst_footprint_label=inst.behavioral_label,
            inst_footprint_prob=inst.probability,
            risk_status=risk.risk_status,
            compliance_status=compliance.status,
            human_explanation=human_exp,
            limitations=COMPLIANCE_LIMITATIONS_STATEMENT,
        )
