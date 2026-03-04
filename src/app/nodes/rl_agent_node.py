
import os
import torch
import numpy as np
import pandas as pd
import joblib
from datetime import datetime
from stable_baselines3 import PPO

from app.schemas.models import Signal
from app.config import settings

# Global model cache
_rl_model = None
_feature_scaler = None

def load_rl_model():
    global _rl_model
    if _rl_model is not None:
        return _rl_model
        
    model_path = "src/app/models/rl_agent_latest.zip"
    try:
        # PPO.load handles the zip extraction
        _rl_model = PPO.load(model_path, device="cpu")
        print(f"✅ RL Agent loaded from {model_path}")
    except Exception as e:
        print(f"⚠️ RL Agent not found at {model_path}. Error: {e}")
        _rl_model = None
        
    return _rl_model

def load_feature_scaler():
    global _feature_scaler
    if _feature_scaler is not None:
        return _feature_scaler
    
    scaler_path = "src/app/models/rl_scaler.pkl"
    try:
        _feature_scaler = joblib.load(scaler_path)
        print(f"✅ Feature scaler loaded from {scaler_path}")
    except Exception as e:
        print(f"⚠️ Feature scaler not found at {scaler_path}. Using raw features. Error: {e}")
        _feature_scaler = None
    
    return _feature_scaler

def get_rl_observation(state: dict):
    """
    Reconstruct the observation vector used in training.
    [Features (10) + Latent (64)] = 74 dims
    """
    features = state.get("features")
    latent = state.get("market_latent_state")
    
    if not features or latent is None:
        return None
    
    # Load scaler
    scaler = load_feature_scaler()
    
    # Extract feature values
    f = features
    
    # Build feature array (must match training order - now 10 features)
    feature_values = [
        (f.rsi if f.rsi else 50.0) / 100.0,             # feat_rsi
        f.orderbook_imbalance if f.orderbook_imbalance else 0.0,  # feat_imbalance
        f.ofi if f.ofi else 0.0,                        # feat_ofi
        ((f.price - f.ema_50) / f.ema_50) if (f.ema_50 and f.price) else 0.0,  # feat_ema_dev
        f.realized_volatility if f.realized_volatility else 0.0,  # feat_vol
        (f.adx if f.adx else 0.0) / 100.0,              # feat_adx
        # NEW REGIME FEATURES
        (f.vol_regime if hasattr(f, 'vol_regime') and f.vol_regime else 1.0),  # feat_vol_regime
        (f.trend_strength if hasattr(f, 'trend_strength') and f.trend_strength else 0.0),  # feat_trend_strength
        (f.momentum_5 if hasattr(f, 'momentum_5') and f.momentum_5 else 0.0),  # feat_momentum_5
        (f.momentum_20 if hasattr(f, 'momentum_20') and f.momentum_20 else 0.0), # feat_momentum_20
    ]
    
    feats_vec = np.array(feature_values, dtype=np.float32).reshape(1, -1)
    
    # Apply scaler if available
    if scaler is not None:
        try:
            feats_vec = scaler.transform(feats_vec).flatten()
            # print(f"DEBUG: Scaled Features: {[round(x, 4) for x in feats_vec]}")
        except Exception as e:
            print(f"Scaler Error: {e}")
            feats_vec = feats_vec.flatten()
    else:
        feats_vec = feats_vec.flatten()
    
    # Latent (64 dims)
    latent_vec = np.array(latent, dtype=np.float32)
    
    # DEBUG: Check latent drift
    print(f"DEBUG: Feature Mean: {np.mean(feats_vec):.4f} | Latent Mean: {np.mean(latent_vec):.4f} | Latent Std: {np.std(latent_vec):.4f}")

    return np.concatenate([feats_vec, latent_vec])

async def rl_agent_node(state: dict) -> dict:
    """
    LangGraph Node for RL Agent Strategy.
    """
    model = load_rl_model()
    if not model:
        # Fallback to neutral signal
        return {
            **state,
            "signals": []
        }
    
    obs = get_rl_observation(state)
    if obs is None:
         return {
            **state,
            "signals": []
        }
        
    # Inference
    # deterministic=True is usually better for trading (no random noise)
    action, _states = model.predict(obs, deterministic=True)
    
    # DEBUG: Print action
    # print(f"DEBUG: RL Agent Prediction -> Action: {action}")
    # if action != 0:
    #     print(f"DEBUG: 🟢 ACTION TRIGGERED: {action} at {state.get('timestamp')}")
    
    # Map Action
    # 0: Neutral, 1: Long, 2: Short
    direction = "NEUTRAL"
    if action == 1: direction = "LONG"
    elif action == 2: direction = "SHORT"
    
    # Current Price for SL/TP calculation
    current_price = state["features"].price
    
    signal = Signal(
        timestamp=datetime.now(),
        symbol=state.get("symbol", "BTCUSDT"),
        strategy="rl_agent",
        direction=direction,
        strength=1.0, # RL doesn't give confidence easily without modification
        confidence=1.0,
        reasoning="PPO Agent Decision",
        entry_price=current_price,
        # Default tight risk management for RL
        stop_loss=current_price * 0.98 if direction == "LONG" else current_price * 1.02, # 2% SL
        take_profit=current_price * 1.04 if direction == "LONG" else current_price * 0.96, # 4% TP (1:2 Ratio)
        trailing_stop_distance=0.0
    )
    
    return {
        **state,
        "signals": [signal]
    }
