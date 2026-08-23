"""
Example: Risk Management
Demonstrates risk calculation and position sizing
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.market_data.data_fetcher import MarketDataFetcher
from src.risk_management.risk_calculator import RiskCalculator
from datetime import datetime, timedelta


def main():
    print("=" * 60)
    print("Risk Management Example")
    print("=" * 60)
    
    # Fetch historical data
    fetcher = MarketDataFetcher(data_source="simulated")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    data = fetcher.get_historical_data("AAPL", start_date, end_date, interval='1D')
    returns = data['close'].pct_change().dropna()
    
    risk_calc = RiskCalculator()
    
    # Example 1: Value at Risk (VaR)
    print("\n1. Value at Risk (VaR):")
    print("-" * 40)
    var_95 = risk_calc.calculate_var(returns, 0.95)
    var_99 = risk_calc.calculate_var(returns, 0.99)
    print(f"VaR (95%): {var_95*100:.2f}%")
    print(f"VaR (99%): {var_99*100:.2f}%")
    
    # Example 2: Conditional VaR (CVaR)
    print("\n2. Conditional VaR (CVaR):")
    print("-" * 40)
    cvar_95 = risk_calc.calculate_cvar(returns, 0.95)
    print(f"CVaR (95%): {cvar_95*100:.2f}%")
    
    # Example 3: Sharpe Ratio
    print("\n3. Sharpe Ratio:")
    print("-" * 40)
    sharpe = risk_calc.calculate_sharpe_ratio(returns)
    print(f"Sharpe Ratio: {sharpe:.4f}")
    
    # Example 4: Sortino Ratio
    print("\n4. Sortino Ratio:")
    print("-" * 40)
    sortino = risk_calc.calculate_sortino_ratio(returns)
    print(f"Sortino Ratio: {sortino:.4f}")
    
    # Example 5: Maximum Drawdown
    print("\n5. Maximum Drawdown:")
    print("-" * 40)
    drawdown_info = risk_calc.calculate_max_drawdown(data['close'])
    print(f"Max Drawdown: {drawdown_info['max_drawdown_pct']:.2f}%")
    print(f"Peak Date: {drawdown_info['peak_date']}")
    print(f"Trough Date: {drawdown_info['trough_date']}")
    
    # Example 6: Position Sizing
    print("\n6. Position Sizing:")
    print("-" * 40)
    account_value = 100000
    risk_per_trade = 0.02  # 2%
    entry_price = 150.00
    stop_loss_price = 145.00
    
    position_size = risk_calc.calculate_position_size(
        account_value, risk_per_trade, entry_price, stop_loss_price
    )
    print(f"Account Value: ${account_value:,}")
    print(f"Risk per Trade: {risk_per_trade*100}%")
    print(f"Entry Price: ${entry_price:.2f}")
    print(f"Stop Loss: ${stop_loss_price:.2f}")
    print(f"Position Size: {position_size} shares")
    print(f"Position Value: ${position_size * entry_price:,.2f}")
    
    # Example 7: Kelly Criterion
    print("\n7. Kelly Criterion:")
    print("-" * 40)
    win_rate = 0.55
    avg_win = 0.03
    avg_loss = 0.02
    
    kelly = risk_calc.calculate_kelly_criterion(win_rate, avg_win, avg_loss)
    print(f"Win Rate: {win_rate*100}%")
    print(f"Average Win: {avg_win*100}%")
    print(f"Average Loss: {avg_loss*100}%")
    print(f"Kelly %: {kelly*100:.2f}%")
    print(f"Half Kelly (recommended): {kelly*50:.2f}%")
    
    # Example 8: Risk-Adjusted Returns
    print("\n8. Risk-Adjusted Return Metrics:")
    print("-" * 40)
    metrics = risk_calc.calculate_risk_adjusted_return(returns)
    print(f"Total Return: {metrics['total_return']*100:.2f}%")
    print(f"Annualized Return: {metrics['annualized_return']*100:.2f}%")
    print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.4f}")
    print(f"Sortino Ratio: {metrics['sortino_ratio']:.4f}")
    print(f"Volatility: {metrics['volatility']*100:.2f}%")


if __name__ == "__main__":
    main()
