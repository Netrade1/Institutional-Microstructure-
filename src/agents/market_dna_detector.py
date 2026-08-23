"""
agents/market_dna_detector.py – Market-DNA Detector Agent (Phase 1).

Classifies the current market regime from order book and feature data.

Regimes:
    trending_up | trending_down | ranging | breakout | reversal |
    compression | expansion | accumulation | distribution | trap | ambiguous
"""

from __future__ import annotations

import math

from src.features.engineer import FeatureVector
from src.order_book.engine import OrderBookState
from src.agents.models import MarketDNAReport


class MarketDNADetectorAgent:
    """
    Rule-based regime classifier for Phase 1.
    Phase 4 will replace the rule layer with an HMM / TCN model.
    """

    def classify(
        self,
        state: OrderBookState,
        features: FeatureVector,
    ) -> MarketDNAReport:
        regime, confidence, signals, stability = self._classify_regime(state, features)
        return MarketDNAReport(
            symbol=state.symbol,
            timestamp_ns=state.timestamp_ns,
            regime=regime,
            regime_confidence=confidence,
            supporting_signals=signals,
            regime_stability=stability,
        )

    @staticmethod
    def _classify_regime(
        state: OrderBookState, fv: FeatureVector
    ) -> tuple[str, float, list[str], float]:
        signals: list[str] = []
        scores: dict[str, float] = {}

        # ── Compression ───────────────────────────────────────────────────────
        compression = 0.0
        if not math.isnan(fv.bb_width) and fv.bb_width < 0.5:
            compression += 0.4
            signals.append("Bollinger Band width compressed.")
        if state.spread_multiple < 1.2:
            compression += 0.2
            signals.append("Spread near historical average.")
        scores["compression"] = compression

        # ── Breakout ──────────────────────────────────────────────────────────
        breakout = 0.0
        if fv.sweep_intensity > 0.5:
            breakout += 0.35
            signals.append(f"Sweep intensity elevated ({fv.sweep_intensity:.2f}).")
        if fv.rvol > 1.8:
            breakout += 0.30
            signals.append(f"Relative volume elevated ({fv.rvol:.1f}x).")
        if fv.breakout_confirmation_score > 0.5:
            breakout += 0.35
        scores["breakout"] = breakout

        # ── Accumulation ──────────────────────────────────────────────────────
        accum = 0.0
        if fv.accumulation_score > 0.5:
            accum += 0.5
            signals.append(f"Accumulation score {fv.accumulation_score:.2f}.")
        if state.absorption_score > 0.5:
            accum += 0.3
        if state.bid_replenishment_rate > 0.3:
            accum += 0.2
        scores["accumulation"] = accum

        # ── Distribution ──────────────────────────────────────────────────────
        distrib = 0.0
        if fv.distribution_score > 0.5:
            distrib += 0.5
            signals.append(f"Distribution score {fv.distribution_score:.2f}.")
        if state.stacking_ask:
            distrib += 0.3
        scores["distribution"] = distrib

        # ── Ranging ───────────────────────────────────────────────────────────
        ranging = 0.0
        if abs(state.book_imbalance) < 0.15 and state.sweep_intensity < 0.3:
            ranging += 0.5
            signals.append("Low imbalance and low sweep: ranging market.")
        if fv.rvol < 0.8:
            ranging += 0.3
        scores["ranging"] = ranging

        # ── Trap ─────────────────────────────────────────────────────────────
        trap = 0.0
        if fv.liquidity_trap_risk > 0.5:
            trap += 0.5
            signals.append(f"Liquidity trap risk {fv.liquidity_trap_risk:.2f}.")
        if fv.false_breakout_prob > 0.4:
            trap += 0.3
        scores["trap"] = trap

        # ── Expansion (post-breakout volatility) ─────────────────────────────
        expansion = 0.0
        if not math.isnan(fv.bb_width) and fv.bb_width > 1.5:
            expansion += 0.4
        if not math.isnan(fv.atr_14) and fv.atr_14 > 0:
            expansion += 0.3
        scores["expansion"] = expansion

        # ── Select dominant regime ────────────────────────────────────────────
        if not scores:
            return "ambiguous", 0.3, signals, 0.3

        best_regime = max(scores, key=lambda k: scores[k])
        best_score = scores[best_regime]

        if best_score < 0.3:
            regime = "ambiguous"
            confidence = 0.3
        else:
            regime = best_regime
            confidence = round(min(best_score, 1.0), 3)

        stability = round(1.0 - (len([s for s in scores.values() if s > 0.3]) - 1) * 0.1, 3)
        stability = max(0.0, stability)

        return regime, confidence, signals[:5], stability
