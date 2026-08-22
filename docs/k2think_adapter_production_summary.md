# K2Think.ai / Market-DNA Production Evidence Adapter — Summary

## Purpose

`k2think_adapter_production-1.py` is a production-hardened evidence adapter for the K2Think.ai / Market-DNA research pipeline. It converts strategy output into validated, append-only decision packets and an auditable SHA-256 hash-chain ledger.

The module is deliberately **research / paper-trading only**. It contains no broker credentials, live-order client, or execution endpoint.

## Governance invariants

The adapter fails closed unless these controls remain intact:

- `paper_trading_only = true`
- `live_execution_enabled = false`
- `human_approval_required = true`
- `model_auto_promotion = false`
- `execution_adapter = DISABLED_NOT_PRESENT`
- Decision authority remains `EVIDENCE_ONLY`
- Captain MarginCall retains final veto authority

A qualifying directional signal becomes `PAPER_CANDIDATE_REQUIRES_HUMAN_APPROVAL`; otherwise it is `RISK_VETO_NO_TRADE`.

## Production hardening

The adapter adds:

- Persistent SHA-256 ledger continuation with full-chain verification
- Cross-platform lock-file protection for concurrent writers
- Deterministic event IDs
- Replay/idempotency protection
- Strict required-column validation
- Strict packet and governance validation
- Atomic manifest writes
- `fsync`-backed JSONL appends
- Correct risk-approved/vetoed candidate accounting
- Structured logging and explicit failure exit codes
- Explicit reset behavior instead of destructive truncation by default

## Decision-packet contents

Each packet records:

- Schema, deterministic event ID, strategy ID, timestamp, symbol and timeframe
- Market-DNA value structure, gamma regime, value area and swing levels
- Order-flow evidence including delta, delta %, POC, imbalances, absorption and confirmation
- Proposed side (`LONG`, `SHORT`, or `NO_TRADE`), entry reference, stop and target
- Captain MarginCall risk decision and veto reasons
- Governance invariants
- Input/source SHA-256 provenance

## Candidate gate

A directional signal is only considered a paper candidate when all of the following are true:

1. Signal is directional rather than `NO_TRADE`.
2. Data quality passes.
3. The signal is inside the permitted session.
4. Participation/volume passes.
5. No news block is active.

Even then, the proposal remains an `UNVALIDATED_RESEARCH_HYPOTHESIS` and requires human approval.

## Audit architecture

The adapter writes three principal artifacts under the configured output directory:

- `decision_packets.jsonl` — append-only validated decision packets
- `audit_ledger.jsonl` — SHA-256 chained audit records
- `adapter_manifest.json` — run statistics, configuration, final ledger hash and execution-governance state

Before continuing an existing ledger, every record is revalidated against its previous hash. Corrupt JSON, broken chain linkage or a hash mismatch causes the adapter to fail closed.

## Replay protection

Event IDs are deterministically derived from strategy ID, timestamp, symbol, timeframe, input SHA-256 and signal. Existing event IDs are loaded before processing, and duplicates are skipped rather than appended again.

## Verification mode

`--verify-only` validates the existing packet/ledger pair without processing new input. It checks the ledger chain and verifies that the number of unique packet event IDs matches the ledger record count.

## CLI behavior

Normal processing requires `--input` and accepts an output directory. `--reset-output` explicitly removes prior packet/ledger/manifest outputs before a new export. Failures are logged and return exit code `2`; successful runs return `0`.

## Dependency

The adapter imports `StrategyConfig` and `generate_signals` from `orderflow_auction_strategy`. If that module is unavailable on `PYTHONPATH`, startup fails immediately with an actionable error.

## Bottom line

This module is an evidence-governance boundary, not an execution engine. Its strongest features are deterministic provenance, replay resistance, persistent tamper-evident auditing, strict validation, and preservation of K2Think's paper-only/human-approval/risk-veto controls. It is suitable as the handoff layer between an order-flow/auction strategy and downstream research, review, audit, and paper-trading workflows, while intentionally withholding live trading authority.
