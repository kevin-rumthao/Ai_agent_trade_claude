"""Ingest graph - market data collection pipeline."""
from typing import TypedDict
from datetime import datetime
from langgraph.graph import StateGraph, END

from app.nodes.market_ingest import ingest_market_data_node, IngestState


def create_ingest_graph() -> StateGraph:
    """
    Create the market data ingestion graph.

    Flow:
    START -> ingest_market_data -> END
    """
    workflow = StateGraph(IngestState)

    # Add nodes
    workflow.add_node("ingest", ingest_market_data_node)

    # Define edges
    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest", END)

    return workflow.compile()

