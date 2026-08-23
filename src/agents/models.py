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
class ParticipantArchetypeReport:
    """WHO layer — behavioural archetype classification (Phase 2A)."""
    symbol: str
    timestamp_ns: int
    archetype: str                 # institutional_accumulator | retail_sentiment_buyer |
                                   # algorithmic_market_maker | momentum_ignitor |
                                   # strategic_seller | informed_flow_proxy | unknown_mixed
    probability: float             # 0.0 – 1.0
    confidence_label: str          # high | medium | low | insufficient_data
    secondary_archetype: Optional[str]
    secondary_probability: float
    evidence: list[str]
    limitations: str               # always populated – compliance requirement


@dataclass
class IPOMicrostructureReport:
    """IPO-specific microstructure signals (Phase 2A)."""
    symbol: str
    timestamp_ns: int
    is_ipo_symbol: bool
    price_discovery_phase: str     # pre_open | price_discovery | stabilisation |
                                   # post_stabilisation | normal_trading
    greenshoe_activity_likely: bool
    stabilisation_agent_likely: bool
    lock_up_proximity_signal: bool  # within 30 days of lock-up expiry
    ipo_specific_signals: list[str]
    confidence_label: str


@dataclass
class MotivationInferenceReport:
    """WHY layer — motivation taxonomy inference (Phase 2A)."""
    symbol: str
    timestamp_ns: int
    motivation_primary: str        # see MOTIVATION_TAXONOMY in motivation_inference_agent.py
    motivation_confidence: str     # high | medium | low
    motivation_evidence: list[str]
    motivation_alternative: str
    archetype_context: str         # the WHO archetype that drove this inference
    reasoning_trace: str           # rule-based narrative or DeepSeek reasoning trace
    engine_used: str               # "rule_based" | "deepseek"
    compliance_cleared: bool


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
    # Phase 2A extended fields (optional – None when agents not yet wired)
    participant_archetype: Optional[str] = None
    participant_archetype_prob: Optional[float] = None
    motivation_primary: Optional[str] = None
    motivation_confidence: Optional[str] = None
    ipo_phase: Optional[str] = None
    timestamp_ms: int = field(default_factory=lambda: int(time.time() * 1000))
