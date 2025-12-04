import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from app.schemas.models import Order, ExecutionResult
from app.schemas.events import OrderbookUpdate
from app.nodes.execution_agent import execution_agent_node, smart_execute_order

@pytest.mark.asyncio
async def test_smart_execute_fill_immediately():
    """Test that smart execution places a limit order and returns success if filled."""
    
    # Mock trading provider
    with patch("app.nodes.execution_agent.trading_provider", new_callable=AsyncMock) as mock_provider:
        # Setup Orderbook
        mock_provider.get_orderbook.return_value = OrderbookUpdate(
            timestamp=datetime.now(),
            symbol="BTCUSDT",
            bids=[(50000.0, 1.0)],
            asks=[(50100.0, 1.0)]
        )
        
        # Setup Execute Order (Limit)
        mock_provider.execute_order.return_value = ExecutionResult(
            success=True,
            order_id="limit_order_1",
            status="NEW",
            timestamp=datetime.now()
        )
        
        # Setup Get Order Status (Filled immediately)
        mock_provider.get_order_status.return_value = ExecutionResult(
            success=True,
            order_id="limit_order_1",
            status="FILLED",
            filled_price=50000.0,
            timestamp=datetime.now()
        )
        
        order = Order(
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET", # Agent should override this anyway? No, input is usually MARKET from strategy
            quantity=0.1,
            instrument_type="SPOT"
        )
        
        # Agent usually receives MARKET orders from strategy
        order.order_type = "MARKET"
        
        result = await smart_execute_order(order)
        
        assert result.success
        assert result.status == "FILLED"
        assert result.filled_price == 50000.0
        
        # Verify calls
        mock_provider.get_orderbook.assert_called_once()
        # Should execute LIMIT order at Best Bid (50000.0)
        args, _ = mock_provider.execute_order.call_args
        executed_order = args[0]
        assert executed_order.order_type == "LIMIT"
        assert executed_order.price == 50000.0

@pytest.mark.asyncio
async def test_smart_execute_timeout_and_chase():
    """Test that smart execution cancels limit order and chases with market after timeout."""
    
    with patch("app.nodes.execution_agent.trading_provider", new_callable=AsyncMock) as mock_provider:
        # Setup Orderbook
        mock_provider.get_orderbook.return_value = OrderbookUpdate(
            timestamp=datetime.now(),
            symbol="BTCUSDT",
            bids=[(50000.0, 1.0)],
            asks=[(50100.0, 1.0)]
        )
        
        # 1. Execute Limit Order -> Success (Placed)
        # 2. Execute Market Order -> Success (Filled)
        mock_provider.execute_order.side_effect = [
            ExecutionResult(success=True, order_id="limit_1", status="NEW", timestamp=datetime.now()), # Limit
            ExecutionResult(success=True, order_id="market_2", status="FILLED", filled_price=50100.0, timestamp=datetime.now()) # Market Chase
        ]
        
        # 2. Get Status -> NEW (Timeout)
        mock_provider.get_order_status.return_value = ExecutionResult(
            success=True, order_id="limit_1", status="NEW", timestamp=datetime.now()
        )
        
        # 3. Cancel Order -> Success
        mock_provider.cancel_order.return_value = ExecutionResult(
            success=True, order_id="limit_1", status="CANCELED", timestamp=datetime.now()
        )
        
        order = Order(
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            quantity=0.1,
            instrument_type="SPOT"
        )
        
        # We need to mock asyncio.sleep to avoid waiting real time
        with patch("asyncio.sleep", return_value=None):
            result = await smart_execute_order(order)
            
        assert result.success
        assert result.status == "FILLED"
        assert result.filled_price == 50100.0 # Market price
        
        # Verify sequence
        # 1. Get Orderbook
        # 2. Place Limit
        # 3. Check Status (5 times)
        # 4. Cancel
        # 5. Place Market
        
        assert mock_provider.execute_order.call_count == 2
        assert mock_provider.cancel_order.call_count == 1
