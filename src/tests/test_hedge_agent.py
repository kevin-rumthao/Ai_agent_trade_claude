"""Test Hedge Agent logic."""
import pytest
from datetime import datetime
from app.nodes.hedge_agent import hedge_agent_node, HedgeAgentState
from app.nodes.risk_manager import risk_management_node, RiskState
from app.schemas.models import Signal, PortfolioState, Position, RiskLimits, MarketFeatures

def test_hedge_agent_logic():
    import asyncio
    asyncio.run(_test_hedge_agent_logic_async())

async def _test_hedge_agent_logic_async():
    # 1. Setup State with Long Spot Position
    portfolio = PortfolioState(
        balance=10000.0,
        equity=10000.0,
        positions=[
            Position(
                symbol="BTC/USD",
                instrument_type="SPOT",
                side="LONG",
                quantity=1.0,
                entry_price=50000.0,
                current_price=50000.0,
                unrealized_pnl=0.0,
                timestamp=datetime.now()
            )
        ],
        open_orders=[],
        timestamp=datetime.now()
    )
    
    state: HedgeAgentState = {
        "signals": [],
        "portfolio": portfolio,
        "symbol": "BTC/USD",
        "timestamp": datetime.now()
    }
    
    # 2. Run Hedge Agent
    new_state = hedge_agent_node(state)
    
    # 3. Verify Signal Generation
    assert len(new_state["signals"]) == 1
    signal = new_state["signals"][0]
    assert signal.strategy == "hedge"
    assert signal.instrument_type == "FUTURE"
    assert signal.direction == "SHORT"
    assert signal.suggested_quantity == 1.0
    
    # 4. Run Risk Manager with this signal
    risk_limits = RiskLimits(
        max_position_size=2.0, # Allow 2.0 to accommodate hedge
        max_drawdown_percent=10.0,
        max_daily_loss=1000.0
    )
    
    risk_state: RiskState = {
        "signals": new_state["signals"],
        "features": MarketFeatures(
            timestamp=datetime.now(),
            symbol="BTC/USD",
            price=50000.0,
            atr=100.0
        ),
        "portfolio": portfolio,
        "approved_orders": [],
        "risk_limits": risk_limits,
        "symbol": "BTC/USD",
        "timestamp": datetime.now()
    }
    
    # Mock settings.allow_shorting if needed, but RiskManager checks it.
    # Assuming settings.allow_shorting is False by default for SPOT, but maybe we need to mock it for FUTURE?
    # The code I wrote:
    # is_short_restricted = signal.direction == "SHORT" and not settings.allow_shorting and signal.instrument_type == "SPOT"
    # So FUTURE shorting should be allowed even if allow_shorting is False (which usually applies to Spot).
    
    final_state = await risk_management_node(risk_state)
    
    # 5. Verify Approved Order
    assert len(final_state["approved_orders"]) == 1
    order = final_state["approved_orders"][0]
    assert order.symbol == "BTC/USD"
    assert order.instrument_type == "FUTURE"
    assert order.side == "SELL"
    assert order.quantity == 1.0
