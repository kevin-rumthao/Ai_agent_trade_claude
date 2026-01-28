import torch
import numpy as np
from typing import TypedDict
from app.models.ts_jepa import TS_JEPA
from app.config import settings

# Global model cache to avoid reloading every tick
_jepa_model = None

def load_jepa_model():
    """Load the pre-trained TS-JEPA model."""
    global _jepa_model
    if _jepa_model is not None:
        return _jepa_model
        
    # Initialize structure
    # input_dim=12 matches our feature vector size (see below)
    model = TS_JEPA(input_dim=12, embed_dim=64)
    
    try:
        # Load weights (You will train this later)
        # model.load_state_dict(torch.load("models/jepa_latest.pth"))
        print("⚠️ JEPA weights not found, using initialized weights (Random State)")
        model.eval()
    except Exception as e:
        print(f"Error loading JEPA: {e}")
    
    _jepa_model = model
    return _jepa_model

async def world_model_node(state: dict) -> dict:
    """
    LangGraph Node: TS-JEPA World Model.
    
    Input: Market Features (EMAs, RSI, OFI, etc.)
    Output: 'market_latent_state' (Vector representing the TRUE market condition)
    """
    features = state.get("features")
    if not features:
        return state

    # 1. Prepare Input Vector (Normalize these in production!)
    # We pull relevant features from your FeatureEngine output
    raw_vector = [
        features.rsi / 100.0 if features.rsi else 0.5,
        features.orderbook_imbalance if features.orderbook_imbalance else 0.0,
        features.ofi if features.ofi else 0.0,
        (features.price - features.ema_50) / features.ema_50 if features.ema_50 else 0.0,
        features.realized_volatility if features.realized_volatility else 0.0,
        features.adx / 100.0 if features.adx else 0.0,
        # ... add more technicals to reach input_dim
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0 # Padding for now
    ]
    
    # 2. Run Inference
    model = load_jepa_model()
    
    tensor_input = torch.FloatTensor(raw_vector).unsqueeze(0) # Batch size 1
    
    with torch.no_grad():
        latent_state = model.get_latent_state(tensor_input)
        
    # 3. Convert to list for LangGraph state
    market_state_vector = latent_state.squeeze().tolist()
    
    # 4. Interpret the State (Optional: Simple Classification for debugging)
    # e.g., First dimension indicates "Bullish/Bearish"
    regime_label = "NEUTRAL"
    if market_state_vector[0] > 0.5:
        regime_label = "BULLISH_STRUCTURAL"
    elif market_state_vector[0] < -0.5:
        regime_label = "BEARISH_STRUCTURAL"

    print(f"🧠 World Model State: {regime_label} (Latent Val: {market_state_vector[0]:.4f})")

    return {
        **state,
        "market_latent_state": market_state_vector,
        # We can update the regime object too if we want to override the rule-based one
        # "regime": MarketRegime(regime=regime_label, confidence=0.9) 
    }