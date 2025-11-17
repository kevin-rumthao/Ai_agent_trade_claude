"""Momentum strategy graph."""
from typing import TypedDict
from datetime import datetime
from langgraph.graph import StateGraph, END

from app.schemas.models import MarketFeatures, Signal
from app.schemas.events import TradeEvent, OrderbookUpdate, KlineEvent
from app.nodes.feature_engineering import compute_features_node
from app.nodes.momentum_policy import momentum_strategy_node


class MomentumGraphState(TypedDict):
    """Combined state for momentum graph."""
    # From ingest
    trades: list[TradeEvent]
    orderbook: OrderbookUpdate | None
    klines: list[KlineEvent]
    # Features
    features: MarketFeatures | None
    # Signal
    signal: Signal | None
    symbol: str
    timestamp: datetime


def create_momentum_graph() -> StateGraph:
    """
    Create the momentum strategy graph.

    Flow:
    START -> compute_features -> momentum_strategy -> END
    """
    workflow = StateGraph(MomentumGraphState)

    # Add nodes (avoid state key names)
    workflow.add_node("compute_features", compute_features_node)
    workflow.add_node("momentum", momentum_strategy_node)

    # Define edges
    workflow.set_entry_point("compute_features")
    workflow.add_edge("compute_features", "momentum")
    workflow.add_edge("momentum", END)

    return workflow.compile()

