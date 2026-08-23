"""
orchestrator.py – Agentic Orchestration Layer (Phase 1).

Wires together all agents into a single synchronous processing pipeline.
In Phase 3, this will be replaced by a LangGraph / CrewAI graph.

Pipeline per tick:
    1. Data Integrity Agent  →  FeedHealthReport
    2. Order Book Engine     →  OrderBookState
    3. Feature Engineer      →  FeatureVector
    4. Order Book Analyst    →  OrderBookAnalystReport
    5. Market-DNA Detector   →  MarketDNAReport
    6. Institutional Footprint Agent → InstitutionalFootprintReport
    7. Risk Governor         →  RiskGovernorReport
    8. Compliance Agent      →  ComplianceReport
    9. Decision Parliament   →  DecisionParliamentResult
   10. Audit Ledger          →  writes JSONL record
   11. Chatbot Interface     →  human-readable response (on demand)
"""

from __future__ import annotations

from src.agents.compliance_agent import ComplianceAgent
from src.agents.decision_parliament import DecisionParliament
from src.agents.institutional_footprint import InstitutionalFootprintAgent
from src.agents.ipo_microstructure_agent import IPOMicrostructureAgent
from src.agents.market_dna_detector import MarketDNADetectorAgent
from src.agents.models import DecisionParliamentResult
from src.agents.motivation_inference_agent import MotivationInferenceAgent
from src.agents.order_book_analyst import OrderBookAnalystAgent
from src.agents.participant_archetype_agent import ParticipantArchetypeAgent
from src.agents.risk_governor import RiskGovernorAgent
from src.audit.ledger import AuditLedger
from src.chatbot.interface import ChatbotInterface, ChatbotResponse
from src.data_intake.data_integrity_agent import DataIntegrityAgent
from src.data_intake.models import FeedHealthReport, OrderBookSnapshot, Trade
from src.features.engineer import FeatureEngineer, FeatureVector
from src.order_book.engine import OrderBookEngine, OrderBookState


class Orchestrator:
    """
    Central pipeline coordinator.

    Instantiate once per symbol and call process() after each
    (snapshot, trades) pair from the feed.
    """

    def __init__(self, symbol: str, feature_log_every: int = 10) -> None:
        self.symbol = symbol
        self._feature_log_every = feature_log_every
        self._tick = 0

        # ── Agents ────────────────────────────────────────────────────────────
        self._integrity = DataIntegrityAgent()
        self._ob_engine = OrderBookEngine()
        self._feature_eng = FeatureEngineer(symbol)
        self._ob_analyst = OrderBookAnalystAgent()
        self._dna_detector = MarketDNADetectorAgent()
        self._inst_footprint = InstitutionalFootprintAgent()
        self._risk_governor = RiskGovernorAgent()
        self._compliance = ComplianceAgent()
        self._parliament = DecisionParliament()
        self._chatbot = ChatbotInterface()
        self._ledger = AuditLedger()
        # Phase 2A agents
        self._archetype_agent = ParticipantArchetypeAgent()
        self._motivation_agent = MotivationInferenceAgent()
        self._ipo_agent = IPOMicrostructureAgent()

        # ── Latest state cache (for dashboard reads) ──────────────────────────
        self.latest_health: FeedHealthReport | None = None
        self.latest_state: OrderBookState | None = None
        self.latest_features: FeatureVector | None = None
        self.latest_result: DecisionParliamentResult | None = None
        # Phase 2A caches
        self.latest_archetype = None
        self.latest_motivation = None
        self.latest_ipo = None

    # ── Public ────────────────────────────────────────────────────────────────

    def process(
        self,
        snapshot: OrderBookSnapshot,
        trades: list[Trade],
    ) -> DecisionParliamentResult:
        """Run full pipeline for one tick. Returns the parliament result."""
        self._tick += 1

        # 1. Data integrity
        health = self._integrity.check(snapshot, trades)
        self._ledger.log_health(health)

        # 2. Order book processing
        state = self._ob_engine.process(snapshot, trades)

        # 3. Feature engineering
        features = self._feature_eng.update(state, trades)

        # 4. Order book analyst
        ob_report = self._ob_analyst.analyse(state, features)

        # 5. Market-DNA detector
        dna_report = self._dna_detector.classify(state, features)

        # 6. Institutional footprint
        inst_report = self._inst_footprint.analyse(state, features)

        # 7. Risk governor
        risk_report = self._risk_governor.evaluate(state, features, health)

        # 8. Compliance (check the human explanation before delivery)
        pre_text = (
            f"{ob_report.directional_bias} {dna_report.regime} "
            f"{inst_report.behavioral_label} {' '.join(state.signals)}"
        )
        compliance_report = self._compliance.check_output(self.symbol, pre_text)

        # 9. Phase 2A — WHO / WHY / IPO agents
        archetype_report = self._archetype_agent.analyse(state, features)
        motivation_report = self._motivation_agent.analyse(state, features, archetype_report)
        ipo_report = self._ipo_agent.analyse(state, features)

        # 10. Decision parliament (extended with Phase 2A reports)
        result = self._parliament.deliberate(
            ob_report, dna_report, inst_report, risk_report, compliance_report,
            archetype_report=archetype_report,
            motivation_report=motivation_report,
            ipo_report=ipo_report,
        )

        # 11. Audit
        self._ledger.log_decision(result)
        self._ledger.log_motivation(motivation_report)
        if self._tick % self._feature_log_every == 0:
            self._ledger.log_features(features)

        # Cache
        self.latest_health = health
        self.latest_state = state
        self.latest_features = features
        self.latest_result = result
        self.latest_archetype = archetype_report
        self.latest_motivation = motivation_report
        self.latest_ipo = ipo_report

        return result

    def chat(self, user_input: str) -> ChatbotResponse:
        """Answer a user query using the latest pipeline state."""
        if not self.latest_result:
            return self._chatbot.respond(user_input)

        # Re-run compliance on the chatbot output
        state = self.latest_state
        features = self.latest_features
        result = self.latest_result

        # Reconstruct minimal agent reports from cached state
        ob_report = self._ob_analyst.analyse(state, features)
        dna_report = self._dna_detector.classify(state, features)
        inst_report = self._inst_footprint.analyse(state, features)
        risk_report = self._risk_governor.evaluate(
            state, features, self.latest_health
        )

        response = self._chatbot.respond(
            user_input,
            ob_report=ob_report,
            dna_report=dna_report,
            inst_report=inst_report,
            risk_report=risk_report,
            parliament_result=result,
            archetype_report=self.latest_archetype,
            motivation_report=self.latest_motivation,
            ipo_report=self.latest_ipo,
        )

        # Final compliance gate on the response text
        compliance_check = self._compliance.check_output(self.symbol, response.text)
        if compliance_check.status == "blocked":
            response.compliance_status = "blocked"
            response.text = (
                "⛔  Response blocked by Compliance Agent. "
                + (compliance_check.violations[0] if compliance_check.violations else "")
            )

        return response

    def close(self) -> None:
        self._ledger.close()
