"""Strategy router node to select appropriate strategy based on regime."""
from typing import TypedDict, Literal
from datetime import datetime

from app.schemas.models import MarketRegime


class RouterState(TypedDict):
    """State for strategy routing."""
    regime: MarketRegime | None
    selected_strategy: Literal["momentum", "mean_reversion", "neutral"] | None
    timestamp: datetime


async def route_strategy_node(state: RouterState) -> RouterState:
    """
    Route to appropriate strategy based on market regime.

    Routing logic:
    - TRENDING -> momentum strategy
    - RANGING -> mean_reversion strategy (not implemented in MVP)
    - HIGH_VOLATILITY -> neutral (reduce exposure)
    - LOW_VOLATILITY -> momentum strategy
    - UNKNOWN -> neutral
    """
    regime = state.get("regime")

    if not regime:
        return {
            **state,
            "selected_strategy": "neutral"
        }

    selected_strategy: Literal["momentum", "mean_reversion", "neutral"]

    if regime.regime == "TRENDING":
        selected_strategy = "momentum"
    elif regime.regime == "RANGING":
        selected_strategy = "mean_reversion"
    elif regime.regime == "HIGH_VOLATILITY":
        selected_strategy = "neutral"  # Avoid trading in high vol
    elif regime.regime == "LOW_VOLATILITY":
        selected_strategy = "momentum"
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
    elif selected == "mean_reversion":
        return "mean_reversion"
    else:
        return "neutral"

