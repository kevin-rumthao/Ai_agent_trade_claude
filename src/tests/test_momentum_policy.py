"""Tests for momentum strategy."""
import pytest
from datetime import datetime

from app.nodes.momentum_policy import momentum_strategy_node, MomentumState
from app.schemas.models import MarketFeatures


@pytest.mark.asyncio
async def test_momentum_long_signal() -> None:
    """Test momentum strategy generates LONG signal when EMA(9) > EMA(50) and price > EMA(9)."""
    features = MarketFeatures(
        timestamp=datetime.now(),
        symbol="BTCUSDT",
        price=51000.0,
        ema_9=50500.0,
        ema_50=50000.0,
        atr=100.0,
        realized_volatility=0.02
    )

    state: MomentumState = {
        "features": features,
        "signal": None,
        "symbol": "BTCUSDT",
        "timestamp": datetime.now()
    }

    result = await momentum_strategy_node(state)

    assert result["signal"] is not None
    signal = result["signal"]

    assert signal.direction == "LONG"
    assert signal.strength > 0
    assert signal.confidence > 0
    assert signal.strategy == "momentum"


@pytest.mark.asyncio
async def test_momentum_short_signal() -> None:
    """Test momentum strategy generates SHORT signal when EMA(9) < EMA(50) and price < EMA(9)."""
    features = MarketFeatures(
        timestamp=datetime.now(),
        symbol="BTCUSDT",
        price=49000.0,
        ema_9=49500.0,
        ema_50=50000.0,
        atr=100.0,
        realized_volatility=0.02
    )

    state: MomentumState = {
        "features": features,
        "signal": None,
        "symbol": "BTCUSDT",
        "timestamp": datetime.now()
    }

    result = await momentum_strategy_node(state)

    assert result["signal"] is not None
    signal = result["signal"]

    assert signal.direction == "SHORT"
    assert signal.strength > 0
    assert signal.confidence > 0


@pytest.mark.asyncio
async def test_momentum_neutral_signal() -> None:
    """Test momentum strategy generates NEUTRAL signal when conditions are unclear."""
    features = MarketFeatures(
        timestamp=datetime.now(),
        symbol="BTCUSDT",
        price=50000.0,
        ema_9=50100.0,  # EMA(9) > EMA(50)
        ema_50=50000.0,
        atr=100.0
    )
    # But price < EMA(9), so mixed signals
    features.price = 50050.0  # Between EMAs

    state: MomentumState = {
        "features": features,
        "signal": None,
        "symbol": "BTCUSDT",
        "timestamp": datetime.now()
    }

    result = await momentum_strategy_node(state)

    assert result["signal"] is not None
    signal = result["signal"]

    # Should be neutral or have low confidence
    assert signal.direction == "NEUTRAL" or signal.confidence < 0.5


@pytest.mark.asyncio
async def test_momentum_insufficient_features() -> None:
    """Test momentum strategy handles missing features gracefully."""
    features = MarketFeatures(
        timestamp=datetime.now(),
        symbol="BTCUSDT",
        price=50000.0,
        ema_9=None,  # Missing
        ema_50=None   # Missing
    )

    state: MomentumState = {
        "features": features,
        "signal": None,
        "symbol": "BTCUSDT",
        "timestamp": datetime.now()
    }

    result = await momentum_strategy_node(state)

    assert result["signal"] is not None
    signal = result["signal"]

    assert signal.direction == "NEUTRAL"
    assert signal.confidence == 0.0


@pytest.mark.asyncio
async def test_momentum_signal_includes_risk_params() -> None:
    """Test that momentum signals include stop loss and take profit levels."""
    features = MarketFeatures(
        timestamp=datetime.now(),
        symbol="BTCUSDT",
        price=51000.0,
        ema_9=50500.0,
        ema_50=50000.0,
        atr=100.0
    )

    state: MomentumState = {
        "features": features,
        "signal": None,
        "symbol": "BTCUSDT",
        "timestamp": datetime.now()
    }

    result = await momentum_strategy_node(state)

    assert result["signal"] is not None
    signal = result["signal"]

    if signal.direction != "NEUTRAL":
        # Should have stop loss and take profit
        assert signal.stop_loss is not None
        assert signal.take_profit is not None
        assert signal.entry_price is not None

