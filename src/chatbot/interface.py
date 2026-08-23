"""
chatbot/interface.py – Chatbot Interface Layer (Phase 2A).

The user-facing command centre.  Accepts natural-language queries and routes
them to the appropriate agents.  Returns structured, human-readable responses.

Supported commands (Phase 2A):
    "analyze {SYMBOL}"
    "who is buying / who is placing orders"
    "why is there buying / selling pressure"
    "what is the order flow / what is being ordered"
    "is this institutional or retail"
    "what is the IPO regime"
    "explain the motivation"
    "summarize participant activity"
    "is there buyer absorption"
    "are large sellers stacking the ask"
    "summarize institutional activity"
    "what is the order flow regime"
    "should this be paper traded"
    "explain the risk"
    "show signals"
    "help"

Phase 3 will replace the rule-based intent parser with a local or API-based
LLM (OpenAI / Anthropic / DeepSeek) to support free-form natural-language.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from src.agents.models import (
    ComplianceReport,
    DecisionParliamentResult,
    InstitutionalFootprintReport,
    IPOMicrostructureReport,
    MarketDNAReport,
    MotivationInferenceReport,
    OrderBookAnalystReport,
    ParticipantArchetypeReport,
    RiskGovernorReport,
)
from src.config import COMPLIANCE_LIMITATIONS_STATEMENT


HELP_TEXT = """
╔════════════════════════════════════════════════════════════════════╗
║   Institutional Microstructure Intelligence — Phase 2A Chatbot     ║
╚════════════════════════════════════════════════════════════════════╝

Available commands:
  analyze <SYMBOL>             Full WHAT / WHO / WHY microstructure analysis
  who <SYMBOL>                 WHO is placing orders? (participant archetype)
  why <SYMBOL>                 WHY are they placing orders? (motivation inference)
  what <SYMBOL>                WHAT is being ordered? (order classification)
  archetype <SYMBOL>           Detailed participant archetype breakdown
  motivation <SYMBOL>          Detailed motivation taxonomy output
  ipo <SYMBOL>                 IPO-specific microstructure signals
  absorption <SYMBOL>          Is buyer absorption present at the bid?
  stacking <SYMBOL>            Are large sellers stacking the ask?
  institutional <SYMBOL>       Summarise institutional-style activity
  regime <SYMBOL>              What is the order-flow regime?
  risk <SYMBOL>                Explain the risk before entry
  paper-trade <SYMBOL>         Should this setup be paper-traded?
  signals <SYMBOL>             Show active order book signals
  help                         Show this help text

Notes:
  • All analysis is for research purposes only.
  • No live execution. Paper-trade mode only by default.
  • Participant archetypes are probabilistic behavioural labels — not identities.
  • Motivation inferences are hypotheses bounded by observable evidence.
  • Participant identity CANNOT be inferred from Level 2 data.
""".strip()


@dataclass
class ChatbotResponse:
    text: str
    symbol: Optional[str]
    intent: str
    compliance_status: str
    disposition: Optional[str] = None


class ChatbotInterface:
    """
    Rule-based intent parser and response formatter.
    Phase 3 will swap the parser for an LLM-based router.
    """

    INTENTS: list[tuple[str, list[str]]] = [
        ("analyze",        ["analyze", "analysis", "level 2", "l2", "activity"]),
        ("who",            ["who is buying", "who is placing", "who is selling", "who is it", "who is"]),
        ("why",            ["why is there", "why are they", "why is buying", "why is selling", "motivation", "why"]),
        ("what",           ["what is being ordered", "what is being traded", "what orders", "what is the order flow"]),
        ("archetype",      ["archetype", "participant type", "participant archetype", "retail or institutional"]),
        ("motivation",     ["explain the motivation", "explain motivation", "motivation inference"]),
        ("ipo",            ["ipo", "ipo regime", "price discovery", "greenshoe", "lock-up", "lock up", "stabilisation"]),
        ("absorption",     ["absorption", "buyer absorption", "absorb"]),
        ("stacking",       ["stacking", "stack", "large sellers", "ask wall"]),
        ("institutional",  ["institutional", "large participant", "footprint", "accumulation", "distribution"]),
        ("regime",         ["regime", "order flow regime", "market dna", "market regime"]),
        ("risk",           ["risk", "explain risk", "before entry", "risk before"]),
        ("paper_trade",    ["paper trade", "paper-trade", "should i trade", "should this be traded"]),
        ("signals",        ["signals", "active signals", "show signals"]),
        ("help",           ["help", "commands", "usage", "?"]),
    ]

    def parse_intent(self, user_input: str) -> tuple[str, Optional[str]]:
        """Extract intent and optional symbol from raw user input."""
        text = user_input.lower().strip()

        # Extract ticker symbol: 1–5 uppercase letters
        symbol_match = re.search(r'\b([A-Z]{1,5})\b', user_input)
        symbol = symbol_match.group(1) if symbol_match else None

        for intent, keywords in self.INTENTS:
            if any(kw in text for kw in keywords):
                return intent, symbol

        return "unknown", symbol

    def respond(
        self,
        user_input: str,
        ob_report: Optional[OrderBookAnalystReport] = None,
        dna_report: Optional[MarketDNAReport] = None,
        inst_report: Optional[InstitutionalFootprintReport] = None,
        risk_report: Optional[RiskGovernorReport] = None,
        compliance_report: Optional[ComplianceReport] = None,
        parliament_result: Optional[DecisionParliamentResult] = None,
        # Phase 2A
        archetype_report: Optional[ParticipantArchetypeReport] = None,
        motivation_report: Optional[MotivationInferenceReport] = None,
        ipo_report: Optional[IPOMicrostructureReport] = None,
    ) -> ChatbotResponse:
        intent, symbol = self.parse_intent(user_input)

        if intent == "help" or not any([ob_report, dna_report, parliament_result]):
            return ChatbotResponse(
                text=HELP_TEXT,
                symbol=symbol,
                intent=intent,
                compliance_status="approved",
            )

        if intent == "analyze":
            text = self._fmt_analyze(symbol, ob_report, dna_report, inst_report, risk_report,
                                     parliament_result, archetype_report, motivation_report, ipo_report)
        elif intent == "who":
            text = self._fmt_who(symbol, archetype_report)
        elif intent == "why":
            text = self._fmt_why(symbol, motivation_report)
        elif intent == "what":
            text = self._fmt_what(symbol, ob_report)
        elif intent == "archetype":
            text = self._fmt_archetype(symbol, archetype_report)
        elif intent == "motivation":
            text = self._fmt_motivation_detail(symbol, motivation_report)
        elif intent == "ipo":
            text = self._fmt_ipo(symbol, ipo_report)
        elif intent == "absorption":
            text = self._fmt_absorption(symbol, ob_report)
        elif intent == "stacking":
            text = self._fmt_stacking(symbol, ob_report)
        elif intent == "institutional":
            text = self._fmt_institutional(symbol, inst_report)
        elif intent == "regime":
            text = self._fmt_regime(symbol, dna_report)
        elif intent == "risk":
            text = self._fmt_risk(symbol, risk_report)
        elif intent == "paper_trade":
            text = self._fmt_paper_trade(symbol, parliament_result, risk_report)
        elif intent == "signals":
            text = self._fmt_signals(symbol, ob_report)
        else:
            text = (
                f"I'm not sure how to interpret that command.\n"
                f"Type 'help' for a list of supported commands."
            )

        comp_status = compliance_report.status if compliance_report else "approved"
        if comp_status == "blocked":
            text = (
                "⛔  This output was blocked by the Compliance Agent.\n"
                + (compliance_report.violations[0] if compliance_report and compliance_report.violations else "")
            )

        return ChatbotResponse(
            text=text,
            symbol=symbol,
            intent=intent,
            compliance_status=comp_status,
            disposition=parliament_result.disposition if parliament_result else None,
        )

    # ── Formatters ─────────────────────────────────────────────────────────────

    @staticmethod
    def _fmt_analyze(
        symbol, ob, dna, inst, risk, parl,
        archetype=None, motivation=None, ipo=None,
    ) -> str:
        lines = [
            f"{'═'*64}",
            f"  MICROSTRUCTURE ANALYSIS  ·  WHAT / WHO / WHY  ·  {symbol or 'N/A'}",
            f"{'═'*64}",
        ]
        # WHAT
        lines.append("  ── WHAT is being ordered? ──────────────────────────────────")
        if ob:
            lines += [
                f"  Order Book Bias   : {ob.directional_bias.upper()}",
                f"  Bias Confidence   : {ob.bias_confidence:.0%}",
                f"  Book Imbalance    : {ob.book_imbalance:+.3f}",
                f"  Spread Multiple   : {ob.spread_multiple:.1f}×",
                f"  Absorption Score  : {ob.absorption_score:.2f}",
                f"  Sweep Intensity   : {ob.sweep_intensity:.2f}",
                f"  Spoof-like Score  : {ob.spoof_like_score:.2f}",
            ]
        # WHO
        lines.append("")
        lines.append("  ── WHO is placing orders? ──────────────────────────────────")
        if archetype:
            lines += [
                f"  Participant Type  : {archetype.archetype.replace('_', ' ').upper()}",
                f"  Probability       : {archetype.probability:.0%}  [{archetype.confidence_label} confidence]",
            ]
            if archetype.secondary_archetype:
                lines.append(
                    f"  Secondary Type    : {archetype.secondary_archetype.replace('_', ' ')} "
                    f"({archetype.secondary_probability:.0%})"
                )
            if archetype.evidence:
                lines.append("  Evidence          :")
                for e in archetype.evidence[:3]:
                    lines.append(f"    • {e}")
        elif inst:
            lines += [
                f"  Behavioral Pattern: {inst.behavioral_label.replace('_', ' ').upper()}",
                f"  Footprint Prob    : {inst.probability:.0%}  [{inst.confidence_label} confidence]",
            ]
        # WHY
        lines.append("")
        lines.append("  ── WHY are they placing orders? ────────────────────────────")
        if motivation:
            lines += [
                f"  Primary Motivation: {motivation.motivation_primary.replace('_', ' ').upper()}",
                f"  Confidence        : {motivation.motivation_confidence.upper()}",
                f"  Alternative       : {motivation.motivation_alternative.replace('_', ' ')}",
                f"  Engine            : {motivation.engine_used}",
            ]
            if motivation.motivation_evidence:
                lines.append("  Motivation Evidence:")
                for e in motivation.motivation_evidence[:3]:
                    lines.append(f"    • {e}")
        # IPO
        if ipo and ipo.is_ipo_symbol:
            lines.append("")
            lines.append("  ── IPO Microstructure ──────────────────────────────────────")
            lines += [
                f"  IPO Phase         : {ipo.price_discovery_phase.replace('_', ' ').upper()}",
                f"  Stabilisation     : {'LIKELY' if ipo.stabilisation_agent_likely else 'Not detected'}",
                f"  Greenshoe-like    : {'LIKELY' if ipo.greenshoe_activity_likely else 'Not detected'}",
                f"  Lock-up Signal    : {'ACTIVE' if ipo.lock_up_proximity_signal else 'Not detected'}",
            ]
        # Regime + Decision
        lines.append("")
        if dna:
            lines += [
                f"  Market Regime     : {dna.regime.upper().replace('_', ' ')}",
                f"  Regime Confidence : {dna.regime_confidence:.0%}",
            ]
        if risk:
            lines += [
                f"  Risk Status       : {risk.risk_status.upper()}",
                f"  Risk Score        : {risk.risk_score:.2f}",
            ]
        if parl:
            lines += [
                "",
                f"  Decision          : {parl.disposition.replace('_', ' ').upper()}",
                f"  Reasoning         : {parl.reasoning}",
            ]
        lines += [
            "",
            f"  ⚠️  {COMPLIANCE_LIMITATIONS_STATEMENT}",
            f"{'─'*64}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _fmt_who(symbol, archetype) -> str:
        if not archetype:
            return "No participant archetype data available. Run 'analyze' first."
        lines = [
            f"WHO Analysis — {symbol or 'N/A'}",
            f"{'─'*44}",
            f"Participant Archetype  : {archetype.archetype.replace('_', ' ').upper()}",
            f"Probability            : {archetype.probability:.0%}",
            f"Confidence             : {archetype.confidence_label.upper()}",
        ]
        if archetype.secondary_archetype:
            lines.append(
                f"Secondary Archetype    : {archetype.secondary_archetype.replace('_', ' ')} "
                f"({archetype.secondary_probability:.0%})"
            )
        lines.append("\nEvidence:")
        for e in archetype.evidence:
            lines.append(f"  • {e}")
        lines += ["", f"⚠️  {archetype.limitations}"]
        return "\n".join(lines)

    @staticmethod
    def _fmt_why(symbol, motivation) -> str:
        if not motivation:
            return "No motivation inference available. Run 'analyze' first."
        lines = [
            f"WHY Analysis — {symbol or 'N/A'}",
            f"{'─'*44}",
            f"Primary Motivation   : {motivation.motivation_primary.replace('_', ' ').upper()}",
            f"Confidence           : {motivation.motivation_confidence.upper()}",
            f"Alternative          : {motivation.motivation_alternative.replace('_', ' ')}",
            f"Archetype Context    : {motivation.archetype_context.replace('_', ' ')}",
            f"Engine               : {motivation.engine_used}",
            "",
            "Motivation Evidence:",
        ]
        for e in motivation.motivation_evidence:
            lines.append(f"  • {e}")
        lines += [
            "",
            "Reasoning Trace:",
            f"  {motivation.reasoning_trace}",
            "",
            f"⚠️  {COMPLIANCE_LIMITATIONS_STATEMENT}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _fmt_what(symbol, ob) -> str:
        if not ob:
            return "No order book data available."
        lines = [
            f"WHAT Analysis — {symbol or 'N/A'}",
            f"{'─'*44}",
            f"Directional Bias     : {ob.directional_bias.upper()}",
            f"Bias Confidence      : {ob.bias_confidence:.0%}",
            f"Book Imbalance       : {ob.book_imbalance:+.3f}",
            f"Spread Multiple      : {ob.spread_multiple:.1f}×",
            f"Absorption Score     : {ob.absorption_score:.2f}  (0=none, 1=strong)",
            f"Sweep Intensity      : {ob.sweep_intensity:.2f}  (0=none, 1=aggressive sweep)",
            f"Iceberg-like Score   : {ob.iceberg_like_score:.2f}",
            f"Spoof-like Score     : {ob.spoof_like_score:.2f}",
            "",
            "Active Signals:",
        ]
        for s in ob.key_signals:
            lines.append(f"  • {s}")
        lines += ["", f"⚠️  {COMPLIANCE_LIMITATIONS_STATEMENT}"]
        return "\n".join(lines)

    @staticmethod
    def _fmt_archetype(symbol, archetype) -> str:
        if not archetype:
            return "No archetype data available. Run 'analyze' first."
        lines = [
            f"Participant Archetype — {symbol or 'N/A'}",
            f"{'─'*48}",
            f"Primary Archetype    : {archetype.archetype.replace('_', ' ').upper()}",
            f"Probability          : {archetype.probability:.0%}",
            f"Confidence           : {archetype.confidence_label.upper()}",
        ]
        if archetype.secondary_archetype:
            lines += [
                f"Secondary Archetype  : {archetype.secondary_archetype.replace('_', ' ')}",
                f"Secondary Prob       : {archetype.secondary_probability:.0%}",
            ]
        lines.append("\nSupporting Evidence:")
        for e in archetype.evidence:
            lines.append(f"  • {e}")
        lines += ["", f"⚠️  {archetype.limitations}"]
        return "\n".join(lines)

    @staticmethod
    def _fmt_motivation_detail(symbol, motivation) -> str:
        if not motivation:
            return "No motivation data available. Run 'analyze' first."
        lines = [
            f"Motivation Inference — {symbol or 'N/A'}",
            f"{'─'*48}",
            f"Primary              : {motivation.motivation_primary.replace('_', ' ').upper()}",
            f"Confidence           : {motivation.motivation_confidence.upper()}",
            f"Alternative          : {motivation.motivation_alternative.replace('_', ' ')}",
            f"Archetype Context    : {motivation.archetype_context.replace('_', ' ')}",
            f"Inference Engine     : {motivation.engine_used}",
            f"Compliance Cleared   : {'✓' if motivation.compliance_cleared else '✗'}",
            "",
            "Motivation Evidence:",
        ]
        for e in motivation.motivation_evidence:
            lines.append(f"  • {e}")
        lines += [
            "",
            "Reasoning Trace:",
            f"  {motivation.reasoning_trace}",
            "",
            f"⚠️  {COMPLIANCE_LIMITATIONS_STATEMENT}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _fmt_ipo(symbol, ipo) -> str:
        if not ipo:
            return "No IPO microstructure data available."
        lines = [
            f"IPO Microstructure — {symbol or 'N/A'}",
            f"{'─'*46}",
            f"IPO Symbol           : {'YES' if ipo.is_ipo_symbol else 'No (standard analysis)'}",
            f"Price Discovery Phase: {ipo.price_discovery_phase.replace('_', ' ').upper()}",
            f"Stabilisation Likely : {'⚠ YES' if ipo.stabilisation_agent_likely else 'Not detected'}",
            f"Greenshoe-like       : {'⚠ YES' if ipo.greenshoe_activity_likely else 'Not detected'}",
            f"Lock-up Proximity    : {'⚠ SIGNAL ACTIVE' if ipo.lock_up_proximity_signal else 'Not detected'}",
            f"Confidence           : {ipo.confidence_label.upper()}",
            "",
            "IPO Signals:",
        ]
        for s in ipo.ipo_specific_signals:
            lines.append(f"  • {s}")
        lines += [
            "",
            "Note: Stabilisation and greenshoe labels describe observable patterns only.",
            "Cross-reference with IPO prospectus (S-1) and lock-up expiry calendar.",
            f"⚠️  {COMPLIANCE_LIMITATIONS_STATEMENT}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _fmt_absorption(symbol, ob) -> str:
        if not ob:
            return "No order book data available."
        score = ob.absorption_score
        label = "elevated" if score > 0.6 else "moderate" if score > 0.3 else "low"
        return (
            f"Buyer Absorption Analysis — {symbol or 'N/A'}\n"
            f"{'─'*40}\n"
            f"Absorption Score  : {score:.2f} ({label})\n"
            f"Book Imbalance    : {ob.book_imbalance:+.3f}\n\n"
            + (
                f"Large buy prints are being absorbed at or near the bid without sustained "
                f"upward price continuation. This pattern is consistent with seller supply "
                f"meeting buyer demand at the level."
                if score > 0.5 else
                "No significant buyer absorption detected at this time."
            )
            + f"\n\n⚠️  {COMPLIANCE_LIMITATIONS_STATEMENT}"
        )

    @staticmethod
    def _fmt_stacking(symbol, ob) -> str:
        if not ob:
            return "No order book data available."
        stacking = "stacking_ask" in [s.lower() for s in ob.key_signals if "stacking" in s.lower()]
        ask_signals = [s for s in ob.key_signals if "ask" in s.lower()]
        return (
            f"Ask-Side Stacking Analysis — {symbol or 'N/A'}\n"
            f"{'─'*40}\n"
            f"Ask Stacking      : {'DETECTED' if stacking else 'Not detected'}\n"
            f"Spoof-like Score  : {ob.spoof_like_score:.2f}\n"
            f"Book Imbalance    : {ob.book_imbalance:+.3f}\n\n"
            + ("\n".join(ask_signals) if ask_signals else "No significant ask-side stacking detected.")
            + f"\n\n⚠️  {COMPLIANCE_LIMITATIONS_STATEMENT}"
        )

    @staticmethod
    def _fmt_institutional(symbol, inst) -> str:
        if not inst:
            return "No institutional footprint data available."
        lines = [
            f"Institutional-Style Activity — {symbol or 'N/A'}",
            f"{'─'*44}",
            f"Behavioral Pattern : {inst.behavioral_label.replace('_', ' ').upper()}",
            f"Probability        : {inst.probability:.0%}",
            f"Confidence         : {inst.confidence_label.upper()}",
            "",
            "Reasoning:",
        ]
        for r in inst.reasoning:
            lines.append(f"  • {r}")
        lines += ["", f"⚠️  {inst.limitations}"]
        return "\n".join(lines)

    @staticmethod
    def _fmt_regime(symbol, dna) -> str:
        if not dna:
            return "No market regime data available."
        lines = [
            f"Market Regime — {symbol or 'N/A'}",
            f"{'─'*36}",
            f"Regime     : {dna.regime.upper().replace('_', ' ')}",
            f"Confidence : {dna.regime_confidence:.0%}",
            f"Stability  : {dna.regime_stability:.0%}",
            "",
            "Supporting signals:",
        ]
        for s in dna.supporting_signals:
            lines.append(f"  • {s}")
        return "\n".join(lines)

    @staticmethod
    def _fmt_risk(symbol, risk) -> str:
        if not risk:
            return "No risk assessment available."
        lines = [
            f"Risk Assessment — {symbol or 'N/A'}",
            f"{'─'*38}",
            f"Status       : {risk.risk_status.upper()}",
            f"Risk Score   : {risk.risk_score:.2f}  (0=low, 1=high)",
            f"Spread OK    : {'✓' if risk.spread_ok else '✗'}",
            f"Data OK      : {'✓' if risk.data_quality_ok else '✗'}",
            f"Model Conf.  : {'✓' if risk.model_confidence_ok else '✗'}",
            f"News Lockout : {'YES — trading paused' if risk.news_lockout else 'No active lockout'}",
        ]
        if risk.veto_reasons:
            lines.append("\nRisk warnings:")
            for v in risk.veto_reasons:
                lines.append(f"  ⚠  {v}")
        lines.append("\nAll execution is paper-only by default. Human approval required for live trading.")
        return "\n".join(lines)

    @staticmethod
    def _fmt_paper_trade(symbol, parl, risk) -> str:
        if not parl:
            return "No Decision Parliament result available."
        disp = parl.disposition
        lines = [
            f"Paper Trade Assessment — {symbol or 'N/A'}",
            f"{'─'*44}",
            f"Disposition : {disp.replace('_', ' ').upper()}",
            f"Reasoning   : {parl.reasoning}",
            "",
            f"Agent Votes:",
            f"  Order Book Analyst : {parl.ob_analyst_vote.upper()} ({parl.ob_analyst_confidence:.0%})",
            f"  Market DNA         : {parl.dna_regime.upper()} ({parl.dna_confidence:.0%})",
            f"  Inst. Footprint    : {parl.inst_footprint_label.replace('_',' ').upper()} ({parl.inst_footprint_prob:.0%})",
            f"  Risk Governor      : {parl.risk_status.upper()}",
            f"  Compliance         : {parl.compliance_status.upper()}",
        ]
        if parl.participant_archetype:
            lines.append(
                f"  Archetype (Phase 2A): {parl.participant_archetype.replace('_', ' ')} "
                f"({parl.participant_archetype_prob:.0%})"
            )
        if parl.motivation_primary:
            lines.append(
                f"  Motivation (Phase 2A): {parl.motivation_primary.replace('_', ' ')} "
                f"[{parl.motivation_confidence}]"
            )
        if disp == "paper_trade_approved":
            lines.append(
                "\n✅  Setup approved for PAPER TRADE ONLY. "
                "No live capital. Human review before any live execution."
            )
        elif disp == "risk_veto":
            if risk and risk.veto_reasons:
                lines.append(f"\n⛔  Risk Veto: {risk.veto_reasons[0]}")
        elif disp == "data_insufficient":
            lines.append("\n⚠️  Data quality is insufficient. Analysis paused.")
        else:
            lines.append(f"\n⏸  Outcome: {disp.replace('_', ' ')}. No execution recommended.")
        lines += ["", f"⚠️  {COMPLIANCE_LIMITATIONS_STATEMENT}"]
        return "\n".join(lines)

    @staticmethod
    def _fmt_signals(symbol, ob) -> str:
        if not ob:
            return "No active signals."
        lines = [
            f"Active Order Book Signals — {symbol or 'N/A'}",
            f"{'─'*44}",
        ]
        for s in ob.key_signals:
            lines.append(f"  • {s}")
        return "\n".join(lines)
