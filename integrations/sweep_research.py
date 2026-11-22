"""Candle-sweep evidence beside read-only L2 diagnostics; no execution authority.

Run ``python -m integrations.sweep_research --help`` for deterministic JSONL replay.
This module deliberately does not create a K2Think decision packet, a governor
permit, a human approval, or a fill. OHLC patterns cannot attest trade/tape flow.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from .liquidity_sweep import DetectorConfig, DetectionRejected, LiquiditySweepDetector
from .smart_l2_readonly import FeedRejected, ReadOnlyBook, canonical_event_hash


def _integer(value: Any, name: str) -> int:
    if type(value) is not int or value < 0:
        raise FeedRejected(f"{name} must be a nonnegative integer")
    return value


class SweepResearchPipeline:
    """Join scoped observations without upgrading their trust or authority.

    Existing ``ReadOnlyBook`` values are diagnostics, not authenticated True
    Delta or Session VWAP. A book is optional; its lack does not prevent chart
    pattern research, but every result remains NO_TRADE either way.
    """

    def __init__(self, symbol: str, timeframe_ns: int, source: str,
                 config: DetectorConfig | None = None, *,
                 book: ReadOnlyBook | None = None, market_source: str | None = None):
        self.detector = LiquiditySweepDetector(symbol, timeframe_ns, source, config)
        if book is not None and (book.symbol != symbol or not market_source
                                 or not isinstance(market_source, str)):
            raise ValueError("a matching book and explicit market_source are required")
        self.symbol, self.book, self.market_source = symbol, book, market_source
        self._market_session: str | None = None
        self._market_received_ns: int | None = None

    def ingest_market_event(self, event: dict, *, asof_ns: int) -> dict:
        if self.book is None:
            raise FeedRejected("no read-only book configured")
        try:
            if not isinstance(event, dict):
                raise FeedRejected("market event must be an object")
            now = _integer(asof_ns, "asof_ns")
            received = _integer(event.get("received_ns"), "received_ns")
            ts = _integer(event.get("ts_ns"), "ts_ns")
            if ts > received or received > now:
                raise FeedRejected("market event is not available at decision time")
            if event.get("source") != self.market_source or event.get("symbol") != self.symbol:
                raise FeedRejected("market source/symbol mismatch")
            session = event.get("session_id")
            if not isinstance(session, str) or not session.strip():
                raise FeedRejected("explicit market session_id required")
            if self._market_received_ns is not None and received < self._market_received_ns:
                raise FeedRejected("market receive-time regression")
            if session != self._market_session:
                if event.get("type") != "snapshot":
                    raise FeedRejected("new market session requires a snapshot")
                self.book.reset()
            result = self.book.ingest(event)
            self._market_session = session
            self._market_received_ns = received
            return result
        except (FeedRejected, TypeError, ValueError) as exc:
            self.book.healthy = False
            raise FeedRejected(str(exc)) from exc

    def _diagnostics(self, session_id: str, asof_ns: int) -> dict:
        if self.book is None or self._market_received_ns is None:
            return {"status": "UNAVAILABLE", "reason": "NO_MARKET_OBSERVATION"}
        if self._market_session != session_id:
            return {"status": "UNAVAILABLE", "reason": "MARKET_SESSION_MISMATCH"}
        if self._market_received_ns > asof_ns:
            return {"status": "UNAVAILABLE", "reason": "MARKET_STATE_NOT_YET_AVAILABLE"}
        return {
            "values": self.book.metrics(asof_ns),
            "source": self.market_source,
            "session_id": session_id,
            "received_ns": self._market_received_ns,
            "asof_ns": asof_ns,
            "provider_authenticated": False,
            "true_delta_verification": "UNVERIFIED",
            "session_vwap_verification": "UNVERIFIED",
        }

    def ingest_bar(self, bar: dict, *, asof_ns: int) -> dict:
        asof_ns = _integer(asof_ns, "asof_ns")
        detection = self.detector.ingest(bar, asof_ns=asof_ns)
        observation = {
            "schema_version": "netrade.sweep_research_observation.v1",
            "evidence_kind": "OHLC_PRICE_PATTERN",
            "price_pattern": detection,
            "market_diagnostics": self._diagnostics(bar.get("session_id", ""), asof_ns),
            "decision": "NO_TRADE",
            "authority": "EVIDENCE_ONLY",
            "required_external_checks": [
                "VERIFIED_SESSION_VWAP", "VERIFIED_TRUE_DELTA", "VERIFIED_SESSION_CVD",
                "TRADE_TAPE_CONFIRMATION", "EXISTING_MKV_QUALIFICATION",
                "EXISTING_RISK_GOVERNOR", "SIGNED_HUMAN_APPROVAL",
            ],
            "governance": {
                "paper_trading_only": True, "live_execution_enabled": False,
                "human_approval_required": True, "risk_governor_final_veto": True,
                "model_auto_promotion": False, "execution_adapter": "DISABLED_NOT_PRESENT",
            },
        }
        observation["observation_id"] = canonical_event_hash(observation)
        return observation


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"nonfinite JSON constant: {value}")


def replay_file(input_path: Path, output_path: Path, *, symbol: str,
                timeframe_ns: int, source: str, config: DetectorConfig) -> dict:
    """Publish a new complete replay output; never overwrite or leave partial data."""
    input_path, output_path = input_path.resolve(), output_path.resolve()
    if input_path == output_path:
        raise ValueError("input and output must differ")
    if output_path.exists():
        raise FileExistsError("output already exists; choose a new output path")
    pipeline = SweepResearchPipeline(symbol, timeframe_ns, source, config)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    digest = sha256()
    counts = {"observations": 0, "buy_setups": 0, "sell_setups": 0,
              "duplicates": 0, "ignored_unconfirmed": 0}
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=output_path.parent, prefix=".sweep-",
                                         suffix=".tmp", delete=False) as output:
            temp_path = Path(output.name)
            with input_path.open("rb") as source_file:
                for line_number, raw in enumerate(source_file, 1):
                    digest.update(raw)
                    if not raw.strip():
                        continue
                    try:
                        row = json.loads(raw, object_pairs_hook=_unique_object,
                                         parse_constant=_reject_constant)
                        if not isinstance(row, dict) or set(row) != {"bar", "asof_ns"}:
                            raise ValueError("each row requires exactly bar and asof_ns")
                        observation = pipeline.ingest_bar(row["bar"], asof_ns=row["asof_ns"])
                    except (ValueError, TypeError, KeyError) as exc:
                        raise ValueError(f"rejected input line {line_number}: {exc}") from exc
                    detection = observation["price_pattern"]
                    counts["observations"] += 1
                    if detection.get("candidate_side") == "BUY":
                        counts["buy_setups"] += 1
                    elif detection.get("candidate_side") == "SELL":
                        counts["sell_setups"] += 1
                    if detection.get("status") == "DUPLICATE":
                        counts["duplicates"] += 1
                    if detection.get("status") == "IGNORED":
                        counts["ignored_unconfirmed"] += 1
                    output.write(json.dumps(observation, sort_keys=True, separators=(",", ":"),
                                            allow_nan=False) + "\n")
            if not counts["observations"]:
                raise ValueError("input contains no observations")
            output.flush()
            os.fsync(output.fileno())
        # Hard-link publication is atomic and refuses a concurrent/existing target.
        os.link(temp_path, output_path)
        return {**counts, "input_sha256": digest.hexdigest(), "output": str(output_path),
                "decision": "NO_TRADE", "authority": "EVIDENCE_ONLY",
                "performance_tested": False}
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--timeframe-seconds", required=True, type=int)
    parser.add_argument("--swing-length", type=int, default=5)
    parser.add_argument("--max-age-bars", type=int, default=0,
                        help="level age from confirmation; 0 disables expiry")
    parser.add_argument("--allow-repeats", action="store_true")
    parser.add_argument("--carry-session-levels", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = replay_file(args.input, args.out, symbol=args.symbol,
                             timeframe_ns=args.timeframe_seconds * 1_000_000_000,
                             source=args.source,
                             config=DetectorConfig(swing_length=args.swing_length,
                                                   one_per_level=not args.allow_repeats,
                                                   reset_on_session=not args.carry_session_levels,
                                                   max_age_bars=args.max_age_bars))
    except (OSError, ValueError, DetectionRejected) as exc:
        print(json.dumps({"status": "REJECTED", "decision": "NO_TRADE", "error": str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
