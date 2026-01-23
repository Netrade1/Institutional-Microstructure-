"""
Machine Learning Models for Price Prediction
Includes LSTM, Random Forest, and XGBoost implementations
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import xgboost as xgb
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from typing import Tuple, Optional
import joblib
import logging

logger = logging.getLogger(__name__)


class LSTMModel:
    """LSTM Neural Network for time series prediction"""
    
    def __init__(self, lookback: int = 60, features: int = 1):
        self.lookback = lookback
        self.features = features
        self.model = None
        self.scaler = StandardScaler()
        
    def build_model(self, units: int = 50, dropout: float = 0.2) -> Sequential:
        """Build LSTM architecture"""
        model = Sequential([
            LSTM(units=units, return_sequences=True, input_shape=(self.lookback, self.features)),
            Dropout(dropout),
            LSTM(units=units, return_sequences=True),
            Dropout(dropout),
            LSTM(units=units),
            Dropout(dropout),
            Dense(units=25),
            Dense(units=1)
        ])
        
        model.compile(optimizer='adam', loss='mean_squared_error', metrics=['mae'])
        self.model = model
        return model
    
    def train(self, X: np.ndarray, y: np.ndarray, epochs: int = 50, batch_size: int = 32) -> dict:
        """Train the LSTM model"""
        if self.model is None:
            self.build_model()
        
        # Split data
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Early stopping
        early_stop = keras.callbacks.EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)
        
        # Train
        history = self.model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            epochs=epochs,
            batch_size=batch_size,
            callbacks=[early_stop],
            verbose=0
        )
        
        logger.info(f"LSTM Training completed. Final loss: {history.history['loss'][-1]:.4f}")
        return history.history
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Make predictions"""
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")
        return self.model.predict(X, verbose=0)
    
    def save(self, path: str):
        """Save model to disk"""
        if self.model:
            self.model.save(f"{path}_lstm.h5")
            joblib.dump(self.scaler, f"{path}_lstm_scaler.pkl")
    
    def load(self, path: str):
        """Load model from disk"""
        self.model = keras.models.load_model(f"{path}_lstm.h5")
        self.scaler = joblib.load(f"{path}_lstm_scaler.pkl")


class RandomForestModel:
    """Random Forest for price prediction"""
    
    def __init__(self, n_estimators: int = 100, max_depth: int = 10):
        self.model = RandomForestRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=42,
            n_jobs=-1
        )
        self.scaler = StandardScaler()
        
    def train(self, X: np.ndarray, y: np.ndarray) -> 'RandomForestModel':
        """Train Random Forest model"""
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train
        self.model.fit(X_scaled, y)
        logger.info(f"Random Forest trained. Score: {self.model.score(X_scaled, y):.4f}")
        return self
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Make predictions"""
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)
    
    def get_feature_importance(self) -> np.ndarray:
        """Get feature importance scores"""
        return self.model.feature_importances_
    
    def save(self, path: str):
        """Save model to disk"""
        joblib.dump(self.model, f"{path}_rf.pkl")
        joblib.dump(self.scaler, f"{path}_rf_scaler.pkl")
    
    def load(self, path: str):
        """Load model from disk"""
        self.model = joblib.load(f"{path}_rf.pkl")
        self.scaler = joblib.load(f"{path}_rf_scaler.pkl")


class XGBoostModel:
    """XGBoost for price prediction"""
    
    def __init__(self, n_estimators: int = 100, learning_rate: float = 0.1, max_depth: int = 6):
        self.model = xgb.XGBRegressor(
            n_estimators=n_estimators,
            learning_rate=learning_rate,
            max_depth=max_depth,
            random_state=42,
            n_jobs=-1
        )
        self.scaler = StandardScaler()
        
    def train(self, X: np.ndarray, y: np.ndarray) -> 'XGBoostModel':
        """Train XGBoost model"""
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Split for validation
        X_train, X_val, y_train, y_val = train_test_split(X_scaled, y, test_size=0.2, random_state=42)
        
        # Train with early stopping
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            early_stopping_rounds=10,
            verbose=False
        )
        
        logger.info(f"XGBoost trained. Best iteration: {self.model.best_iteration}")
        return self
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Make predictions"""
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)
    
    def get_feature_importance(self) -> dict:
        """Get feature importance scores"""
        return self.model.get_booster().get_score(importance_type='weight')
    
    def save(self, path: str):
        """Save model to disk"""
        joblib.dump(self.model, f"{path}_xgb.pkl")
        joblib.dump(self.scaler, f"{path}_xgb_scaler.pkl")
    
    def load(self, path: str):
        """Load model from disk"""
        self.model = joblib.load(f"{path}_xgb.pkl")
        self.scaler = joblib.load(f"{path}_xgb_scaler.pkl")


class EnsembleModel:
    """Ensemble of multiple models for robust predictions"""
    
    def __init__(self):
        self.lstm = None
        self.rf = None
        self.xgb = None
        self.weights = [0.4, 0.3, 0.3]  # LSTM, RF, XGB
        
    def train(self, X_lstm: np.ndarray, X_features: np.ndarray, y: np.ndarray):
        """Train all models in the ensemble"""
        logger.info("Training ensemble models...")
        
        # Train LSTM
        self.lstm = LSTMModel(lookback=X_lstm.shape[1], features=X_lstm.shape[2])
        self.lstm.train(X_lstm, y, epochs=30)
        
        # Reshape for tree models
        X_flat = X_features.reshape(X_features.shape[0], -1) if len(X_features.shape) > 2 else X_features
        
        # Train Random Forest
        self.rf = RandomForestModel()
        self.rf.train(X_flat, y)
        
        # Train XGBoost
        self.xgb = XGBoostModel()
        self.xgb.train(X_flat, y)
        
        logger.info("Ensemble training completed")
        
    def predict(self, X_lstm: np.ndarray, X_features: np.ndarray) -> np.ndarray:
        """Make ensemble predictions"""
        # Get predictions from each model
        lstm_pred = self.lstm.predict(X_lstm).flatten()
        
        X_flat = X_features.reshape(X_features.shape[0], -1) if len(X_features.shape) > 2 else X_features
        rf_pred = self.rf.predict(X_flat)
        xgb_pred = self.xgb.predict(X_flat)
        
        # Weighted average
        ensemble_pred = (
            self.weights[0] * lstm_pred +
            self.weights[1] * rf_pred +
            self.weights[2] * xgb_pred
        )
        
        return ensemble_pred
    
    def save(self, path: str):
        """Save all models"""
        self.lstm.save(path)
        self.rf.save(path)
        self.xgb.save(path)
        joblib.dump(self.weights, f"{path}_ensemble_weights.pkl")
    
    def load(self, path: str):
        """Load all models"""
        self.lstm = LSTMModel()
        self.lstm.load(path)
        self.rf = RandomForestModel()
        self.rf.load(path)
        self.xgb = XGBoostModel()
        self.xgb.load(path)
        self.weights = joblib.load(f"{path}_ensemble_weights.pkl")
