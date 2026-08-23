"""
agents/order_book_analyst.py – Order Book Analyst Agent (Phase 1).

Interprets the fully processed OrderBookState and produces a structured
directional assessment with supporting signals.
"""

from __future__ import annotations

from src.features.engineer import FeatureVector
from src.order_book.engine import OrderBookState
from src.agents.models import OrderBookAnalystReport


class OrderBookAnalystAgent:
    """
    Analyses bid/ask pressure, imbalance, stacking, pulling, absorption,
    sweep activity, spread behaviour, and microprice pressure.

    Returns a structured OrderBookAnalystReport.
    """

    def analyse(
        self,
        state: OrderBookState,
        features: FeatureVector,
    ) -> OrderBookAnalystReport:
        bias, confidence = self._compute_bias(features)
        return OrderBookAnalystReport(
            symbol=state.symbol,
            timestamp_ns=state.timestamp_ns,
            directional_bias=bias,
            bias_confidence=confidence,
            key_signals=state.signals,
            absorption_score=state.absorption_score,
            sweep_intensity=state.sweep_intensity,
            spoof_like_score=state.spoof_like_score,
            iceberg_like_score=state.iceberg_like_score,
            spread_multiple=state.spread_multiple,
            book_imbalance=state.book_imbalance,
        )

    @staticmethod
    def _compute_bias(fv: FeatureVector) -> tuple[str, float]:
        """
        Combine multiple signals into a directional bias score.
        Returns (direction, confidence).
        """
        score = 0.0

        # Order flow imbalance (primary signal)
        score += fv.order_flow_imbalance * 0.30

        # Book imbalance
        score += fv.bid_ask_imbalance * 0.20

        # Microprice bias
        score += fv.microprice_bias * 200 * 0.10   # normalise pips

        # Accumulation vs distribution
        score += (fv.accumulation_score - fv.distribution_score) * 0.20

        # Buy/sell ratio (centralised around 0.5)
        score += (fv.rolling_buy_sell_ratio - 0.5) * 2 * 0.10

        # Absorption increases conviction in the dominant side
        if fv.order_flow_imbalance > 0 and fv.absorption_score > 0.5:
            score += 0.10
        elif fv.order_flow_imbalance < 0 and fv.absorption_score > 0.5:
            score -= 0.10

        # Stacking on ask = bearish signal
        if fv.stacking_ask:
            score -= 0.10
        if fv.stacking_bid:
            score += 0.10

        # Pulling on bid = bearish signal
        if fv.pulling_bid:
            score -= 0.10
        if fv.pulling_ask:
            score += 0.10

        if score > 0.15:
            direction = "bullish"
        elif score < -0.15:
            direction = "bearish"
        else:
            direction = "neutral"

        confidence = round(min(abs(score), 1.0), 3)
        return direction, confidence
