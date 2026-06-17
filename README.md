# Institutional Microstructure Intelligence System
### Phase 1 — Research Prototype | Paper-Only | Compliance-Aware | Audit-Driven

> **"Evidence first. Risk second. Execution last."**

A sophisticated, institutional-grade AI Agentic Trading Intelligence System for Level 2 order book analysis, market microstructure intelligence, behavioural order-flow inference, and risk-controlled decision support.

---

## What This Is

This system analyses Level 2 order book data, market depth, time-and-sales data, liquidity behaviour, order-flow imbalance, trade prints, bid/ask pressure, volume behaviour, and market microstructure signals — through a chatbot-style interface and a live research dashboard.

It functions as a **disciplined institutional research desk with a risk officer beside it**, not as an uncontrolled autonomous trading bot. Every signal is probabilistic, every claim is bounded by available evidence, and no execution occurs without human authorisation.

---

## Critical Compliance Constraint

> **The system classifies behaviour, not identity.**

The system may say:
- *"The activity resembles institutional-style accumulation."*
- *"The order flow suggests large-participant absorption."*
- *"Institutional-style accumulation probability: 68%, confidence: medium."*

The system will **never** say:
- *"BlackRock is buying here."*
- *"Citadel is selling this level."*
- *"A specific hedge fund is accumulating."*

Unless that claim is backed by legal, public, authorised, and verifiable data such as SEC filings or licensed institutional datasets.

---

## Architecture

```
User / Chatbot Interface
        ↓
Agentic Orchestration Layer
        ↓
Market Data Intake Layer  ←  Polygon.io / Alpaca / IBKR / Sample feed
        ↓
Order Book Processing Engine
        ↓
Feature Engineering Layer
        ↓
Market Participant Behaviour Inference Layer
        ↓
[Phase 2] Machine Learning Prediction Layer
        ↓
Decision Parliament / Multi-Agent Review
        ↓
Risk & Compliance Guardrails
        ↓
Research Output / Alert / Paper Trade
        ↓
Audit Ledger + Explainability Report
```

---

## Phase 1 Components

| Module | Location | Purpose |
|---|---|---|
| Sample Feed | `src/data_intake/sample_feed.py` | Synthetic L2 feed for offline development |
| Polygon Feed | `src/data_intake/polygon_feed.py` | Polygon.io WebSocket feed adapter |
| Data Integrity Agent | `src/data_intake/data_integrity_agent.py` | Feed quality, latency, bad-tick detection |
| Data Models | `src/data_intake/models.py` | Canonical Quote, OrderBookSnapshot, Trade models |
| Order Book Engine | `src/order_book/engine.py` | Depth, imbalance, absorption, sweep, spoof-like signals |
| Feature Engineer | `src/features/engineer.py` | 40+ ML-ready features (OB + technical + behavioral) |
| Order Book Analyst | `src/agents/order_book_analyst.py` | Directional bias from order book signals |
| Market-DNA Detector | `src/agents/market_dna_detector.py` | Regime classification |
| Institutional Footprint Agent | `src/agents/institutional_footprint.py` | Behavioural pattern inference (compliance-bounded) |
| Risk Governor | `src/agents/risk_governor.py` | Risk evaluation with veto authority |
| Compliance Agent | `src/agents/compliance_agent.py` | Hard-coded identity-inference blocks |
| Decision Parliament | `src/agents/decision_parliament.py` | Multi-agent voting and final disposition |
| Chatbot Interface | `src/chatbot/interface.py` | Natural-language command parsing and response |
| Audit Ledger | `src/audit/ledger.py` | Append-only JSONL audit log |
| Orchestrator | `src/orchestrator.py` | Full pipeline coordinator |
| Dashboard | `src/dashboard/app.py` | Streamlit research dashboard |
| CLI | `main.py` | Demo, chat, and dashboard launcher |

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — add your Polygon.io or Alpaca API keys if using live feeds.
# The sample feed works offline with no API keys required.
```

### 3. Run offline demo (no API keys needed)

```bash
python main.py demo --symbol NVDA --ticks 30 --verbose
```

### 4. Interactive chatbot session

```bash
python main.py chat --symbol AAPL
```

**Example commands in the chatbot:**
```
analyze AAPL
is there buyer absorption?
are large sellers stacking the ask?
summarize institutional activity
what is the order flow regime?
explain the risk before entry
should this setup be paper-traded?
help
```

### 5. Launch the Streamlit dashboard

```bash
python main.py dashboard
# or directly:
streamlit run src/dashboard/app.py
```

### 6. Run tests

```bash
pytest tests/ -v
```

---

## Features Computed

### Core Order Book Features (20+)
`bid_ask_imbalance`, `depth_weighted_imbalance`, `spread`, `mid_price`, `microprice`, `microprice_bias`, `order_flow_imbalance`, `absorption_score`, `sweep_intensity`, `spoof_like_score`, `iceberg_like_score`, `bid/ask_replenishment_rate`, `volume_at_bid/ask`, `rolling_buy_sell_ratio`, `spread_multiple`, `stacking_bid/ask`, `pulling_bid/ask`, …

### Technical Indicators
`vwap`, `vwap_deviation`, `rvol`, `rsi_14`, `atr_14`, `macd_line/signal/histogram`, `bb_upper/lower/width/pct_b`, `obv`, `ma_slope_5/20`

### Behavioural Composite Scores
`accumulation_score`, `distribution_score`, `institutional_footprint_prob`, `momentum_ignition_risk`, `liquidity_trap_risk`, `breakout_confirmation_score`, `false_breakout_prob`

---

## Decision Parliament Dispositions

| Disposition | Meaning |
|---|---|
| `research_approved` | Analysis delivered, no execution signal |
| `watchlist` | Setup identified, not yet actionable |
| `paper_trade_approved` | All agents clear — paper execution authorised |
| `human_review` | Conflicting signals — escalate to analyst |
| `rejected` | Evidence insufficient |
| `risk_veto` | Risk Governor blocked execution |
| `data_insufficient` | Feed quality too low for reliable output |
| `blocked` | Compliance Agent blocked the output |

---

## Execution Modes

| Stage | Status |
|---|---|
| 1. Research only | ✅ Active (Phase 1) |
| 2. Historical backtest | 🔲 Phase 2 |
| 3. Paper trading | 🔲 Phase 3 (broker sandbox) |
| 4. Simulated execution with slippage | 🔲 Phase 4 |
| 5. Human-approved tiny-capital live test | 🔲 Phase 5 |
| 6. Controlled monitored deployment | 🔲 Phase 6 |

**Live trading is disabled by default.** `EXECUTION_MODE=paper` is enforced in configuration. `EXECUTION_MODE=live` requires explicit override, human approval, and passing all risk/compliance gates.

---

## Development Roadmap

| Phase | Description | Status |
|---|---|---|
| **Phase 1** | Research Prototype: L2 parser, feature engineering, chatbot, audit log, dashboard | ✅ Complete |
| **Phase 2** | ML Baseline: Random Forest / XGBoost, walk-forward validation, prediction dashboard | 🔲 Planned |
| **Phase 3** | Agentic Framework: LangGraph orchestration, News/Filings Agent, LLM explanation | 🔲 Planned |
| **Phase 4** | Deep Learning: LSTM, Transformer, DeepLOB, anomaly detection | 🔲 Planned |
| **Phase 5** | Paper Trading Execution: broker sandbox, slippage logging, RL-based execution | 🔲 Planned |
| **Phase 6** | Controlled Live Testing: tiny capital, auto-shutdown, compliance review | 🔲 Long-term |

---

## Limitations

**What Level 2 data can reasonably suggest:**
- Buyer/seller pressure at specific price levels
- Liquidity imbalance between bid and ask
- Absorption, accumulation-like, or distribution-like behaviour patterns
- Algorithmic or market-maker-like quoting patterns
- Spoof-like or iceberg-like activity signals

**What Level 2 data cannot prove:**
- The legal identity of any specific buyer or seller
- Whether a named fund, institution, or individual is behind activity
- The true intent behind any order with certainty
- That any observed pattern will result in a specific price outcome

---

## Technology Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Data Science | NumPy, pandas, Polars |
| ML (Phase 2+) | scikit-learn, XGBoost, LightGBM, PyTorch |
| Market Data | Polygon.io, Alpaca, Interactive Brokers API |
| Dashboard | Streamlit, Plotly |
| Agentic (Phase 3+) | LangGraph, CrewAI, or custom router |
| LLM (Phase 3+) | OpenAI / Anthropic / DeepSeek / Ollama (local) |
| Storage | PostgreSQL, Parquet, JSONL audit logs |
| API | FastAPI, WebSockets |

---

## Responsible Use

This system is a **research tool**. It does not constitute financial advice. Past performance of any signal or model does not guarantee future performance. All behavioural classifications are probabilistic estimates based on observable market data only.

> The mature system behaves like a disciplined institutional research desk with a risk officer beside it — not like a reckless trading bot.
