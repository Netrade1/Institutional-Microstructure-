# Institutional Microstructure Toolkit 🗽

A comprehensive Python toolkit for institutional trading and market microstructure analysis. This library provides tools for market data analysis, order book management, trade execution, microstructure metrics, technical indicators, and risk management.

## Features

### 📊 Market Data
- Real-time and historical market data fetching
- Tick-level data support
- Order book snapshots
- Multiple data source support (simulated, with extensibility for real APIs)

### 📈 Order Book Analysis
- Limit order book representation and manipulation
- Bid-ask spread calculations
- Market depth analysis
- Order book imbalance metrics
- Market impact estimation
- VWAP calculations

### 🔄 Trade Execution
- Order creation and management (Market, Limit, Stop orders)
- Order lifecycle tracking
- Position calculation
- Fill management
- Time-in-force support (GTC, DAY, IOC, FOK)

### 🔬 Market Microstructure Metrics
- Quoted and relative spread
- Effective and realized spread
- Price impact measures
- Roll's measure
- Amihud illiquidity ratio
- Kyle's lambda
- PIN (Probability of Informed Trading)
- Market depth metrics
- Volatility measures

### 📉 Technical Indicators
- Moving Averages (SMA, EMA)
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Bollinger Bands
- ATR (Average True Range)
- Stochastic Oscillator
- ADX (Average Directional Index)
- OBV (On-Balance Volume)
- VWAP (Volume Weighted Average Price)
- CCI (Commodity Channel Index)
- Momentum and Rate of Change

### ⚠️ Risk Management
- Value at Risk (VaR)
- Conditional VaR (CVaR/Expected Shortfall)
- Sharpe Ratio
- Sortino Ratio
- Maximum Drawdown
- Position sizing algorithms
- Kelly Criterion
- Beta calculation
- Portfolio risk metrics

## Installation

```bash
# Clone the repository
git clone https://github.com/Netrade1/Institutional-Microstructure-.git
cd Institutional-Microstructure-

# Install dependencies
pip install -r requirements.txt

# Or install in development mode
pip install -e .
```

## Requirements

- Python 3.8+
- numpy >= 1.24.0
- pandas >= 2.0.0
- requests >= 2.31.0
- websocket-client >= 1.6.0
- python-dateutil >= 2.8.2
- pytz >= 2023.3

## Quick Start

### Market Data Example

```python
from src.market_data.data_fetcher import MarketDataFetcher
from datetime import datetime, timedelta

# Initialize market data fetcher
fetcher = MarketDataFetcher(data_source="simulated")

# Get real-time quote
quote = fetcher.get_quote("AAPL")
print(f"Bid: ${quote['bid']:.2f}, Ask: ${quote['ask']:.2f}")

# Get historical data
end_date = datetime.now()
start_date = end_date - timedelta(days=30)
historical = fetcher.get_historical_data("AAPL", start_date, end_date)
print(historical.head())
```

### Order Book Analysis

```python
from src.market_data.data_fetcher import MarketDataFetcher
from src.order_book.order_book import OrderBook

# Fetch order book data
fetcher = MarketDataFetcher()
ob_data = fetcher.get_order_book_snapshot("MSFT", depth=10)

# Analyze order book
order_book = OrderBook("MSFT")
order_book.update(ob_data['bids'], ob_data['asks'])

print(f"Mid Price: ${order_book.get_mid_price():.2f}")
print(f"Spread: ${order_book.get_spread():.4f}")
print(f"Imbalance: {order_book.get_imbalance():.4f}")
```

### Order Management

```python
from src.execution.order_manager import OrderManager

# Initialize order manager
order_manager = OrderManager()

# Create a limit order
order = order_manager.create_order(
    symbol="AAPL",
    side="buy",
    quantity=100,
    order_type="limit",
    price=150.50
)

# Submit the order
order_manager.submit_order(order.order_id)

# Check position
position = order_manager.calculate_position("AAPL")
print(f"Position: {position['quantity']} @ ${position['average_price']:.2f}")
```

### Technical Indicators

```python
from src.indicators.technical_indicators import TechnicalIndicators
import pandas as pd

indicators = TechnicalIndicators()

# Calculate RSI
rsi = indicators.rsi(price_series, period=14)

# Calculate MACD
macd_line, signal_line, histogram = indicators.macd(price_series)

# Calculate Bollinger Bands
upper, middle, lower = indicators.bollinger_bands(price_series)
```

### Risk Management

```python
from src.risk_management.risk_calculator import RiskCalculator

risk_calc = RiskCalculator()

# Calculate VaR
var_95 = risk_calc.calculate_var(returns, confidence_level=0.95)

# Calculate Sharpe Ratio
sharpe = risk_calc.calculate_sharpe_ratio(returns)

# Position sizing
position_size = risk_calc.calculate_position_size(
    account_value=100000,
    risk_per_trade=0.02,
    entry_price=150.00,
    stop_loss_price=145.00
)
```

## Examples

The `examples/` directory contains comprehensive examples:

- `example_market_data.py` - Market data fetching and analysis
- `example_order_book.py` - Order book analysis and microstructure metrics
- `example_order_management.py` - Order creation and management
- `example_technical_indicators.py` - Technical indicator calculations
- `example_risk_management.py` - Risk metrics and position sizing

Run examples:

```bash
cd examples
python example_market_data.py
python example_order_book.py
python example_order_management.py
python example_technical_indicators.py
python example_risk_management.py
```

## Project Structure

```
Institutional-Microstructure-/
├── src/
│   ├── market_data/          # Market data fetching
│   │   └── data_fetcher.py
│   ├── order_book/           # Order book analysis
│   │   └── order_book.py
│   ├── execution/            # Order management
│   │   └── order_manager.py
│   ├── microstructure/       # Microstructure metrics
│   │   └── metrics.py
│   ├── indicators/           # Technical indicators
│   │   └── technical_indicators.py
│   ├── risk_management/      # Risk calculations
│   │   └── risk_calculator.py
│   └── utils/                # Utility functions
│       └── config.py
├── examples/                 # Example scripts
├── requirements.txt          # Dependencies
├── setup.py                  # Package setup
└── README.md                 # This file
```

## Configuration

The toolkit supports configuration through the `ConfigManager` class:

```python
from src.utils.config import ConfigManager

config = ConfigManager()
config.set('market_data.source', 'simulated')
config.set('risk.max_position_size', 100000)
config.save()
```

## Use Cases

This toolkit is designed for:

- **Quantitative Researchers**: Analyze market microstructure and develop trading strategies
- **Algorithmic Traders**: Build and test trading algorithms with realistic market data
- **Risk Managers**: Calculate risk metrics and monitor portfolio risk
- **Market Makers**: Analyze order books and optimize quote placement
- **Academic Research**: Study market microstructure phenomena
- **Portfolio Managers**: Track positions and calculate performance metrics

## Extending the Toolkit

### Adding New Data Sources

Extend the `MarketDataFetcher` class to support additional data sources:

```python
class CustomDataFetcher(MarketDataFetcher):
    def __init__(self, api_key):
        super().__init__(api_key=api_key, data_source="custom")
    
    def get_quote(self, symbol):
        # Implement custom data source logic
        pass
```

### Custom Indicators

Add custom technical indicators by extending the `TechnicalIndicators` class:

```python
class CustomIndicators(TechnicalIndicators):
    @staticmethod
    def my_custom_indicator(prices, period):
        # Implement custom indicator logic
        pass
```

## Contributing

Contributions are welcome! Please feel free to submit issues, fork the repository, and create pull requests.

## License

This project is open source and available under the MIT License.

## Disclaimer

This toolkit is for educational and research purposes. Always perform thorough testing before using in production trading environments. Past performance does not guarantee future results.

## Author

**Netrade1**

## Acknowledgments

Built with passion for quantitative finance and market microstructure analysis. 🗽
