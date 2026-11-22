# Liquidity sweep detection contract

## Purpose and scope

This implements the price-detection process from ReubenMiles' supplied Pine v6
`Liquidity Hunter | Clean Signals`, with the source attribution and MPL notice
preserved in the derived files. It has no broker connection, order endpoint,
portfolio sizing, entry/exit strategy, risk approval, or human-approval issuer.

Implementation base: `Netrade1/Institutional-Microstructure-`, review branch
`review/smart-l2-integration-20261122`, pinned commit
`7b769ccc81e82f544e996a94222a6cfac95475b6`.

The Python detector is streaming, causal, and deterministic for an identical
input sequence and configuration. Prices use Decimal. The Pine indicator uses
native `ta.pivothigh` / `ta.pivotlow` and `barstate.isconfirmed`.

## Original detection conditions

1. Default swing length is five bars on either side. The pivot's occurrence time
   and later confirmation time are distinct.
2. A newly confirmed pivot replaces its side's previous stored level before
   testing the current candle, matching the original statement ordering.
3. BUY condition: `low < lastLow` and `close > lastLow`.
4. SELL condition: `high > lastHigh` and `close < lastHigh`.
5. Only a completed candle can produce an event. Merely touching or closing
   exactly on a level is insufficient.
6. Candle color is irrelevant. There is no open-versus-close test.

No signal is backdated to the pivot's occurrence or to the sweep candle's wick.
There is no extra five-bar delay after a later sweep of an already known level.

## Added research policies

These are implementation safeguards introduced with this change, not statements
that the user previously approved a new trading strategy or numeric risk plan.

| Policy | Default | Effect |
|---|---|---|
| Unique pivot extremum | Required in Python; enabled in Pine | Equal extrema in the confirmation window are not promoted. This avoids claiming unobserved cross-runtime tie parity. |
| One directional event per level | Enabled | Later raw sweeps remain observable but do not create repeated eligible setup events. |
| Dual-direction candle | Suppressed | Preserve both raw flags, emit no directional candidate. |
| Session reset | Enabled | Clear levels and pivot warmup at an explicit new session. |
| Missing-bar gap | Reset | Clear levels and pivot warmup rather than bridging unobserved bars. |
| Maximum level age | 0, disabled | No invented age threshold. When configured, age is measured in bars since confirmation. |

Python sessions are explicit producer-supplied `session_id` values. Pine uses
`time_tradingday`, which is a trading-day policy, not proof of a particular
regular-hours or premarket calendar. Python and Pine comparisons must use matching
session identifiers, chart data, timeframe, and settings. A timestamp gap resets
warmup even when carrying levels across session labels is enabled.

The Pine indicator supports standard fixed intraday time bars. Unsupported chart
types or unavailable/inconsistent bar times yield no candidates. Its optional
native-tie mode is not claimed to have a matching Python implementation.

No unreviewed ATR stop, 2R target, position size, risk percentage, ADX threshold,
RSI setting, or VWAP/CVD sign rule is added to this detector. Such rules belong in
the existing independently governed strategy and risk layers.

## Python API and bar contract

```python
from integrations.liquidity_sweep import DetectorConfig, LiquiditySweepDetector

detector = LiquiditySweepDetector(
    symbol="SYNTH",
    timeframe_ns=60_000_000_000,
    source="synthetic-fixture",
    config=DetectorConfig(swing_length=5),
)
observation = detector.ingest(bar, asof_ns=decision_availability_ns)
```

`bar` has these fields:

| Field | Meaning |
|---|---|
| `symbol`, `source` | Explicit identities matching the detector scope |
| `timeframe_ns` | Positive fixed bar duration in integer nanoseconds |
| `session_id` | Explicit session identity, not inferred from local machine time |
| `open_time_ns`, `close_time_ns` | Bar interval boundaries |
| `received_ns` | When the completed record became available |
| `open`, `high`, `low`, `close` | Finite positive Decimal-compatible prices; decimal strings are recommended |
| `is_closed` | Actual boolean, not a truthy string |

The replay wrapper stores one JSON object per line containing exactly `bar` and
`asof_ns`. The decision boundary cannot precede the completed record's receipt,
and receipt cannot precede the bar close. This is point-in-time replay, not a
claim that historical observations are current market data.

Invalid finalized bars latch the detector closed until explicit reset. A reset
clears state and requires a fresh contiguous warmup. Unconfirmed bars do not
change state. A matching duplicate of the latest finalized bar is marked as a
duplicate and cannot emit a second candidate; corrections and backward history
must be rejected and replayed explicitly rather than changing prior decisions.

The result contains raw BUY/SELL booleans, an optional eligible `candidate_side`,
level provenance, confirmation/availability timestamps, policy, reason codes,
and stable identifiers. `candidate_side` describes a chart setup only. The
financial decision remains `NO_TRADE`.

## Read-only L2 composition

```python
from integrations.smart_l2_readonly import ReadOnlyBook
from integrations.sweep_research import SweepResearchPipeline

pipeline = SweepResearchPipeline(
    "SYNTH", 60_000_000_000, "synthetic-fixture",
    book=ReadOnlyBook("SYNTH"), market_source="synthetic-book",
)
# Market records need explicit source and session_id in addition to the book API.
pipeline.ingest_market_event(market_record, asof_ns=market_availability_ns)
research = pipeline.ingest_bar(bar, asof_ns=decision_availability_ns)
```

The wrapper prevents a market state received after the decision boundary from
being joined into an earlier candle observation. Session mismatch also prevents
the join. A new market session requires a fresh snapshot and resets the book's
accumulators. The existing book's internal freshness setting is not redefined as
a user-approved strategy threshold.

Book metrics remain explicitly unverified diagnostics. Their `cvd` and `vwap`
values must not be relabeled authenticated True Delta, Session CVD, or Session
VWAP. The detector neither authenticates a provider nor establishes entitlement.

## Downstream evidence and authorization boundary

The evidence type is `OHLC_PRICE_PATTERN`. Any downstream field requiring
`TRADE_TAPE` must remain unavailable until independent tape evidence is supplied.
In particular, a price reclaim cannot populate an authenticated tape/sweep
confirmation field or become a human approval.

All composed observations retain:

```text
decision = NO_TRADE
authority = EVIDENCE_ONLY
paper_trading_only = true
live_execution_enabled = false
human_approval_required = true
risk_governor_final_veto = true
model_auto_promotion = false
execution_adapter = DISABLED_NOT_PRESENT
```

The remaining checks include verified Session VWAP, True Delta and Session CVD,
trade/tape evidence, existing Mk-V qualification, the existing Risk Governor,
and independently signed human approval. This package implements no substitute
authorization path, and a SELL setup does not open a short or close a position.

## Pine usage

Paste `pine/liquidity_hunter_research.pine` into Pine Editor, save, and compile.
Review its visible levels and setup markers on ordinary intraday candlesticks.
Levels appear only once confirmed. Label visibility and alert enablement are
separate controls. Create an alert for the script's `alert()` calls and retain
bar-close behavior; the payload is research evidence, not an order instruction.

Pine and Python JSON envelopes are intentionally explicit about their different
timestamp units: Pine uses milliseconds and Python uses nanoseconds. Do not join
their timestamps or instrument identifiers without normalization. Native Pine
compilation, chart replay, tie handling, and cross-runtime signal parity remain
separate observed acceptance gates.

Pine exports evidence prices with up to 16 fractional digits instead of rounding
to the instrument's minimum tick. Its JSON declares this precision limit and
does not claim an exact binary-float round trip. The observation key is descriptive,
not a cryptographic integrity hash. Python normalizes exact Decimal inputs;
decimal-string inputs avoid importing a caller's binary-float rounding.

## Replay and validation

```bash
python -m unittest discover -s tests -v
python -m compileall -q integrations tests
python -m integrations.sweep_research --input examples/synthetic_sweep_bars.jsonl --out reports/local/sweep_evidence.jsonl --symbol SYNTH --source synthetic-fixture --timeframe-seconds 60
git diff --check
```

The example is entirely synthetic. It exercises a known low, BUY, repeated BUY,
known high, SELL, and a dual-direction candle. It contains no orders or returns.
Replay records every observation, including suppressed and unavailable cases.
The input hash establishes local byte identity, not provider authenticity.

Output is published only after all input rows pass validation. Existing output
files are preserved, including under concurrent publication. A rejected replay
does not publish a misleading partial result. Choose a new output path to rerun.

Software checks establish defined detector behavior and authority boundaries.
They do not establish profitable expectancy, actual broker fills, authenticated
market data, deployment, or permission to trade.
