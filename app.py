"""
Streamlit Dashboard for AI Trading Bot
Provides real-time monitoring and control interface
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import yaml
import json
import logging
from typing import Dict, List, Any

from trading_bot.bot import AITradingBot

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="AI Trading Bot Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better mobile responsiveness and professional look
st.markdown("""
<style>
    /* Main container styling */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Metric cards */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    /* Status badges */
    .status-badge {
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-weight: 600;
        display: inline-block;
        margin: 0.25rem;
    }
    
    .status-active {
        background-color: #10b981;
        color: white;
    }
    
    .status-inactive {
        background-color: #ef4444;
        color: white;
    }
    
    .status-pending {
        background-color: #f59e0b;
        color: white;
    }
    
    /* Button styling */
    .stButton > button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        padding: 0.5rem 1rem;
    }
    
    /* Mobile responsiveness */
    @media (max-width: 768px) {
        .main .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }
    }
    
    /* Theme-specific styling */
    [data-theme="dark"] {
        --background-color: #1f2937;
        --text-color: #f9fafb;
    }
</style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize Streamlit session state variables"""
    if 'bot' not in st.session_state:
        st.session_state.bot = None
    if 'bot_status' not in st.session_state:
        st.session_state.bot_status = {
            'initialized': False,
            'trained': False,
            'running': False,
            'last_update': None
        }
    if 'theme' not in st.session_state:
        st.session_state.theme = 'light'
    if 'config' not in st.session_state:
        try:
            with open('config.yaml', 'r') as f:
                st.session_state.config = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            st.session_state.config = {}


def load_config() -> Dict:
    """Load configuration from YAML file"""
    try:
        with open('config.yaml', 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        st.error(f"Failed to load configuration: {e}")
        return {}


def save_config(config: Dict):
    """Save configuration to YAML file"""
    try:
        with open('config.yaml', 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        st.success("Configuration saved successfully!")
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        st.error(f"Failed to save configuration: {e}")


def initialize_bot():
    """Initialize the trading bot"""
    try:
        with st.spinner("Initializing bot..."):
            st.session_state.bot = AITradingBot()
            st.session_state.bot_status['initialized'] = True
            st.session_state.bot_status['last_update'] = datetime.now().isoformat()
            logger.info("Bot initialized via Streamlit")
            st.success("✅ Bot initialized successfully!")
            st.rerun()
    except Exception as e:
        logger.error(f"Error initializing bot: {e}")
        st.error(f"Failed to initialize bot: {e}")


def train_bot():
    """Train the bot models"""
    if st.session_state.bot is None:
        st.error("Please initialize the bot first")
        return
    
    try:
        with st.spinner("Training models... This may take several minutes."):
            data = st.session_state.bot.fetch_and_prepare_data()
            st.session_state.bot.train_models(data)
            st.session_state.bot_status['trained'] = True
            st.session_state.bot_status['last_update'] = datetime.now().isoformat()
            logger.info("Bot trained via Streamlit")
            st.success("✅ Bot trained successfully!")
            st.rerun()
    except Exception as e:
        logger.error(f"Error training bot: {e}")
        st.error(f"Failed to train bot: {e}")


def execute_trading_cycle():
    """Execute one trading cycle"""
    if st.session_state.bot is None:
        st.error("Please initialize the bot first")
        return
    
    if not st.session_state.bot.is_trained:
        st.error("Please train the bot first")
        return
    
    try:
        with st.spinner("Executing trading cycle..."):
            st.session_state.bot_status['running'] = True
            st.session_state.bot_status['last_update'] = datetime.now().isoformat()
            
            data = st.session_state.bot.fetch_and_prepare_data()
            st.session_state.bot.execute_trading_cycle(data)
            
            logger.info("Trading cycle executed via Streamlit")
            st.success("✅ Trading cycle completed successfully!")
            st.rerun()
    except Exception as e:
        logger.error(f"Error in trading cycle: {e}")
        st.session_state.bot_status['running'] = False
        st.error(f"Failed to execute trading cycle: {e}")


def stop_trading():
    """Stop trading bot"""
    st.session_state.bot_status['running'] = False
    st.session_state.bot_status['last_update'] = datetime.now().isoformat()
    logger.info("Trading stopped via Streamlit")
    st.success("Trading stopped")
    st.rerun()


def render_header():
    """Render dashboard header"""
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.title("🤖 AI Trading Bot Dashboard")
        st.caption("Autonomous Trading System with Machine Learning")
    
    with col2:
        # Theme toggle
        theme = st.selectbox(
            "Theme",
            ["Light", "Dark"],
            index=0 if st.session_state.theme == 'light' else 1,
            key="theme_selector"
        )
        if theme.lower() != st.session_state.theme:
            st.session_state.theme = theme.lower()
            st.rerun()


def render_status_bar():
    """Render status bar with bot status badges"""
    st.subheader("System Status")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        status_class = "status-active" if st.session_state.bot_status['initialized'] else "status-inactive"
        status_text = "Initialized" if st.session_state.bot_status['initialized'] else "Not Initialized"
        st.markdown(f'<div class="status-badge {status_class}">{status_text}</div>', unsafe_allow_html=True)
    
    with col2:
        status_class = "status-active" if st.session_state.bot_status['trained'] else "status-inactive"
        status_text = "Trained" if st.session_state.bot_status['trained'] else "Not Trained"
        st.markdown(f'<div class="status-badge {status_class}">{status_text}</div>', unsafe_allow_html=True)
    
    with col3:
        status_class = "status-active" if st.session_state.bot_status['running'] else "status-inactive"
        status_text = "Running" if st.session_state.bot_status['running'] else "Stopped"
        st.markdown(f'<div class="status-badge {status_class}">{status_text}</div>', unsafe_allow_html=True)
    
    with col4:
        if st.session_state.bot_status['last_update']:
            update_time = datetime.fromisoformat(st.session_state.bot_status['last_update'])
            st.caption(f"Last Update: {update_time.strftime('%H:%M:%S')}")


def render_controls():
    """Render bot control buttons"""
    st.subheader("Bot Controls")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🚀 Initialize Bot", type="primary", disabled=st.session_state.bot_status['initialized']):
            initialize_bot()
    
    with col2:
        if st.button("🎓 Train Models", disabled=not st.session_state.bot_status['initialized']):
            train_bot()
    
    with col3:
        if st.button("▶️ Start Trading", disabled=not st.session_state.bot_status['trained'] or st.session_state.bot_status['running']):
            execute_trading_cycle()
    
    with col4:
        if st.button("⏹️ Stop Trading", disabled=not st.session_state.bot_status['running']):
            stop_trading()


def render_portfolio_metrics():
    """Render portfolio metrics"""
    if st.session_state.bot is None or not st.session_state.bot_status['initialized']:
        st.info("Initialize the bot to view portfolio metrics")
        return
    
    st.subheader("📊 Portfolio Overview")
    
    portfolio = st.session_state.bot.portfolio
    
    # Main metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Value",
            f"${portfolio.total_value:,.2f}",
            f"{portfolio.total_return * 100:.2f}%"
        )
    
    with col2:
        st.metric(
            "Available Cash",
            f"${portfolio.cash:,.2f}"
        )
    
    with col3:
        st.metric(
            "Total P&L",
            f"${portfolio.total_profit_loss:,.2f}",
            delta_color="normal" if portfolio.total_profit_loss >= 0 else "inverse"
        )
    
    with col4:
        st.metric(
            "Number of Trades",
            len(portfolio.trade_history)
        )


def render_performance_metrics():
    """Render performance metrics"""
    if st.session_state.bot is None or not st.session_state.bot_status['initialized']:
        return
    
    try:
        metrics = st.session_state.bot.get_performance_metrics()
        
        st.subheader("📈 Performance Metrics")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Return", f"{metrics.get('total_return', 0) * 100:.2f}%")
            st.metric("Open Positions", metrics.get('num_positions', 0))
        
        with col2:
            sharpe = metrics.get('sharpe_ratio', 0)
            st.metric("Sharpe Ratio", f"{sharpe:.2f}" if sharpe else "N/A")
            st.metric("Max Drawdown", f"{metrics.get('max_drawdown', 0) * 100:.2f}%")
        
        with col3:
            win_rate = metrics.get('win_rate', 0)
            st.metric("Win Rate", f"{win_rate * 100:.2f}%" if win_rate else "N/A")
            st.metric("Profit Factor", f"{metrics.get('profit_factor', 0):.2f}")
            
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")


def render_equity_curve():
    """Render equity curve visualization"""
    if st.session_state.bot is None or not st.session_state.bot_status['initialized']:
        return
    
    st.subheader("💹 Equity Curve")
    
    portfolio = st.session_state.bot.portfolio
    
    # Get trade history
    if portfolio.trade_history:
        # Create equity curve data
        equity_data = []
        running_value = st.session_state.config.get('trading', {}).get('initial_capital', 100000)
        
        for trade in portfolio.trade_history:
            if 'timestamp' in trade and 'profit_loss' in trade:
                running_value += trade.get('profit_loss', 0)
                equity_data.append({
                    'timestamp': trade['timestamp'],
                    'equity': running_value
                })
        
        if equity_data:
            df = pd.DataFrame(equity_data)
            
            # Create Plotly figure
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=df['timestamp'],
                y=df['equity'],
                mode='lines',
                name='Portfolio Value',
                line=dict(color='#667eea', width=2),
                fill='tozeroy',
                fillcolor='rgba(102, 126, 234, 0.2)'
            ))
            
            # Add initial capital line
            initial_capital = st.session_state.config.get('trading', {}).get('initial_capital', 100000)
            fig.add_hline(
                y=initial_capital,
                line_dash="dash",
                line_color="gray",
                annotation_text="Initial Capital"
            )
            
            fig.update_layout(
                title="Portfolio Equity Curve",
                xaxis_title="Time",
                yaxis_title="Portfolio Value ($)",
                hovermode='x unified',
                template='plotly_white',
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No trade history available yet. Execute a trading cycle to see the equity curve.")


def render_positions():
    """Render current positions"""
    if st.session_state.bot is None or not st.session_state.bot_status['initialized']:
        return
    
    st.subheader("📍 Current Positions")
    
    portfolio = st.session_state.bot.portfolio
    
    if portfolio.positions:
        positions_data = []
        for symbol, pos in portfolio.positions.items():
            positions_data.append({
                'Symbol': symbol,
                'Shares': pos.shares,
                'Entry Price': f"${pos.entry_price:.2f}",
                'Current Price': f"${pos.current_price:.2f}",
                'Value': f"${pos.value:.2f}",
                'P&L': f"${pos.profit_loss:.2f}",
                'P&L %': f"{pos.profit_loss_pct * 100:.2f}%"
            })
        
        df = pd.DataFrame(positions_data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No open positions")


def render_trade_history():
    """Render trade history"""
    if st.session_state.bot is None or not st.session_state.bot_status['initialized']:
        return
    
    st.subheader("📜 Trade History")
    
    portfolio = st.session_state.bot.portfolio
    
    if portfolio.trade_history:
        # Get last 50 trades
        trades = portfolio.trade_history[-50:]
        
        # Convert to DataFrame
        df = pd.DataFrame(trades)
        
        # Format columns if they exist
        if not df.empty:
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            if 'price' in df.columns:
                df['price'] = df['price'].apply(lambda x: f"${x:.2f}")
            if 'profit_loss' in df.columns:
                df['profit_loss'] = df['profit_loss'].apply(lambda x: f"${x:.2f}")
            
            st.dataframe(df, use_container_width=True)
    else:
        st.info("No trade history available yet")


def render_configuration():
    """Render configuration management interface"""
    st.subheader("⚙️ Configuration")
    
    config = st.session_state.config
    
    with st.expander("Trading Settings", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            symbols = st.text_area(
                "Trading Symbols (one per line)",
                value="\n".join(config.get('trading', {}).get('symbols', [])),
                height=100
            )
            
            initial_capital = st.number_input(
                "Initial Capital ($)",
                value=config.get('trading', {}).get('initial_capital', 100000),
                min_value=1000,
                step=1000
            )
            
            max_position_size = st.slider(
                "Max Position Size (%)",
                min_value=5,
                max_value=50,
                value=int(config.get('trading', {}).get('max_position_size', 0.2) * 100),
                step=5
            )
        
        with col2:
            stop_loss = st.slider(
                "Stop Loss (%)",
                min_value=1,
                max_value=10,
                value=int(config.get('trading', {}).get('stop_loss', 0.02) * 100),
                step=1
            )
            
            take_profit = st.slider(
                "Take Profit (%)",
                min_value=1,
                max_value=20,
                value=int(config.get('trading', {}).get('take_profit', 0.05) * 100),
                step=1
            )
        
        if st.button("Save Configuration"):
            # Update config
            if 'trading' not in config:
                config['trading'] = {}
            
            config['trading']['symbols'] = [s.strip() for s in symbols.split('\n') if s.strip()]
            config['trading']['initial_capital'] = initial_capital
            config['trading']['max_position_size'] = max_position_size / 100
            config['trading']['stop_loss'] = stop_loss / 100
            config['trading']['take_profit'] = take_profit / 100
            
            save_config(config)
            st.session_state.config = config
    
    with st.expander("Risk Management Settings", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            max_daily_loss = st.slider(
                "Max Daily Loss (%)",
                min_value=1,
                max_value=20,
                value=int(config.get('risk', {}).get('max_daily_loss', 0.05) * 100),
                step=1
            )
        
        with col2:
            max_portfolio_risk = st.slider(
                "Max Portfolio Risk (%)",
                min_value=5,
                max_value=50,
                value=int(config.get('risk', {}).get('max_portfolio_risk', 0.15) * 100),
                step=5
            )
        
        if st.button("Save Risk Settings"):
            if 'risk' not in config:
                config['risk'] = {}
            
            config['risk']['max_daily_loss'] = max_daily_loss / 100
            config['risk']['max_portfolio_risk'] = max_portfolio_risk / 100
            
            save_config(config)
            st.session_state.config = config


def render_ml_model_info():
    """Render ML model information"""
    st.subheader("🧠 ML Model Information")
    
    if st.session_state.bot is None or not st.session_state.bot_status['trained']:
        st.info("Train the bot to view model information")
        return
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**LSTM Model**")
        st.caption("Deep learning for time series")
        st.caption("Weight: 40%")
    
    with col2:
        st.markdown("**Random Forest**")
        st.caption("Tree ensemble classifier")
        st.caption("Weight: 30%")
    
    with col3:
        st.markdown("**XGBoost**")
        st.caption("Gradient boosting")
        st.caption("Weight: 30%")


def main():
    """Main application"""
    # Initialize session state
    initialize_session_state()
    
    # Render header
    render_header()
    
    st.divider()
    
    # Render status bar
    render_status_bar()
    
    st.divider()
    
    # Render controls
    render_controls()
    
    st.divider()
    
    # Main content
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "📈 Performance", "⚙️ Configuration", "🧠 ML Models"])
    
    with tab1:
        render_portfolio_metrics()
        st.divider()
        render_equity_curve()
        st.divider()
        render_positions()
        st.divider()
        render_trade_history()
    
    with tab2:
        render_performance_metrics()
    
    with tab3:
        render_configuration()
    
    with tab4:
        render_ml_model_info()
    
    # Footer
    st.divider()
    st.caption("AI Trading Bot Dashboard - Powered by Streamlit | Last refreshed: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


if __name__ == "__main__":
    main()
