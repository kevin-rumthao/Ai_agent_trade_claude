"""Tests for feature engineering node."""
import pytest
from datetime import datetime

from app.nodes.feature_engineering import (
    compute_features_node,
    FeatureState,
    feature_engine
)
from app.schemas.events import KlineEvent, OrderbookUpdate


@pytest.mark.asyncio
async def test_compute_features_with_klines() -> None:
    """Test feature computation with kline data."""
    # Create sample klines
    klines = [
        KlineEvent(
            timestamp=datetime.now(),
            symbol="BTCUSDT",
            interval="1m",
            open=50000.0,
            high=50100.0,
            low=49900.0,
            close=50050.0,
            volume=10.0
        )
        for _ in range(100)
    ]

    state: FeatureState = {
        "trades": [],
        "orderbook": None,
        "klines": klines,
        "features": None,
        "symbol": "BTCUSDT",
        "timestamp": datetime.now()
    }

    result = await compute_features_node(state)

    assert result["features"] is not None
    assert result["features"].price > 0
    assert result["features"].symbol == "BTCUSDT"


@pytest.mark.asyncio
async def test_compute_features_with_orderbook() -> None:
    """Test feature computation with orderbook."""
    orderbook = OrderbookUpdate(
        timestamp=datetime.now(),
        symbol="BTCUSDT",
        bids=[(50000.0, 1.0), (49950.0, 2.0)],
        asks=[(50050.0, 1.0), (50100.0, 2.0)]
    )

    state: FeatureState = {
        "trades": [],
        "orderbook": orderbook,
        "klines": [],
        "features": None,
        "symbol": "BTCUSDT",
        "timestamp": datetime.now()
    }

    result = await compute_features_node(state)

    assert result["features"] is not None
    features = result["features"]

    # Should have orderbook-derived features
    assert features.orderbook_imbalance is not None
    assert features.spread is not None


@pytest.mark.asyncio
async def test_feature_engine_ema_computation() -> None:
    """Test EMA computation."""
    from app.nodes.feature_engineering import FeatureEngine

    engine = FeatureEngine()

    # Test EMA computation
    prices = [100.0, 101.0, 102.0, 101.5, 103.0, 102.5, 104.0, 103.5, 105.0]
    result = engine.compute_ema(prices, 9)

    assert result is not None
    assert isinstance(result, float)
    assert result > 0


@pytest.mark.asyncio
async def test_features_include_all_expected_fields() -> None:
    """Test that features include all expected technical indicators."""
    # Create comprehensive sample data
    klines = [
        KlineEvent(
            timestamp=datetime.now(),
            symbol="BTCUSDT",
            interval="1m",
            open=50000.0 + i,
            high=50100.0 + i,
            low=49900.0 + i,
            close=50050.0 + i,
            volume=10.0
        )
        for i in range(100)
    ]

    orderbook = OrderbookUpdate(
        timestamp=datetime.now(),
        symbol="BTCUSDT",
        bids=[(50000.0, 1.0)],
        asks=[(50050.0, 1.0)]
    )

    state: FeatureState = {
        "trades": [],
        "orderbook": orderbook,
        "klines": klines,
        "features": None,
        "symbol": "BTCUSDT",
        "timestamp": datetime.now()
    }

    result = await compute_features_node(state)

    assert result["features"] is not None
    features = result["features"]

    # Check that all expected features are present
    assert hasattr(features, 'price')
    assert hasattr(features, 'ema_9')
    assert hasattr(features, 'ema_50')
    assert hasattr(features, 'atr')
    assert hasattr(features, 'realized_volatility')
    assert hasattr(features, 'orderbook_imbalance')
    assert hasattr(features, 'spread')

