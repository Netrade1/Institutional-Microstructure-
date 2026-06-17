"""
agents/models.py – Agent output data models.

All agent assessments are typed dataclasses.  The Decision Parliament
collects these and computes the final disposition.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class OrderBookAnalystReport:
    symbol: str
    timestamp_ns: int
    directional_bias: str          # "bullish" | "bearish" | "neutral"
    bias_confidence: float         # 0.0 – 1.0
    key_signals: list[str]
    absorption_score: float
    sweep_intensity: float
    spoof_like_score: float
    iceberg_like_score: float
    spread_multiple: float
    book_imbalance: float


@dataclass
class MarketDNAReport:
    symbol: str
    timestamp_ns: int
    regime: str                    # trend | range | breakout | reversal | compression |
                                   # expansion | accumulation | distribution | trap | ambiguous
    regime_confidence: float
    supporting_signals: list[str]
    regime_stability: float        # 0.0 – 1.0


@dataclass
class InstitutionalFootprintReport:
    symbol: str
    timestamp_ns: int
    behavioral_label: str          # accumulation_like | distribution_like | neutral | mixed
    probability: float
    confidence_label: str          # low | medium | high | insufficient_data
    reasoning: list[str]
    limitations: str               # always populated – compliance requirement


@dataclass
class RiskGovernorReport:
    symbol: str
    timestamp_ns: int
    risk_status: str               # clear | caution | veto
    risk_score: float              # 0.0 – 1.0 (higher = more risk)
    veto: bool
    veto_reasons: list[str]
    spread_ok: bool
    data_quality_ok: bool
    model_confidence_ok: bool
    news_lockout: bool


@dataclass
class ComplianceReport:
    symbol: str
    timestamp_ns: int
    status: str                    # approved | flagged | blocked
    violations: list[str]
    warnings: list[str]


@dataclass
class DecisionParliamentResult:
    symbol: str
    timestamp_ns: int
    disposition: str               # research_approved | watchlist | paper_trade_approved |
                                   # human_review | rejected | risk_veto | data_insufficient
    reasoning: str
    ob_analyst_vote: str
    ob_analyst_confidence: float
    dna_regime: str
    dna_confidence: float
    inst_footprint_label: str
    inst_footprint_prob: float
    risk_status: str
    compliance_status: str
    human_explanation: str
    limitations: str
    timestamp_ms: int = field(default_factory=lambda: int(time.time() * 1000))
