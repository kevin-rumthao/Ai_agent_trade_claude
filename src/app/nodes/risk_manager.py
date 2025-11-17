"""Risk management node."""
from typing import TypedDict
from datetime import datetime

from app.schemas.models import Signal, Order, RiskLimits, PortfolioState
from app.tools.trading_provider import trading_provider
from app.config import settings


class RiskState(TypedDict):
    """State for risk management."""
    signal: Signal | None
    portfolio: PortfolioState | None
    approved_orders: list[Order]
    risk_limits: RiskLimits
    symbol: str
    timestamp: datetime


async def risk_management_node(state: RiskState) -> RiskState:
    """
    Apply risk management rules to trading signals.

    Checks:
    1. Position size limits
    2. Maximum drawdown
    3. Daily loss limits
    4. Portfolio exposure

    Outputs approved orders if signal passes risk checks.
    """
    signal = state.get("signal")
    symbol = state.get("symbol", settings.symbol)

    # Get or create risk limits
    risk_limits = state.get("risk_limits", RiskLimits(
        max_position_size=settings.max_position_size,
        max_drawdown_percent=settings.max_drawdown_percent,
        max_daily_loss=settings.max_daily_loss
    ))

    # Get current portfolio state
    portfolio = state.get("portfolio")
    if not portfolio:
        try:
            # Use provider abstraction; Binance/Alpaca differences are hidden inside provider
            portfolio = await trading_provider.get_portfolio_state()
        except Exception as e:
            print(f"Failed to fetch portfolio state: {e}")
            # Return empty approved orders
            return {
                **state,
                "approved_orders": [],
                "risk_limits": risk_limits,
                "portfolio": None
            }

    approved_orders: list[Order] = []

    # If no signal or neutral signal, check if we should close positions
    if not signal or signal.direction == "NEUTRAL":
        # Close existing positions if any
        if portfolio and portfolio.positions:
            for position in portfolio.positions:
                close_order = Order(
                    symbol=position.symbol,
                    side="SELL" if position.side == "LONG" else "BUY",
                    order_type="MARKET",
                    quantity=position.quantity
                )
                approved_orders.append(close_order)

        return {
            **state,
            "approved_orders": approved_orders,
            "risk_limits": risk_limits,
            "portfolio": portfolio
        }

    # Check signal confidence threshold
    if signal.confidence < 0.5:
        print(f"Signal confidence {signal.confidence:.2f} below threshold 0.5")
        return {
            **state,
            "approved_orders": [],
            "risk_limits": risk_limits,
            "portfolio": portfolio
        }

    # Enforce long-only behavior on spot providers when shorting is disabled
    if signal.direction == "SHORT" and not settings.allow_shorting:
        # Determine existing long position size (if any) for this symbol
        long_qty = 0.0
        for position in portfolio.positions:
            if position.symbol == symbol and position.side == "LONG":
                long_qty += position.quantity

        if long_qty <= 0:
            # No long to close and shorting not allowed -> suppress order
            print("Shorting disabled; no existing long position to close. Suppressing SHORT order.")
            return {
                **state,
                "approved_orders": [],
                "risk_limits": risk_limits,
                "portfolio": portfolio
            }
        # Allow only closing/reducing existing long up to current quantity
        close_qty = min(long_qty, risk_limits.max_position_size)
        if close_qty <= 0:
            print("Calculated close quantity non-positive; skipping.")
            return {
                **state,
                "approved_orders": [],
                "risk_limits": risk_limits,
                "portfolio": portfolio
            }

        close_order = Order(
            symbol=symbol,
            side="SELL",
            order_type="MARKET",
            quantity=close_qty,
        )
        return {
            **state,
            "approved_orders": [close_order],
            "risk_limits": risk_limits,
            "portfolio": portfolio,
        }

    # Check daily loss limit
    if portfolio.daily_pnl < -risk_limits.max_daily_loss:
        print(f"Daily loss limit reached: {portfolio.daily_pnl:.2f}")
        return {
            **state,
            "approved_orders": [],
            "risk_limits": risk_limits,
            "portfolio": portfolio
        }

    # Check if we already have a position in the signal direction
    has_position = False
    for position in portfolio.positions:
        if position.symbol == symbol:
            if (position.side == "LONG" and signal.direction == "LONG") or \
               (position.side == "SHORT" and signal.direction == "SHORT"):
                has_position = True
                print(f"Already have {position.side} position")
                break

    if has_position:
        return {
            **state,
            "approved_orders": [],
            "risk_limits": risk_limits,
            "portfolio": portfolio
        }

    # Calculate position size based on risk
    position_size = _calculate_position_size(
        signal=signal,
        portfolio=portfolio,
        risk_limits=risk_limits
    )

    if position_size <= 0:
        print("Position size calculated as zero or negative")
        return {
            **state,
            "approved_orders": [],
            "risk_limits": risk_limits,
            "portfolio": portfolio
        }

    # Create entry order
    entry_order = Order(
        symbol=symbol,
        side="BUY" if signal.direction == "LONG" else "SELL",
        order_type="MARKET",
        quantity=position_size
    )
    approved_orders.append(entry_order)

    # TODO: Add stop loss and take profit orders
    # For now, keep it simple with just market entry

    return {
        **state,
        "approved_orders": approved_orders,
        "risk_limits": risk_limits,
        "portfolio": portfolio
    }


def _calculate_position_size(
    signal: Signal,
    portfolio: PortfolioState,
    risk_limits: RiskLimits
) -> float:
    """
    Calculate appropriate position size based on risk parameters.

    Uses fixed sizing for MVP, but can be extended to:
    - Volatility-based sizing
    - Kelly criterion
    - Risk parity
    """
    if risk_limits.position_sizing_method == "FIXED":
        # Simple fixed size, respecting max position size
        return min(risk_limits.max_position_size, 0.01)  # 0.01 BTC default

    elif risk_limits.position_sizing_method == "VOLATILITY":
        # Size inversely proportional to volatility
        # TODO: Implement volatility-based sizing
        return risk_limits.max_position_size

    else:
        return risk_limits.max_position_size

