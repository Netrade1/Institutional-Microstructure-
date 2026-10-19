# Repository guide

This is a paper-only institutional microstructure research prototype.

- Read [the enforced boundaries](rules/README.md) and [documentation index](docs/README.md).
- Start with [README](README.md) for the existing L2 system.
- For SEC holdings retrieval, failure behavior, evidence provenance and identity boundaries, read [the holdings guide](docs/sec13f.md).
- For the October 19 implementation decisions, tests and known gaps, read [the validation record](docs/sec13f-validation.md).
- Run tests with `python -m pytest -q` after installing the project test dependencies.

Preserve Risk Governor veto and mandatory human approval. Holdings are a separate historical research source; never use them to name the sender of a market order. Configuration must reject live execution. Test these boundaries in `tests/test_sec13f.py` and `tests/test_agents.py`.
