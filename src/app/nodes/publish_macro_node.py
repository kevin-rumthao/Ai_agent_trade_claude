from datetime import datetime
from app.config import settings
from app.utils.redis_client import redis_manager
from typing import Dict, Any

async def publish_macro_state_node(state: dict) -> dict:
    """
    Publish the computed macro state (regime, sentiment) to Redis.
    This serves as the bridge between the Slow LLM Loop and the Fast Execution Loop.
    """
    try:
        macro_dict: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "symbol": state.get("symbol", settings.symbol)
        }
        
        # Extract regime if exists
        regime = state.get("regime")
        if regime:
            macro_dict["regime"] = {
                "regime": regime.regime.value if hasattr(regime.regime, 'value') else str(regime.regime),
                "confidence": float(regime.confidence)
            }
            
        # Extract world model info
        latent = state.get("market_latent_state")
        if latent is not None:
             macro_dict["market_latent_state"] = latent
             
        # Extract sentiment
        if state.get("sentiment_fear_greed") is not None:
            macro_dict["sentiment_fear_greed"] = state["sentiment_fear_greed"]
            
        if state.get("sentiment_funding_rate") is not None:
            macro_dict["sentiment_funding_rate"] = state["sentiment_funding_rate"]
            
        # Write to Redis
        success = await redis_manager.set_macro_state(macro_dict)
        if success:
             print("✅ Successfully published macro state to Redis")
        else:
             print("⚠️ Failed to publish macro state to Redis")
             
    except Exception as e:
        print(f"Error publishing macro state: {e}")
        
    return state
