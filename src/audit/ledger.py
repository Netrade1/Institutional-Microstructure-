"""
audit/ledger.py – Append-only JSONL Audit Ledger (Phase 1).

Every system decision, agent vote, feature snapshot, and risk assessment
is written to a date-partitioned JSONL file.

Design principles:
    - Append-only: records are never modified or deleted
    - Every record is a self-contained JSON object on a single line
    - Human-readable and machine-parseable
    - Phase 2+ will add PostgreSQL/Parquet archival layer

Record types:
    decision      – Decision Parliament result (written for every tick)
    data_quality  – FeedHealthReport
    feature       – FeatureVector snapshot (sampled, not every tick)
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

import orjson

from src.config import AUDIT_LOG_DIR
from src.agents.models import DecisionParliamentResult
from src.data_intake.models import FeedHealthReport
from src.features.engineer import FeatureVector


class AuditLedger:
    """
    Thread-safe append-only JSONL audit ledger.

    One file per symbol per date: e.g., NVDA_2026-06-17.jsonl
    """

    def __init__(self, log_dir: Path = AUDIT_LOG_DIR) -> None:
        self._log_dir = log_dir
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._handles: dict[str, object] = {}

    # ── Public ────────────────────────────────────────────────────────────────

    def log_decision(self, result: DecisionParliamentResult) -> None:
        record = {
            "record_type": "decision",
            "timestamp": result.timestamp_ns,
            "timestamp_ms": result.timestamp_ms,
            "symbol": result.symbol,
            "disposition": result.disposition,
            "reasoning": result.reasoning,
            "ob_analyst_vote": result.ob_analyst_vote,
            "ob_analyst_confidence": result.ob_analyst_confidence,
            "dna_regime": result.dna_regime,
            "dna_confidence": result.dna_confidence,
            "inst_footprint_label": result.inst_footprint_label,
            "inst_footprint_prob": result.inst_footprint_prob,
            "risk_status": result.risk_status,
            "compliance_status": result.compliance_status,
            "human_explanation": result.human_explanation,
            "limitations": result.limitations,
        }
        self._write(result.symbol, record)

    def log_health(self, health: FeedHealthReport) -> None:
        record = {
            "record_type": "data_quality",
            "timestamp": health.timestamp_ns,
            "symbol": health.symbol,
            "feed": health.feed,
            "quality_score": health.quality_score,
            "latency_ms": health.latency_ms,
            "stale_quote": health.stale_quote,
            "gap_detected": health.gap_detected,
            "bad_ticks": health.bad_ticks,
            "missing_ticks": health.missing_ticks,
            "is_healthy": health.is_healthy,
            "notes": health.notes,
        }
        self._write(health.symbol, record)

    def log_features(self, fv: FeatureVector) -> None:
        record = {"record_type": "feature"} | fv.to_dict()
        self._write(fv.symbol, record)

    def close(self) -> None:
        for fh in self._handles.values():
            try:
                fh.close()  # type: ignore[attr-defined]
            except Exception:
                pass

    # ── Private ───────────────────────────────────────────────────────────────

    def _write(self, symbol: str, record: dict) -> None:
        fh = self._get_handle(symbol)
        try:
            line = orjson.dumps(record).decode() + "\n"
        except Exception:
            line = json.dumps(record, default=str) + "\n"
        fh.write(line)  # type: ignore[attr-defined]
        fh.flush()      # type: ignore[attr-defined]

    def _get_handle(self, symbol: str):
        from datetime import date
        key = f"{symbol}_{date.today().isoformat()}"
        if key not in self._handles:
            path = self._log_dir / f"{key}.jsonl"
            self._handles[key] = open(path, "a", encoding="utf-8")
        return self._handles[key]
