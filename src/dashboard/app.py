"""
dashboard/app.py – Streamlit Research Dashboard (Phase 1).

Provides a live visual interface for:
  - Order book depth chart (bid / ask ladders)
  - Bid/ask imbalance gauge
  - Order flow imbalance time series
  - Behavioral signal panel
  - Decision Parliament disposition
  - Chat interface
  - Audit log viewer

Run with:
    streamlit run src/dashboard/app.py
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from threading import Thread

import plotly.graph_objects as go
import streamlit as st

from src.config import DEFAULT_SYMBOL
from src.data_intake.sample_feed import SampleFeedAdapter
from src.orchestrator import Orchestrator

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Microstructure Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Configuration")
    symbol = st.text_input("Symbol", value=DEFAULT_SYMBOL).upper()
    feed_source = st.selectbox("Data Feed", ["Sample (offline)", "Polygon.io", "Alpaca"])
    st.caption("Live feeds require API keys in .env")
    st.divider()
    st.markdown(
        "**Execution Mode**\n"
        "🟡 PAPER ONLY  \n"
        "Live execution is disabled by default.  \n"
        "Human approval required for live trading."
    )
    st.divider()
    st.caption(
        "⚠️ All analysis is for research purposes only. "
        "Behavioural classifications are probabilistic estimates. "
        "Participant identity cannot be inferred from Level 2 data."
    )

# ── Session state ─────────────────────────────────────────────────────────────
if "orchestrator" not in st.session_state or st.session_state.get("symbol") != symbol:
    st.session_state.orchestrator = Orchestrator(symbol)
    st.session_state.symbol = symbol
    st.session_state.obi_history = deque(maxlen=120)
    st.session_state.ofi_history = deque(maxlen=120)
    st.session_state.mid_history = deque(maxlen=120)
    st.session_state.ts_history = deque(maxlen=120)
    st.session_state.chat_history = []
    st.session_state.latest_result = None

orch: Orchestrator = st.session_state.orchestrator

# ── Header ────────────────────────────────────────────────────────────────────
st.title(f"📊 Institutional Microstructure Intelligence — {symbol}")
st.caption("Phase 1 Research Prototype | Paper-Only | Compliance-Aware | Audit-Driven")

# ── Tick one snapshot synchronously (for demo / refresh) ─────────────────────
feed = SampleFeedAdapter(symbol=symbol, base_price=185.0)
snapshot = feed.get_snapshot()
trades = feed._generate_trades()

result = orch.process(snapshot, trades)
st.session_state.latest_result = result

state = orch.latest_state
features = orch.latest_features
health = orch.latest_health

# Store history
ts = time.time()
st.session_state.obi_history.append(state.book_imbalance)
st.session_state.ofi_history.append(state.order_flow_imbalance)
st.session_state.mid_history.append(state.mid_price)
st.session_state.ts_history.append(ts)

# ── Top KPI row ───────────────────────────────────────────────────────────────
col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    st.metric("Mid Price", f"${state.mid_price:.2f}")
with col2:
    st.metric("Spread", f"${state.spread:.4f}", f"{state.spread_multiple:.1f}×avg")
with col3:
    obi = state.book_imbalance
    col3.metric("Book Imbalance", f"{obi:+.3f}", "Bullish" if obi > 0.15 else "Bearish" if obi < -0.15 else "Neutral")
with col4:
    st.metric("Absorption", f"{state.absorption_score:.2f}")
with col5:
    st.metric("Sweep", f"{state.sweep_intensity:.2f}")
with col6:
    disp_color = {
        "paper_trade_approved": "🟢",
        "watchlist": "🟡",
        "research_approved": "🔵",
        "risk_veto": "🔴",
        "data_insufficient": "⚠️",
        "blocked": "⛔",
        "human_review": "🟠",
        "rejected": "⚫",
    }.get(result.disposition, "⚪")
    st.metric("Disposition", f"{disp_color} {result.disposition.replace('_', ' ').upper()}")

st.divider()

# ── Two-column layout: order book + charts ────────────────────────────────────
left, right = st.columns([1, 2])

with left:
    st.subheader("📖 Order Book Depth")
    if state.bids and state.asks:
        bid_prices = [lvl.price for lvl in state.bids[:8]]
        bid_sizes = [lvl.size for lvl in state.bids[:8]]
        ask_prices = [lvl.price for lvl in state.asks[:8]]
        ask_sizes = [lvl.size for lvl in state.asks[:8]]

        fig_ob = go.Figure()
        fig_ob.add_trace(go.Bar(
            x=bid_sizes,
            y=[f"${p:.2f}" for p in bid_prices],
            orientation="h",
            name="Bid",
            marker_color="rgba(0, 200, 100, 0.7)",
        ))
        fig_ob.add_trace(go.Bar(
            x=ask_sizes,
            y=[f"${p:.2f}" for p in ask_prices],
            orientation="h",
            name="Ask",
            marker_color="rgba(220, 60, 60, 0.7)",
        ))
        fig_ob.update_layout(
            barmode="overlay",
            height=350,
            margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(x=0.7, y=1),
            xaxis_title="Size",
        )
        st.plotly_chart(fig_ob, use_container_width=True)
    else:
        st.info("Waiting for order book data…")

    # Signal panel
    st.subheader("🔔 Active Signals")
    for sig in state.signals:
        if "stacking" in sig.lower() or "absorption" in sig.lower():
            st.warning(sig)
        elif "sweep" in sig.lower() or "spoof" in sig.lower():
            st.error(sig)
        elif "no significant" in sig.lower():
            st.info(sig)
        else:
            st.success(sig)

with right:
    st.subheader("📈 Order Book Imbalance (rolling)")
    obi_list = list(st.session_state.obi_history)
    ofi_list = list(st.session_state.ofi_history)
    mid_list = list(st.session_state.mid_history)

    if obi_list:
        fig_obi = go.Figure()
        fig_obi.add_trace(go.Scatter(
            y=obi_list, mode="lines", name="OBI",
            line=dict(color="royalblue", width=2),
        ))
        fig_obi.add_trace(go.Scatter(
            y=ofi_list, mode="lines", name="OFI",
            line=dict(color="darkorange", width=2),
        ))
        fig_obi.add_hline(y=0, line_dash="dash", line_color="gray")
        fig_obi.add_hline(y=0.3, line_dash="dot", line_color="green", annotation_text="Bullish threshold")
        fig_obi.add_hline(y=-0.3, line_dash="dot", line_color="red", annotation_text="Bearish threshold")
        fig_obi.update_layout(
            height=240,
            margin=dict(l=10, r=10, t=10, b=10),
            yaxis=dict(range=[-1.1, 1.1]),
        )
        st.plotly_chart(fig_obi, use_container_width=True)

    st.subheader("💹 Mid Price")
    if mid_list:
        fig_mid = go.Figure()
        fig_mid.add_trace(go.Scatter(
            y=mid_list, mode="lines", name="Mid",
            line=dict(color="white", width=2),
            fill="tozeroy", fillcolor="rgba(100,100,200,0.15)",
        ))
        if features and features.vwap:
            fig_mid.add_hline(y=features.vwap, line_dash="dash", line_color="gold",
                              annotation_text="VWAP")
        fig_mid.update_layout(
            height=200,
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig_mid, use_container_width=True)

# ── Behavioral / Institutional panel ─────────────────────────────────────────
st.divider()
st.subheader("🔍 Behavioral Intelligence")
b1, b2, b3, b4 = st.columns(4)

with b1:
    st.metric("Accumulation Score", f"{features.accumulation_score:.2f}" if features else "—")
with b2:
    st.metric("Distribution Score", f"{features.distribution_score:.2f}" if features else "—")
with b3:
    st.metric("Inst. Footprint Prob", f"{features.institutional_footprint_prob:.0%}" if features else "—")
with b4:
    st.metric("Liquidity Trap Risk", f"{features.liquidity_trap_risk:.2f}" if features else "—")

# ── Technical indicators ─────────────────────────────────────────────────────
st.divider()
st.subheader("📐 Technical Indicators")
t1, t2, t3, t4, t5 = st.columns(5)
with t1:
    st.metric("RSI (14)", f"{features.rsi_14:.1f}" if features and not __import__('math').isnan(features.rsi_14) else "—")
with t2:
    st.metric("ATR (14)", f"{features.atr_14:.4f}" if features and not __import__('math').isnan(features.atr_14) else "—")
with t3:
    st.metric("MACD", f"{features.macd_line:.4f}" if features and not __import__('math').isnan(features.macd_line) else "—")
with t4:
    st.metric("BB Width", f"{features.bb_width:.4f}" if features and not __import__('math').isnan(features.bb_width) else "—")
with t5:
    st.metric("RVOL", f"{features.rvol:.2f}×" if features else "—")

# ── Data quality ──────────────────────────────────────────────────────────────
st.divider()
st.subheader("🛡️ Data & Risk Status")
dq1, dq2, dq3, dq4, dq5 = st.columns(5)
with dq1:
    q = health.quality_score if health else 0
    st.metric("Feed Quality", f"{q:.0%}", delta="OK" if q >= 0.8 else "LOW")
with dq2:
    st.metric("Latency", f"{health.latency_ms:.0f}ms" if health else "—")
with dq3:
    st.metric("Risk Status", result.risk_status.upper())
with dq4:
    st.metric("Compliance", result.compliance_status.upper())
with dq5:
    st.metric("Spoof-like Score", f"{state.spoof_like_score:.2f}")

# ── Decision Parliament summary ───────────────────────────────────────────────
st.divider()
st.subheader("🏛️ Decision Parliament")
with st.expander("View Parliament Votes", expanded=True):
    parl_cols = st.columns(5)
    parl_cols[0].metric("OB Analyst", f"{result.ob_analyst_vote.upper()}", f"{result.ob_analyst_confidence:.0%}")
    parl_cols[1].metric("Market DNA", result.dna_regime.upper(), f"{result.dna_confidence:.0%}")
    parl_cols[2].metric("Footprint", result.inst_footprint_label.replace("_", " ").upper(), f"{result.inst_footprint_prob:.0%}")
    parl_cols[3].metric("Risk Gov.", result.risk_status.upper())
    parl_cols[4].metric("Compliance", result.compliance_status.upper())
    st.info(f"**Reasoning:** {result.reasoning}")
    st.caption(f"⚠️  {result.limitations}")

# ── Chatbot interface ─────────────────────────────────────────────────────────
st.divider()
st.subheader("💬 Research Chatbot")

chat_container = st.container()
with chat_container:
    for msg in st.session_state.chat_history[-10:]:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            st.markdown(f"**You:** {content}")
        else:
            st.markdown(f"**System:**\n```\n{content}\n```")

user_input = st.chat_input("Ask about the order book… (e.g. 'analyze AAPL', 'explain the risk', 'help')")
if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    response = orch.chat(user_input)
    st.session_state.chat_history.append({"role": "assistant", "content": response.text})
    st.rerun()

# ── Auto-refresh ──────────────────────────────────────────────────────────────
st.divider()
refresh = st.button("🔄 Refresh Analysis")
if refresh:
    st.rerun()

st.caption(
    "Auto-refresh: press Refresh or use `streamlit run` with `--server.runOnSave true`. "
    "Live feed streaming will be added in Phase 3."
)
