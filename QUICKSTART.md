# Quick Start Guide

## 🚀 Getting Started in 5 Minutes

### Step 1: Clone and Setup

\`\`\`bash
# Clone the repository
git clone https://github.com/Netrade1/Institutional-Microstructure-.git
cd Institutional-Microstructure-

# Run setup script (Linux/Mac)
chmod +x setup.sh
./setup.sh

# Or on Windows
setup.bat
\`\`\`

### Step 2: Activate Environment

\`\`\`bash
# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate.bat
\`\`\`

### Step 3: Run Demo

\`\`\`bash
# Quick demo (no dependencies)
python demo.py
\`\`\`

### Step 4: Configure (Optional)

Edit \`config.yaml\` to customize:
- Trading symbols
- Initial capital
- Risk parameters

### Step 5: Run the Bot

\`\`\`bash
# Train models and run
python main.py --train --cycles 1

# Or start the dashboard
python main.py --dashboard
# Then open http://localhost:5000 in your browser
\`\`\`

## 📊 Using the Dashboard

1. Click **Initialize Bot** - Sets up the trading system
2. Click **Train Models** - Trains ML models (takes a few minutes)
3. Click **Start Trading** - Executes one trading cycle
4. View your portfolio, positions, and trades in real-time

## 🎯 Example Workflow

\`\`\`bash
# 1. Setup
./setup.sh
source venv/bin/activate

# 2. Run with training
python main.py --train --cycles 1

# 3. View results
# Check console output for portfolio status
\`\`\`

## ⚙️ Configuration Tips

### For Conservative Trading
\`\`\`yaml
trading:
  max_position_size: 0.1  # Max 10% per position
  stop_loss: 0.01         # 1% stop loss
  
risk:
  max_daily_loss: 0.02    # Max 2% daily loss
\`\`\`

### For Aggressive Trading
\`\`\`yaml
trading:
  max_position_size: 0.3  # Max 30% per position
  stop_loss: 0.03         # 3% stop loss
  
risk:
  max_daily_loss: 0.10    # Max 10% daily loss
\`\`\`

## 🧪 Testing

\`\`\`bash
# Run tests
python -m unittest discover tests/
\`\`\`

## 🐛 Troubleshooting

### Issue: Module not found
**Solution**: Make sure you activated the virtual environment

### Issue: API connection error
**Solution**: Check your internet connection, yfinance needs access to Yahoo Finance

### Issue: Training takes too long
**Solution**: Reduce \`history_days\` in config.yaml or use fewer models

## 📚 Next Steps

1. Read the full README.md
2. Review SYSTEM_OVERVIEW.md for architecture details
3. Customize config.yaml for your strategy
4. Run backtests to validate performance
5. Deploy to production

## ⚠️ Important Reminders

- This is for educational purposes
- Always test with small amounts first
- Never invest more than you can afford to lose
- Past performance ≠ future results

## 🤝 Need Help?

- Check the README.md
- Review code comments
- Open an issue on GitHub
- Run the demo.py for examples

Happy Trading! 🎉
