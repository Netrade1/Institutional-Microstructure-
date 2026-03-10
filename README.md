# AI Trading Bot Platform 🤖📈

A state-of-the-art cutting-edge machine learning augmented intelligence autonomous AI Trading Bot Platform System and Dashboard.

---

## 🚀 **WANT TO DEPLOY NOW?** 

### Not sure what to do? Here's how to get started:

#### 📱 Deploy to Cloud (Access from Phone/Tablet)
➡️ **[READ: DEPLOY_NOW.md](DEPLOY_NOW.md)** - 3 simple steps to deploy!

#### 💻 Run Locally (Test on Your Computer)
```bash
pip install streamlit
streamlit run app.py
```
Open: `http://localhost:8501`

**Choose one option above to get started!** ⬆️

---

## 🌟 Features

### Advanced Machine Learning
- **LSTM Neural Networks** - Deep learning for time series prediction
- **Random Forest** - Ensemble learning for robust predictions
- **XGBoost** - Gradient boosting for high accuracy
- **Ensemble Models** - Combines multiple models for superior performance

### Intelligent Trading Strategies
- **ML-Based Strategy** - Predictions driven by ensemble models
- **Technical Analysis** - RSI, MACD, Bollinger Bands, ADX
- **Hybrid Strategy** - Combines ML and technical indicators
- **Backtesting Framework** - Test strategies on historical data

### Risk Management System
- **Portfolio Management** - Track positions and P/L
- **Position Sizing** - Kelly Criterion with risk adjustments
- **Stop Loss/Take Profit** - Automatic risk controls
- **Daily Loss Limits** - Prevents excessive losses
- **Portfolio Risk Controls** - Maximum exposure limits

### Real-Time Dashboard
- **Web Interface** - Beautiful, responsive dashboard
- **Live Monitoring** - Real-time portfolio tracking
- **Performance Metrics** - Returns, Sharpe ratio, drawdown
- **Trade History** - Complete audit trail
- **Controls** - Initialize, train, start/stop trading

## 🚀 Quick Start

### Installation

1. Clone the repository:
```bash
git clone https://github.com/Netrade1/Institutional-Microstructure-.git
cd Institutional-Microstructure-
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

### Configuration

Edit `config.yaml` to customize:
- Trading symbols
- Initial capital
- Risk parameters
- ML model settings
- Dashboard settings

### Running the Bot

**Command Line Mode:**
```bash
# Train models and run one trading cycle
python main.py --train --cycles 1

# Run multiple cycles without retraining
python main.py --cycles 5
```

**Dashboard Mode:**
```bash
# Start the web dashboard
python main.py --dashboard

# Access at http://localhost:5000
```

## 📊 System Architecture

```
AI Trading Bot Platform
│
├── Data Layer
│   ├── Market Data Fetcher (yfinance)
│   └── Feature Engineering (Technical Indicators)
│
├── ML Layer
│   ├── LSTM Model (TensorFlow/Keras)
│   ├── Random Forest (scikit-learn)
│   ├── XGBoost
│   └── Ensemble Model
│
├── Strategy Layer
│   ├── ML Trading Strategy
│   ├── Technical Strategy
│   ├── Hybrid Strategy
│   └── Backtesting Framework
│
├── Risk Management Layer
│   ├── Portfolio Manager
│   ├── Risk Manager
│   ├── Position Sizing
│   └── Portfolio Optimizer
│
└── Dashboard Layer
    ├── Flask API Backend
    └── HTML/CSS/JS Frontend
```

## 🧪 Testing

Run the test suite:
```bash
python -m pytest tests/ -v

# Or using unittest
python -m unittest discover tests/
```

## 📈 Technical Indicators

The system implements the following technical indicators:
- **Moving Averages**: SMA, EMA
- **Momentum**: RSI, MACD
- **Volatility**: Bollinger Bands, ATR
- **Trend**: ADX
- **Volume**: Volume Ratio, OBV

## 🔬 Machine Learning Models

### LSTM Neural Network
- Multi-layer LSTM architecture
- Early stopping to prevent overfitting
- Sequences-based time series prediction

### Random Forest
- 100 estimators by default
- Feature importance analysis
- Robust to overfitting

### XGBoost
- Gradient boosting with early stopping
- Optimized hyperparameters
- Fast training and prediction

### Ensemble
- Weighted average of all models
- Leverages strengths of each approach
- More stable predictions

## 💼 Risk Management

### Position Sizing
- Kelly Criterion-based sizing
- Volatility-adjusted positions
- Maximum position limits (20% default)

### Risk Controls
- Stop Loss: 2% default
- Take Profit: 5% default
- Daily Loss Limit: 5% default
- Portfolio Risk Limit: 15% default

## 🎯 Trading Signals

Signals are generated based on:
1. **ML Predictions** - Price forecasts from ensemble
2. **Technical Indicators** - RSI, MACD, Bollinger Bands
3. **Confidence Scoring** - Signal strength assessment
4. **Risk Validation** - All trades validated against risk rules

## 📱 Dashboard Features

- **Portfolio Overview**: Total value, P/L, returns
- **Open Positions**: Real-time position tracking
- **Trade History**: Complete trading log
- **Performance Metrics**: Sharpe ratio, max drawdown
- **Controls**: Start/stop, train, refresh

## 🔧 Configuration Options

### Trading Parameters
- `symbols`: List of trading instruments
- `initial_capital`: Starting capital
- `max_position_size`: Maximum position as % of capital
- `stop_loss`: Stop loss percentage
- `take_profit`: Take profit percentage

### ML Parameters
- `models`: List of models to use
- `lookback_period`: Historical data window
- `prediction_horizon`: Forecast period
- `training_split`: Train/test split ratio

### Risk Parameters
- `max_daily_loss`: Maximum daily loss %
- `max_portfolio_risk`: Maximum portfolio risk %
- `diversification_min`: Minimum number of positions

## 🌐 API Endpoints

- `GET /api/status` - Bot status
- `GET /api/portfolio` - Portfolio data
- `GET /api/performance` - Performance metrics
- `GET /api/trades` - Trade history
- `POST /api/initialize` - Initialize bot
- `POST /api/train` - Train models
- `POST /api/start` - Start trading
- `POST /api/stop` - Stop trading

## 🛡️ Security

- No hardcoded credentials
- Environment variable support
- API authentication ready
- Secure data handling

## 📚 Dependencies

- **ML/Data**: numpy, pandas, scikit-learn, tensorflow, xgboost
- **Trading**: yfinance, ta, ccxt
- **Web**: Flask, flask-cors
- **Visualization**: matplotlib, plotly

## 🤝 Contributing

This is a research and educational project. Feel free to fork and extend!

## ⚠️ Disclaimer

This trading bot is for educational and research purposes only. Trading involves significant risk of loss. Never trade with money you cannot afford to lose. Past performance does not guarantee future results.

## 📄 License

MIT License - My liberty of Code to my Scripts 🗽

## 🎓 Future Enhancements

- [ ] Support for more exchanges (Binance, Coinbase, etc.)
- [ ] Sentiment analysis integration
- [ ] Deep reinforcement learning strategies
- [ ] Advanced portfolio optimization
- [ ] Real-time streaming data
- [ ] Alert notifications (email, SMS)
- [ ] Mobile app
- [ ] Paper trading mode

## 📧 Contact

For questions or collaborations, please open an issue on GitHub.

---

**Built with ❤️ using cutting-edge AI and ML technologies** 
