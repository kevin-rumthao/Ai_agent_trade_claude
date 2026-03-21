"""Slow Macro trading graph - reasoning and regime analysis."""
from langgraph.graph import StateGraph, END

from app.schemas.models import RiskLimits
from app.langgraph_graphs.full_mvp_graph import FullMVPState

from app.nodes.market_ingest import ingest_market_data_node
from app.nodes.feature_engineering import compute_features_node
from app.nodes.sentiment_enrichment import enrich_sentiment_node
from app.nodes.ts_jepa_node import world_model_node
from app.nodes.regime_classifier import classify_regime_node
from app.nodes.publish_macro_node import publish_macro_state_node

def create_slow_macro_graph() -> StateGraph:
    """
    Create the slow macro analysis graph.
    Flow: START -> ingest -> features -> sentiment -> world_model -> regime -> publish -> END
    """
    workflow = StateGraph(FullMVPState)

    # Add nodes
    workflow.add_node("ingest", ingest_market_data_node)
    workflow.add_node("compute_features", compute_features_node)
    workflow.add_node("enrich_sentiment", enrich_sentiment_node)
    workflow.add_node("world_model", world_model_node)
    workflow.add_node("classify_regime", classify_regime_node)
    workflow.add_node("publish", publish_macro_state_node)

    # Define linear edges
    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest", "compute_features")
    workflow.add_edge("compute_features", "enrich_sentiment")
    workflow.add_edge("enrich_sentiment", "world_model")
    workflow.add_edge("world_model", "classify_regime")
    workflow.add_edge("classify_regime", "publish")
    workflow.add_edge("publish", END)

    return workflow.compile()
