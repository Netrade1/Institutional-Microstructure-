"""
agents/ipo_microstructure_agent.py – IPO Microstructure Agent (Phase 2A).

Detects IPO-specific microstructure signals:
  - Price discovery phase classification
  - Stabilisation agent activity patterns
  - Greenshoe (over-allotment option) exercise-like behaviour
  - Lock-up expiry proximity signals
  - Underwriter price support patterns

These signals are observable from Level 2 data alone.  Named entity claims
(e.g., 'the underwriter is Goldman Sachs') are prohibited.

IPO Phases:
    pre_open           – pre-market, indicative only
    price_discovery    – first 30–90 minutes of trading; wide spread, high volume volatility
    stabilisation      – potential underwriter support below IPO price
    post_stabilisation – stabilisation period ended
    normal_trading     – typical secondary-market microstructure
"""

from __future__ import annotations

from src.config import COMPLIANCE_LIMITATIONS_STATEMENT, IPO_SYMBOLS
from src.features.engineer import FeatureVector
from src.order_book.engine import OrderBookState
from src.agents.models import IPOMicrostructureReport


class IPOMicrostructureAgent:
    """
    IPO-specific microstructure signal detector.

    Identifies observable patterns associated with IPO price dynamics.
    All claims are behavioural — no named participant assertions.
    """

    def analyse(
        self,
        state: OrderBookState,
        features: FeatureVector,
    ) -> IPOMicrostructureReport:
        is_ipo = state.symbol.upper() in {s.upper() for s in IPO_SYMBOLS}
        signals: list[str] = []

        phase = self._classify_phase(state, features, signals)
        greenshoe = self._detect_greenshoe_like(state, features, signals)
        stabilisation = self._detect_stabilisation(state, features, signals)
        lock_up = self._detect_lock_up_proximity(state, features, signals)

        if not signals:
            signals.append("No IPO-specific microstructure signals detected.")

        conf = "high" if len(signals) >= 3 else "medium" if len(signals) >= 1 else "low"

        return IPOMicrostructureReport(
            symbol=state.symbol,
            timestamp_ns=state.timestamp_ns,
            is_ipo_symbol=is_ipo,
            price_discovery_phase=phase,
            greenshoe_activity_likely=greenshoe,
            stabilisation_agent_likely=stabilisation,
            lock_up_proximity_signal=lock_up,
            ipo_specific_signals=signals,
            confidence_label=conf,
        )

    @staticmethod
    def _classify_phase(
        state: OrderBookState,
        fv: FeatureVector,
        signals: list[str],
    ) -> str:
        """
        Infer approximate IPO trading phase from microstructure signals.
        """
        # Wide spread + extreme volume = price discovery
        if state.spread_multiple > 3.0 and fv.rvol > 4.0:
            signals.append(
                f"Extreme spread ({state.spread_multiple:.1f}×) and relative volume "
                f"({fv.rvol:.1f}×) — consistent with IPO price discovery phase."
            )
            return "price_discovery"

        # Bid absorption below reference + tight spread on bid side = stabilisation
        if (
            state.absorption_score > 0.6
            and fv.vwap_deviation < -0.005
            and not state.stacking_ask
        ):
            signals.append(
                "Consistent bid absorption below VWAP without ask stacking — "
                "pattern consistent with price stabilisation activity."
            )
            return "stabilisation"

        # Moderate spread, returning to normal depth
        if state.spread_multiple < 1.5 and fv.rvol < 2.0:
            return "normal_trading"

        # Default for elevated but non-extreme conditions
        if state.spread_multiple > 1.5 and fv.rvol > 2.0:
            return "post_stabilisation"

        return "normal_trading"

    @staticmethod
    def _detect_greenshoe_like(
        state: OrderBookState,
        fv: FeatureVector,
        signals: list[str],
    ) -> bool:
        """
        Detect patterns consistent with greenshoe option exercise.
        Greenshoe typically creates sustained bid support just below IPO price.
        """
        # Strong bid absorption + replenishment at a consistent level without price advance
        if (
            state.absorption_score > 0.55
            and state.bid_replenishment_rate > 0.40
            and fv.vwap_deviation < 0.002
            and fv.order_flow_imbalance > 0.10
        ):
            signals.append(
                "Sustained bid absorption with high replenishment rate near reference price — "
                "pattern is consistent with over-allotment support activity (greenshoe-like)."
            )
            return True
        return False

    @staticmethod
    def _detect_stabilisation(
        state: OrderBookState,
        fv: FeatureVector,
        signals: list[str],
    ) -> bool:
        """
        Detect patterns consistent with underwriter price stabilisation.
        Stabilisation creates mechanical bid support at or near the IPO offer price.
        """
        if (
            state.absorption_score > 0.65
            and fv.vwap_deviation < -0.003
            and fv.accumulation_score > 0.45
            and state.stacking_bid
        ):
            signals.append(
                "Large bid stacking + absorption below VWAP — observable pattern is consistent "
                "with stabilisation-agent-like support behaviour."
            )
            return True
        return False

    @staticmethod
    def _detect_lock_up_proximity(
        state: OrderBookState,
        fv: FeatureVector,
        signals: list[str],
    ) -> bool:
        """
        Detect order flow patterns that may coincide with lock-up expiry proximity.
        These are purely behavioural signals — calendar data is not available at runtime
        without a data feed.  The signal is a pattern flag only.
        """
        # Distribution pressure + growing relative volume = potential insider/employee selling
        if (
            fv.distribution_score > 0.55
            and fv.rvol > 2.5
            and fv.order_flow_imbalance < -0.15
        ):
            signals.append(
                f"Distribution score ({fv.distribution_score:.2f}) with elevated relative volume "
                f"({fv.rvol:.1f}×) and negative OFI — cross-reference with IPO lock-up calendar. "
                "Pattern may be consistent with post-lock-up selling pressure."
            )
            return True
        return False
