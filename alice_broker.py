from __future__ import annotations

"""
ALICE / DECISION PARLIAMENT
Institutional-Grade IBKR Broker Adapter
---------------------------------------
Enhanced single-file implementation for integrating a Python trading stack
with Interactive Brokers while preserving a broker-agnostic execution schema.

Major upgrades in this version
- Stronger validation and safer intent handling
- Better risk checks: cash, notional, confidence, shorting, stop-based order risk
- Paper broker with realized/unrealized PnL tracking
- Bracket-style protective logic in paper mode (stop / take-profit)
- Native IBKR bracket order transmission using parent/child orders
- Open order registry and cancel support
- Price update loop for paper mode to simulate fills and exits
- Broker health checks and cleaner event payloads
- SQLite WAL mode and richer persistence
- More robust IBKR status handling scaffolding

This is still a scaffold, not a profitability machine.
Always test in IBKR paper trading before enabling live routing.
"""

import abc
import dataclasses
import datetime as dt
import enum
import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

try:
    from ib_insync import (
        IB,
        Stock,
        Forex,
        Future,
        Crypto,
        MarketOrder,
        LimitOrder,
        StopOrder,
        StopLimitOrder,
    )
    IB_INSYNC_AVAILABLE = True
except Exception:
    IB_INSYNC_AVAILABLE = False
    IB = object  # type: ignore
    Stock = Forex = Future = Crypto = object  # type: ignore
    MarketOrder = LimitOrder = StopOrder = StopLimitOrder = object  # type: ignore


# =============================================================================
# LOGGING
# =============================================================================

def build_logger(name: str = "alice_broker") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    logger.addHandler(handler)
    return logger


logger = build_logger()


# =============================================================================
# ENUMS / SCHEMAS
# =============================================================================

class Environment(str, enum.Enum):
    PAPER = "paper"
    LIVE = "live"


class AssetType(str, enum.Enum):
    STOCK = "stock"
    FOREX = "forex"
    FUTURE = "future"
    CRYPTO = "crypto"
    OPTION = "option"


class OrderSide(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, enum.Enum):
    MARKET = "MKT"
    LIMIT = "LMT"
    STOP = "STP"
    STOP_LIMIT = "STP_LMT"


class TimeInForce(str, enum.Enum):
    DAY = "DAY"
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"


class IntentSource(str, enum.Enum):
    ALICE = "alice"
    MAD_HATTER = "mad_hatter"
    PARLIAMENT = "parliament"
    HUMAN = "human"
    BACKTEST = "backtest"
    SCANNER = "scanner"


class DecisionAction(str, enum.Enum):
    ENTER_LONG = "enter_long"
    ENTER_SHORT = "enter_short"
    EXIT_LONG = "exit_long"
    EXIT_SHORT = "exit_short"
    REDUCE = "reduce"
    HOLD = "hold"
    CANCEL = "cancel"


class ExecutionStatus(str, enum.Enum):
    CREATED = "created"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"
    TRIGGERED = "triggered"


class RiskVerdict(str, enum.Enum):
    APPROVE = "approve"
    THROTTLE = "throttle"
    REJECT = "reject"


@dataclass(slots=True)
class Instrument:
    symbol: str
    asset_type: AssetType = AssetType.STOCK
    exchange: str = "SMART"
    currency: str = "USD"
    primary_exchange: Optional[str] = None
    expiry: Optional[str] = None
    multiplier: Optional[str] = None


@dataclass(slots=True)
class DecisionContext:
    source: IntentSource
    strategy_id: str
    strategy_version: str
    model_family: str = "rules"
    signal_strength: float = 0.0
    confidence: float = 0.0
    rationale: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RiskEnvelope:
    max_notional: float
    max_position_qty: float
    max_daily_loss: float
    max_symbol_exposure: float
    max_order_risk: float
    min_confidence: float = 0.0
    spread_limit_bps: Optional[float] = None
    slippage_limit_bps: Optional[float] = None
    volatility_cap: Optional[float] = None
    allow_short: bool = False
    allow_fractional: bool = True
    allow_after_hours: bool = False
    kill_switch_enabled: bool = True


@dataclass(slots=True)
class OrderIntent:
    instrument: Instrument
    action: DecisionAction
    side: OrderSide
    quantity: float
    order_type: OrderType = OrderType.MARKET
    tif: TimeInForce = TimeInForce.DAY
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    trailing_percent: Optional[float] = None
    trailing_amount: Optional[float] = None
    decision: Optional[DecisionContext] = None
    risk: Optional[RiskEnvelope] = None
    parent_client_order_id: Optional[str] = None
    client_order_id: str = field(default_factory=lambda: f"alice-{uuid.uuid4().hex[:16]}")
    created_at_utc: str = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RiskCheckResult:
    verdict: RiskVerdict
    approved_quantity: float
    reasons: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionReport:
    execution_id: str
    client_order_id: str
    broker_order_id: Optional[str]
    status: ExecutionStatus
    symbol: str
    side: str
    quantity: float
    filled_quantity: float = 0.0
    avg_fill_price: Optional[float] = None
    message: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)
    created_at_utc: str = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())
    updated_at_utc: str = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())


@dataclass(slots=True)
class PositionSnapshot:
    symbol: str
    quantity: float
    avg_cost: float
    market_price: Optional[float] = None
    market_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    realized_pnl: Optional[float] = None
    account: Optional[str] = None


@dataclass(slots=True)
class AccountSnapshot:
    account_id: str
    net_liquidation: float = 0.0
    available_funds: float = 0.0
    buying_power: float = 0.0
    excess_liquidity: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    timestamp_utc: str = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())


@dataclass(slots=True)
class OpenOrder:
    client_order_id: str
    symbol: str
    side: str
    quantity: float
    order_type: str
    status: str
    broker_order_id: Optional[str] = None
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    parent_client_order_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BracketState:
    entry_client_order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    stop_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    active: bool = True


@dataclass(slots=True)
class BracketSubmissionResult:
    parent: ExecutionReport
    take_profit: Optional[ExecutionReport] = None
    stop_loss: Optional[ExecutionReport] = None


# =============================================================================
# PERSISTENCE LAYER
# =============================================================================

class ExecutionJournal:
    def __init__(self, db_path: Union[str, Path] = "alice_execution_journal.db") -> None:
        self.db_path = str(db_path)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_reports (
                    execution_id TEXT PRIMARY KEY,
                    client_order_id TEXT NOT NULL,
                    broker_order_id TEXT,
                    status TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    filled_quantity REAL NOT NULL,
                    avg_fill_price REAL,
                    message TEXT,
                    raw_json TEXT,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS order_intents (
                    client_order_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS risk_checks (
                    client_order_id TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    approved_quantity REAL NOT NULL,
                    reasons_json TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def write_intent(self, intent: OrderIntent) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO order_intents (client_order_id, payload_json, created_at_utc)
                VALUES (?, ?, ?)
                """,
                (intent.client_order_id, json.dumps(to_jsonable(intent), default=str), intent.created_at_utc),
            )
            conn.commit()

    def write_risk_check(self, client_order_id: str, result: RiskCheckResult) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO risk_checks (
                    client_order_id, verdict, approved_quantity, reasons_json, metrics_json, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    client_order_id,
                    result.verdict.value,
                    result.approved_quantity,
                    json.dumps(result.reasons),
                    json.dumps(result.metrics),
                    utc_now(),
                ),
            )
            conn.commit()

    def write_report(self, report: ExecutionReport) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO execution_reports (
                    execution_id, client_order_id, broker_order_id, status, symbol, side,
                    quantity, filled_quantity, avg_fill_price, message, raw_json,
                    created_at_utc, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report.execution_id,
                    report.client_order_id,
                    report.broker_order_id,
                    report.status.value,
                    report.symbol,
                    report.side,
                    report.quantity,
                    report.filled_quantity,
                    report.avg_fill_price,
                    report.message,
                    json.dumps(report.raw, default=str),
                    report.created_at_utc,
                    report.updated_at_utc,
                ),
            )
            conn.commit()


# =============================================================================
# HELPERS
# =============================================================================

def to_jsonable(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj):
        return {k: to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(x) for x in obj]
    return obj


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def normalize_status(status_text: str) -> ExecutionStatus:
    normalized = (status_text or "").lower()
    if "fill" in normalized:
        return ExecutionStatus.FILLED
    if "partial" in normalized:
        return ExecutionStatus.PARTIALLY_FILLED
    if "cancel" in normalized:
        return ExecutionStatus.CANCELLED
    if "trigger" in normalized:
        return ExecutionStatus.TRIGGERED
    if "reject" in normalized or "inactive" in normalized or "error" in normalized:
        return ExecutionStatus.FAILED
    return ExecutionStatus.SUBMITTED


def validate_intent(intent: OrderIntent) -> None:
    if intent.quantity < 0:
        raise ValueError("OrderIntent.quantity must be non-negative.")
    if intent.action in {DecisionAction.HOLD, DecisionAction.CANCEL} and intent.quantity != 0:
        raise ValueError("HOLD and CANCEL intents must have quantity 0.")
    if intent.order_type == OrderType.LIMIT and intent.limit_price is None:
        raise ValueError("LIMIT order requires limit_price.")
    if intent.order_type == OrderType.STOP and intent.stop_price is None:
        raise ValueError("STOP order requires stop_price.")
    if intent.order_type == OrderType.STOP_LIMIT and (intent.stop_price is None or intent.limit_price is None):
        raise ValueError("STOP_LIMIT order requires stop_price and limit_price.")
    if intent.trailing_percent is not None and intent.trailing_percent <= 0:
        raise ValueError("trailing_percent must be positive.")
    if intent.trailing_amount is not None and intent.trailing_amount <= 0:
        raise ValueError("trailing_amount must be positive.")


# =============================================================================
# EVENT BUS
# =============================================================================

class EventHook:
    def __init__(self) -> None:
        self._listeners: List[Callable[[Dict[str, Any]], None]] = []

    def subscribe(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        self._listeners.append(callback)

    def unsubscribe(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        self._listeners = [fn for fn in self._listeners if fn is not callback]

    def emit(self, event: Dict[str, Any]) -> None:
        for listener in list(self._listeners):
            try:
                listener(event)
            except Exception as exc:
                logger.exception("Event listener failed: %s", exc)


# =============================================================================
# RISK ENGINE
# =============================================================================

class RiskEngine:
    """
    Evaluates an OrderIntent against a RiskEnvelope and account state.

    Checks performed
    ----------------
    1. Kill-switch gate
    2. Min confidence threshold
    3. Short-selling permission
    4. Available cash vs notional cost
    5. Notional cap per order
    6. Symbol exposure cap
    7. Max position quantity
    8. Order-risk cap (stop-distance × qty)
    9. Daily loss limit
    """

    def __init__(self, journal: Optional[ExecutionJournal] = None) -> None:
        self._journal = journal

    def check(
        self,
        intent: OrderIntent,
        account: AccountSnapshot,
        current_positions: Optional[Dict[str, PositionSnapshot]] = None,
        daily_realized_loss: float = 0.0,
        market_price: Optional[float] = None,
    ) -> RiskCheckResult:
        risk = intent.risk
        reasons: List[str] = []
        metrics: Dict[str, Any] = {}

        if risk is None:
            return RiskCheckResult(
                verdict=RiskVerdict.APPROVE,
                approved_quantity=intent.quantity,
                reasons=["No risk envelope provided; auto-approved."],
                metrics=metrics,
            )

        qty = intent.quantity
        approved_qty = qty

        # 1. Kill-switch
        if risk.kill_switch_enabled and os.environ.get("ALICE_KILL_SWITCH", "0") == "1":
            reasons.append("Kill switch is active.")
            return RiskCheckResult(
                verdict=RiskVerdict.REJECT,
                approved_quantity=0.0,
                reasons=reasons,
                metrics=metrics,
            )

        # 2. Confidence gate
        confidence = intent.decision.confidence if intent.decision else 0.0
        metrics["confidence"] = confidence
        if confidence < risk.min_confidence:
            reasons.append(
                f"Confidence {confidence:.3f} below minimum {risk.min_confidence:.3f}."
            )
            return RiskCheckResult(
                verdict=RiskVerdict.REJECT,
                approved_quantity=0.0,
                reasons=reasons,
                metrics=metrics,
            )

        # 3. Short-selling permission
        if intent.side == OrderSide.SELL and intent.action in {
            DecisionAction.ENTER_SHORT
        } and not risk.allow_short:
            reasons.append("Short selling is not permitted by this risk envelope.")
            return RiskCheckResult(
                verdict=RiskVerdict.REJECT,
                approved_quantity=0.0,
                reasons=reasons,
                metrics=metrics,
            )

        # 4 & 5. Notional checks
        ref_price = (
            market_price
            or intent.limit_price
            or intent.stop_price
            or 0.0
        )
        notional = ref_price * qty
        metrics["ref_price"] = ref_price
        metrics["notional"] = notional
        metrics["available_funds"] = account.available_funds

        if notional > risk.max_notional:
            # Throttle quantity to fit within notional cap
            if ref_price > 0:
                capped_qty = risk.max_notional / ref_price
                if not risk.allow_fractional:
                    capped_qty = float(int(capped_qty))
                approved_qty = min(approved_qty, capped_qty)
                reasons.append(
                    f"Notional {notional:.2f} exceeds cap {risk.max_notional:.2f}; "
                    f"quantity throttled to {approved_qty}."
                )
            else:
                reasons.append("Cannot compute notional without a reference price; order rejected.")
                return RiskCheckResult(
                    verdict=RiskVerdict.REJECT,
                    approved_quantity=0.0,
                    reasons=reasons,
                    metrics=metrics,
                )

        # 4b. Cash availability
        order_cost = ref_price * approved_qty
        if intent.side == OrderSide.BUY and order_cost > account.available_funds:
            if ref_price > 0 and account.available_funds > 0:
                cash_qty = account.available_funds / ref_price
                if not risk.allow_fractional:
                    cash_qty = float(int(cash_qty))
                approved_qty = min(approved_qty, cash_qty)
                reasons.append(
                    f"Insufficient cash ({account.available_funds:.2f}); "
                    f"quantity throttled to {approved_qty}."
                )
            else:
                reasons.append("Insufficient cash and cannot throttle; order rejected.")
                return RiskCheckResult(
                    verdict=RiskVerdict.REJECT,
                    approved_quantity=0.0,
                    reasons=reasons,
                    metrics=metrics,
                )

        # 6. Symbol exposure cap
        current_pos = (current_positions or {}).get(intent.instrument.symbol)
        existing_qty = abs(current_pos.quantity) if current_pos else 0.0
        metrics["existing_position_qty"] = existing_qty
        if existing_qty + approved_qty > risk.max_symbol_exposure:
            allowed = max(0.0, risk.max_symbol_exposure - existing_qty)
            if not risk.allow_fractional:
                allowed = float(int(allowed))
            approved_qty = min(approved_qty, allowed)
            reasons.append(
                f"Symbol exposure cap {risk.max_symbol_exposure} reached; "
                f"quantity throttled to {approved_qty}."
            )

        # 7. Max position quantity
        if approved_qty > risk.max_position_qty:
            approved_qty = risk.max_position_qty
            if not risk.allow_fractional:
                approved_qty = float(int(approved_qty))
            reasons.append(
                f"Max position qty {risk.max_position_qty} applied."
            )

        # 8. Stop-based order risk
        if intent.stop_price is not None and ref_price > 0:
            stop_distance = abs(ref_price - intent.stop_price)
            order_risk = stop_distance * approved_qty
            metrics["stop_distance"] = stop_distance
            metrics["order_risk"] = order_risk
            if order_risk > risk.max_order_risk:
                if stop_distance > 0:
                    risk_qty = risk.max_order_risk / stop_distance
                    if not risk.allow_fractional:
                        risk_qty = float(int(risk_qty))
                    approved_qty = min(approved_qty, risk_qty)
                    reasons.append(
                        f"Order risk {order_risk:.2f} exceeds cap {risk.max_order_risk:.2f}; "
                        f"quantity throttled to {approved_qty}."
                    )

        # 9. Daily loss limit
        metrics["daily_realized_loss"] = daily_realized_loss
        if abs(daily_realized_loss) >= risk.max_daily_loss:
            reasons.append(
                f"Daily loss limit {risk.max_daily_loss:.2f} reached "
                f"(current: {daily_realized_loss:.2f}); order rejected."
            )
            return RiskCheckResult(
                verdict=RiskVerdict.REJECT,
                approved_quantity=0.0,
                reasons=reasons,
                metrics=metrics,
            )

        if approved_qty <= 0:
            return RiskCheckResult(
                verdict=RiskVerdict.REJECT,
                approved_quantity=0.0,
                reasons=reasons or ["Approved quantity reduced to zero."],
                metrics=metrics,
            )

        verdict = RiskVerdict.THROTTLE if approved_qty < qty else RiskVerdict.APPROVE
        return RiskCheckResult(
            verdict=verdict,
            approved_quantity=approved_qty,
            reasons=reasons,
            metrics=metrics,
        )


# =============================================================================
# ABSTRACT BROKER ADAPTER
# =============================================================================

class BrokerAdapter(abc.ABC):
    """
    Broker-agnostic interface that all broker implementations must satisfy.
    """

    on_fill: EventHook
    on_reject: EventHook
    on_cancel: EventHook
    on_status_change: EventHook

    @abc.abstractmethod
    def submit_order(self, intent: OrderIntent) -> ExecutionReport:
        """Submit a single order intent and return the initial execution report."""

    @abc.abstractmethod
    def submit_bracket(self, intent: OrderIntent) -> BracketSubmissionResult:
        """
        Submit an entry order together with protective stop-loss and
        take-profit child orders.
        """

    @abc.abstractmethod
    def cancel_order(self, client_order_id: str) -> ExecutionReport:
        """Request cancellation of an open order by client_order_id."""

    @abc.abstractmethod
    def get_open_orders(self) -> List[OpenOrder]:
        """Return all open orders tracked by this adapter."""

    @abc.abstractmethod
    def get_positions(self) -> List[PositionSnapshot]:
        """Return current position snapshots."""

    @abc.abstractmethod
    def get_account(self) -> AccountSnapshot:
        """Return a current account snapshot."""

    @abc.abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Return a dict describing broker connectivity / health."""

    @abc.abstractmethod
    def connect(self) -> None:
        """Establish connection to broker."""

    @abc.abstractmethod
    def disconnect(self) -> None:
        """Tear down connection to broker."""


# =============================================================================
# PAPER BROKER
# =============================================================================

class _PaperPosition:
    """Internal mutable position tracker for the paper broker."""

    def __init__(self, symbol: str, quantity: float, avg_cost: float) -> None:
        self.symbol = symbol
        self.quantity = quantity
        self.avg_cost = avg_cost
        self.realized_pnl: float = 0.0

    def apply_fill(self, side: OrderSide, qty: float, fill_price: float) -> float:
        """Update position after a fill. Returns realized PnL from this fill."""
        realized = 0.0
        if side == OrderSide.BUY:
            if self.quantity < 0:
                # Covering a short
                closing = min(qty, abs(self.quantity))
                realized = closing * (self.avg_cost - fill_price)
                self.quantity += closing
                qty -= closing
            if qty > 0:
                # Adding to long
                total_cost = self.avg_cost * max(self.quantity, 0) + fill_price * qty
                self.quantity += qty
                self.avg_cost = total_cost / self.quantity if self.quantity != 0 else fill_price
        else:  # SELL
            if self.quantity > 0:
                # Closing a long
                closing = min(qty, self.quantity)
                realized = closing * (fill_price - self.avg_cost)
                self.quantity -= closing
                qty -= closing
            if qty > 0:
                # Opening or adding to short
                if self.quantity == 0:
                    self.avg_cost = fill_price
                else:
                    total_cost = self.avg_cost * abs(self.quantity) + fill_price * qty
                    self.quantity -= qty
                    self.avg_cost = total_cost / abs(self.quantity) if self.quantity != 0 else fill_price
                    qty = 0
                if qty > 0:
                    self.quantity -= qty
                    self.avg_cost = fill_price
        self.realized_pnl += realized
        return realized

    def unrealized_pnl(self, market_price: float) -> float:
        if self.quantity == 0:
            return 0.0
        return self.quantity * (market_price - self.avg_cost)


class PaperBroker(BrokerAdapter):
    """
    In-memory paper trading broker.

    Features
    --------
    - Instant market-order fills at the provided (or simulated) price
    - Limit/stop order simulation via a background price-update loop
    - Bracket order protective logic (stop-loss + take-profit)
    - Realized and unrealized PnL tracking per position
    - Open-order registry with cancel support
    - Event emission on fill, reject, cancel, status change
    """

    DEFAULT_INITIAL_CASH = 100_000.0
    _PRICE_LOOP_INTERVAL = 2.0  # seconds

    def __init__(
        self,
        account_id: str = "PAPER-0001",
        initial_cash: float = DEFAULT_INITIAL_CASH,
        journal: Optional[ExecutionJournal] = None,
        risk_engine: Optional[RiskEngine] = None,
    ) -> None:
        self._account_id = account_id
        self._cash = initial_cash
        self._initial_cash = initial_cash
        self._journal = journal
        self._risk_engine = risk_engine or RiskEngine(journal)
        self._lock = threading.Lock()

        self._positions: Dict[str, _PaperPosition] = {}
        self._open_orders: Dict[str, OpenOrder] = {}
        self._brackets: Dict[str, BracketState] = {}
        self._market_prices: Dict[str, float] = {}
        self._daily_realized_loss: float = 0.0
        self._total_realized_pnl: float = 0.0

        self.on_fill = EventHook()
        self.on_reject = EventHook()
        self.on_cancel = EventHook()
        self.on_status_change = EventHook()

        self._price_loop_thread: Optional[threading.Thread] = None
        self._price_loop_running = False

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        self._price_loop_running = True
        self._price_loop_thread = threading.Thread(
            target=self._price_update_loop, daemon=True, name="paper-price-loop"
        )
        self._price_loop_thread.start()
        logger.info("PaperBroker connected. Account: %s  Cash: %.2f", self._account_id, self._cash)

    def disconnect(self) -> None:
        self._price_loop_running = False
        if self._price_loop_thread:
            self._price_loop_thread.join(timeout=5.0)
        logger.info("PaperBroker disconnected.")

    # ------------------------------------------------------------------
    # Price management
    # ------------------------------------------------------------------

    def update_price(self, symbol: str, price: float) -> None:
        """Feed a market price for a symbol; triggers pending order evaluation."""
        with self._lock:
            self._market_prices[symbol] = price

    def _price_update_loop(self) -> None:
        while self._price_loop_running:
            try:
                self._evaluate_pending_orders()
            except Exception as exc:
                logger.exception("Price loop error: %s", exc)
            time.sleep(self._PRICE_LOOP_INTERVAL)

    def _evaluate_pending_orders(self) -> None:
        with self._lock:
            pending = [
                o for o in list(self._open_orders.values())
                if o.status in ("submitted", "partially_filled")
            ]
        for order in pending:
            price = self._market_prices.get(order.symbol)
            if price is None:
                continue
            self._try_fill_pending(order, price)

    def _try_fill_pending(self, order: OpenOrder, price: float) -> None:
        triggered = False
        if order.order_type == OrderType.LIMIT.value:
            if order.side == OrderSide.BUY.value and price <= (order.limit_price or float("inf")):
                triggered = True
            elif order.side == OrderSide.SELL.value and price >= (order.limit_price or 0):
                triggered = True
        elif order.order_type == OrderType.STOP.value:
            if order.side == OrderSide.BUY.value and price >= (order.stop_price or 0):
                triggered = True
            elif order.side == OrderSide.SELL.value and price <= (order.stop_price or float("inf")):
                triggered = True
        elif order.order_type == OrderType.STOP_LIMIT.value:
            if order.side == OrderSide.BUY.value and price >= (order.stop_price or 0):
                if price <= (order.limit_price or float("inf")):
                    triggered = True
            elif order.side == OrderSide.SELL.value and price <= (order.stop_price or float("inf")):
                if price >= (order.limit_price or 0):
                    triggered = True

        if triggered:
            fill_price = price
            self._execute_fill(order.client_order_id, fill_price)

    # ------------------------------------------------------------------
    # Order submission
    # ------------------------------------------------------------------

    def submit_order(self, intent: OrderIntent) -> ExecutionReport:
        try:
            validate_intent(intent)
        except ValueError as exc:
            report = self._make_report(intent, ExecutionStatus.REJECTED, message=str(exc))
            self._emit_reject(report, str(exc))
            return report

        account = self.get_account()
        risk_result = self._risk_engine.check(
            intent,
            account,
            current_positions={s: self._pos_snapshot(p) for s, p in self._positions.items()},
            daily_realized_loss=self._daily_realized_loss,
            market_price=self._market_prices.get(intent.instrument.symbol),
        )

        if self._journal:
            self._journal.write_intent(intent)
            self._journal.write_risk_check(intent.client_order_id, risk_result)

        if risk_result.verdict == RiskVerdict.REJECT:
            report = self._make_report(
                intent,
                ExecutionStatus.REJECTED,
                message="; ".join(risk_result.reasons),
            )
            self._emit_reject(report, report.message)
            if self._journal:
                self._journal.write_report(report)
            return report

        approved_qty = risk_result.approved_quantity

        with self._lock:
            open_order = OpenOrder(
                client_order_id=intent.client_order_id,
                symbol=intent.instrument.symbol,
                side=intent.side.value,
                quantity=approved_qty,
                order_type=intent.order_type.value,
                status=ExecutionStatus.SUBMITTED.value,
                limit_price=intent.limit_price,
                stop_price=intent.stop_price,
                take_profit_price=intent.take_profit_price,
                parent_client_order_id=intent.parent_client_order_id,
                metadata={"risk_reasons": risk_result.reasons},
            )
            self._open_orders[intent.client_order_id] = open_order

        report = self._make_report(intent, ExecutionStatus.SUBMITTED, quantity=approved_qty)
        self.on_status_change.emit({"event": "submitted", "report": to_jsonable(report)})

        if self._journal:
            self._journal.write_report(report)

        # Immediate fill for market orders
        if intent.order_type == OrderType.MARKET:
            fill_price = self._market_prices.get(intent.instrument.symbol, 0.0)
            if fill_price <= 0:
                fill_price = intent.limit_price or intent.stop_price or 1.0
            fill_report = self._execute_fill(intent.client_order_id, fill_price)
            if fill_report is not None:
                return fill_report

        return report

    def submit_bracket(self, intent: OrderIntent) -> BracketSubmissionResult:
        """
        Submit entry order. If stop_price or take_profit_price are set on the
        intent, register protective child orders that will be submitted once the
        parent fill is confirmed.
        """
        parent_report = self.submit_order(intent)

        if parent_report.status in {ExecutionStatus.REJECTED, ExecutionStatus.FAILED}:
            return BracketSubmissionResult(parent=parent_report)

        with self._lock:
            bracket = BracketState(
                entry_client_order_id=intent.client_order_id,
                symbol=intent.instrument.symbol,
                side=intent.side,
                quantity=intent.quantity,
                stop_price=intent.stop_price,
                take_profit_price=intent.take_profit_price,
            )
            self._brackets[intent.client_order_id] = bracket

        return BracketSubmissionResult(parent=parent_report)

    # ------------------------------------------------------------------
    # Fill execution
    # ------------------------------------------------------------------

    def _execute_fill(self, client_order_id: str, fill_price: float) -> Optional[ExecutionReport]:
        with self._lock:
            order = self._open_orders.get(client_order_id)
            if order is None or order.status not in ("submitted", "partially_filled"):
                return None

            side = OrderSide(order.side)
            qty = order.quantity

            # Update cash
            if side == OrderSide.BUY:
                self._cash -= fill_price * qty
            else:
                self._cash += fill_price * qty

            # Update position
            pos = self._positions.setdefault(order.symbol, _PaperPosition(order.symbol, 0.0, 0.0))
            realized = pos.apply_fill(side, qty, fill_price)
            self._total_realized_pnl += realized
            if realized < 0:
                self._daily_realized_loss += abs(realized)

            # Remove zero positions
            if pos.quantity == 0.0:
                del self._positions[order.symbol]

            order.status = ExecutionStatus.FILLED.value

        execution_id = f"fill-{uuid.uuid4().hex[:12]}"
        report = ExecutionReport(
            execution_id=execution_id,
            client_order_id=client_order_id,
            broker_order_id=None,
            status=ExecutionStatus.FILLED,
            symbol=order.symbol,
            side=order.side,
            quantity=qty,
            filled_quantity=qty,
            avg_fill_price=fill_price,
            message="Paper fill",
            updated_at_utc=utc_now(),
        )

        if self._journal:
            self._journal.write_report(report)

        self.on_fill.emit(
            {
                "event": "fill",
                "client_order_id": client_order_id,
                "symbol": order.symbol,
                "side": order.side,
                "qty": qty,
                "fill_price": fill_price,
                "realized_pnl": realized if order.side == OrderSide.SELL.value else 0.0,
                "report": to_jsonable(report),
            }
        )

        # Activate bracket protection
        self._check_bracket_activation(client_order_id, fill_price)

        return report

    def _check_bracket_activation(self, entry_client_order_id: str, entry_fill_price: float) -> None:
        bracket = self._brackets.get(entry_client_order_id)
        if bracket is None or not bracket.active:
            return

        bracket.active = False
        protective_side = OrderSide.SELL if bracket.side == OrderSide.BUY else OrderSide.BUY
        action = DecisionAction.EXIT_LONG if bracket.side == OrderSide.BUY else DecisionAction.EXIT_SHORT

        if bracket.stop_price is not None:
            stop_intent = OrderIntent(
                instrument=Instrument(symbol=bracket.symbol),
                action=action,
                side=protective_side,
                quantity=bracket.quantity,
                order_type=OrderType.STOP,
                stop_price=bracket.stop_price,
                parent_client_order_id=entry_client_order_id,
            )
            self.submit_order(stop_intent)

        if bracket.take_profit_price is not None:
            tp_intent = OrderIntent(
                instrument=Instrument(symbol=bracket.symbol),
                action=action,
                side=protective_side,
                quantity=bracket.quantity,
                order_type=OrderType.LIMIT,
                limit_price=bracket.take_profit_price,
                parent_client_order_id=entry_client_order_id,
            )
            self.submit_order(tp_intent)

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    def cancel_order(self, client_order_id: str) -> ExecutionReport:
        with self._lock:
            order = self._open_orders.get(client_order_id)
            if order is None:
                return ExecutionReport(
                    execution_id=f"cancel-{uuid.uuid4().hex[:12]}",
                    client_order_id=client_order_id,
                    broker_order_id=None,
                    status=ExecutionStatus.FAILED,
                    symbol="UNKNOWN",
                    side="",
                    quantity=0.0,
                    message="Order not found.",
                )
            if order.status in (ExecutionStatus.FILLED.value, ExecutionStatus.CANCELLED.value):
                return ExecutionReport(
                    execution_id=f"cancel-{uuid.uuid4().hex[:12]}",
                    client_order_id=client_order_id,
                    broker_order_id=None,
                    status=ExecutionStatus.FAILED,
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    message=f"Cannot cancel order with status: {order.status}.",
                )
            order.status = ExecutionStatus.CANCELLED.value

        report = ExecutionReport(
            execution_id=f"cancel-{uuid.uuid4().hex[:12]}",
            client_order_id=client_order_id,
            broker_order_id=None,
            status=ExecutionStatus.CANCELLED,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            message="Cancelled by request.",
            updated_at_utc=utc_now(),
        )

        if self._journal:
            self._journal.write_report(report)

        self.on_cancel.emit({"event": "cancel", "client_order_id": client_order_id, "report": to_jsonable(report)})
        return report

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_open_orders(self) -> List[OpenOrder]:
        with self._lock:
            return [
                o for o in self._open_orders.values()
                if o.status in (ExecutionStatus.SUBMITTED.value, ExecutionStatus.PARTIALLY_FILLED.value)
            ]

    def get_positions(self) -> List[PositionSnapshot]:
        with self._lock:
            return [self._pos_snapshot(p) for p in self._positions.values()]

    def get_account(self) -> AccountSnapshot:
        with self._lock:
            total_market_value = 0.0
            total_unrealized = 0.0
            for symbol, pos in self._positions.items():
                mp = self._market_prices.get(symbol, pos.avg_cost)
                mv = pos.quantity * mp
                total_market_value += mv
                total_unrealized += pos.unrealized_pnl(mp)

            net_liq = self._cash + total_market_value
            return AccountSnapshot(
                account_id=self._account_id,
                net_liquidation=net_liq,
                available_funds=self._cash,
                buying_power=self._cash,
                excess_liquidity=self._cash,
                realized_pnl=self._total_realized_pnl,
                unrealized_pnl=total_unrealized,
            )

    def health_check(self) -> Dict[str, Any]:
        return {
            "broker": "PaperBroker",
            "connected": self._price_loop_running,
            "account_id": self._account_id,
            "cash": self._cash,
            "open_orders": len(self.get_open_orders()),
            "positions": len(self._positions),
            "timestamp_utc": utc_now(),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_report(
        self,
        intent: OrderIntent,
        status: ExecutionStatus,
        message: str = "",
        quantity: Optional[float] = None,
    ) -> ExecutionReport:
        return ExecutionReport(
            execution_id=f"exec-{uuid.uuid4().hex[:12]}",
            client_order_id=intent.client_order_id,
            broker_order_id=None,
            status=status,
            symbol=intent.instrument.symbol,
            side=intent.side.value,
            quantity=quantity if quantity is not None else intent.quantity,
            message=message,
        )

    def _pos_snapshot(self, pos: _PaperPosition) -> PositionSnapshot:
        mp = self._market_prices.get(pos.symbol, pos.avg_cost)
        return PositionSnapshot(
            symbol=pos.symbol,
            quantity=pos.quantity,
            avg_cost=pos.avg_cost,
            market_price=mp,
            market_value=pos.quantity * mp,
            unrealized_pnl=pos.unrealized_pnl(mp),
            realized_pnl=pos.realized_pnl,
            account=self._account_id,
        )

    def _emit_reject(self, report: ExecutionReport, reason: str) -> None:
        self.on_reject.emit({"event": "reject", "reason": reason, "report": to_jsonable(report)})


# =============================================================================
# IBKR BROKER ADAPTER
# =============================================================================

class IBKRBroker(BrokerAdapter):
    """
    Interactive Brokers adapter backed by ib_insync.

    Usage
    -----
    1. Ensure TWS or IB Gateway is running with API access enabled.
    2. Instantiate with environment=Environment.PAPER for paper trading.
    3. Call connect() before submitting any orders.
    4. Always call disconnect() on shutdown.

    This is a scaffold. Real-money usage requires thorough testing in
    IBKR paper mode first. See ib_insync docs for advanced configuration.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 1,
        environment: Environment = Environment.PAPER,
        journal: Optional[ExecutionJournal] = None,
        risk_engine: Optional[RiskEngine] = None,
        readonly: bool = False,
        timeout: float = 30.0,
    ) -> None:
        if not IB_INSYNC_AVAILABLE:
            raise RuntimeError(
                "ib_insync is not installed. Install it with: pip install ib_insync"
            )

        self._host = host
        self._port = port
        self._client_id = client_id
        self._environment = environment
        self._journal = journal
        self._risk_engine = risk_engine or RiskEngine(journal)
        self._readonly = readonly
        self._timeout = timeout

        self._ib: Any = IB()
        self._lock = threading.Lock()
        self._open_orders: Dict[str, OpenOrder] = {}
        self._client_to_broker: Dict[str, int] = {}

        self.on_fill = EventHook()
        self.on_reject = EventHook()
        self.on_cancel = EventHook()
        self.on_status_change = EventHook()

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        self._ib.connect(
            host=self._host,
            port=self._port,
            clientId=self._client_id,
            readonly=self._readonly,
            timeout=self._timeout,
        )
        self._ib.orderStatusEvent += self._on_order_status
        self._ib.errorEvent += self._on_error
        logger.info(
            "IBKRBroker connected. host=%s port=%d clientId=%d env=%s",
            self._host, self._port, self._client_id, self._environment.value,
        )

    def disconnect(self) -> None:
        try:
            self._ib.disconnect()
        except Exception as exc:
            logger.warning("IBKRBroker disconnect warning: %s", exc)
        logger.info("IBKRBroker disconnected.")

    # ------------------------------------------------------------------
    # Order submission
    # ------------------------------------------------------------------

    def submit_order(self, intent: OrderIntent) -> ExecutionReport:
        try:
            validate_intent(intent)
        except ValueError as exc:
            report = self._rejected_report(intent, str(exc))
            self._emit_reject(report, str(exc))
            return report

        account = self.get_account()
        risk_result = self._risk_engine.check(intent, account)

        if self._journal:
            self._journal.write_intent(intent)
            self._journal.write_risk_check(intent.client_order_id, risk_result)

        if risk_result.verdict == RiskVerdict.REJECT:
            msg = "; ".join(risk_result.reasons)
            report = self._rejected_report(intent, msg)
            self._emit_reject(report, msg)
            if self._journal:
                self._journal.write_report(report)
            return report

        contract = self._build_contract(intent.instrument)
        ib_order = self._build_ib_order(intent, risk_result.approved_quantity)

        trade = self._ib.placeOrder(contract, ib_order)
        broker_order_id = str(trade.order.orderId)

        with self._lock:
            self._client_to_broker[intent.client_order_id] = trade.order.orderId
            self._open_orders[intent.client_order_id] = OpenOrder(
                client_order_id=intent.client_order_id,
                symbol=intent.instrument.symbol,
                side=intent.side.value,
                quantity=risk_result.approved_quantity,
                order_type=intent.order_type.value,
                status=ExecutionStatus.SUBMITTED.value,
                broker_order_id=broker_order_id,
                limit_price=intent.limit_price,
                stop_price=intent.stop_price,
                take_profit_price=intent.take_profit_price,
            )

        report = ExecutionReport(
            execution_id=f"exec-{uuid.uuid4().hex[:12]}",
            client_order_id=intent.client_order_id,
            broker_order_id=broker_order_id,
            status=ExecutionStatus.SUBMITTED,
            symbol=intent.instrument.symbol,
            side=intent.side.value,
            quantity=risk_result.approved_quantity,
            message="Order submitted to IBKR.",
        )

        if self._journal:
            self._journal.write_report(report)

        self.on_status_change.emit({"event": "submitted", "report": to_jsonable(report)})
        return report

    def submit_bracket(self, intent: OrderIntent) -> BracketSubmissionResult:
        """
        Submit a bracket order (entry + protective stop + take-profit)
        using IBKR's native parent/child order mechanism.
        """
        try:
            validate_intent(intent)
        except ValueError as exc:
            report = self._rejected_report(intent, str(exc))
            self._emit_reject(report, str(exc))
            return BracketSubmissionResult(parent=report)

        account = self.get_account()
        risk_result = self._risk_engine.check(intent, account)

        if self._journal:
            self._journal.write_intent(intent)
            self._journal.write_risk_check(intent.client_order_id, risk_result)

        if risk_result.verdict == RiskVerdict.REJECT:
            msg = "; ".join(risk_result.reasons)
            report = self._rejected_report(intent, msg)
            self._emit_reject(report, msg)
            if self._journal:
                self._journal.write_report(report)
            return BracketSubmissionResult(parent=report)

        approved_qty = risk_result.approved_quantity
        contract = self._build_contract(intent.instrument)
        protective_side = "SELL" if intent.side == OrderSide.BUY else "BUY"

        parent_order = self._build_ib_order(intent, approved_qty)
        parent_order.transmit = False

        tp_report: Optional[ExecutionReport] = None
        sl_report: Optional[ExecutionReport] = None

        take_profit_order = None
        stop_loss_order = None

        if intent.take_profit_price is not None:
            take_profit_order = LimitOrder(
                action=protective_side,
                totalQuantity=approved_qty,
                lmtPrice=intent.take_profit_price,
                tif=intent.tif.value,
            )
            take_profit_order.parentId = parent_order.orderId
            take_profit_order.transmit = False

        if intent.stop_price is not None:
            stop_loss_order = StopOrder(
                action=protective_side,
                totalQuantity=approved_qty,
                stopPrice=intent.stop_price,
                tif=intent.tif.value,
            )
            stop_loss_order.parentId = parent_order.orderId
            stop_loss_order.transmit = True  # transmits the whole bracket
        elif take_profit_order is not None:
            take_profit_order.transmit = True  # transmit if no stop

        parent_trade = self._ib.placeOrder(contract, parent_order)
        parent_broker_id = str(parent_trade.order.orderId)

        with self._lock:
            self._client_to_broker[intent.client_order_id] = parent_trade.order.orderId
            self._open_orders[intent.client_order_id] = OpenOrder(
                client_order_id=intent.client_order_id,
                symbol=intent.instrument.symbol,
                side=intent.side.value,
                quantity=approved_qty,
                order_type=intent.order_type.value,
                status=ExecutionStatus.SUBMITTED.value,
                broker_order_id=parent_broker_id,
                limit_price=intent.limit_price,
                stop_price=intent.stop_price,
                take_profit_price=intent.take_profit_price,
            )

        parent_report = ExecutionReport(
            execution_id=f"exec-{uuid.uuid4().hex[:12]}",
            client_order_id=intent.client_order_id,
            broker_order_id=parent_broker_id,
            status=ExecutionStatus.SUBMITTED,
            symbol=intent.instrument.symbol,
            side=intent.side.value,
            quantity=approved_qty,
            message="Bracket parent submitted to IBKR.",
        )

        if take_profit_order is not None:
            tp_trade = self._ib.placeOrder(contract, take_profit_order)
            tp_coid = f"alice-tp-{uuid.uuid4().hex[:12]}"
            tp_report = ExecutionReport(
                execution_id=f"exec-{uuid.uuid4().hex[:12]}",
                client_order_id=tp_coid,
                broker_order_id=str(tp_trade.order.orderId),
                status=ExecutionStatus.SUBMITTED,
                symbol=intent.instrument.symbol,
                side=protective_side,
                quantity=approved_qty,
                message="Bracket take-profit submitted.",
            )

        if stop_loss_order is not None:
            sl_trade = self._ib.placeOrder(contract, stop_loss_order)
            sl_coid = f"alice-sl-{uuid.uuid4().hex[:12]}"
            sl_report = ExecutionReport(
                execution_id=f"exec-{uuid.uuid4().hex[:12]}",
                client_order_id=sl_coid,
                broker_order_id=str(sl_trade.order.orderId),
                status=ExecutionStatus.SUBMITTED,
                symbol=intent.instrument.symbol,
                side=protective_side,
                quantity=approved_qty,
                message="Bracket stop-loss submitted.",
            )

        if self._journal:
            self._journal.write_report(parent_report)
            if tp_report:
                self._journal.write_report(tp_report)
            if sl_report:
                self._journal.write_report(sl_report)

        return BracketSubmissionResult(
            parent=parent_report,
            take_profit=tp_report,
            stop_loss=sl_report,
        )

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    def cancel_order(self, client_order_id: str) -> ExecutionReport:
        with self._lock:
            broker_id = self._client_to_broker.get(client_order_id)

        if broker_id is None:
            return ExecutionReport(
                execution_id=f"cancel-{uuid.uuid4().hex[:12]}",
                client_order_id=client_order_id,
                broker_order_id=None,
                status=ExecutionStatus.FAILED,
                symbol="UNKNOWN",
                side="",
                quantity=0.0,
                message="Broker order ID not found for client order ID.",
            )

        open_trades = {t.order.orderId: t for t in self._ib.openTrades()}
        trade = open_trades.get(broker_id)
        if trade:
            self._ib.cancelOrder(trade.order)

        report = ExecutionReport(
            execution_id=f"cancel-{uuid.uuid4().hex[:12]}",
            client_order_id=client_order_id,
            broker_order_id=str(broker_id),
            status=ExecutionStatus.CANCELLED,
            symbol=self._open_orders.get(client_order_id, OpenOrder(
                client_order_id=client_order_id, symbol="UNKNOWN",
                side="", quantity=0.0, order_type="", status="",
            )).symbol,
            side="",
            quantity=0.0,
            message="Cancel request sent to IBKR.",
            updated_at_utc=utc_now(),
        )

        if self._journal:
            self._journal.write_report(report)

        self.on_cancel.emit({"event": "cancel", "client_order_id": client_order_id, "report": to_jsonable(report)})
        return report

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_open_orders(self) -> List[OpenOrder]:
        trades = self._ib.openTrades()
        result: List[OpenOrder] = []
        for trade in trades:
            o = trade.order
            c = trade.contract
            result.append(
                OpenOrder(
                    client_order_id=str(o.orderId),
                    symbol=c.symbol,
                    side=o.action,
                    quantity=float(o.totalQuantity),
                    order_type=o.orderType,
                    status=trade.orderStatus.status,
                    broker_order_id=str(o.orderId),
                    limit_price=o.lmtPrice if o.lmtPrice else None,
                    stop_price=o.auxPrice if o.auxPrice else None,
                )
            )
        return result

    def get_positions(self) -> List[PositionSnapshot]:
        positions = self._ib.positions()
        result: List[PositionSnapshot] = []
        for pos in positions:
            result.append(
                PositionSnapshot(
                    symbol=pos.contract.symbol,
                    quantity=float(pos.position),
                    avg_cost=float(pos.avgCost),
                    account=pos.account,
                )
            )
        return result

    def get_account(self) -> AccountSnapshot:
        summary = self._ib.accountSummary()
        values: Dict[str, float] = {}
        for item in summary:
            try:
                values[item.tag] = float(item.value)
            except (ValueError, TypeError):
                pass

        return AccountSnapshot(
            account_id=summary[0].account if summary else "IBKR",
            net_liquidation=values.get("NetLiquidation", 0.0),
            available_funds=values.get("AvailableFunds", 0.0),
            buying_power=values.get("BuyingPower", 0.0),
            excess_liquidity=values.get("ExcessLiquidity", 0.0),
            realized_pnl=values.get("RealizedPnL", 0.0),
            unrealized_pnl=values.get("UnrealizedPnL", 0.0),
        )

    def health_check(self) -> Dict[str, Any]:
        connected = self._ib.isConnected()
        return {
            "broker": "IBKRBroker",
            "connected": connected,
            "host": self._host,
            "port": self._port,
            "client_id": self._client_id,
            "environment": self._environment.value,
            "timestamp_utc": utc_now(),
        }

    # ------------------------------------------------------------------
    # IBKR event handlers
    # ------------------------------------------------------------------

    def _on_order_status(self, trade: Any) -> None:
        status_text = trade.orderStatus.status
        status = normalize_status(status_text)
        client_order_id = str(trade.order.orderId)

        with self._lock:
            if client_order_id in self._open_orders:
                self._open_orders[client_order_id].status = status.value

        report = ExecutionReport(
            execution_id=f"status-{uuid.uuid4().hex[:12]}",
            client_order_id=client_order_id,
            broker_order_id=str(trade.order.orderId),
            status=status,
            symbol=trade.contract.symbol,
            side=trade.order.action,
            quantity=float(trade.order.totalQuantity),
            filled_quantity=float(trade.orderStatus.filled),
            avg_fill_price=float(trade.orderStatus.avgFillPrice) if trade.orderStatus.avgFillPrice else None,
            message=status_text,
            updated_at_utc=utc_now(),
        )

        if self._journal:
            self._journal.write_report(report)

        self.on_status_change.emit({"event": "status_change", "status": status.value, "report": to_jsonable(report)})

        if status == ExecutionStatus.FILLED:
            self.on_fill.emit({"event": "fill", "report": to_jsonable(report)})
        elif status == ExecutionStatus.CANCELLED:
            self.on_cancel.emit({"event": "cancel", "report": to_jsonable(report)})

    def _on_error(self, req_id: int, error_code: int, error_string: str, contract: Any) -> None:
        logger.error(
            "IBKR error: reqId=%d code=%d msg=%s contract=%s",
            req_id, error_code, error_string, contract,
        )

    # ------------------------------------------------------------------
    # Contract / order builders
    # ------------------------------------------------------------------

    def _build_contract(self, instrument: Instrument) -> Any:
        asset = instrument.asset_type
        if asset == AssetType.STOCK:
            return Stock(
                instrument.symbol,
                instrument.exchange,
                instrument.currency,
            )
        if asset == AssetType.FOREX:
            return Forex(instrument.symbol)
        if asset == AssetType.FUTURE:
            return Future(
                symbol=instrument.symbol,
                lastTradeDateOrContractMonth=instrument.expiry or "",
                exchange=instrument.exchange,
                currency=instrument.currency,
                multiplier=instrument.multiplier or "",
            )
        if asset == AssetType.CRYPTO:
            return Crypto(
                symbol=instrument.symbol,
                exchange=instrument.exchange,
                currency=instrument.currency,
            )
        raise ValueError(f"Unsupported asset type for IBKR: {asset}")

    def _build_ib_order(self, intent: OrderIntent, quantity: float) -> Any:
        action = intent.side.value
        tif = intent.tif.value

        if intent.order_type == OrderType.MARKET:
            return MarketOrder(action=action, totalQuantity=quantity, tif=tif)
        if intent.order_type == OrderType.LIMIT:
            return LimitOrder(action=action, totalQuantity=quantity, lmtPrice=intent.limit_price, tif=tif)
        if intent.order_type == OrderType.STOP:
            return StopOrder(action=action, totalQuantity=quantity, stopPrice=intent.stop_price, tif=tif)
        if intent.order_type == OrderType.STOP_LIMIT:
            return StopLimitOrder(
                action=action,
                totalQuantity=quantity,
                stopPrice=intent.stop_price,
                lmtPrice=intent.limit_price,
                tif=tif,
            )
        raise ValueError(f"Unsupported order type: {intent.order_type}")

    def _rejected_report(self, intent: OrderIntent, message: str) -> ExecutionReport:
        return ExecutionReport(
            execution_id=f"exec-{uuid.uuid4().hex[:12]}",
            client_order_id=intent.client_order_id,
            broker_order_id=None,
            status=ExecutionStatus.REJECTED,
            symbol=intent.instrument.symbol,
            side=intent.side.value,
            quantity=intent.quantity,
            message=message,
        )

    def _emit_reject(self, report: ExecutionReport, reason: str) -> None:
        self.on_reject.emit({"event": "reject", "reason": reason, "report": to_jsonable(report)})


# =============================================================================
# BROKER FACTORY
# =============================================================================

class BrokerFactory:
    """
    Constructs and returns the appropriate broker adapter based on the
    requested environment or explicit broker type.

    Examples
    --------
    >>> broker = BrokerFactory.create(environment=Environment.PAPER)
    >>> broker.connect()
    >>> report = broker.submit_order(intent)
    >>> broker.disconnect()
    """

    @staticmethod
    def create(
        environment: Environment = Environment.PAPER,
        broker_type: Optional[str] = None,
        journal: Optional[ExecutionJournal] = None,
        risk_engine: Optional[RiskEngine] = None,
        **kwargs: Any,
    ) -> BrokerAdapter:
        """
        Parameters
        ----------
        environment:
            PAPER for simulation, LIVE for real orders.
        broker_type:
            Optional override: 'paper' or 'ibkr'.
        journal:
            Shared ExecutionJournal instance for persistence.
        risk_engine:
            Shared RiskEngine instance.
        **kwargs:
            Forwarded to the chosen broker adapter's constructor.
        """
        resolved = (broker_type or environment.value).lower()

        if resolved == "paper":
            return PaperBroker(
                journal=journal,
                risk_engine=risk_engine,
                **kwargs,
            )

        if resolved in ("ibkr", "live"):
            return IBKRBroker(
                environment=environment,
                journal=journal,
                risk_engine=risk_engine,
                **kwargs,
            )

        raise ValueError(f"Unknown broker type: {resolved!r}. Choose 'paper' or 'ibkr'.")


# =============================================================================
# MODULE SELF-TEST
# =============================================================================

if __name__ == "__main__":
    import tempfile

    print("=== ALICE Broker Adapter - Self Test ===\n")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    journal = ExecutionJournal(db_path)
    risk_engine = RiskEngine(journal)

    broker = BrokerFactory.create(
        environment=Environment.PAPER,
        journal=journal,
        risk_engine=risk_engine,
        initial_cash=50_000.0,
    )
    broker.connect()

    fills: List[Dict[str, Any]] = []
    broker.on_fill.subscribe(lambda ev: fills.append(ev))

    # Feed a price
    broker.update_price("AAPL", 175.0)  # type: ignore[attr-defined]

    # Build risk envelope
    risk = RiskEnvelope(
        max_notional=10_000.0,
        max_position_qty=100.0,
        max_daily_loss=2_000.0,
        max_symbol_exposure=200.0,
        max_order_risk=1_000.0,
        min_confidence=0.5,
        allow_short=True,
    )

    decision = DecisionContext(
        source=IntentSource.ALICE,
        strategy_id="demo",
        strategy_version="1.0",
        confidence=0.85,
    )

    # --- Test 1: Simple market buy ---
    intent = OrderIntent(
        instrument=Instrument("AAPL"),
        action=DecisionAction.ENTER_LONG,
        side=OrderSide.BUY,
        quantity=10.0,
        risk=risk,
        decision=decision,
    )
    report = broker.submit_order(intent)
    print(f"[BUY]  status={report.status.value}  fill_price={report.avg_fill_price}")
    assert report.status == ExecutionStatus.FILLED, f"Expected FILLED got {report.status}"
    assert len(fills) == 1

    # --- Test 2: Market sell ---
    intent2 = OrderIntent(
        instrument=Instrument("AAPL"),
        action=DecisionAction.EXIT_LONG,
        side=OrderSide.SELL,
        quantity=10.0,
        risk=risk,
        decision=decision,
    )
    report2 = broker.submit_order(intent2)
    print(f"[SELL] status={report2.status.value}  fill_price={report2.avg_fill_price}")
    assert report2.status == ExecutionStatus.FILLED

    # --- Test 3: Bracket order ---
    broker.update_price("AAPL", 175.0)  # type: ignore[attr-defined]
    bracket_intent = OrderIntent(
        instrument=Instrument("AAPL"),
        action=DecisionAction.ENTER_LONG,
        side=OrderSide.BUY,
        quantity=5.0,
        stop_price=170.0,
        take_profit_price=185.0,
        risk=risk,
        decision=decision,
    )
    bracket_result = broker.submit_bracket(bracket_intent)
    print(f"[BRACKET] parent={bracket_result.parent.status.value}")
    assert bracket_result.parent.status == ExecutionStatus.FILLED

    # --- Test 4: Confidence rejection ---
    low_conf_decision = DecisionContext(
        source=IntentSource.ALICE,
        strategy_id="demo",
        strategy_version="1.0",
        confidence=0.1,
    )
    intent3 = OrderIntent(
        instrument=Instrument("AAPL"),
        action=DecisionAction.ENTER_LONG,
        side=OrderSide.BUY,
        quantity=5.0,
        risk=risk,
        decision=low_conf_decision,
    )
    report3 = broker.submit_order(intent3)
    print(f"[LOW CONF] status={report3.status.value}")
    assert report3.status == ExecutionStatus.REJECTED

    # --- Test 5: Cancel a limit order ---
    limit_intent = OrderIntent(
        instrument=Instrument("AAPL"),
        action=DecisionAction.ENTER_LONG,
        side=OrderSide.BUY,
        quantity=3.0,
        order_type=OrderType.LIMIT,
        limit_price=160.0,
        risk=risk,
        decision=decision,
    )
    limit_report = broker.submit_order(limit_intent)
    cancel_report = broker.cancel_order(limit_intent.client_order_id)
    print(f"[CANCEL] status={cancel_report.status.value}")
    assert cancel_report.status == ExecutionStatus.CANCELLED

    # --- Account snapshot ---
    acct = broker.get_account()
    print(f"\nAccount: cash={acct.available_funds:.2f}  realized_pnl={acct.realized_pnl:.2f}")

    # --- Health check ---
    health = broker.health_check()
    print(f"Health: {health}")

    broker.disconnect()
    print("\n=== All assertions passed ===")
