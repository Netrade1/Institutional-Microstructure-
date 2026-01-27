"""
Configuration Manager
Handles configuration loading and management
"""

import json
import os
from typing import Dict, Any, Optional


class ConfigManager:
    """
    Manages application configuration settings.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path or "config.json"
        self.config: Dict[str, Any] = {}
        
        if os.path.exists(self.config_path):
            self.load()
    
    def load(self):
        """Load configuration from file"""
        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            self.config = {}
    
    def save(self):
        """Save configuration to file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value.
        
        Args:
            key: Configuration key (supports dot notation, e.g., 'api.key')
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """
        Set configuration value.
        
        Args:
            key: Configuration key (supports dot notation)
            value: Value to set
        """
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def get_all(self) -> Dict[str, Any]:
        """Get all configuration"""
        return self.config.copy()
    
    def update(self, config_dict: Dict[str, Any]):
        """
        Update configuration with dictionary.
        
        Args:
            config_dict: Dictionary with configuration updates
        """
        self._deep_update(self.config, config_dict)
    
    def _deep_update(self, base_dict: Dict, update_dict: Dict):
        """Recursively update nested dictionary"""
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value


# Default configuration
DEFAULT_CONFIG = {
    "market_data": {
        "source": "simulated",
        "api_key": None,
        "cache_enabled": True,
        "cache_duration": 300
    },
    "execution": {
        "default_time_in_force": "GTC",
        "max_order_size": 10000,
        "enable_pre_trade_checks": True
    },
    "risk": {
        "max_position_size": 100000,
        "max_portfolio_risk": 0.20,
        "default_risk_per_trade": 0.02,
        "enable_position_limits": True
    },
    "microstructure": {
        "order_book_depth": 10,
        "tick_data_buffer_size": 1000
    },
    "logging": {
        "level": "INFO",
        "file": "trading.log",
        "console": True
    }
}
