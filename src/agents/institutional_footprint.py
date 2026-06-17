"""
agents/institutional_footprint.py – Institutional Footprint Agent (Phase 1).

Estimates broad behavioral patterns in the order flow.

COMPLIANCE REQUIREMENT (HARD):
    This agent NEVER identifies, names, or implies the identity of any
    specific market participant, institution, firm, fund, or individual.
    All outputs are probabilistic behavioral labels with mandatory
    limitations statements.

Permitted outputs (examples):
    "The activity resembles institutional-style accumulation."
    "The order flow suggests large-participant absorption."
    "Institutional-style accumulation probability: 68%, confidence: medium."

Prohibited outputs:
    "BlackRock is buying here."
    "Citadel is selling this level."
    "A specific hedge fund is accumulating."
"""

from __future__ import annotations

from src.config import COMPLIANCE_LIMITATIONS_STATEMENT
from src.features.engineer import FeatureVector
from src.order_book.engine import OrderBookState
from src.agents.models import InstitutionalFootprintReport


class InstitutionalFootprintAgent:

    def analyse(
        self,
        state: OrderBookState,
        features: FeatureVector,
    ) -> InstitutionalFootprintReport:
        label, prob, conf_label, reasoning = self._classify(state, features)
        return InstitutionalFootprintReport(
            symbol=state.symbol,
            timestamp_ns=state.timestamp_ns,
            behavioral_label=label,
            probability=prob,
            confidence_label=conf_label,
            reasoning=reasoning,
            limitations=COMPLIANCE_LIMITATIONS_STATEMENT,
        )

    @staticmethod
    def _classify(
        state: OrderBookState, fv: FeatureVector
    ) -> tuple[str, float, str, list[str]]:
        reasoning: list[str] = []
        accum_prob = fv.accumulation_score
        distrib_prob = fv.distribution_score

        # Adjust probabilities with corroborating signals
        if state.absorption_score > 0.5:
            accum_prob += 0.08
            reasoning.append(f"Large-print absorption score: {state.absorption_score:.2f}.")
        if state.bid_replenishment_rate > 0.3:
            accum_prob += 0.06
            reasoning.append(f"Bid replenishment rate: {state.bid_replenishment_rate:.2f}.")
        if state.iceberg_like_score > 0.4:
            accum_prob += 0.06
            distrib_prob += 0.04
            reasoning.append(f"Iceberg-like clip patterns detected (score {state.iceberg_like_score:.2f}).")
        if fv.order_flow_imbalance > 0.2:
            accum_prob += 0.07
            reasoning.append(f"Positive order-flow imbalance: {fv.order_flow_imbalance:.2f}.")
        elif fv.order_flow_imbalance < -0.2:
            distrib_prob += 0.07
            reasoning.append(f"Negative order-flow imbalance: {fv.order_flow_imbalance:.2f}.")
        if state.stacking_ask:
            distrib_prob += 0.10
            reasoning.append("Ask-side stacking detected near resistance.")
        if fv.vwap_deviation < -0.005:
            distrib_prob += 0.05
            reasoning.append("Price trading below VWAP.")
        elif fv.vwap_deviation > 0.005:
            accum_prob += 0.05
            reasoning.append("Price trading above VWAP.")

        accum_prob = round(min(accum_prob, 1.0), 3)
        distrib_prob = round(min(distrib_prob, 1.0), 3)

        if accum_prob > distrib_prob and accum_prob >= 0.40:
            label = "accumulation_like"
            prob = accum_prob
        elif distrib_prob > accum_prob and distrib_prob >= 0.40:
            label = "distribution_like"
            prob = distrib_prob
        elif max(accum_prob, distrib_prob) >= 0.25:
            label = "mixed"
            prob = max(accum_prob, distrib_prob)
        else:
            label = "neutral"
            prob = max(accum_prob, distrib_prob)

        if prob >= 0.65:
            conf = "high"
        elif prob >= 0.45:
            conf = "medium"
        elif prob >= 0.30:
            conf = "low"
        else:
            conf = "insufficient_data"

        if not reasoning:
            reasoning.append("No strong corroborating behavioral signals detected.")

        return label, prob, conf, reasoning
