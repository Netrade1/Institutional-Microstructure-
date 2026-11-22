# SPDX-License-Identifier: MPL-2.0
# Price-pattern rules adapted from "Liquidity Hunter | Clean Signals", © ReubenMiles.
"""Causal, bounded, evidence-only OHLC liquidity-sweep detection.

This is a price-pattern observation, never trade-tape confirmation, a trading
approval, or an order. Unique-extremum pivots avoid assuming undocumented Pine
tie behavior. Pine compilation and cross-runtime parity have not been observed.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from typing import Any, Mapping


SCHEMA_VERSION = "netrade.liquidity_sweep.v1"
ENGINE_VERSION = "1.0.0"


class DetectionRejected(ValueError):
    """Invalid finalized evidence; reset and replay are required to recover."""


def _integer(value: Any, name: str, *, positive: bool = False) -> int:
    if type(value) is not int or value < (1 if positive else 0) or value > 2**63 - 1:
        raise DetectionRejected(f"{name} must be a {'positive' if positive else 'nonnegative'} signed-64-bit integer")
    return value


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > 256:
        raise DetectionRejected(f"{name} must be a nonempty, trimmed string of at most 256 characters")
    return value


def _price(value: Any, name: str) -> Decimal:
    if type(value) not in (int, float, str, Decimal):
        raise DetectionRejected(f"{name} must be a finite positive decimal")
    text = str(value)
    if len(text) > 256:
        raise DetectionRejected(f"{name} decimal representation is too large")
    try:
        result = Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise DetectionRejected(f"{name} must be a finite positive decimal") from exc
    if not result.is_finite() or result <= 0:
        raise DetectionRejected(f"{name} must be a finite positive decimal")
    # A serialization bound, not a trading-price or tick-size rule.
    if abs(result.as_tuple().exponent) > 256:
        raise DetectionRejected(f"{name} decimal exponent is too large")
    return result


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return sha256(encoded.encode("utf-8")).hexdigest()


def _governance() -> dict[str, Any]:
    return {
        "authority": "EVIDENCE_ONLY",
        "paper_trading_only": True,
        "live_execution_enabled": False,
        "human_approval_required": True,
        "risk_governor_final_veto": True,
        "model_auto_promotion": False,
        "execution_authorized": False,
    }


@dataclass(frozen=True)
class DetectorConfig:
    """Research policy, distinct from approved portfolio/entry risk settings.

    max_age_bars counts accepted bars AFTER pivot confirmation; zero disables
    expiry. The 500-bar swing cap only bounds processing and retained memory.
    """

    swing_length: int = 5
    one_per_level: bool = True
    reset_on_session: bool = True
    max_age_bars: int = 0

    def __post_init__(self) -> None:
        if type(self.swing_length) is not int or not 2 <= self.swing_length <= 500:
            raise DetectionRejected("swing_length must be an integer from 2 through 500")
        if type(self.one_per_level) is not bool or type(self.reset_on_session) is not bool:
            raise DetectionRejected("policy switches must be actual booleans")
        _integer(self.max_age_bars, "max_age_bars")

    def evidence(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "left_bars": self.swing_length,
            "right_bars": self.swing_length,
            "pivot_tie_policy": "REJECT_TIED_EXTREMES",
            "gap_policy": "RESET_LEVELS_AND_WARMUP",
            "dual_signal_policy": "SUPPRESS_BOTH_WITHOUT_CONSUMING",
            "age_origin": "PIVOT_CONFIRMATION",
            "pine_parity_status": "NOT_OBSERVED",
        }


@dataclass(frozen=True)
class ClosedBar:
    symbol: str
    timeframe_ns: int
    source: str
    session_id: str
    open_time_ns: int
    close_time_ns: int
    received_ns: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    is_closed: bool

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ClosedBar":
        if not isinstance(value, Mapping):
            raise DetectionRejected("bar must be an object")
        required = tuple(cls.__dataclass_fields__)
        missing = [field for field in required if field not in value]
        if missing:
            raise DetectionRejected("missing bar fields: " + ", ".join(missing))
        if type(value["is_closed"]) is not bool:
            raise DetectionRejected("is_closed must be an actual boolean")
        bar = cls(
            symbol=_text(value["symbol"], "symbol"),
            timeframe_ns=_integer(value["timeframe_ns"], "timeframe_ns", positive=True),
            source=_text(value["source"], "source"),
            session_id=_text(value["session_id"], "session_id"),
            open_time_ns=_integer(value["open_time_ns"], "open_time_ns"),
            close_time_ns=_integer(value["close_time_ns"], "close_time_ns"),
            received_ns=_integer(value["received_ns"], "received_ns"),
            open=_price(value["open"], "open"),
            high=_price(value["high"], "high"),
            low=_price(value["low"], "low"),
            close=_price(value["close"], "close"),
            is_closed=value["is_closed"],
        )
        if bar.close_time_ns - bar.open_time_ns != bar.timeframe_ns:
            raise DetectionRejected("bar duration does not match timeframe_ns")
        if bar.high < max(bar.open, bar.low, bar.close) or bar.low > min(bar.open, bar.high, bar.close):
            raise DetectionRejected("OHLC values do not form a valid candle")
        if bar.is_closed and bar.received_ns < bar.close_time_ns:
            raise DetectionRejected("final bar received before its close")
        return bar

    def to_mapping(self) -> dict[str, Any]:
        result = asdict(self)
        for field in ("open", "high", "low", "close"):
            result[field] = _decimal_text(getattr(self, field))
        return result


@dataclass(frozen=True)
class _Level:
    side: str
    price: Decimal
    pivot: ClosedBar
    confirmation: ClosedBar
    confirmed_asof_ns: int
    confirmation_index: int
    used: bool = False

    def evidence(self, current_index: int) -> dict[str, Any]:
        result = {
            "side": self.side,
            "price": _decimal_text(self.price),
            "symbol": self.pivot.symbol,
            "timeframe_ns": self.pivot.timeframe_ns,
            "source": self.pivot.source,
            "pivot_open_time_ns": self.pivot.open_time_ns,
            "pivot_close_time_ns": self.pivot.close_time_ns,
            "pivot_received_ns": self.pivot.received_ns,
            "pivot_session_id": self.pivot.session_id,
            "confirmed_close_time_ns": self.confirmation.close_time_ns,
            "confirmed_received_ns": self.confirmation.received_ns,
            "confirmed_asof_ns": self.confirmed_asof_ns,
        }
        return {
            **result,
            "level_id": _hash(result),
            "age_bars": current_index - self.confirmation_index,
            "used": self.used,
        }


class LiquiditySweepDetector:
    """One source/symbol/timeframe stream; accepts final time bars in order.

    A bad finalized observation latches the detector until reset(). Accepted
    market state is retained for diagnosis, but cannot produce more signals.
    reset() discards it; a subsequent replay must establish new pivots causally.
    No clock or freshness threshold is invented. asof_ns is the declared replay
    or observation boundary; this detector never declares data live or fresh.
    """

    def __init__(self, symbol: str, timeframe_ns: int, source: str, config: DetectorConfig | None = None):
        self.symbol = _text(symbol, "symbol")
        self.timeframe_ns = _integer(timeframe_ns, "timeframe_ns", positive=True)
        self.source = _text(source, "source")
        if config is not None and not isinstance(config, DetectorConfig):
            raise DetectionRejected("config must be DetectorConfig")
        self.config = config or DetectorConfig()
        self.reset()

    def reset(self) -> None:
        self.healthy = True
        self.rejection_reason: str | None = None
        self._window: deque[ClosedBar] = deque(maxlen=2 * self.config.swing_length + 1)
        self._high: _Level | None = None
        self._low: _Level | None = None
        self._index = -1
        self._last_bar: ClosedBar | None = None
        self._last_asof_ns: int | None = None
        self._last_result: dict[str, Any] | None = None

    def _base(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "engine_version": ENGINE_VERSION,
            "evidence_type": "OHLC_PRICE_PATTERN",
            "decision": "NO_TRADE",
            "governance": _governance(),
            "policy": self.config.evidence(),
        }

    def _restart_window(self) -> None:
        self._window.clear()
        self._high = self._low = None
        self._index = -1

    def ingest(self, value: Mapping[str, Any] | ClosedBar, *, asof_ns: int) -> dict[str, Any]:
        # Never advance a pivot or consume a level on an unfinished candle.
        if isinstance(value, Mapping) and value.get("is_closed") is False:
            return {
                **self._base(), "event_id": None, "status": "IGNORED",
                "raw_buy": False, "raw_sell": False, "candidate_side": None,
                "reasons": ["UNCONFIRMED_BAR"], "candle": None, "levels": None,
                "provenance": None,
            }
        if isinstance(value, ClosedBar) and value.is_closed is False:
            return self.ingest({"is_closed": False}, asof_ns=asof_ns)
        if not self.healthy:
            raise DetectionRejected("detector is latched; reset and replay required: " + str(self.rejection_reason))
        try:
            asof_ns = _integer(asof_ns, "asof_ns")
            # Revalidate direct dataclass instances so construction cannot bypass checks.
            bar = ClosedBar.from_mapping(asdict(value) if isinstance(value, ClosedBar) else value)
            if not bar.is_closed:
                raise DetectionRejected("only finalized bars may enter the detector")
            if (bar.symbol, bar.timeframe_ns, bar.source) != (self.symbol, self.timeframe_ns, self.source):
                raise DetectionRejected("source/symbol/timeframe scope mismatch")
            if bar.received_ns > asof_ns:
                raise DetectionRejected("bar was not available at asof_ns")
            if self._last_asof_ns is not None and asof_ns < self._last_asof_ns:
                raise DetectionRejected("asof timestamp regression")
            if self._last_bar is not None:
                if bar.close_time_ns == self._last_bar.close_time_ns:
                    if bar != self._last_bar:
                        raise DetectionRejected("corrected or conflicting finalized bar; explicit replay required")
                    duplicate = deepcopy(self._last_result)
                    duplicate.update(status="DUPLICATE", candidate_side=None, reasons=["DUPLICATE_FINAL_BAR"])
                    return duplicate
                if bar.close_time_ns < self._last_bar.close_time_ns or bar.open_time_ns < self._last_bar.close_time_ns:
                    raise DetectionRejected("out-of-order or overlapping finalized bar")
                if bar.received_ns < self._last_bar.received_ns:
                    raise DetectionRejected("receive timestamp regression")
        except (DetectionRejected, KeyError, TypeError, ValueError, ArithmeticError) as exc:
            self.healthy = False
            self.rejection_reason = str(exc)
            if isinstance(exc, DetectionRejected):
                raise
            raise DetectionRejected(str(exc)) from exc

        reasons: list[str] = []
        if self._last_bar is not None:
            session_changed = bar.session_id != self._last_bar.session_id
            gap = bar.open_time_ns != self._last_bar.close_time_ns
            if session_changed and self.config.reset_on_session:
                reasons.append("SESSION_RESET")
            if gap:
                reasons.append("GAP_RESET")
            if gap or (session_changed and self.config.reset_on_session):
                self._restart_window()

        self._index += 1
        self._window.append(bar)
        width = 2 * self.config.swing_length + 1
        if len(self._window) == width:
            window = tuple(self._window)
            pivot = window[self.config.swing_length]
            peers = window[:self.config.swing_length] + window[self.config.swing_length + 1:]
            # Replacement precedes sweep evaluation, matching the source ordering.
            if all(pivot.high > peer.high for peer in peers):
                self._high = _Level("HIGH", pivot.high, pivot, bar, asof_ns, self._index)
            if all(pivot.low < peer.low for peer in peers):
                self._low = _Level("LOW", pivot.low, pivot, bar, asof_ns, self._index)

        raw_buy = self._low is not None and bar.low < self._low.price < bar.close
        raw_sell = self._high is not None and bar.close < self._high.price < bar.high
        candidate: str | None = None
        if raw_buy and raw_sell:
            reasons.append("AMBIGUOUS_DUAL_SWEEP")
        elif raw_buy or raw_sell:
            level = self._low if raw_buy else self._high
            blocked = False
            if self.config.one_per_level and level.used:
                reasons.append("LEVEL_ALREADY_USED")
                blocked = True
            if self.config.max_age_bars and self._index - level.confirmation_index > self.config.max_age_bars:
                reasons.append("LEVEL_EXPIRED")
                blocked = True
            if not blocked:
                candidate = "BUY" if raw_buy else "SELL"
                if raw_buy:
                    self._low = replace(level, used=True)
                else:
                    self._high = replace(level, used=True)
        elif len(self._window) < width:
            reasons.append("WARMUP")
        elif self._low is None and self._high is None:
            reasons.append("NO_CONFIRMED_PIVOT")

        status = "PATTERN_CANDIDATE" if candidate else (
            "SUPPRESSED" if raw_buy or raw_sell else ("WARMUP" if len(self._window) < width else "NO_PATTERN")
        )
        levels = {
            "high": self._high.evidence(self._index) if self._high else None,
            "low": self._low.evidence(self._index) if self._low else None,
        }
        candle = bar.to_mapping()
        provenance = {
            "source": self.source,
            "source_authentication": "UNVERIFIED",
            "input_sha256": _hash(candle),
            "observed_asof_ns": asof_ns,
            "signal_close_time_ns": bar.close_time_ns,
            "signal_received_ns": bar.received_ns,
            "signal_available_ns": asof_ns,
            "freshness_status": "NOT_ASSESSED",
            "true_delta_status": "NOT_PROVIDED",
            "tape_sweep_confirmation": "NOT_PROVIDED",
        }
        result = {
            **self._base(),
            "status": status,
            "raw_buy": raw_buy,
            "raw_sell": raw_sell,
            "candidate_side": candidate,
            "reasons": reasons,
            "candle": candle,
            "levels": levels,
            "provenance": provenance,
        }
        result["event_id"] = _hash(result)
        self._last_bar = bar
        self._last_asof_ns = asof_ns
        self._last_result = deepcopy(result)
        return result
