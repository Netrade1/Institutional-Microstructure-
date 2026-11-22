# Institutional-Microstructure-
My liberty of Code to my Scripts 🗽 

## Liquidity sweep detection — research only

The new detector records a completed candle's breach and reclaim of a previously
confirmed swing level. It is price-pattern evidence, not authenticated order flow
or an approved trade. Every integration observation retains `NO_TRADE` and
`EVIDENCE_ONLY` authority.

- [Detection contract, policies, and use](docs/liquidity_sweep_detection.md)
- [Pine v6 indicator](pine/liquidity_hunter_research.pine)
- [Python streaming detector](integrations/liquidity_sweep.py)
- [Read-only L2 observation bridge and JSONL replay](integrations/sweep_research.py)
- [Validation record](docs/liquidity_sweep_validation.md)

Python 3.10+ and the standard library are sufficient for this detector and its
tests. The unrelated legacy evidence adapter has separate dependencies.

```bash
python -m unittest discover -s tests -v
python -m integrations.sweep_research --input examples/synthetic_sweep_bars.jsonl --out reports/local/sweep_evidence.jsonl --symbol SYNTH --source synthetic-fixture --timeframe-seconds 60
```

The example contains synthetic candles for correctness checks, with no returns,
fills, or profitability claims. Choose a new `--out` path when rerunning; replay
never overwrites an existing output. The Pine source still requires observed
compilation and chart-replay comparison in TradingView before runtime parity can
be claimed.
