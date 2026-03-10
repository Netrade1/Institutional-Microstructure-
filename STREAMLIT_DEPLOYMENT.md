# AI Trading Bot - Streamlit Dashboard Deployment Guide

## Overview
This guide explains how to deploy the AI Trading Bot dashboard to Streamlit Cloud for easy access from any device, including Android phones.

## Features
- 🤖 Real-time bot monitoring and control
- 📊 Portfolio tracking with live metrics
- 📈 Interactive equity curve visualization
- ⚙️ Configuration management interface
- 🧠 ML model performance monitoring
- 🌓 Dark/Light theme toggle
- 📱 Mobile-responsive design

## Local Development

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Installation

1. Clone the repository:
```bash
git clone https://github.com/Netrade1/Institutional-Microstructure-.git
cd Institutional-Microstructure-
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure the bot:
Edit `config.yaml` to set your trading parameters:
- Trading symbols
- Initial capital
- Risk parameters
- ML model settings

### Running Locally

Start the Streamlit dashboard:
```bash
streamlit run app.py
```

The dashboard will be available at `http://localhost:8501`

## Deploying to Streamlit Cloud

### Step 1: Prepare Your Repository

1. Ensure all files are committed to your GitHub repository
2. Make sure `requirements.txt` is up to date
3. Verify `config.yaml` has sensible defaults

### Step 2: Deploy to Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Sign in with your GitHub account
3. Click "New app"
4. Select your repository: `Netrade1/Institutional-Microstructure-`
5. Set the main file path: `app.py`
6. Click "Deploy"

### Step 3: Access from Mobile

Once deployed, you'll get a URL like:
```
https://your-app-name.streamlit.app
```

Open this URL in any mobile browser (Chrome, Safari, etc.) to access the dashboard.

## Usage Guide

### 1. Initialize the Bot
Click the "🚀 Initialize Bot" button to create a bot instance with your configuration.

### 2. Train Models
Click "🎓 Train Models" to train the ML models (LSTM, Random Forest, XGBoost) on historical data.
- This may take several minutes
- Models are trained on technical indicators

### 3. Start Trading
Click "▶️ Start Trading" to execute a trading cycle:
- Fetches latest market data
- Generates predictions
- Creates trading signals
- Executes trades based on risk management rules

### 4. Monitor Performance
Use the tabs to view:
- **Dashboard**: Portfolio overview, equity curve, positions, trades
- **Performance**: Sharpe ratio, max drawdown, win rate, profit factor
- **Configuration**: Adjust trading and risk parameters
- **ML Models**: View model information and weights

### 5. Stop Trading
Click "⏹️ Stop Trading" to halt the bot.

## Configuration Options

### Trading Settings
- **Symbols**: Assets to trade (e.g., BTC/USDT, AAPL, GOOGL)
- **Initial Capital**: Starting portfolio value
- **Max Position Size**: Maximum % of portfolio per trade
- **Stop Loss**: Maximum loss per trade before exit
- **Take Profit**: Target profit per trade

### Risk Management
- **Max Daily Loss**: Maximum portfolio loss per day
- **Max Portfolio Risk**: Maximum total portfolio risk exposure

## Mobile Tips

### Android Devices
1. Open Chrome or your preferred browser
2. Navigate to your Streamlit Cloud URL
3. For best experience, use landscape mode for charts
4. Add to home screen for quick access:
   - Menu → Add to Home screen

### iOS Devices
1. Open Safari
2. Navigate to your Streamlit Cloud URL
3. Tap the Share button
4. Select "Add to Home Screen"

## Troubleshooting

### Bot Not Initializing
- Check that `config.yaml` exists and is valid
- Verify all required dependencies are installed

### Training Takes Too Long
- Reduce `history_days` in config.yaml
- Use fewer symbols
- Consider using a more powerful deployment option

### Mobile Layout Issues
- Try rotating to landscape mode
- Zoom out if content is too large
- Clear browser cache

## Security Considerations

⚠️ **Important**: This dashboard is for educational and testing purposes.

For production use:
1. Never commit API keys or secrets to the repository
2. Use environment variables for sensitive data
3. Enable authentication on Streamlit Cloud (Pro plan)
4. Regularly update dependencies for security patches
5. Use paper trading or testnet APIs for testing

## Support

For issues or questions:
1. Check the [GitHub Issues](https://github.com/Netrade1/Institutional-Microstructure-/issues)
2. Review the code documentation
3. Contact the repository maintainers

## License

See LICENSE file in the repository.
