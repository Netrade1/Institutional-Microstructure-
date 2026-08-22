#!/usr/bin/env python3
"""Production-hardened K2Think.ai / Market-DNA evidence adapter.

Scope
-----
This module is a PAPER-TRADING / RESEARCH evidence adapter only. It deliberately
contains no broker credentials, live order client, or execution endpoint.

Hardening added versus the original adapter:
* persistent SHA-256 ledger continuation with full-chain verification
* cross-platform lock-file protection for writers
* deterministic event IDs and replay/idempotency protection
* strict required-column and packet validation
* atomic manifest writes and fsync-backed JSONL appends
* corrected risk-approved candidate accounting
* structured logs and explicit failure exit codes
* optional explicit reset instead of destructive truncation by default
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import logging
import math
import os
import sys
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

try:
    from orderflow_auction_strategy import StrategyConfig, generate_signals
except ImportError as exc:  # fail closed with an actionable message
    raise SystemExit(
        "Missing dependency 'orderflow_auction_strategy'. Place that module on PYTHONPATH "
        "before running the adapter."
    ) from exc

LOGGER = logging.getLogger("k2think_adapter")
GENESIS_HASH = "0" * 64
SCHEMA_VERSION = "k2think.decision_packet.v2"
STRATEGY_ID = "auction_failure_orderflow_v1"
APPROVED_DECISION = "PAPER_CANDIDATE_REQUIRES_HUMAN_APPROVAL"
VETO_DECISION = "RISK_VETO_NO_TRADE"

REQUIRED_SIGNAL_COLUMNS = {
    "timestamp",
    "signal",
    "data_quality_ok",
    "in_session",
    "volume_ok",
    "news_blocked",
    "value_up",
    "value_down",
    "gamma_regime",
    "value_center",
    "value_low",
    "value_high",
    "swing_high",
    "swing_low",
    "delta",
    "delta_pct",
    "poc_price",
    "buy_imbalances",
    "sell_imbalances",
    "long_absorption",
    "short_absorption",
    "long_confirmation",
    "short_confirmation",
    "close",
    "stop",
    "target",
    "input_sha256",
}


def canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _strict_bool(value: Any, field: str) -> bool:
    if isinstance(value, (bool, type(pd.NA))):
        if value is pd.NA:
            raise ValueError(f"{field} cannot be NA")
        return bool(value)
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    raise ValueError(f"{field} must be boolean-like, got {value!r}")


def _validate_sha256(value: str, field: str, *, allow_placeholder: bool = False) -> str:
    text = str(value)
    if allow_placeholder and text == "NOT_SUPPLIED":
        return text
    if len(text) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in text):
        raise ValueError(f"{field} must be a 64-character SHA-256 hex digest")
    return text.lower()


def validate_signal_frame(signals: pd.DataFrame) -> None:
    missing = sorted(REQUIRED_SIGNAL_COLUMNS.difference(signals.columns))
    if missing:
        raise ValueError(f"generate_signals() output is missing required columns: {', '.join(missing)}")
    if signals.empty:
        LOGGER.warning("generate_signals() returned zero rows")


def make_event_id(row: pd.Series, config: StrategyConfig) -> str:
    identity = {
        "strategy_id": STRATEGY_ID,
        "timestamp_utc": pd.Timestamp(row["timestamp"]).isoformat(),
        "symbol": str(row.get("symbol", config.symbol)),
        "timeframe_minutes": int(config.timeframe_minutes),
        "input_sha256": str(row["input_sha256"]),
        "signal": int(row["signal"]),
    }
    return sha256_text(canonical_json(identity))


def validate_packet(packet: dict[str, Any]) -> None:
    required_top = {
        "schema_version",
        "event_id",
        "strategy_id",
        "timestamp_utc",
        "symbol",
        "timeframe",
        "authority",
        "market_dna",
        "orderflow_evidence",
        "proposal",
        "captain_margincall",
        "governance",
        "provenance",
    }
    missing = sorted(required_top.difference(packet))
    if missing:
        raise ValueError(f"packet missing required fields: {', '.join(missing)}")
    _validate_sha256(packet["event_id"], "event_id")
    _validate_sha256(packet["provenance"]["input_sha256"], "input_sha256")
    _validate_sha256(packet["provenance"]["source_hash"], "source_hash", allow_placeholder=True)
    if packet["authority"] != "EVIDENCE_ONLY":
        raise ValueError("authority must remain EVIDENCE_ONLY")
    gov = packet["governance"]
    invariants = {
        "paper_trading_only": True,
        "live_execution_enabled": False,
        "human_approval_required": True,
        "model_auto_promotion": False,
        "execution_adapter": "DISABLED_NOT_PRESENT",
    }
    for key, expected in invariants.items():
        if gov.get(key) != expected:
            raise ValueError(f"governance invariant violation: {key}={gov.get(key)!r}")


def make_packet(row: pd.Series, config: StrategyConfig) -> dict[str, Any]:
    try:
        signal = int(row["signal"])
        side = {1: "LONG", -1: "SHORT", 0: "NO_TRADE"}[signal]
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError(f"signal must be one of -1, 0, 1; got {row.get('signal')!r}") from exc

    data_ok = _strict_bool(row["data_quality_ok"], "data_quality_ok")
    session_ok = _strict_bool(row["in_session"], "in_session")
    participation_ok = _strict_bool(row["volume_ok"], "volume_ok")
    news_clear = not _strict_bool(row["news_blocked"], "news_blocked")
    candidate = side != "NO_TRADE" and data_ok and session_ok and participation_ok and news_clear
    risk_decision = APPROVED_DECISION if candidate else VETO_DECISION

    timestamp = pd.Timestamp(row["timestamp"])
    if pd.isna(timestamp):
        raise ValueError("timestamp cannot be NA")

    gamma_value = int(row["gamma_regime"])
    if gamma_value not in {-1, 0, 1}:
        raise ValueError(f"gamma_regime must be -1, 0, or 1; got {gamma_value!r}")

    source_hash_raw = str(row.get("source_hash", "NOT_SUPPLIED"))
    input_hash = _validate_sha256(str(row["input_sha256"]), "input_sha256")
    source_hash = _validate_sha256(source_hash_raw, "source_hash", allow_placeholder=True)

    packet = {
        "schema_version": SCHEMA_VERSION,
        "event_id": make_event_id(row, config),
        "strategy_id": STRATEGY_ID,
        "timestamp_utc": timestamp.isoformat(),
        "symbol": str(row.get("symbol", config.symbol)),
        "timeframe": f"{int(config.timeframe_minutes)}m",
        "authority": "EVIDENCE_ONLY",
        "market_dna": {
            "value_structure": (
                "UP"
                if _strict_bool(row["value_up"], "value_up")
                else "DOWN"
                if _strict_bool(row["value_down"], "value_down")
                else "SIDEWAYS"
            ),
            "gamma_regime": {1: "POSITIVE", 0: "UNKNOWN_OR_TRANSITION", -1: "NEGATIVE"}[gamma_value],
            "value_center": _finite(row["value_center"]),
            "value_low": _finite(row["value_low"]),
            "value_high": _finite(row["value_high"]),
            "swing_high": _finite(row["swing_high"]),
            "swing_low": _finite(row["swing_low"]),
        },
        "orderflow_evidence": {
            "delta": _finite(row["delta"]),
            "delta_pct": _finite(row["delta_pct"]),
            "poc_price": _finite(row["poc_price"]),
            "buy_imbalances": int(row["buy_imbalances"]),
            "sell_imbalances": int(row["sell_imbalances"]),
            "long_absorption": _strict_bool(row["long_absorption"], "long_absorption"),
            "short_absorption": _strict_bool(row["short_absorption"], "short_absorption"),
            "long_confirmation": _strict_bool(row["long_confirmation"], "long_confirmation"),
            "short_confirmation": _strict_bool(row["short_confirmation"], "short_confirmation"),
        },
        "proposal": {
            "side": side,
            "entry_reference": _finite(row["close"]) if candidate else None,
            "stop": _finite(row["stop"]) if candidate else None,
            "target": _finite(row["target"]) if candidate else None,
            "status": "UNVALIDATED_RESEARCH_HYPOTHESIS",
        },
        "captain_margincall": {
            "decision": risk_decision,
            "final_veto": True,
            "reasons": {
                "data_quality_ok": data_ok,
                "session_ok": session_ok,
                "participation_ok": participation_ok,
                "news_clear": news_clear,
            },
        },
        "governance": {
            "paper_trading_only": True,
            "live_execution_enabled": False,
            "human_approval_required": True,
            "model_auto_promotion": False,
            "execution_adapter": "DISABLED_NOT_PRESENT",
        },
        "provenance": {
            "input_sha256": input_hash,
            "source_hash": source_hash,
        },
    }
    validate_packet(packet)
    return packet


class LockFile:
    def __init__(self, path: Path, timeout_seconds: float = 10.0) -> None:
        self.path = path
        self.timeout_seconds = timeout_seconds
        self.fd: int | None = None

    def __enter__(self) -> "LockFile":
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            try:
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.fd, f"pid={os.getpid()}\n".encode("ascii"))
                os.fsync(self.fd)
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timed out waiting for lock: {self.path}")
                time.sleep(0.05)

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self.fd is not None:
            os.close(self.fd)
        with contextlib.suppress(FileNotFoundError):
            self.path.unlink()


def _append_line_fsync(path: Path, line: str) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_name)


class HashChainLedger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.previous_hash = GENESIS_HASH
        self.record_count = 0
        if self.path.exists() and self.path.stat().st_size:
            self.verify_and_resume()

    def verify_and_resume(self) -> None:
        previous = GENESIS_HASH
        count = 0
        with self.path.open("r", encoding="utf-8") as handle:
            for line_no, raw in enumerate(handle, 1):
                if not raw.strip():
                    continue
                try:
                    record = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"ledger JSON corruption at line {line_no}") from exc
                supplied_hash = record.get("record_hash")
                if record.get("previous_hash") != previous:
                    raise ValueError(f"ledger chain break at line {line_no}")
                unsigned = {"previous_hash": record["previous_hash"], "packet": record["packet"]}
                expected = sha256_text(canonical_json(unsigned))
                if supplied_hash != expected:
                    raise ValueError(f"ledger hash mismatch at line {line_no}")
                previous = supplied_hash
                count += 1
        self.previous_hash = previous
        self.record_count = count

    def append(self, packet: dict[str, Any]) -> dict[str, Any]:
        record = {"previous_hash": self.previous_hash, "packet": packet}
        record["record_hash"] = sha256_text(canonical_json(record))
        _append_line_fsync(self.path, canonical_json(record))
        self.previous_hash = record["record_hash"]
        self.record_count += 1
        return record


def load_existing_event_ids(packet_path: Path) -> set[str]:
    event_ids: set[str] = set()
    if not packet_path.exists():
        return event_ids
    with packet_path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                packet = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"packet JSON corruption at line {line_no}") from exc
            event_id = packet.get("event_id")
            if event_id:
                event_ids.add(_validate_sha256(event_id, f"event_id line {line_no}"))
    return event_ids


def _safe_reset(paths: Iterable[Path]) -> None:
    for path in paths:
        if path.exists():
            path.unlink()


def export_packets(
    input_csv: Path,
    output_dir: Path,
    config: StrategyConfig | None = None,
    *,
    reset_output: bool = False,
) -> dict[str, int | str]:
    cfg = config or StrategyConfig()
    cfg.validate()
    if not input_csv.is_file():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    raw = pd.read_csv(input_csv)
    signals = generate_signals(raw, cfg)
    validate_signal_frame(signals)

    output_dir.mkdir(parents=True, exist_ok=True)
    packet_path = output_dir / "decision_packets.jsonl"
    ledger_path = output_dir / "audit_ledger.jsonl"
    manifest_path = output_dir / "adapter_manifest.json"
    lock_path = output_dir / ".adapter.lock"

    with LockFile(lock_path):
        if reset_output:
            LOGGER.warning("Explicit reset requested; deleting prior packet/ledger/manifest files")
            _safe_reset((packet_path, ledger_path, manifest_path))

        ledger = HashChainLedger(ledger_path)
        seen = load_existing_event_ids(packet_path)

        raw_directional_signals = 0
        approved_candidates = 0
        vetoed_directional_signals = 0
        no_trade_signals = 0
        appended = 0
        replay_skipped = 0

        for index, row in signals.iterrows():
            try:
                packet = make_packet(row, cfg)
            except Exception as exc:
                raise ValueError(f"Failed to build packet for signal row index {index}: {exc}") from exc

            side = packet["proposal"]["side"]
            decision = packet["captain_margincall"]["decision"]
            if side == "NO_TRADE":
                no_trade_signals += 1
            else:
                raw_directional_signals += 1
                if decision == APPROVED_DECISION:
                    approved_candidates += 1
                else:
                    vetoed_directional_signals += 1

            event_id = packet["event_id"]
            if event_id in seen:
                replay_skipped += 1
                continue

            # Packet then ledger are both append-only; lock prevents concurrent writers.
            _append_line_fsync(packet_path, canonical_json(packet))
            ledger.append(packet)
            seen.add(event_id)
            appended += 1

        manifest = {
            "schema_version": "k2think.adapter_manifest.v2",
            "processed_rows_this_run": int(len(signals)),
            "appended_packets_this_run": appended,
            "replay_skipped_this_run": replay_skipped,
            "raw_directional_signals_this_run": raw_directional_signals,
            "risk_approved_candidates_this_run": approved_candidates,
            "risk_vetoed_directional_signals_this_run": vetoed_directional_signals,
            "no_trade_signals_this_run": no_trade_signals,
            "ledger_record_count_total": ledger.record_count,
            "final_ledger_hash": ledger.previous_hash,
            "config": asdict(cfg),
            "execution_authority": "NONE",
            "paper_trading_only": True,
            "live_execution_enabled": False,
        }
        _atomic_write_text(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    LOGGER.info(
        "processed=%s appended=%s replay_skipped=%s approved=%s vetoed=%s no_trade=%s",
        len(signals),
        appended,
        replay_skipped,
        approved_candidates,
        vetoed_directional_signals,
        no_trade_signals,
    )
    return {
        "processed_rows": int(len(signals)),
        "appended_packets": appended,
        "replay_skipped": replay_skipped,
        "risk_approved_candidates": approved_candidates,
        "risk_vetoed_directional_signals": vetoed_directional_signals,
        "no_trade_signals": no_trade_signals,
        "final_ledger_hash": ledger.previous_hash,
    }


def verify_output(output_dir: Path) -> dict[str, int | str]:
    packet_path = output_dir / "decision_packets.jsonl"
    ledger_path = output_dir / "audit_ledger.jsonl"
    if not packet_path.exists() or not ledger_path.exists():
        raise FileNotFoundError("Expected decision_packets.jsonl and audit_ledger.jsonl")
    ledger = HashChainLedger(ledger_path)
    event_ids = load_existing_event_ids(packet_path)
    if len(event_ids) != ledger.record_count:
        raise ValueError(
            f"packet/ledger count mismatch: unique_packets={len(event_ids)} ledger_records={ledger.record_count}"
        )
    return {
        "unique_packets": len(event_ids),
        "ledger_records": ledger.record_count,
        "final_ledger_hash": ledger.previous_hash,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Emit K2Think paper-only decision packets")
    parser.add_argument("--input", type=Path, help="Input CSV for the underlying strategy")
    parser.add_argument("--output-dir", type=Path, default=Path("k2think_output"))
    parser.add_argument("--reset-output", action="store_true", help="Explicitly delete prior adapter outputs before export")
    parser.add_argument("--verify-only", action="store_true", help="Verify existing packet/ledger integrity without processing input")
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        if args.verify_only:
            result = verify_output(args.output_dir)
        else:
            if args.input is None:
                raise ValueError("--input is required unless --verify-only is used")
            result = export_packets(args.input, args.output_dir, reset_output=args.reset_output)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        LOGGER.exception("Adapter failed closed: %s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
