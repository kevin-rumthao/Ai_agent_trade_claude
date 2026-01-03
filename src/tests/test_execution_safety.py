
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from app.nodes.execution_agent import smart_execute_order, ExecutionResult, Order
from app.config import settings

@pytest.mark.asyncio
async def test_watchdog_triggers_on_late_fill():
    """
    Verify that if a LIMIT order fills during the wait loop (but not immediately),
    the Watchdog in smart_execute_order triggers and places a Stop-Loss.
    """
    # 1. Setup Mock Provider
    mock_provider = AsyncMock()
    
    # Mock Orderbook (for smart execution price check)
    mock_provider.get_orderbook.return_value = MagicMock(
        bids=[(50000.0, 1.0)], 
        asks=[(50100.0, 1.0)]
    )

    # Mock execute_order:
    # First call (Limit Order) -> Success, OrderID="ORDER_1"
    # Second call (Stop Loss) -> We want to verify this happens!
    mock_provider.execute_order.side_effect = [
        ExecutionResult(success=True, order_id="ORDER_1", filled_quantity=0.0, status="NEW", timestamp=datetime.now()), # Limit placement
        ExecutionResult(success=True, order_id="SL_ORDER", filled_quantity=0.0, status="NEW", timestamp=datetime.now()) # SL placement
    ]

    # Mock get_order_status
    # Call 1: NEW (Wait loop 1)
    # Call 2: FILLED (Wait loop 2) -> Should trigger Watchdog
    mock_provider.get_order_status.side_effect = [
        ExecutionResult(success=True, order_id="ORDER_1", filled_quantity=0.0, status="NEW", timestamp=datetime.now()),
        ExecutionResult(success=True, order_id="ORDER_1", filled_quantity=1.0, status="FILLED", filled_price=50000.0, timestamp=datetime.now())
    ]
    
    # Mock cancel_order (should not be called if verified correctly, but safe to mock)
    mock_provider.cancel_order.return_value = ExecutionResult(success=True, status="CANCELED", timestamp=datetime.now())

    # 2. Patch dependencies
    with patch("app.nodes.execution_agent.trading_provider", mock_provider):
        with patch("app.config.settings.trading_provider", "binance"): # Force non-Alpaca to trigger Watchdog
            
            # 3. Create Order
            order = Order(
                symbol="BTCUSDT",
                side="BUY",
                quantity=1.0,
                order_type="LIMIT", # Use valid order type
                execution_style="PASSIVE", # Triggers smart_execute_order 
                stop_loss=49000.0,
                take_profit=52000.0
            )

            # 4. Run Execution
            result = await smart_execute_order(order)

            # 5. Assertions
            assert result.status == "FILLED"
            assert result.order_id == "ORDER_1"
            
            # Verify Watchdog Triggered:
            # execute_order should have been called twice: 
            # 1. The initial Limit Buy
            # 2. The Stop Loss Sell
            assert mock_provider.execute_order.call_count == 2
            
            # Check the second call (Stop Loss)
            sl_call_args = mock_provider.execute_order.call_args_list[1]
            sl_order = sl_call_args[0][0]
            
            assert sl_order.order_type == "STOP_LOSS"
            assert sl_order.stop_price == 49000.0
            assert sl_order.side == "SELL"
