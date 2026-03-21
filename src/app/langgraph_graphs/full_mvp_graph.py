"""Full MVP trading graph — clean single-pipeline architecture.

Flow:
  START → ingest → compute_features → enrich_sentiment → classify_regime
        → route_strategy → [momentum|mean_reversion|swing|neutral]
        → hedge_agent → risk_check → execute_orders → END
"""
from typing import TypedDict, Literal
from datetime import datetime
from langgraph.graph import StateGraph, END

from app.schemas.events import TradeEvent, OrderbookUpdate, KlineEvent
from app.schemas.models import (
    MarketFeatures,
    MarketRegime,
    Signal,
    Order,
    ExecutionResult,
    PortfolioState,
    RiskLimits,
)
from app.nodes.market_ingest import ingest_market_data_node
from app.nodes.feature_engineering import compute_features_node
from app.nodes.sentiment_enrichment import enrich_sentiment_node
from app.nodes.regime_classifier import classify_regime_node
from app.nodes.strategy_router import route_strategy_node, get_strategy_node_name
from app.nodes.momentum_policy import momentum_strategy_node
from app.nodes.mean_reversion_policy import mean_reversion_strategy_node
from app.nodes.swing_policy import swing_strategy_node
from app.nodes.hedge_agent import hedge_agent_node
from app.nodes.risk_manager import risk_management_node
from app.nodes.execution_agent import execution_agent_node


# ─── State ────────────────────────────────────────────────────────────────────
class FullMVPState(TypedDict):
    """Complete pipeline state."""
    # Market data
    trades:    list[TradeEvent]
    orderbook: OrderbookUpdate | None
    klines:    list[KlineEvent]

    # Features
    features: MarketFeatures | None

    # Sentiment
    sentiment_fear_greed:   float | None
    sentiment_funding_rate: float | None

    # Regime
    regime: MarketRegime | None

    # Strategy routing
    selected_strategy: Literal["momentum", "mean_reversion", "swing", "neutral"] | None

    # Signals & orders
    signals:           list[Signal]
    portfolio:         PortfolioState | None
    approved_orders:   list[Order]
    risk_limits:       RiskLimits
    execution_results: list[ExecutionResult]

    # Metadata
    symbol:    str
    timestamp: datetime


# ─── Neutral strategy node ────────────────────────────────────────────────────
def neutral_strategy_node(state: FullMVPState) -> FullMVPState:
    """Emit a NEUTRAL signal — used when regime confidence is low or vol is extreme."""
    from app.config import settings

    signal = Signal(
        timestamp=datetime.now(),
        symbol=state.get("symbol", settings.symbol),
        strategy="neutral",
        direction="NEUTRAL",
        strength=0.0,
        confidence=1.0,
        reasoning="Neutral: low regime confidence or HIGH_VOLATILITY",
    )
    return {**state, "signals": [signal]}


# ─── Graph factory ────────────────────────────────────────────────────────────
def create_full_mvp_graph() -> StateGraph:
    """
    Compile and return the full MVP LangGraph.

    Nodes (in order):
      ingest → compute_features → enrich_sentiment → classify_regime
      → route_strategy → {momentum | mean_reversion | swing | neutral}
      → hedge_agent → risk_check → execute_orders → END
    """
    workflow = StateGraph(FullMVPState)

    # ── Data & features
    workflow.add_node("ingest",           ingest_market_data_node)
    workflow.add_node("compute_features", compute_features_node)
    workflow.add_node("enrich_sentiment", enrich_sentiment_node)

    # ── Regime (LightGBM)
    workflow.add_node("classify_regime",  classify_regime_node)

    # ── Strategy selection
    workflow.add_node("route_strategy",   route_strategy_node)

    # ── Strategy implementations
    workflow.add_node("momentum",         momentum_strategy_node)
    workflow.add_node("mean_reversion",   mean_reversion_strategy_node)
    workflow.add_node("swing",            swing_strategy_node)
    workflow.add_node("neutral",          neutral_strategy_node)

    # ── Risk & execution
    workflow.add_node("hedge_agent",      hedge_agent_node)
    workflow.add_node("risk_check",       risk_management_node)
    workflow.add_node("execute_orders",   execution_agent_node)

    # ── Edges — linear section
    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest",           "compute_features")
    workflow.add_edge("compute_features", "enrich_sentiment")
    workflow.add_edge("enrich_sentiment", "classify_regime")
    workflow.add_edge("classify_regime",  "route_strategy")

    # ── Conditional edge: router → strategy
    workflow.add_conditional_edges(
        "route_strategy",
        get_strategy_node_name,
        {
            "momentum":      "momentum",
            "mean_reversion": "mean_reversion",
            "swing":         "swing",
            "neutral":       "neutral",
        },
    )

    # ── All strategies converge at hedge_agent
    for strategy in ("momentum", "mean_reversion", "swing", "neutral"):
        workflow.add_edge(strategy, "hedge_agent")

    workflow.add_edge("hedge_agent",    "risk_check")
    workflow.add_edge("risk_check",     "execute_orders")
    workflow.add_edge("execute_orders", END)

    return workflow.compile()
