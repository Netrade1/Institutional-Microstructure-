"""
AI Trading Bot Dashboard
Real-time monitoring and visualization system
"""

import json
from datetime import datetime
from typing import Dict, List
import os


class TradingDashboard:
    """
    Interactive Dashboard for AI Trading Bot Platform
    Provides real-time monitoring, analytics, and control interface
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.refresh_rate = 1  # seconds
        
    def generate_dashboard_html(self, output_path: str = 'dashboard.html'):
        """Generate interactive HTML dashboard"""
        metrics = self.bot.get_performance_metrics()
        
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Trading Bot Dashboard</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            color: #333;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        .header {{
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            margin-bottom: 20px;
            text-align: center;
        }}
        
        .header h1 {{
            color: #667eea;
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        
        .header .subtitle {{
            color: #666;
            font-size: 1.1em;
        }}
        
        .status-bar {{
            background: #2ecc71;
            color: white;
            padding: 15px 30px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }}
        
        .status-bar .status {{
            font-size: 1.2em;
            font-weight: bold;
        }}
        
        .status-indicator {{
            width: 15px;
            height: 15px;
            background: #00ff00;
            border-radius: 50%;
            display: inline-block;
            margin-right: 10px;
            animation: pulse 2s infinite;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        
        .metric-card {{
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            transition: transform 0.3s;
        }}
        
        .metric-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.2);
        }}
        
        .metric-card .label {{
            color: #888;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }}
        
        .metric-card .value {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }}
        
        .metric-card .value.positive {{
            color: #2ecc71;
        }}
        
        .metric-card .value.negative {{
            color: #e74c3c;
        }}
        
        .section {{
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        
        .section h2 {{
            color: #667eea;
            margin-bottom: 20px;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }}
        
        .portfolio-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        .portfolio-table th {{
            background: #667eea;
            color: white;
            padding: 15px;
            text-align: left;
        }}
        
        .portfolio-table td {{
            padding: 12px 15px;
            border-bottom: 1px solid #eee;
        }}
        
        .portfolio-table tr:hover {{
            background: #f5f5f5;
        }}
        
        .features-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        
        .feature-box {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }}
        
        .feature-box h3 {{
            margin-bottom: 10px;
            font-size: 1.3em;
        }}
        
        .feature-box ul {{
            list-style: none;
            padding-left: 0;
        }}
        
        .feature-box li {{
            padding: 5px 0;
            padding-left: 20px;
            position: relative;
        }}
        
        .feature-box li:before {{
            content: "✓";
            position: absolute;
            left: 0;
            font-weight: bold;
        }}
        
        .timestamp {{
            text-align: center;
            color: #666;
            margin-top: 20px;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 AI Trading Bot Platform</h1>
            <p class="subtitle">State-of-the-art Machine Learning Powered Autonomous Trading System</p>
        </div>
        
        <div class="status-bar">
            <div class="status">
                <span class="status-indicator"></span>
                System Status: ACTIVE & TRADING
            </div>
            <div>Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
        </div>
        
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="label">Account Value</div>
                <div class="value">${metrics.get('current_value', 0):,.2f}</div>
            </div>
            
            <div class="metric-card">
                <div class="label">Total Return</div>
                <div class="value {'positive' if metrics.get('total_return_pct', 0) > 0 else 'negative'}">
                    {metrics.get('total_return_pct', 0):+.2f}%
                </div>
            </div>
            
            <div class="metric-card">
                <div class="label">Sharpe Ratio</div>
                <div class="value">{metrics.get('sharpe_ratio', 0):.2f}</div>
            </div>
            
            <div class="metric-card">
                <div class="label">Win Rate</div>
                <div class="value">{metrics.get('win_rate_pct', 0):.1f}%</div>
            </div>
            
            <div class="metric-card">
                <div class="label">Total Trades</div>
                <div class="value">{metrics.get('total_trades', 0)}</div>
            </div>
            
            <div class="metric-card">
                <div class="label">Max Drawdown</div>
                <div class="value negative">{metrics.get('max_drawdown', 0)*100:.2f}%</div>
            </div>
        </div>
        
        <div class="section">
            <h2>📊 Current Portfolio</h2>
            <table class="portfolio-table">
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Type</th>
                        <th>Size</th>
                        <th>Entry Price</th>
                        <th>Market Value</th>
                        <th>P&L</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(self._generate_portfolio_rows())}
                </tbody>
            </table>
            {self._generate_cash_row()}
        </div>
        
        <div class="section">
            <h2>📈 Recent Trading Activity</h2>
            <table class="portfolio-table">
                <thead>
                    <tr>
                        <th>Timestamp</th>
                        <th>Symbol</th>
                        <th>Action</th>
                        <th>Size</th>
                        <th>Price</th>
                        <th>P&L</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(self._generate_trade_rows())}
                </tbody>
            </table>
        </div>
        
        <div class="section">
            <h2>🚀 Platform Features</h2>
            <div class="features-grid">
                <div class="feature-box">
                    <h3>Machine Learning Models</h3>
                    <ul>
                        <li>LSTM Neural Networks</li>
                        <li>Random Forest Ensemble</li>
                        <li>XGBoost Gradient Boosting</li>
                        <li>Multi-Model Ensemble</li>
                    </ul>
                </div>
                
                <div class="feature-box">
                    <h3>Risk Management</h3>
                    <ul>
                        <li>Kelly Criterion Position Sizing</li>
                        <li>Dynamic Stop-Loss</li>
                        <li>Portfolio Risk Controls</li>
                        <li>Volatility-Adjusted Positions</li>
                    </ul>
                </div>
                
                <div class="feature-box">
                    <h3>Technical Indicators</h3>
                    <ul>
                        <li>Moving Averages (SMA/EMA)</li>
                        <li>RSI & MACD</li>
                        <li>Bollinger Bands</li>
                        <li>ATR Volatility</li>
                    </ul>
                </div>
                
                <div class="feature-box">
                    <h3>Advanced Analytics</h3>
                    <ul>
                        <li>Real-time Performance Tracking</li>
                        <li>Sharpe Ratio Optimization</li>
                        <li>Drawdown Analysis</li>
                        <li>Win Rate Metrics</li>
                    </ul>
                </div>
            </div>
        </div>
        
        <div class="timestamp">
            Dashboard Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
        </div>
    </div>
</body>
</html>
"""
        
        with open(output_path, 'w') as f:
            f.write(html_content)
        
        return output_path
    
    def _generate_portfolio_rows(self) -> List[str]:
        """Generate HTML rows for portfolio positions"""
        rows = []
        for symbol, position in self.bot.portfolio.items():
            pnl = position['market_value'] - (position['size'] * position['entry_price'])
            pnl_class = 'positive' if pnl > 0 else 'negative'
            
            rows.append(f"""
                    <tr>
                        <td><strong>{symbol}</strong></td>
                        <td>{position['type']}</td>
                        <td>{position['size']}</td>
                        <td>${position['entry_price']:.2f}</td>
                        <td>${position['market_value']:,.2f}</td>
                        <td class="{pnl_class}">${pnl:,.2f}</td>
                    </tr>
            """)
        
        if not rows:
            rows.append("""
                    <tr>
                        <td colspan="6" style="text-align: center; padding: 20px; color: #888;">
                            No open positions
                        </td>
                    </tr>
            """)
        
        return rows
    
    def _generate_cash_row(self) -> str:
        """Generate cash balance display"""
        return f"""
            <div style="margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 5px;">
                <strong>Cash Balance:</strong> ${self.bot.cash:,.2f}
            </div>
        """
    
    def _generate_trade_rows(self) -> List[str]:
        """Generate HTML rows for recent trades"""
        rows = []
        recent_trades = self.bot.trades_history[-10:]  # Last 10 trades
        
        for trade in reversed(recent_trades):
            timestamp = trade['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            pnl_display = ''
            
            if trade['action'] == 'CLOSE' and 'pnl' in trade:
                pnl = trade['pnl']
                pnl_class = 'positive' if pnl > 0 else 'negative'
                pnl_display = f'<span class="{pnl_class}">${pnl:,.2f}</span>'
            else:
                pnl_display = '-'
            
            rows.append(f"""
                    <tr>
                        <td>{timestamp}</td>
                        <td><strong>{trade['symbol']}</strong></td>
                        <td>{trade['action']}</td>
                        <td>{trade['size']}</td>
                        <td>${trade['price']:.2f}</td>
                        <td>{pnl_display}</td>
                    </tr>
            """)
        
        if not rows:
            rows.append("""
                    <tr>
                        <td colspan="6" style="text-align: center; padding: 20px; color: #888;">
                            No trades yet
                        </td>
                    </tr>
            """)
        
        return rows
    
    def display_console_dashboard(self):
        """Display a text-based dashboard in the console"""
        metrics = self.bot.get_performance_metrics()
        
        print("\n" + "="*70)
        print(" " * 15 + "AI TRADING BOT DASHBOARD")
        print("="*70)
        print()
        
        print("PERFORMANCE METRICS:")
        print("-" * 70)
        print(f"Account Value:    ${metrics.get('current_value', 0):>15,.2f}")
        print(f"Total Return:     {metrics.get('total_return_pct', 0):>15.2f}%")
        print(f"Sharpe Ratio:     {metrics.get('sharpe_ratio', 0):>15.2f}")
        print(f"Win Rate:         {metrics.get('win_rate_pct', 0):>15.1f}%")
        print(f"Total Trades:     {metrics.get('total_trades', 0):>15}")
        print(f"Max Drawdown:     {metrics.get('max_drawdown', 0)*100:>15.2f}%")
        print()
        
        print("CURRENT PORTFOLIO:")
        print("-" * 70)
        if self.bot.portfolio:
            for symbol, position in self.bot.portfolio.items():
                pnl = position['market_value'] - (position['size'] * position['entry_price'])
                print(f"{symbol:6} | {position['type']:5} | Size: {position['size']:4} | "
                      f"Entry: ${position['entry_price']:7.2f} | P&L: ${pnl:>10,.2f}")
        else:
            print("  No open positions")
        
        print(f"\nCash Balance: ${self.bot.cash:,.2f}")
        print("="*70)
        print()


if __name__ == '__main__':
    from trading_bot import AITradingBot, generate_sample_data
    
    # Initialize bot and run simulation
    bot = AITradingBot()
    market_data = generate_sample_data('AAPL', days=252)
    processed_data = bot.process_market_data(market_data)
    
    for i in range(len(processed_data)):
        current_data = processed_data.iloc[i]
        bot.execute_trading_logic(current_data, 'AAPL')
        bot.update_portfolio_value({'AAPL': current_data['close']})
    
    # Generate dashboard
    dashboard = TradingDashboard(bot)
    
    # Console dashboard
    dashboard.display_console_dashboard()
    
    # HTML dashboard
    html_path = dashboard.generate_dashboard_html()
    print(f"✓ HTML Dashboard generated: {html_path}")
    print(f"✓ Open {html_path} in your web browser to view the interactive dashboard")
