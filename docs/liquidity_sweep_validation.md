# Liquidity sweep implementation — observed validation

Date: 2026-11-22.

Source base: `Netrade1/Institutional-Microstructure-` at
`7b769ccc81e82f544e996a94222a6cfac95475b6`, the existing Smart L2 review branch.
This change adds an OHLC detector and read-only evidence composition. It does not
merge or deploy the trading platform, authenticate market data, or authorize a
paper/live order.

## Observed checks

| Check | Observed result |
|---|---|
| `python -m unittest discover -s tests -v` | 49 passed; no failures or skips |
| Detector tests | 30 passed |
| Existing read-only L2 tests | 7 passed |
| Read-only composition and replay tests | 12 passed |
| `python -m compileall -q integrations tests` | Passed |
| `git diff --check` | Passed |
| Documented synthetic CLI replay | Completed; 16 observations |
| Independent code review | Completed; identified and corrected Pine evidence tick-rounding issue |
| Pine UTF-8/string/delimiter/whitespace inspection | Completed; not a compiler result |
| TradingView compilation | Not observed |
| Python/Pine chart-replay parity | Not observed |
| Real provider feed/entitlement/recording acceptance | Not performed |
| Profitability or paper-fill evaluation | Not performed; no fills or returns generated |

The local test count includes focused regressions for pivot confirmation delay,
prefix invariance, update ordering, strict equalities, candle-color independence,
ambiguous dual sweeps, reused levels, ties, session and gap warmup, malformed
inputs, timing availability, duplicate/correction handling, configuration
identity, no authorization promotion, future-market joins, mismatched sessions,
deterministic replay, ignored-input accounting, and atomic output publication.

## Synthetic replay evidence

Input: `examples/synthetic_sweep_bars.jsonl`.

Input SHA-256:
`2de650760b705798ab0880dccc0794bb77ef0d1f2bb824bc6bbd8854c3adf8ae`.

Output SHA-256 from the documented default replay:
`adf122cb6ee889c8331541d7f215ecb0f14296ed2769b3c6cb26e8c168da9cc6`.

| One-based bar | Raw pattern | Eligible setup | Result |
|---|---|---|---|
| 12 | BUY | BUY | Price-pattern evidence only |
| 13 | BUY | None | Repeated level suppressed |
| 15 | SELL | SELL | Price-pattern evidence only |
| 16 | BUY and SELL | None | Ambiguous dual sweep suppressed |

All 16 output observations retain `decision=NO_TRADE`, `authority=EVIDENCE_ONLY`,
paper-only governance, and required external verification/approval checks.
The data are invented test candles. Their behavior establishes plumbing and
specified detection logic only, not market expectancy or actual fills.

## Review correction

The independent review found that Pine's `format.mintick` would round exported
prices while the raw detection comparison used the original values. A sub-tick
reclaim could therefore appear as equality in the JSON evidence. The corrected
formatter exports up to 16 fractional digits and explicitly labels its bounded
precision. The observation key remains non-cryptographic, and exact cross-runtime
numeric parity remains unverified.

## Remaining acceptance boundaries

The Pine indicator must be compiled and compared on actual standard intraday
chart bars. Chart/trading-day scope must match the Python producer's explicit
session identifiers. Native-tie mode has no Python equivalence claim.

Provider authentication, true event/receipt timestamps, actual Session VWAP and
True Delta/CVD, the downstream tape contract, Risk Governor and signed human
approval must be verified independently. The detector does not satisfy or
replace these checks. Any status of the GitHub CI run is separate evidence from
the local results recorded here.
