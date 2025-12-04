"""Test risk management logic."""
import pytest
from datetime import datetime
from app.nodes.risk_manager import risk_management_node, RiskState
from app.schemas.models import Signal, PortfolioState, RiskLimits, MarketFeatures, Position
from app.config import settings

@pytest.mark.asyncio
async def test_volatility_sizing():
    """Test volatility-based position sizing."""
    # Setup
    settings.risk_per_trade_percent = 0.01  # 1% risk
    settings.atr_stop_multiplier = 2.0
    
    # Portfolio: $10,000 equity
    portfolio = PortfolioState(
        balance=10000.0,
        equity=10000.0,
        positions=[],
        open_orders=[],
        timestamp=datetime.now()
    )
    
    # Signal: LONG at $100
    signal = Signal(
        timestamp=datetime.now(),
        symbol="BTC/USD",
        strategy="test",
        direction="LONG",
        strength=1.0,
        confidence=1.0,
        entry_price=100.0
    )
    
    # Features: ATR = 2.0
    features = MarketFeatures(
        timestamp=datetime.now(),
        symbol="BTC/USD",
        price=100.0,
        atr=2.0
    )
    
    # Risk Limits: Volatility sizing
    risk_limits = RiskLimits(
        max_position_size=100.0, # Large enough not to cap (need > 25.0)
        position_sizing_method="VOLATILITY"
    )
    
    state: RiskState = {
        "signal": signal,
        "features": features,
        "portfolio": portfolio,
        "approved_orders": [],
        "risk_limits": risk_limits,
        "symbol": "BTC/USD",
        "timestamp": datetime.now()
    }
    
    # Execution
    result = await risk_management_node(state)
    orders = result["approved_orders"]
    
    assert len(orders) == 1
    order = orders[0]
    
    # Calculation:
    # Risk Amount = 10000 * 0.01 = 100
    # Stop Distance = ATR * Multiplier = 2.0 * 2.0 = 4.0
    # Position Size = 100 / 4.0 = 25.0 units
    
    assert order.quantity == 25.0
    assert order.stop_price == 100.0 - 4.0  # 96.0

@pytest.mark.asyncio
async def test_atr_stop_loss_short():
    """Test ATR stop loss for SHORT positions."""
    # Setup
    settings.atr_stop_multiplier = 2.0
    settings.allow_shorting = True
    
    portfolio = PortfolioState(
        balance=10000.0,
        equity=10000.0,
        positions=[],
        open_orders=[],
        timestamp=datetime.now()
    )
    
    signal = Signal(
        timestamp=datetime.now(),
        symbol="BTC/USD",
        strategy="test",
        direction="SHORT",
        strength=1.0,
        confidence=1.0,
        entry_price=100.0
    )
    
    features = MarketFeatures(
        timestamp=datetime.now(),
        symbol="BTC/USD",
        price=100.0,
        atr=2.0
    )
    
    risk_limits = RiskLimits(
        max_position_size=1.0,
        position_sizing_method="VOLATILITY"
    )
    
    state: RiskState = {
        "signal": signal,
        "features": features,
        "portfolio": portfolio,
        "approved_orders": [],
        "risk_limits": risk_limits,
        "symbol": "BTC/USD",
        "timestamp": datetime.now()
    }
    
    result = await risk_management_node(state)
    order = result["approved_orders"][0]
    
    # Stop Price for SHORT = Entry + (ATR * Multiplier)
    # 100 + (2.0 * 2.0) = 104.0
    assert order.stop_price == 104.0

@pytest.mark.asyncio
async def test_fallback_sizing():
    """Test fallback to fixed sizing when ATR is missing."""
    portfolio = PortfolioState(
        balance=10000.0,
        equity=10000.0,
        positions=[],
        open_orders=[],
        timestamp=datetime.now()
    )
    
    signal = Signal(
        timestamp=datetime.now(),
        symbol="BTC/USD",
        strategy="test",
        direction="LONG",
        strength=1.0,
        confidence=1.0,
        entry_price=100.0
    )
    
    # No ATR
    features = MarketFeatures(
        timestamp=datetime.now(),
        symbol="BTC/USD",
        price=100.0,
        atr=None
    )
    
    risk_limits = RiskLimits(
        max_position_size=0.5,
        position_sizing_method="VOLATILITY"
    )
    
    state: RiskState = {
        "signal": signal,
        "features": features,
        "portfolio": portfolio,
        "approved_orders": [],
        "risk_limits": risk_limits,
        "symbol": "BTC/USD",
        "timestamp": datetime.now()
    }
    
    result = await risk_management_node(state)
    order = result["approved_orders"][0]
    
    # Should fallback to fixed size (min(max_pos, 0.01))
    # max_pos = 0.5, default fixed = 0.01 -> 0.01
    assert order.quantity == 0.01
    assert order.stop_price is None
