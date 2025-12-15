"""Execution agent node for order execution."""
from typing import TypedDict
from datetime import datetime
import asyncio

from app.schemas.models import Order, ExecutionResult
from app.tools.trading_provider import trading_provider


class ExecutionState(TypedDict):
    """State for order execution."""
    approved_orders: list[Order]
    execution_results: list[ExecutionResult]
    symbol: str
    timestamp: datetime


async def execution_agent_node(state: ExecutionState) -> ExecutionState:
    """
    Execute approved orders on the exchange using Smart Execution.

    Smart Execution Logic:
    1. Try to place LIMIT order at Best Bid/Ask.
    2. Wait for a few seconds.
    3. If not filled, cancel and chase with MARKET order.
    """
    import asyncio
    
    approved_orders = state.get("approved_orders", [])
    execution_results: list[ExecutionResult] = []

    if not approved_orders:
        # print("No approved orders to execute")
        return {
            **state,
            "execution_results": []
        }

    for order in approved_orders:
        try:
            print(f"Executing order: {order.side} {order.quantity} {order.symbol}")
            
            # Smart Execution logic
            if order.execution_style == "PASSIVE":
                result = await smart_execute_order(order)
            else:
                # Default to simple execution (Market/Limit as specified)
                # If Market, it's Aggressive Taker
                result = await trading_provider.execute_order(order)
                
            execution_results.append(result)

            if result.success:
                print(f"Order executed successfully: {result.order_id} @ {result.filled_price}")
            else:
                print(f"Order execution failed: {result.error_message}")

        except Exception as e:
            # Create failed execution result
            error_result = ExecutionResult(
                success=False,
                status="ERROR",
                error_message=str(e),
                timestamp=datetime.now()
            )
            execution_results.append(error_result)
            print(f"Exception during order execution: {e}")

    return {
        **state,
        "execution_results": execution_results,
        "timestamp": datetime.now()
    }


async def smart_execute_order(order: Order) -> ExecutionResult:
    """
    Execute an order with smart routing (Limit -> Chase).
    """
    # 1. Get current Orderbook to find Best Bid/Ask
    try:
        ob = await trading_provider.get_orderbook(order.symbol, limit=5)
    except Exception as e:
        print(f"Failed to get orderbook for smart execution: {e}. Falling back to MARKET.")
        # Fallback to Market
        order.order_type = "MARKET"
        return await trading_provider.execute_order(order)

    # Determine Limit Price
    price = 0.0
    if order.side == "BUY":
        # Buy at Best Bid (Maker) or slightly higher?
        # To be a Maker, we should be at Best Bid.
        # If we want immediate fill but better than Market, we might match Best Ask?
        # Let's try to be a Maker at Best Bid first.
        if ob.bids:
            price = ob.bids[0][0]
        else:
            # Fallback
            order.order_type = "MARKET"
            return await trading_provider.execute_order(order)
    else:
        # Sell at Best Ask (Maker)
        if ob.asks:
            price = ob.asks[0][0]
        else:
            # Fallback
            order.order_type = "MARKET"
            return await trading_provider.execute_order(order)

    # Place LIMIT Order
    limit_order = Order(
        symbol=order.symbol,
        side=order.side,
        order_type="LIMIT",
        quantity=order.quantity,
        price=price,
        time_in_force="GTC",
        instrument_type=order.instrument_type
    )
    
    print(f"Placing LIMIT {order.side} @ {price}")
    result = await trading_provider.execute_order(limit_order)
    
    if not result.success:
        print(f"Limit order placement failed: {result.error_message}. Retrying with MARKET.")
        order.order_type = "MARKET"
        return await trading_provider.execute_order(order)
        
    order_id = result.order_id
    if not order_id:
         print("No order ID returned. Assuming failed.")
         return result

    # 2. Wait for Fill (e.g., 5 seconds)
    # We could poll status
    for _ in range(5):
        await asyncio.sleep(1.0)
        status = await trading_provider.get_order_status(order_id, order.symbol)
        
        if status.status == "FILLED":
            return status
        if status.status == "CANCELED" or status.status == "REJECTED":
            print("Limit order canceled/rejected. Retrying with MARKET.")
            break
            
    # 3. If not filled, Cancel and Chase
    print(f"Limit order {order_id} not filled after 5s. Canceling and Chasing...")
    try:
        await trading_provider.cancel_order(order_id, order.symbol)
    except Exception as e:
        print(f"Failed to cancel order {order_id}: {e}. It might be filled already.")
        # Check status one last time
        status = await trading_provider.get_order_status(order_id, order.symbol)
        if status.status == "FILLED":
            return status
            
    # Place MARKET Order (Chase)
    print("Placing MARKET Chase order...")
    market_order = Order(
        symbol=order.symbol,
        side=order.side,
        order_type="MARKET",
        quantity=order.quantity,
        instrument_type=order.instrument_type
    )
    return await trading_provider.execute_order(market_order)


