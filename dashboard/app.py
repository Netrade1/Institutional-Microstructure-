"""
Dashboard API - Flask backend for AI Trading Bot Dashboard
Provides real-time monitoring and control
"""
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import yaml
import json
from datetime import datetime
import logging

from trading_bot.bot import AITradingBot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Global bot instance
bot = None
bot_status = {
    'initialized': False,
    'trained': False,
    'running': False,
    'last_update': None
}


@app.route('/')
def index():
    """Render main dashboard"""
    return render_template('dashboard.html')


@app.route('/api/status')
def get_status():
    """Get bot status"""
    return jsonify({
        'status': bot_status,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/portfolio')
def get_portfolio():
    """Get current portfolio status"""
    if bot is None:
        return jsonify({'error': 'Bot not initialized'}), 400
    
    positions = []
    for symbol, pos in bot.portfolio.positions.items():
        positions.append({
            'symbol': symbol,
            'shares': pos.shares,
            'entry_price': pos.entry_price,
            'current_price': pos.current_price,
            'value': pos.value,
            'profit_loss': pos.profit_loss,
            'profit_loss_pct': pos.profit_loss_pct * 100
        })
    
    return jsonify({
        'total_value': bot.portfolio.total_value,
        'cash': bot.portfolio.cash,
        'total_return': bot.portfolio.total_return * 100,
        'total_pl': bot.portfolio.total_profit_loss,
        'positions': positions,
        'num_trades': len(bot.portfolio.trade_history)
    })


@app.route('/api/performance')
def get_performance():
    """Get performance metrics"""
    if bot is None:
        return jsonify({'error': 'Bot not initialized'}), 400
    
    metrics = bot.get_performance_metrics()
    return jsonify(metrics)


@app.route('/api/trades')
def get_trades():
    """Get trade history"""
    if bot is None:
        return jsonify({'error': 'Bot not initialized'}), 400
    
    return jsonify({
        'trades': bot.portfolio.trade_history[-50:]  # Last 50 trades
    })


@app.route('/api/initialize', methods=['POST'])
def initialize_bot():
    """Initialize the trading bot"""
    global bot, bot_status
    
    try:
        bot = AITradingBot()
        bot_status['initialized'] = True
        bot_status['last_update'] = datetime.now().isoformat()
        
        logger.info("Bot initialized via API")
        return jsonify({'success': True, 'message': 'Bot initialized'})
    
    except Exception as e:
        logger.error(f"Error initializing bot: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/train', methods=['POST'])
def train_bot():
    """Train the bot models"""
    global bot_status
    
    if bot is None:
        return jsonify({'error': 'Bot not initialized'}), 400
    
    try:
        data = bot.fetch_and_prepare_data()
        bot.train_models(data)
        
        bot_status['trained'] = True
        bot_status['last_update'] = datetime.now().isoformat()
        
        logger.info("Bot trained via API")
        return jsonify({'success': True, 'message': 'Bot trained successfully'})
    
    except Exception as e:
        logger.error(f"Error training bot: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/start', methods=['POST'])
def start_trading():
    """Start trading bot"""
    global bot_status
    
    if bot is None:
        return jsonify({'error': 'Bot not initialized'}), 400
    
    if not bot.is_trained:
        return jsonify({'error': 'Bot not trained'}), 400
    
    try:
        bot_status['running'] = True
        bot_status['last_update'] = datetime.now().isoformat()
        
        # Execute one trading cycle
        data = bot.fetch_and_prepare_data()
        bot.execute_trading_cycle(data)
        
        logger.info("Trading cycle executed via API")
        return jsonify({'success': True, 'message': 'Trading cycle completed'})
    
    except Exception as e:
        logger.error(f"Error in trading cycle: {e}")
        bot_status['running'] = False
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stop', methods=['POST'])
def stop_trading():
    """Stop trading bot"""
    global bot_status
    
    bot_status['running'] = False
    bot_status['last_update'] = datetime.now().isoformat()
    
    logger.info("Trading stopped via API")
    return jsonify({'success': True, 'message': 'Trading stopped'})


@app.route('/api/config')
def get_config():
    """Get current configuration"""
    try:
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        return jsonify(config)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Load config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Run Flask app
    app.run(
        host=config['dashboard']['host'],
        port=config['dashboard']['port'],
        debug=config['dashboard']['debug']
    )
