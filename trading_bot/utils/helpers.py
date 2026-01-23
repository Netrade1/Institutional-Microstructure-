"""Utility functions for the trading bot"""
import yaml
import json
import logging
from datetime import datetime
from typing import Dict, Any


def load_config(config_path: str) -> Dict:
    """Load configuration from YAML file"""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def save_results(results: Dict[str, Any], filepath: str):
    """Save results to JSON file"""
    with open(filepath, 'w') as f:
        json.dump(results, f, indent=2, default=str)


def setup_logging(level=logging.INFO):
    """Setup logging configuration"""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f'logs/trading_bot_{datetime.now().strftime("%Y%m%d")}.log'),
            logging.StreamHandler()
        ]
    )
