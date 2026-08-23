"""
Main entry point for the AI Trading Bot
"""
import argparse
import sys
from trading_bot.bot import AITradingBot
from trading_bot.utils import setup_logging


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='AI Trading Bot - Autonomous Trading System')
    parser.add_argument('--config', type=str, default='config.yaml', help='Path to config file')
    parser.add_argument('--train', action='store_true', help='Train models before trading')
    parser.add_argument('--cycles', type=int, default=1, help='Number of trading cycles to run')
    parser.add_argument('--dashboard', action='store_true', help='Run dashboard server')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    
    if args.dashboard:
        # Run dashboard
        print("Starting AI Trading Bot Dashboard...")
        print("Dashboard will be available at http://localhost:5000")
        from dashboard.app import app
        import yaml
        
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
        
        app.run(
            host=config['dashboard']['host'],
            port=config['dashboard']['port'],
            debug=config['dashboard']['debug']
        )
    else:
        # Run trading bot
        print("="*60)
        print("AI Trading Bot - Autonomous Trading System")
        print("="*60)
        
        bot = AITradingBot(config_path=args.config)
        portfolio = bot.run(train=args.train, cycles=args.cycles)
        
        print("\n" + "="*60)
        print("Trading Session Completed")
        print("="*60)
        
        metrics = bot.get_performance_metrics()
        print(f"\nTotal Value: ${metrics['total_value']:,.2f}")
        print(f"Total Return: {metrics['total_return']:.2%}")
        print(f"Number of Trades: {metrics['num_trades']}")
        print(f"Open Positions: {metrics['num_positions']}")
        print(f"Available Cash: ${metrics['cash']:,.2f}")


if __name__ == "__main__":
    main()
