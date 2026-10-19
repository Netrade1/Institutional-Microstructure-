# Historical holdings and paper research boundary

SEC holdings must remain outside the L2 decision pipeline. A named manager may appear in a historical filing report, never as the inferred sender of an order. Do not interpret notices, missing data or failed requests as zero holdings.

Execution remains paper-only, with mandatory human approval and Risk Governor veto. Strong model agreement cannot approve a paper trade automatically.

## Enforcement

Mechanism files: `tests/test_sec13f.py` and `tests/test_agents.py`.

`tests/test_sec13f.py::test_holdings_never_import_trading_pipeline`, `test_live_configuration_fails_closed`, the malformed/unavailable evidence tests, and `tests/test_agents.py::TestDecisionParliament::test_strong_paper_candidate_requires_human_approval` / `test_risk_veto_blocks_all`. These ran in the 119-test passing suite recorded in [validation](../docs/sec13f-validation.md).

For operation and limitations, use [the guide](../docs/sec13f.md). Revisit this boundary only with an explicit architectural decision and tests preserving the user-authorized governance.
