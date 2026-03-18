"""Strategy router node to select appropriate strategy based on regime."""
from typing import TypedDict, Literal
from datetime import datetime

from app.schemas.models import MarketRegime, MarketFeatures


class RouterState(TypedDict):
    """State for strategy routing."""
    regime: MarketRegime | None
    features: MarketFeatures | None
    selected_strategy: Literal["momentum", "mean_reversion", "swing", "neutral"] | None
    timestamp: datetime


async def route_strategy_node(state: RouterState) -> RouterState:
    """
    Route to appropriate strategy based on market regime and features.

    Routing logic:
    - TRENDING:
      - Pullback (RSI < 45 in Uptrend) -> Swing Strategy
      - Strong Trend -> Momentum Strategy
    - RANGING -> Mean Reversion Strategy
    - HIGH_VOLATILITY -> Neutral (reduce exposure)
    - LOW_VOLATILITY -> Momentum Strategy (breakout anticipation)
    - UNKNOWN -> Neutral
    """
    regime = state.get("regime")
    features = state.get("features")

    if not regime:
        return {
            **state,
            "selected_strategy": "neutral"
        }

    selected_strategy: Literal["momentum", "mean_reversion", "swing", "neutral"]

    if regime.regime == "TRENDING":
        # Default to Momentum
        selected_strategy = "momentum"
        
        # Check for Swing (Pullback) opportunities if features available
        if features and features.rsi is not None and features.ema_50 and features.ema_200:
            rsi = features.rsi
            is_uptrend = features.ema_50 > features.ema_200
            
            # Swing Logic: Route to Swing if we are in a pullback within a trend
            if is_uptrend:
                if rsi < 55:  # Pullback zone
                    selected_strategy = "swing"
            else:  # Downtrend
                if rsi > 45:  # Rally zone
                    selected_strategy = "swing"
                    
    elif regime.regime == "RANGING":
        selected_strategy = "mean_reversion"
        
    elif regime.regime == "HIGH_VOLATILITY":
        selected_strategy = "neutral"  # Avoid trading in high vol or reduce size
        
    elif regime.regime == "LOW_VOLATILITY":
        selected_strategy = "momentum" # Anticipate breakout
        
    else:  # UNKNOWN
        selected_strategy = "neutral"

    # Override if confidence is too low
    if regime.confidence < 0.4:
        selected_strategy = "neutral"

    return {
        **state,
        "selected_strategy": selected_strategy,
        "timestamp": datetime.now()
    }


def get_strategy_node_name(state: RouterState) -> str:
    """Conditional edge to determine which strategy node to call."""
    selected = state.get("selected_strategy")

    if selected == "momentum":
        return "momentum"
    elif selected == "swing":
        return "swing"
    elif selected == "mean_reversion":
        return "mean_reversion"
    else:
        return "neutral"
