"""
agents/participant_archetype_agent.py – Participant Archetype Agent (Phase 2A).

WHO layer: classifies the behavioural archetype of market participants observed
in Level 2 order-flow data.

COMPLIANCE REQUIREMENT (HARD):
    This agent NEVER identifies, names, or implies the identity of any
    specific market participant, institution, firm, fund, or individual.
    All outputs are probabilistic behavioural archetype labels with mandatory
    limitations statements.

Archetypes (observable behaviour signatures only):
    institutional_accumulator  – iceberg orders, VWAP-anchored absorption, low urgency
    retail_sentiment_buyer     – market orders at open, round-number clusters, high spread tolerance
    algorithmic_market_maker   – tight bid/ask cycling, rapid quote refresh, mean-reversion
    momentum_ignitor           – sweep patterns, spoof-then-pull, volume spike + fast retrace
    strategic_seller           – ask stacking, sweep exhaustion, dark-print divergence
    informed_flow_proxy        – pre-catalyst accumulation, size concentration at key levels
                                 (requires corroborating public data; never asserts insider knowledge)
    unknown_mixed              – no dominant pattern
"""

from __future__ import annotations

from src.config import COMPLIANCE_LIMITATIONS_STATEMENT
from src.features.engineer import FeatureVector
from src.order_book.engine import OrderBookState
from src.agents.models import ParticipantArchetypeReport


# Archetype labels – exhaustive permitted set
ARCHETYPES = {
    "institutional_accumulator",
    "retail_sentiment_buyer",
    "algorithmic_market_maker",
    "momentum_ignitor",
    "strategic_seller",
    "informed_flow_proxy",
    "unknown_mixed",
}


class ParticipantArchetypeAgent:
    """
    WHO-layer inference.  Scores seven mutually exclusive behavioural archetypes
    using observable Level 2 signals.  Returns the dominant archetype plus a
    secondary archetype when two patterns are in close competition.
    """

    def analyse(
        self,
        state: OrderBookState,
        features: FeatureVector,
    ) -> ParticipantArchetypeReport:
        scores, evidence = self._score_archetypes(state, features)

        # Sort by score descending
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        primary_arch, primary_prob = ranked[0]
        secondary_arch, secondary_prob = ranked[1]

        # Normalise to keep within [0, 1]
        primary_prob = round(min(primary_prob, 1.0), 3)
        secondary_prob = round(min(secondary_prob, 1.0), 3)

        # Confidence label
        if primary_prob >= 0.65:
            conf = "high"
        elif primary_prob >= 0.45:
            conf = "medium"
        elif primary_prob >= 0.30:
            conf = "low"
        else:
            primary_arch = "unknown_mixed"
            conf = "insufficient_data"

        # If secondary is too close to primary, both are relevant
        secondary = secondary_arch if secondary_prob >= 0.30 else None

        return ParticipantArchetypeReport(
            symbol=state.symbol,
            timestamp_ns=state.timestamp_ns,
            archetype=primary_arch,
            probability=primary_prob,
            confidence_label=conf,
            secondary_archetype=secondary,
            secondary_probability=secondary_prob,
            evidence=evidence.get(primary_arch, []),
            limitations=COMPLIANCE_LIMITATIONS_STATEMENT,
        )

    @staticmethod
    def _score_archetypes(
        state: OrderBookState,
        fv: FeatureVector,
    ) -> tuple[dict[str, float], dict[str, list[str]]]:
        """
        Score each archetype from 0.0 to 1.0 using observable signals.
        Returns (scores_dict, evidence_dict).
        """
        scores: dict[str, float] = {a: 0.0 for a in ARCHETYPES}
        evidence: dict[str, list[str]] = {a: [] for a in ARCHETYPES}

        # ── Institutional Accumulator ─────────────────────────────────────────
        ia = "institutional_accumulator"
        if state.iceberg_like_score > 0.4:
            scores[ia] += 0.20
            evidence[ia].append(f"Iceberg-like clip patterns (score {state.iceberg_like_score:.2f}).")
        if state.absorption_score > 0.5:
            scores[ia] += 0.15
            evidence[ia].append(f"Large-print absorption at bid (score {state.absorption_score:.2f}).")
        if fv.vwap_deviation > 0.002 and fv.order_flow_imbalance > 0.15:
            scores[ia] += 0.12
            evidence[ia].append("Price above VWAP with positive OFI — VWAP-anchored accumulation pattern.")
        if state.bid_replenishment_rate > 0.3:
            scores[ia] += 0.10
            evidence[ia].append(f"High bid replenishment rate ({state.bid_replenishment_rate:.2f}) — consistent with patient buyer.")
        if fv.accumulation_score > 0.5:
            scores[ia] += 0.15
            evidence[ia].append(f"Composite accumulation score elevated ({fv.accumulation_score:.2f}).")

        # ── Retail Sentiment Buyer ────────────────────────────────────────────
        rs = "retail_sentiment_buyer"
        if state.sweep_intensity > 0.5 and fv.rolling_buy_sell_ratio > 1.3:
            scores[rs] += 0.20
            evidence[rs].append("Market-order sweep with high buy/sell ratio — urgency consistent with retail FOMO.")
        if state.spread_multiple > 2.0 and fv.order_flow_imbalance > 0.1:
            scores[rs] += 0.12
            evidence[rs].append(f"Buying into wide spread ({state.spread_multiple:.1f}×) — low price sensitivity.")
        if fv.rvol > 2.0 and fv.rolling_buy_sell_ratio > 1.5:
            scores[rs] += 0.15
            evidence[rs].append(f"Elevated relative volume ({fv.rvol:.1f}×) with strong buy imbalance — sentiment-driven demand.")

        # ── Algorithmic Market Maker ──────────────────────────────────────────
        mm = "algorithmic_market_maker"
        if state.bid_replenishment_rate > 0.5 and state.ask_replenishment_rate > 0.5:
            scores[mm] += 0.20
            evidence[mm].append("Simultaneous high bid and ask replenishment — symmetric quoting pattern.")
        if state.spread_multiple < 1.2 and abs(fv.bid_ask_imbalance) < 0.15:
            scores[mm] += 0.18
            evidence[mm].append("Tight spread with near-balanced book — market-maker neutral positioning.")
        if state.spoof_like_score < 0.1 and state.iceberg_like_score < 0.1:
            scores[mm] += 0.08
            evidence[mm].append("No spoof or iceberg patterns — clean two-sided quoting.")

        # ── Momentum Ignitor ─────────────────────────────────────────────────
        mi = "momentum_ignitor"
        if state.sweep_intensity > 0.7:
            scores[mi] += 0.25
            evidence[mi].append(f"High sweep intensity ({state.sweep_intensity:.2f}) — aggressive level-taking.")
        if state.spoof_like_score > 0.5:
            scores[mi] += 0.20
            evidence[mi].append(f"Spoof-like activity detected (score {state.spoof_like_score:.2f}) — order placement and cancellation pattern.")
        if fv.rvol > 3.0 and fv.momentum_ignition_risk > 0.5:
            scores[mi] += 0.15
            evidence[mi].append("Extreme relative volume with high momentum-ignition risk score.")

        # ── Strategic Seller ─────────────────────────────────────────────────
        ss = "strategic_seller"
        if state.stacking_ask:
            scores[ss] += 0.20
            evidence[ss].append("Ask-side stacking at resistance — controlled distribution pattern.")
        if fv.distribution_score > 0.5:
            scores[ss] += 0.18
            evidence[ss].append(f"Composite distribution score elevated ({fv.distribution_score:.2f}).")
        if fv.vwap_deviation < -0.003 and fv.order_flow_imbalance < -0.15:
            scores[ss] += 0.12
            evidence[ss].append("Price below VWAP with negative OFI — strategic selling pressure.")
        if state.ask_replenishment_rate > 0.4 and not state.stacking_bid:
            scores[ss] += 0.10
            evidence[ss].append("Asymmetric ask replenishment without bid support — one-sided supply.")

        # ── Informed Flow Proxy ───────────────────────────────────────────────
        # Only triggered when both accumulation AND catalyst-consistent signals are present.
        # NEVER implies insider knowledge — requires public corroboration.
        ip = "informed_flow_proxy"
        if (
            fv.accumulation_score > 0.6
            and state.iceberg_like_score > 0.5
            and fv.institutional_footprint_prob > 0.6
        ):
            scores[ip] += 0.25
            evidence[ip].append(
                "High accumulation + iceberg score + institutional footprint probability — "
                "pattern consistent with informed flow (public corroboration required)."
            )
        if fv.breakout_confirmation_score > 0.6 and state.absorption_score > 0.6:
            scores[ip] += 0.12
            evidence[ip].append("Breakout confirmation with strong absorption — pre-catalyst positioning signal.")

        # ── Fallback: unknown_mixed ───────────────────────────────────────────
        max_score = max(scores[a] for a in ARCHETYPES if a != "unknown_mixed")
        if max_score < 0.20:
            scores["unknown_mixed"] = 0.25
            evidence["unknown_mixed"].append("No dominant observable pattern. Mixed or ambiguous order flow.")

        return scores, evidence
