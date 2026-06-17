"""
agents/risk_governor.py – Risk Governor Agent / Captain MarginCall (Phase 1).

Evaluates every setup for risk acceptability.
Has veto authority: a Veto status blocks all execution recommendations.

Evaluates:
    - Spread vs historical average
    - Data quality score
    - Model confidence (placeholder in Phase 1)
    - Spread multiple
    - Liquidity trap risk
    - Momentum ignition risk
    - Spoof-like conditions
    - News lockout (hardcoded False in Phase 1 — Phase 3 adds News Agent)
"""

from __future__ import annotations

from src.config import (
    MAX_SPREAD_MULTIPLE,
    MIN_DATA_QUALITY_SCORE,
    MIN_MODEL_CONFIDENCE,
)
from src.data_intake.models import FeedHealthReport
from src.features.engineer import FeatureVector
from src.order_book.engine import OrderBookState
from src.agents.models import RiskGovernorReport


class RiskGovernorAgent:
    """
    The system's risk officer. Produces a RiskGovernorReport and can veto
    any execution recommendation.
    """

    def evaluate(
        self,
        state: OrderBookState,
        features: FeatureVector,
        health: FeedHealthReport,
        model_confidence: float = float("nan"),
    ) -> RiskGovernorReport:
        veto_reasons: list[str] = []

        # ── Spread check ──────────────────────────────────────────────────────
        spread_ok = state.spread_multiple <= MAX_SPREAD_MULTIPLE
        if not spread_ok:
            veto_reasons.append(
                f"Spread is {state.spread_multiple:.1f}× the 20-snapshot average "
                f"(threshold: {MAX_SPREAD_MULTIPLE}×). Execution risk elevated."
            )

        # ── Data quality check ────────────────────────────────────────────────
        dq_ok = health.quality_score >= MIN_DATA_QUALITY_SCORE
        if not dq_ok:
            veto_reasons.append(
                f"Data quality score {health.quality_score:.2f} is below threshold "
                f"{MIN_DATA_QUALITY_SCORE}."
            )
        if health.stale_quote:
            veto_reasons.append("Feed has a stale quote — data freshness cannot be guaranteed.")
        if health.gap_detected:
            veto_reasons.append("Sequence gap detected in feed — order book state may be incomplete.")

        # ── Model confidence ──────────────────────────────────────────────────
        import math
        conf_ok = math.isnan(model_confidence) or model_confidence >= MIN_MODEL_CONFIDENCE
        if not conf_ok:
            veto_reasons.append(
                f"ML model confidence {model_confidence:.2f} below threshold "
                f"{MIN_MODEL_CONFIDENCE}. Signal reliability is insufficient."
            )

        # ── Liquidity trap ────────────────────────────────────────────────────
        if features.liquidity_trap_risk > 0.6:
            veto_reasons.append(
                f"Liquidity trap risk elevated ({features.liquidity_trap_risk:.2f}). "
                "Wide spread, thin depth, or rapid liquidity removal detected."
            )

        # ── Spoof-like conditions ─────────────────────────────────────────────
        if features.spoof_like_score > 0.5:
            veto_reasons.append(
                f"Spoof-like behaviour score elevated ({features.spoof_like_score:.2f}). "
                "Book may not reflect true supply/demand."
            )

        # ── News lockout (Phase 1: static False; Phase 3 adds live check) ─────
        news_lockout = False

        # ── Risk score ────────────────────────────────────────────────────────
        risk_score = 0.0
        if not spread_ok:
            risk_score += 0.30
        if not dq_ok:
            risk_score += 0.30
        if not conf_ok:
            risk_score += 0.15
        risk_score += features.liquidity_trap_risk * 0.15
        risk_score += features.spoof_like_score * 0.10
        risk_score = round(min(risk_score, 1.0), 3)

        # ── Status ────────────────────────────────────────────────────────────
        veto = len(veto_reasons) > 0 and risk_score >= 0.30
        if veto:
            status = "veto"
        elif risk_score >= 0.20:
            status = "caution"
        else:
            status = "clear"

        return RiskGovernorReport(
            symbol=state.symbol,
            timestamp_ns=state.timestamp_ns,
            risk_status=status,
            risk_score=risk_score,
            veto=veto,
            veto_reasons=veto_reasons,
            spread_ok=spread_ok,
            data_quality_ok=dq_ok,
            model_confidence_ok=conf_ok,
            news_lockout=news_lockout,
        )
