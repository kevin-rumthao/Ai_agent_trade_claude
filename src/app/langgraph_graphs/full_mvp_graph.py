"""Full MVP trading graph - complete pipeline."""
from typing import TypedDict, Literal
from datetime import datetime
from langgraph.graph import StateGraph, END
from app.nodes.ts_jepa_node import world_model_node

from app.schemas.events import TradeEvent, OrderbookUpdate, KlineEvent
from app.schemas.models import (
    MarketFeatures,
    MarketRegime,
    Signal,
    Order,
    ExecutionResult,
    PortfolioState,
    RiskLimits
)
from app.nodes.market_ingest import ingest_market_data_node
from app.nodes.feature_engineering import compute_features_node
from app.nodes.regime_classifier import classify_regime_node
from app.nodes.strategy_router import route_strategy_node, get_strategy_node_name
from app.nodes.momentum_policy import momentum_strategy_node
from app.nodes.mean_reversion_policy import mean_reversion_strategy_node
from app.nodes.swing_policy import swing_strategy_node
from app.nodes.rl_agent_node import rl_agent_node # NEW
from app.nodes.sentiment_enrichment import enrich_sentiment_node
from app.nodes.risk_manager import risk_management_node
from app.nodes.execution_agent import execution_agent_node
from app.nodes.hedge_agent import hedge_agent_node


class FullMVPState(TypedDict):
    """Complete state for full MVP pipeline."""
    # Market data
    trades: list[TradeEvent]
    orderbook: OrderbookUpdate | None
    klines: list[KlineEvent]

    # Features
    features: MarketFeatures | None

    # World Model
    market_latent_state: list[float] | None

    # Sentiment
    sentiment_fear_greed: float | None
    sentiment_funding_rate: float | None

    # Regime
    regime: MarketRegime | None

    # Strategy routing
    selected_strategy: Literal["momentum", "mean_reversion", "swing", "rl_agent", "neutral"] | None

    # Signal
    signals: list[Signal]

    # Risk management
    portfolio: PortfolioState | None
    approved_orders: list[Order]
    risk_limits: RiskLimits

    # Execution
    execution_results: list[ExecutionResult]

    # Metadata
    symbol: str
    timestamp: datetime


def neutral_strategy_node(state: FullMVPState) -> FullMVPState:
    """
    Neutral strategy - generate no-trade signal.
    Used when market conditions are unfavorable.
    """
    from app.config import settings

    signal = Signal(
        timestamp=datetime.now(),
        symbol=state.get("symbol", settings.symbol),
        strategy="neutral",
        direction="NEUTRAL",
        strength=0.0,
        confidence=1.0,
        reasoning="Neutral market conditions or low regime confidence"
    )

    return {
        **state,
        "signals": [signal]
    }


def create_full_mvp_graph() -> StateGraph:
    """
    Create the complete MVP trading graph.

    Flow:
    START -> ingest -> features -> regime -> router -> [momentum|mean_reversion|rl_agent|neutral] -> risk -> execution -> END

    The router uses conditional edges to select the appropriate strategy.
    """
    workflow = StateGraph(FullMVPState)

    # Add all nodes (avoid state key names)
    workflow.add_node("ingest", ingest_market_data_node)
    workflow.add_node("compute_features", compute_features_node)
    workflow.add_node("enrich_sentiment", enrich_sentiment_node)
    workflow.add_node("world_model", world_model_node)
    workflow.add_node("classify_regime", classify_regime_node)
    workflow.add_node("route_strategy", route_strategy_node)
    workflow.add_node("momentum", momentum_strategy_node)
    workflow.add_node("swing", swing_strategy_node) # NEW
    workflow.add_node("mean_reversion", mean_reversion_strategy_node)
    workflow.add_node("rl_agent", rl_agent_node) # NEW
    workflow.add_node("neutral", neutral_strategy_node)
    workflow.add_node("hedge_agent", hedge_agent_node)
    workflow.add_node("risk_check", risk_management_node)
    workflow.add_node("execute_orders", execution_agent_node)

    # Define linear edges
    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest", "compute_features")
    workflow.add_edge("compute_features", "enrich_sentiment")
    workflow.add_edge("enrich_sentiment", "world_model")
    workflow.add_edge("world_model", "classify_regime")
    workflow.add_edge("classify_regime", "route_strategy")

    # Conditional edge from router to strategy
    workflow.add_conditional_edges(
        "route_strategy",
        get_strategy_node_name,
        {
            "momentum": "momentum",
            "swing": "swing",
            "mean_reversion": "mean_reversion",
            "rl_agent": "rl_agent", # NEW
            "neutral": "neutral"
        }
    )

    # All strategies flow to hedge agent
    workflow.add_edge("momentum", "hedge_agent")
    workflow.add_edge("swing", "hedge_agent")
    workflow.add_edge("mean_reversion", "hedge_agent")
    workflow.add_edge("rl_agent", "hedge_agent") # NEW
    workflow.add_edge("neutral", "hedge_agent")

    # Hedge agent to risk management
    workflow.add_edge("hedge_agent", "risk_check")

    # Risk to execution to end
    workflow.add_edge("risk_check", "execute_orders")
    workflow.add_edge("execute_orders", END)

    return workflow.compile()
