# Change and validation record — October 19, 2026

Request: John requested a separate read-only SEC Form 13F adapter, reproducible evidence, deterministic tests, honest holdings/behavior boundaries and paper-only human-approved operation. Base: PR #7, `copilot/explain-repo-structure`, commit `55728635894908e26af60aedea2a8e254953c21b`. PR #7 was open at inspection. This change is stacked on its head; it is not a merge of PR #7.

## Decision and knowledge delta

Before: L2 participant classification and a synthetic feed existed; the inspected pipeline had no authenticated public holdings retrieval. The code already prohibited participant identity inference, but README wording could imply a filing could justify present-tense attribution. Configuration accepted live mode and Parliament could produce paper approval without human action.

Now: `src/holdings/` provides an independent research CLI/API. No holdings object enters Orchestrator, L2 agents, vote calculation, broker routes or model promotion. Config rejects non-paper mode; the former strong-signal approval branch returns `human_review`. Existing risk/compliance/data gates remain intact. UI text reflects mandatory paper approval.

Knowledge delta: `README.md` routes to `docs/sec13f.md` (operation, rules, limitations, source references) and this record (decisions, evidence, gaps). `AGENTS.md` supplies the previously absent agent entry point. No existing repository-specific routers, ledger or wiki were found. The new `docs/README.md`, `rules/` and `.ai/ledger/decision/` index the guide, enforceable boundary and decision; `.ai/BRIEF.md` is a concise manually maintained checkpoint. The installed Akinator brief generator emitted a nonportable generator reference; its output was replaced with this source-linked checkpoint. The standard-library boundary avoids new runtime dependencies for this research adapter; existing project dependencies remain unchanged.

Alternatives rejected: named-manager output inside behavioral agents (identity leakage), fuzzy security-name matching (false attribution), summing amended reports (double counting), and representing failed downloads as zero positions (false absence). Optional exact identifier mapping remains operator-reviewed rather than pretending an issuer ticker directory is a CUSIP security master.

Compatibility: consumers that relied on `paper_trade_approved` from strong signals must now handle `human_review`. The corresponding existing test was strengthened to require human review and pending-approval wording. No automatic execution or human-approval persistence is introduced. Roll back the adapter independently if needed; do not restore automatic approvals or live-mode configuration as an incidental rollback.

## Observed evidence

An authentic complete SEC submission was downloaded over HTTPS without personal contact information in the request: accession `0001104659-23-116968`, manager **Stilwell Value LLC**, period **2023-09-30**, filed **2023-11-13**. The unmodified source and timestamped checksum manifest are in `tests/fixtures/sec13f/`. Parser output: **39 entries; USD 183,087,736 reported value total**. This validates one authentic filing's parsing and reconciliation to the primary total, not the truth of ownership or general coverage across all filing formats.

The contact-bearing production client was tested using deterministic mocks; an unattended end-to-end live CLI discovery/retrieval run with an operator-approved contact remains unverified. Web retrieval of raw XML was unsupported by the search interface; direct public complete-submission retrieval succeeded. An initial request containing a personal email was rejected by automatic review; no personal email was sent in the successful retrieval.

Full suite: `python -m pytest -q` → **119 passed**, exit 0. Existing Risk Governor veto, compliance and orchestrator tests passed. New tests cover authentic source hash and totals, synthetic amendments/notices/options/principal values, confidential/combination flags, date/value-unit transitions, malformed/nonfinite/contradictory evidence, identity/digest/time mismatches, discovery scope and historical deduplication/conflicts, mapping uncertainty, blocked transport, error exits and import isolation.

Test environment: Python 3.12 virtual environment with pytest, pytest-asyncio, pydantic, numpy, pandas, python-dotenv, loguru and orjson. Initial collection failed because orjson was absent; installing that existing dependency resolved collection. No tests were skipped or deleted. Synthetic variants are generated from the authentic fixture in memory and labeled synthetic, not claimed as additional real filings.

## Limits and next evidence

- One authentic modern 13F-HR has been validated. Authentic amendment, notice, legacy-unit and multi-document coverage remains unverified; those paths have deterministic synthetic tests.
- No production security mapping dataset is configured. No claim about SPCX ownership or a particular fund is established by this implementation.
- No complete amendment consolidation, historical ownership change calculation, or point-in-time strategy evaluation is implemented.
- There is no evidence here of returns, profitability, model calibration, trades, fills or independent manager asset verification.
- Revisit this record when SEC schemas/units change, new formats are supported, mapping sources are introduced, or the adapter is connected to another consumer.

Review lenses: source economics remain historical and incomplete; architecture separates identities from L2; operation has explicit contact/rate/error requirements; numeric handling preserves units and exact reported totals; product language avoids current ownership and order attribution. Manual documentation review checked README → guide/record reachability and correspondence to implemented behavior.

Akinator knowledge checks: strict coverage reported no findings; ledger verification and rule conflict checks passed. These are documentation consistency checks, not additional trading or SEC integration proof.
