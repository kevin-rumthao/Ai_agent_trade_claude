"""Test mean reversion strategy logic."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from app.nodes.mean_reversion_policy import mean_reversion_strategy_node, MeanReversionState
from app.schemas.models import MarketFeatures, Signal
from app.schemas.events import KlineEvent
from app.config import settings

@pytest.mark.asyncio
async def test_mean_reversion_long_signal_confirmed():
    """Test that strategy generates LONG signal when oversold AND confirmed."""
    # Setup:
    # 1. Previous Candle: Close < Lower Band (Oversold)
    # 2. Current Candle: Close > Lower Band (Confirmation)
    # 3. RSI < Oversold
    
    klines = []
    # Fill history
    for i in range(30):
        klines.append(KlineEvent(
            timestamp=datetime.now(),
            symbol="BTC/USD",
            open=100.0, high=100.0, low=100.0, close=100.0, volume=1.0,
            interval="1m"
        ))
        
    # Previous candle (index -2): Close at 95 (Below Prev Lower Band of 98)
    klines[-2].close = 95.0
    
    # Current features
    features = MarketFeatures(
        timestamp=datetime.now(),
        symbol="BTC/USD",
        price=99.0, # Current Price > Current Lower Band (98)
        rsi=25.0,  # Oversold
        bollinger_upper=102.0,
        bollinger_mid=100.0,
        bollinger_lower=98.0,  # Current Lower Band
        ema_9=100.0,
        ema_50=100.0,
        atr=1.0,
        realized_volatility=0.01,
        adx=30.0,
        orderbook_imbalance=0.0,
        spread=0.1,
        vwap=100.0
    )
    
    state: MeanReversionState = {
        "features": features,
        "klines": klines,
        "signal": None,
        "symbol": "BTC/USD",
        "timestamp": datetime.now()
    }
    
    # Mock feature_engine.compute_bollinger_bands to return bands for the PREVIOUS window
    # We want Prev Lower Band to be 98.0, so 95.0 is "Outside"
    with patch("app.nodes.mean_reversion_policy.feature_engine") as mock_engine:
        mock_engine.compute_bollinger_bands.return_value = (102.0, 100.0, 98.0) # Upper, Mid, Lower
        
        result = await mean_reversion_strategy_node(state)
        signal = result["signals"][0]
        
        assert signal.direction == "LONG"
        assert signal.confidence >= 0.8
        assert "Mean Reversion Long" in signal.reasoning
        assert "Price closed back inside" in signal.reasoning
        assert "Oversold" not in signal.reasoning # The new logic doesn't explicitly say "Oversold" in the reasoning string I constructed, it says "RSI ..."

@pytest.mark.asyncio
async def test_mean_reversion_wait_for_confirmation():
    """Test that strategy WAITS (Neutral) when price is outside but no crossover."""
    # Setup:
    # Previous: Outside (95 < 98)
    # Current: Still Outside (90 < 98)
    
    klines = []
    for i in range(30):
        klines.append(KlineEvent(
            timestamp=datetime.now(),
            symbol="BTC/USD",
            open=100.0, high=100.0, low=100.0, close=100.0, volume=1.0,
            interval="1m"
        ))
    
    # Previous close 95
    klines[-2].close = 95.0
    
    features = MarketFeatures(
        timestamp=datetime.now(),
        symbol="BTC/USD",
        price=90.0, # Current Price still 90 (Outside)
        rsi=20.0,
        bollinger_upper=102.0,
        bollinger_mid=100.0,
        bollinger_lower=98.0, 
        ema_9=100.0,
        ema_50=100.0,
        atr=1.0,
        realized_volatility=0.01,
        adx=30.0,
        orderbook_imbalance=0.0,
        spread=0.1,
        vwap=100.0
    )
    
    state: MeanReversionState = {
        "features": features,
        "klines": klines,
        "signal": None,
        "symbol": "BTC/USD",
        "timestamp": datetime.now()
    }
    
    with patch("app.nodes.mean_reversion_policy.feature_engine") as mock_engine:
        mock_engine.compute_bollinger_bands.return_value = (102.0, 100.0, 98.0)
        
        result = await mean_reversion_strategy_node(state)
        signal = result["signals"][0]
        
        assert signal.direction == "NEUTRAL"
        assert "waiting for confirmation" in signal.reasoning

@pytest.mark.asyncio
async def test_mean_reversion_short_signal_confirmed():
    """Test that strategy generates SHORT signal when overbought AND confirmed."""
    # Setup:
    # Previous: Close > Upper Band (105 > 102)
    # Current: Close < Upper Band (101 < 102)
    
    klines = []
    for i in range(30):
        klines.append(KlineEvent(
            timestamp=datetime.now(),
            symbol="BTC/USD",
            open=100.0, high=100.0, low=100.0, close=100.0, volume=1.0,
            interval="1m"
        ))
        
    klines[-2].close = 105.0
    
    features = MarketFeatures(
        timestamp=datetime.now(),
        symbol="BTC/USD",
        price=101.0, # Returned inside
        rsi=75.0,  # Overbought
        bollinger_upper=102.0,
        bollinger_mid=100.0,
        bollinger_lower=98.0,
        ema_9=100.0,
        ema_50=100.0,
        atr=1.0,
        realized_volatility=0.01,
        adx=30.0,
        orderbook_imbalance=0.0,
        spread=0.1,
        vwap=100.0
    )
    
    state: MeanReversionState = {
        "features": features,
        "klines": klines,
        "signal": None,
        "symbol": "BTC/USD",
        "timestamp": datetime.now()
    }
    
    with patch("app.nodes.mean_reversion_policy.feature_engine") as mock_engine:
        mock_engine.compute_bollinger_bands.return_value = (102.0, 100.0, 98.0)
        
        result = await mean_reversion_strategy_node(state)
        signal = result["signals"][0]
        
        assert signal.direction == "SHORT"
        assert signal.confidence >= 0.8
        assert "Mean Reversion Short" in signal.reasoning
