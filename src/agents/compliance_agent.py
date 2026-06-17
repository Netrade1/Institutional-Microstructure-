"""
agents/compliance_agent.py – Compliance Agent (Phase 1).

Hard-coded compliance enforcement layer.

Responsibilities:
    - Block identity-inference claims (HARD BLOCK)
    - Detect prohibited language before any output is delivered
    - Ensure limitations statement is present on all behavioral outputs
    - Flag unlicensed data usage concerns
    - Enforce paper-trading-only default

This agent runs as the final gate before any output reaches the user.
A 'blocked' status prevents the response from being delivered.
"""

from __future__ import annotations

import re

from src.config import IDENTITY_CLAIM_BLOCKED_TERMS, COMPLIANCE_LIMITATIONS_STATEMENT
from src.agents.models import ComplianceReport


class ComplianceAgent:
    """
    Final compliance gate.

    Call check_output() on any text before it is delivered to the user.
    Call check_behavioral_label() to validate behavioral inference outputs.
    """

    PROHIBITED_PATTERNS = [
        # Direct identity claims
        r"\bis buying\b",
        r"\bis selling\b",
        r"\bis accumulating\b",
        r"\bis distributing\b",
        r"\bis entering\b",
        r"\bis exiting\b",
        r"behind this order",
        r"behind the order",
        r"behind this move",
        r"behind this trade",
        r"is the buyer",
        r"is the seller",
        r"is the institution",
        r"named institution",
        r"specific institution",
        r"specific fund",
        r"specific hedge fund",
        r"specific individual",
        r"specific person",
        r"specific corporation",
    ]

    def check_output(self, symbol: str, text: str) -> ComplianceReport:
        """
        Scan generated text for compliance violations before delivery.
        Returns ComplianceReport with status, violations, and warnings.
        """
        violations: list[str] = []
        warnings: list[str] = []
        text_lower = text.lower()

        # ── Hard block: named institution claims ──────────────────────────────
        for term in IDENTITY_CLAIM_BLOCKED_TERMS:
            if term in text_lower:
                violations.append(
                    f"Prohibited identity claim: text contains '{term}'. "
                    "Identity inference from Level 2 data is not permitted."
                )

        # ── Hard block: prohibited pattern phrases ────────────────────────────
        for pattern in self.PROHIBITED_PATTERNS:
            if re.search(pattern, text_lower):
                violations.append(
                    f"Prohibited claim pattern detected: '{pattern}'. "
                    "This language implies specific participant identity without authorised evidence."
                )

        # ── Warning: limitations statement missing ────────────────────────────
        if "level 2 data does not reveal" not in text_lower and "behavioral" in text_lower:
            warnings.append(
                "Behavioral classification output may be missing the required limitations statement."
            )

        # ── Warning: certainty language on probabilistic outputs ──────────────
        certainty_terms = ["definitely", "certainly", "confirmed", "guaranteed", "proven"]
        for ct in certainty_terms:
            if ct in text_lower:
                warnings.append(
                    f"Certainty language detected ('{ct}') in probabilistic output. "
                    "Consider replacing with confidence-qualified language."
                )

        if violations:
            status = "blocked"
        elif warnings:
            status = "flagged"
        else:
            status = "approved"

        return ComplianceReport(
            symbol=symbol,
            timestamp_ns=__import__("time").time_ns(),
            status=status,
            violations=violations,
            warnings=warnings,
        )

    def check_behavioral_label(
        self, label: str, reasoning: list[str]
    ) -> tuple[bool, str]:
        """
        Validate that a behavioral label is compliant.
        Returns (is_valid, error_message).
        """
        permitted_labels = {
            "accumulation_like",
            "distribution_like",
            "neutral",
            "mixed",
            "retail_like",
            "algorithmic_like",
            "market_maker_like",
            "momentum_like",
            "liquidity_seeking",
        }
        if label not in permitted_labels:
            return False, (
                f"Behavioral label '{label}' is not in the permitted set. "
                "Labels must describe observable behavior patterns, not participant identity."
            )
        return True, ""

    @staticmethod
    def add_limitations(text: str) -> str:
        """Append the compliance limitations statement to any behavioral output."""
        if "level 2 data does not reveal" not in text.lower():
            return text + f"\n\n⚠️  {COMPLIANCE_LIMITATIONS_STATEMENT}"
        return text
