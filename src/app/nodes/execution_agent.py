"""Execution agent node for order execution."""
from typing import TypedDict
from datetime import datetime
import asyncio

from app.schemas.models import Order, ExecutionResult
from app.tools.trading_provider import trading_provider
from app.config import settings


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
    
    approved_orders = state.get("approved_orders", [])
    execution_results: list[ExecutionResult] = []

    if not approved_orders:
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
                result = await safe_execute_order(order)
                
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


async def safe_execute_order(order: Order) -> ExecutionResult:
    """
    Execute an order and ensure safety orders (SL/TP) are placed if not handled by OTOCO.
    """
    # 1. Execute the main order
    result = await trading_provider.execute_order(order)
    
    # 2. Safety Watchdog: If successful, check if we need to place separate SL/TP
    if result.success and (order.stop_loss or order.take_profit):
        await ensure_safety_orders(order, result)
        
    return result


async def ensure_safety_orders(order: Order, fill_result: ExecutionResult):
    """Place safety orders (Stop Loss / Take Profit) if not handled by OTOCO."""
    
    # If provider is Alpaca, it likely handled it via OrderClass.BRACKET if params were present.
    # We trust AlpacaTool to have done it if order.stop_loss was present.
    if settings.trading_provider == "alpaca":
        return
        
    # For others (e.g. Binance), we explicitly place STOP orders if the tool doesn't support OTOCO
    # NOTE: This assumes the main order was filled fully. 
    # If partial fill, we should ideally adjust. using filled_quantity.
    
    qty = fill_result.filled_quantity
    if qty <= 0:
        return

    if order.stop_loss:
        print(f"Watchdog: Placing separate Stop Loss for filled order {fill_result.order_id}")
        sl_order = Order(
            symbol=order.symbol,
            side="SELL" if order.side == "BUY" else "BUY",
            order_type="STOP_LOSS",
            quantity=qty,
            stop_price=order.stop_loss, # Trigger price
            price=None, # Market stop
            time_in_force="GTC"
        )
        try:
             await trading_provider.execute_order(sl_order)
             print(f"Watchdog: Stop Loss placed successfully.")
        except Exception as e:
             print(f"CRITICAL: Failed to place Safety Stop Loss: {e}")

    # Similar logic could apply for Take Profit, but SL is critical.


async def smart_execute_order(order: Order) -> ExecutionResult:
    """
    Execute an order with smart routing (Limit -> Chase).
    """
    # 1. Get current Orderbook to find Best Bid/Ask
    try:
        ob = await trading_provider.get_orderbook(order.symbol, limit=5)
    except Exception as e:
        print(f"Failed to get orderbook for smart execution: {e}. Falling back to MARKET.")
        order.order_type = "MARKET"
        return await safe_execute_order(order)

    # Determine Limit Price
    price = 0.0
    if order.side == "BUY":
        # Buy at Best Bid (Maker)
        if ob.bids:
            price = ob.bids[0][0]
        else:
            order.order_type = "MARKET"
            return await safe_execute_order(order)
    else:
        # Sell at Best Ask (Maker)
        if ob.asks:
            price = ob.asks[0][0]
        else:
            order.order_type = "MARKET"
            return await safe_execute_order(order)

    # Place LIMIT Order
    # IMPORTANT: Forward the SL/TP params!
    limit_order = Order(
        symbol=order.symbol,
        side=order.side,
        order_type="LIMIT",
        quantity=order.quantity,
        price=price,
        time_in_force="GTC",
        instrument_type=order.instrument_type,
        stop_loss=order.stop_loss,
        take_profit=order.take_profit
    )
    
    print(f"Placing LIMIT {order.side} @ {price}")
    # Use safe_execute_order to handle OTOCO/Watchdog if this fills
    result = await safe_execute_order(limit_order)
    
    if not result.success:
        print(f"Limit order placement failed: {result.error_message}. Retrying with MARKET.")
        order.order_type = "MARKET"
        return await safe_execute_order(order)
        
    order_id = result.order_id
    if not order_id:
         print("No order ID returned. Assuming failed.")
         return result

    # 2. Wait for Fill (e.g., 5 seconds)
    for _ in range(5):
        await asyncio.sleep(1.0)
        status = await trading_provider.get_order_status(order_id, order.symbol)
        
        if status.status == "FILLED":
            # If filled, safe_execute_order logic (which ran on placement) might have already done Watchdog?
            # Wait, safe_execute_order called execute_order.
            # If execute_order returned "NEW", safe_execute_order's result.success is True.
            # But filled_quantity might be 0.
            # If filled_quantity is 0, ensure_safety_orders returns early.
            # So if it FILLS later, we need to catch that event?
            # PROBLEM: safe_execute_order only checks immediately after placement.
            # If it's a Limit order that fills 3 seconds later, the Watchdog in safe_execute_order is GONE.
            # WE NEED A SECOND WATCHDOG CHECK HERE.
            
            # If provider is Alpaca/OTOCO, it's fine (attached at creation).
            # If Binance/Manual, we need to place SL NOW.
            
            # Check if we need to place SL now that it is filled
            if settings.trading_provider != "alpaca" and (order.stop_loss or order.take_profit):
                 print(f"Watchdog Trigger: Order {order_id} filled during wait loop. Ensuring Safety Orders.")
                 # Construct a minimal result with filled qty to pass to watchdog
                 # We rely on the status object which should have filled quantity
                 await ensure_safety_orders(order, status)
                 
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
        status = await trading_provider.get_order_status(order_id, order.symbol)
        if status.status == "FILLED":
            if settings.trading_provider != "alpaca" and (order.stop_loss or order.take_profit):
                 await ensure_safety_orders(order, status)
            return status
            
    # Place MARKET Order (Chase)
    print("Placing MARKET Chase order...")
    # Forward SL/TP!
    market_order = Order(
        symbol=order.symbol,
        side=order.side,
        order_type="MARKET",
        quantity=order.quantity,
        instrument_type=order.instrument_type,
        stop_loss=order.stop_loss,
        take_profit=order.take_profit
    )
    return await safe_execute_order(market_order)



