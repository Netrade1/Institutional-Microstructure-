"""
agents/motivation_inference_agent.py – Motivation Inference Agent (Phase 2A).

WHY layer: infers the most likely economic motivation behind the dominant
participant archetype observed in the order flow.

Two-mode engine:
    1. Rule-based (default) — deterministic, requires no API keys, fully auditable.
    2. DeepSeek-R1 enhanced — if DEEPSEEK_API_KEY is set, the rule-based output is
       enriched with a DeepSeek reasoning trace via the OpenAI-compatible API.
       Falls back to rule-based silently if the API call fails.

MOTIVATION TAXONOMY
───────────────────
ACCUMULATION:
    position_building_ahead_of_catalyst   – pre-catalyst accumulation
    index_rebalancing                     – mandatory passive rebalancing
    mandate_driven_allocation             – pension / endowment / passive fund mandate
    arbitrage_convergence                 – spread/convergence play
    informed_flow_proxy                   – corroborated by public SEC filings only

DISTRIBUTION:
    lock_up_expiry_selling                – approaching lock-up expiry
    stop_loss_exit                        – involuntary risk exit
    profit_taking_resistance              – technical profit-taking
    risk_reduction_macro_event            – de-risking ahead of macro catalyst
    tax_loss_harvesting                   – seasonal / year-end
    short_entry_negative_thesis           – directional short

NEUTRAL / LIQUIDITY:
    market_making_neutral                 – no directional bias
    portfolio_rebalancing_neutral         – size-neutral rebalancing
    options_hedging_delta_adjustment      – delta hedge

UNKNOWN:
    unknown                               – insufficient evidence
"""

from __future__ import annotations

from src.config import (
    COMPLIANCE_LIMITATIONS_STATEMENT,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
)
from src.features.engineer import FeatureVector
from src.order_book.engine import OrderBookState
from src.agents.models import MotivationInferenceReport, ParticipantArchetypeReport


# Full taxonomy set used for validation
MOTIVATION_TAXONOMY = {
    # Accumulation
    "position_building_ahead_of_catalyst",
    "index_rebalancing",
    "mandate_driven_allocation",
    "arbitrage_convergence",
    "informed_flow_proxy",
    # Distribution
    "lock_up_expiry_selling",
    "stop_loss_exit",
    "profit_taking_resistance",
    "risk_reduction_macro_event",
    "tax_loss_harvesting",
    "short_entry_negative_thesis",
    # Neutral
    "market_making_neutral",
    "portfolio_rebalancing_neutral",
    "options_hedging_delta_adjustment",
    # Unknown
    "unknown",
}

# Archetype → motivation mapping (rule-based prior)
_ARCHETYPE_MOTIVATION_MAP: dict[str, tuple[str, str]] = {
    "institutional_accumulator":  ("position_building_ahead_of_catalyst", "mandate_driven_allocation"),
    "retail_sentiment_buyer":     ("position_building_ahead_of_catalyst", "stop_loss_exit"),
    "algorithmic_market_maker":   ("market_making_neutral",               "options_hedging_delta_adjustment"),
    "momentum_ignitor":           ("short_entry_negative_thesis",         "profit_taking_resistance"),
    "strategic_seller":           ("profit_taking_resistance",            "risk_reduction_macro_event"),
    "informed_flow_proxy":        ("position_building_ahead_of_catalyst", "informed_flow_proxy"),
    "unknown_mixed":              ("unknown",                             "unknown"),
}


class MotivationInferenceAgent:
    """
    WHY-layer inference.

    Call analyse() after ParticipantArchetypeAgent to obtain a motivation
    taxonomy label, confidence score, and supporting evidence.

    If DEEPSEEK_API_KEY is set in config, the output is enriched with a
    DeepSeek-R1 reasoning trace.  The rule-based result is always produced
    first so that the system is never dependent on external API availability.
    """

    def analyse(
        self,
        state: OrderBookState,
        features: FeatureVector,
        archetype_report: ParticipantArchetypeReport,
    ) -> MotivationInferenceReport:
        # Always produce rule-based result first
        primary, alt, evidence, confidence, trace = self._rule_based(
            state, features, archetype_report
        )
        engine = "rule_based"

        # Optionally enrich with DeepSeek if API key is available
        if DEEPSEEK_API_KEY:
            try:
                ds_trace = self._deepseek_enrich(state, features, archetype_report, primary, evidence)
                trace = ds_trace
                engine = "deepseek"
            except Exception:
                pass  # Silently fall back to rule-based

        return MotivationInferenceReport(
            symbol=state.symbol,
            timestamp_ns=state.timestamp_ns,
            motivation_primary=primary,
            motivation_confidence=confidence,
            motivation_evidence=evidence,
            motivation_alternative=alt,
            archetype_context=archetype_report.archetype,
            reasoning_trace=trace,
            engine_used=engine,
            compliance_cleared=True,
        )

    @staticmethod
    def _rule_based(
        state: OrderBookState,
        fv: FeatureVector,
        arch: ParticipantArchetypeReport,
    ) -> tuple[str, str, list[str], str, str]:
        """
        Deterministic rule engine.  Returns:
          (primary_motivation, alt_motivation, evidence_list, confidence, trace)
        """
        archetype = arch.archetype
        primary, alt = _ARCHETYPE_MOTIVATION_MAP.get(archetype, ("unknown", "unknown"))
        evidence: list[str] = list(arch.evidence)  # carry forward archetype evidence
        trace_parts: list[str] = [f"Archetype: {archetype} (p={arch.probability:.2f})."]

        # ── Refine primary motivation using contextual signals ────────────────

        if archetype == "institutional_accumulator":
            if fv.rvol > 3.0:
                primary = "position_building_ahead_of_catalyst"
                evidence.append(f"Relative volume spike ({fv.rvol:.1f}×) consistent with catalyst-driven accumulation.")
                trace_parts.append("Elevated RVOL → catalyst-driven accumulation hypothesis elevated.")
            elif fv.accumulation_score > 0.6 and fv.order_flow_imbalance < 0.1:
                primary = "mandate_driven_allocation"
                evidence.append("Quiet, low-urgency accumulation pattern consistent with mandate-driven flow.")
                trace_parts.append("Low urgency + steady accumulation → mandate allocation.")
            else:
                evidence.append("Standard accumulation pattern — catalyst or mandate motivation probable.")

        elif archetype == "retail_sentiment_buyer":
            if fv.rvol > 2.5:
                evidence.append(f"High relative volume ({fv.rvol:.1f}×) amplifies retail FOMO hypothesis.")
                trace_parts.append("RVOL > 2.5× with retail signature → FOMO motivation elevated.")
            elif fv.rolling_buy_sell_ratio > 1.8:
                evidence.append(f"Buy/sell ratio of {fv.rolling_buy_sell_ratio:.1f}× is typical of sentiment-driven buying.")

        elif archetype == "algorithmic_market_maker":
            if abs(fv.bid_ask_imbalance) < 0.05:
                evidence.append("Near-zero book imbalance confirms neutral market-making stance.")
                trace_parts.append("Near-zero imbalance → market-making neutral confirmed.")

        elif archetype == "momentum_ignitor":
            if state.spoof_like_score > 0.6:
                primary = "short_entry_negative_thesis"
                evidence.append(f"Spoof-like score {state.spoof_like_score:.2f} consistent with directional short entry.")
                trace_parts.append("High spoof score → short-entry / momentum manipulation hypothesis.")
            elif state.sweep_intensity > 0.8:
                evidence.append(f"Sweep intensity {state.sweep_intensity:.2f} — stop-cluster triggering pattern.")

        elif archetype == "strategic_seller":
            if fv.distribution_score > 0.6:
                if fv.vwap_deviation < -0.005:
                    primary = "stop_loss_exit"
                    evidence.append("Selling below VWAP with high distribution score — involuntary stop-loss exit pattern.")
                    trace_parts.append("Below-VWAP distribution → stop-loss exit hypothesis elevated.")
                else:
                    primary = "profit_taking_resistance"
                    evidence.append("Selling into resistance with high distribution score — profit-taking pattern.")
                    trace_parts.append("At-resistance distribution → profit-taking hypothesis elevated.")
            if fv.rvol > 3.0:
                alt = "risk_reduction_macro_event"
                evidence.append(f"Volume spike ({fv.rvol:.1f}×) with selling pressure — macro risk-reduction possible.")

        elif archetype == "informed_flow_proxy":
            evidence.append(
                "Pattern is consistent with informed positioning. "
                "Cross-reference SEC EDGAR 13F / Form 4 filings before drawing conclusions."
            )
            trace_parts.append("Informed flow proxy — public disclosure corroboration required.")

        # Confidence based on archetype confidence + evidence count
        if arch.confidence_label == "high" and len(evidence) >= 2:
            confidence = "high"
        elif arch.confidence_label in {"high", "medium"} and len(evidence) >= 1:
            confidence = "medium"
        else:
            confidence = "low"

        if not evidence:
            evidence.append("Insufficient observable signals to determine motivation with confidence.")
            confidence = "low"

        trace = " | ".join(trace_parts) if trace_parts else "No rule triggers fired."
        return primary, alt, evidence, confidence, trace

    @staticmethod
    def _deepseek_enrich(
        state: OrderBookState,
        fv: FeatureVector,
        arch: ParticipantArchetypeReport,
        primary_motivation: str,
        evidence: list[str],
    ) -> str:
        """
        Send a structured prompt to DeepSeek-R1 via OpenAI-compatible API
        and return the reasoning trace.  Never replaces compliance-cleared
        rule-based output — only enriches the reasoning narrative.
        """
        import openai  # imported lazily to avoid hard dependency when not needed

        client = openai.OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
        )

        prompt = (
            f"You are an institutional market microstructure analyst. "
            f"You NEVER identify named market participants. "
            f"You speak in probabilistic, compliance-safe language.\n\n"
            f"INSTRUMENT: {state.symbol}\n"
            f"PARTICIPANT ARCHETYPE: {arch.archetype} (probability: {arch.probability:.0%}, "
            f"confidence: {arch.confidence_label})\n"
            f"RULE-BASED MOTIVATION: {primary_motivation}\n"
            f"EVIDENCE:\n" + "\n".join(f"  - {e}" for e in evidence) + "\n\n"
            f"MARKET CONTEXT:\n"
            f"  Order flow imbalance: {fv.order_flow_imbalance:+.3f}\n"
            f"  Relative volume: {fv.rvol:.2f}×\n"
            f"  VWAP deviation: {fv.vwap_deviation:+.4f}\n"
            f"  Absorption score: {state.absorption_score:.2f}\n"
            f"  Sweep intensity: {state.sweep_intensity:.2f}\n"
            f"  Spoof-like score: {state.spoof_like_score:.2f}\n\n"
            f"Task: In 2–3 sentences, provide an institutional-grade reasoning narrative "
            f"explaining WHY this archetype is most likely placing orders now. "
            f"Do NOT name any institution. Use probabilistic language. "
            f"State confidence level. Mention any alternative motivation if plausible."
        )

        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
