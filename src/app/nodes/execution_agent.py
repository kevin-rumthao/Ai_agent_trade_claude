"""Execution agent node for order execution."""
from typing import TypedDict
from datetime import datetime

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
    Execute approved orders on the exchange.

    For each approved order:
    1. Submit to exchange
    2. Record execution result
    3. Handle errors gracefully
    """
    approved_orders = state.get("approved_orders", [])
    execution_results: list[ExecutionResult] = []

    if not approved_orders:
        print("No approved orders to execute")
        return {
            **state,
            "execution_results": []
        }

    for order in approved_orders:
        try:
            print(f"Executing order: {order.side} {order.quantity} {order.symbol}")

            # Execute order through trading provider
            result = await trading_provider.execute_order(order)
            execution_results.append(result)

            if result.success:
                print(f"Order executed successfully: {result.order_id}")
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

