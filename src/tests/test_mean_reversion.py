"""Test mean reversion strategy logic."""
import pytest
from datetime import datetime
from app.nodes.mean_reversion_policy import mean_reversion_strategy_node, MeanReversionState
from app.schemas.models import MarketFeatures, Signal
from app.config import settings

@pytest.mark.asyncio
async def test_mean_reversion_long_signal():
    """Test that strategy generates LONG signal when oversold."""
    # Setup state with oversold conditions
    # Price < Lower Band AND RSI < Oversold (30)
    features = MarketFeatures(
        timestamp=datetime.now(),
        symbol="BTC/USD",
        price=95.0,
        rsi=25.0,  # Oversold
        bollinger_upper=110.0,
        bollinger_mid=100.0,
        bollinger_lower=98.0,  # Price is below lower band
        ema_9=100.0,
        ema_50=100.0
    )
    
    state: MeanReversionState = {
        "features": features,
        "signal": None,
        "symbol": "BTC/USD",
        "timestamp": datetime.now()
    }
    
    result = await mean_reversion_strategy_node(state)
    signal = result["signal"]
    
    assert signal is not None
    assert signal.direction == "LONG"
    assert signal.strategy == "mean_reversion"
    assert signal.confidence == 0.8
    assert "Oversold" in signal.reasoning

@pytest.mark.asyncio
async def test_mean_reversion_short_signal():
    """Test that strategy generates SHORT signal when overbought."""
    # Setup state with overbought conditions
    # Price > Upper Band AND RSI > Overbought (70)
    features = MarketFeatures(
        timestamp=datetime.now(),
        symbol="BTC/USD",
        price=115.0,
        rsi=75.0,  # Overbought
        bollinger_upper=110.0,  # Price is above upper band
        bollinger_mid=100.0,
        bollinger_lower=90.0,
        ema_9=100.0,
        ema_50=100.0
    )
    
    state: MeanReversionState = {
        "features": features,
        "signal": None,
        "symbol": "BTC/USD",
        "timestamp": datetime.now()
    }
    
    result = await mean_reversion_strategy_node(state)
    signal = result["signal"]
    
    assert signal is not None
    assert signal.direction == "SHORT"
    assert signal.strategy == "mean_reversion"
    assert signal.confidence == 0.8
    assert "Overbought" in signal.reasoning

@pytest.mark.asyncio
async def test_mean_reversion_neutral_signal():
    """Test that strategy generates NEUTRAL signal when in range."""
    features = MarketFeatures(
        timestamp=datetime.now(),
        symbol="BTC/USD",
        price=100.0,
        rsi=50.0,  # Neutral
        bollinger_upper=110.0,
        bollinger_mid=100.0,
        bollinger_lower=90.0,
        ema_9=100.0,
        ema_50=100.0
    )
    
    state: MeanReversionState = {
        "features": features,
        "signal": None,
        "symbol": "BTC/USD",
        "timestamp": datetime.now()
    }
    
    result = await mean_reversion_strategy_node(state)
    signal = result["signal"]
    
    assert signal is not None
    assert signal.direction == "NEUTRAL"
    assert signal.strategy == "mean_reversion"
    assert "In range" in signal.reasoning
