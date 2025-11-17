"""Tests for market ingestion node."""
import pytest
from datetime import datetime

from app.nodes.market_ingest import ingest_market_data_node, IngestState
from app.schemas.events import TradeEvent, OrderbookUpdate, KlineEvent


@pytest.mark.asyncio
async def test_ingest_empty_state() -> None:
    """Test ingestion with empty initial state."""
    state: IngestState = {
        "trades": [],
        "orderbook": None,
        "klines": [],
        "symbol": "BTCUSDT",
        "timestamp": datetime.now()
    }

    result = await ingest_market_data_node(state)

    assert "symbol" in result
    assert result["symbol"] == "BTCUSDT"
    assert isinstance(result["trades"], list)
    assert isinstance(result["klines"], list)


@pytest.mark.asyncio
async def test_ingest_preserves_symbol() -> None:
    """Test that ingestion preserves symbol."""
    state: IngestState = {
        "trades": [],
        "orderbook": None,
        "klines": [],
        "symbol": "ETHUSDT",
        "timestamp": datetime.now()
    }

    result = await ingest_market_data_node(state)

    assert result["symbol"] == "ETHUSDT"


@pytest.mark.asyncio
async def test_ingest_returns_valid_types() -> None:
    """Test that ingestion returns correct types."""
    state: IngestState = {
        "trades": [],
        "orderbook": None,
        "klines": [],
        "symbol": "BTCUSDT",
        "timestamp": datetime.now()
    }

    result = await ingest_market_data_node(state)

    assert isinstance(result["trades"], list)
    assert isinstance(result["klines"], list)

    # All trades should be TradeEvent instances if present
    for trade in result["trades"]:
        assert isinstance(trade, TradeEvent)

    # All klines should be KlineEvent instances if present
    for kline in result["klines"]:
        assert isinstance(kline, KlineEvent)

    # Orderbook should be OrderbookUpdate or None
    if result["orderbook"] is not None:
        assert isinstance(result["orderbook"], OrderbookUpdate)

