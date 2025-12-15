"""Risk management node."""
from typing import TypedDict
from datetime import datetime

from app.schemas.models import Signal, Order, RiskLimits, PortfolioState, MarketFeatures
from app.tools.trading_provider import trading_provider
from app.config import settings


class RiskState(TypedDict):
    """State for risk management."""
    signals: list[Signal]
    features: MarketFeatures | None
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
    signals = state.get("signals", [])
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

    # If no signals, check if we should close positions (if strategy was neutral)
    # But now we have a list. If list is empty or all neutral?
    # For now, if any signal is valid, we process it.
    
    # Check daily loss limit first (global check)
    if portfolio.daily_pnl < -risk_limits.max_daily_loss:
        print(f"Daily loss limit reached: {portfolio.daily_pnl:.2f}")
        return {
            **state,
            "approved_orders": [],
            "risk_limits": risk_limits,
            "portfolio": portfolio
        }

    features = state.get("features")
    atr = features.atr if features else None
    vol_forecast = features.volatility_forecast if features else None

    for signal in signals:
        if signal.direction == "NEUTRAL":
            continue

        # Check signal confidence threshold
        if signal.confidence < 0.5:
            print(f"Signal confidence {signal.confidence:.2f} below threshold 0.5")
            continue

        # Enforce long-only behavior on spot providers when shorting is disabled
        # TODO: Check instrument_type. If FUTURE, shorting might be allowed even if settings.allow_shorting is False for Spot?
        # For now, assume settings.allow_shorting applies globally or check signal.instrument_type
        
        is_short_restricted = signal.direction == "SHORT" and not settings.allow_shorting and signal.instrument_type == "SPOT"
        
        if is_short_restricted:
            # Determine existing long position size (if any) for this symbol
            long_qty = 0.0
            for position in portfolio.positions:
                if position.symbol == symbol and position.side == "LONG" and position.instrument_type == "SPOT":
                    long_qty += position.quantity

            if long_qty <= 0:
                print("Shorting disabled; no existing long position to close. Suppressing SHORT order.")
                continue
            
            # Allow only closing/reducing existing long up to current quantity
            close_qty = min(long_qty, risk_limits.max_position_size)
            if close_qty <= 0:
                continue

            close_order = Order(
                symbol=symbol,
                instrument_type=signal.instrument_type,
                side="SELL",
                order_type="MARKET",
                quantity=close_qty,
            )
            approved_orders.append(close_order)
            continue

        # Check if we already have a position in the signal direction
        has_position = False
        for position in portfolio.positions:
            if position.symbol == symbol and position.instrument_type == signal.instrument_type:
                if (position.side == "LONG" and signal.direction == "LONG") or \
                   (position.side == "SHORT" and signal.direction == "SHORT"):
                    has_position = True
                    print(f"Already have {position.side} position for {signal.instrument_type}")
                    break

        if has_position:
            continue

        # Calculate position size based on risk
        position_size = _calculate_position_size(
            signal=signal,
            portfolio=portfolio,
            risk_limits=risk_limits,
            atr=atr,
            vol_forecast=vol_forecast,
            current_price=signal.entry_price or 0.0
        )

        if position_size <= 0:
            print(f"Position size calculated as zero or negative for {signal.instrument_type}")
            continue

        # Calculate Stop Loss price if ATR is available
        stop_price = None
        if atr:
            if signal.direction == "LONG":
                stop_price = (signal.entry_price or 0.0) - (atr * settings.atr_stop_multiplier)
            elif signal.direction == "SHORT":
                stop_price = (signal.entry_price or 0.0) + (atr * settings.atr_stop_multiplier)

        # Create entry order
        entry_order = Order(
            symbol=symbol,
            instrument_type=signal.instrument_type,
            side="BUY" if signal.direction == "LONG" else "SELL",
            order_type="MARKET",
            quantity=position_size,
            stop_price=stop_price
        )
        approved_orders.append(entry_order)

    return {
        **state,
        "approved_orders": approved_orders,
        "risk_limits": risk_limits,
        "portfolio": portfolio
    }


def _calculate_position_size(
    signal: Signal,
    portfolio: PortfolioState,
    risk_limits: RiskLimits,
    atr: float | None = None,
    vol_forecast: float | None = None,
    current_price: float = 0.0
) -> float:
    """
    Calculate appropriate position size based on risk parameters.
    
    Supports:
    - FIXED: Fixed size (e.g. 0.01 BTC)
    - VOLATILITY: Risk % of equity / (ATR * Multiplier)
    """
    # If signal has a suggested quantity (e.g. from Hedge Agent), use it but validate against limits
    if signal.suggested_quantity is not None and signal.suggested_quantity > 0:
        return min(signal.suggested_quantity, risk_limits.max_position_size)

    if risk_limits.position_sizing_method == "FIXED":
        # Simple fixed size, respecting max position size
        return min(risk_limits.max_position_size, 0.01)  # 0.01 BTC default

    elif risk_limits.position_sizing_method == "VOLATILITY":
        if atr is None or atr <= 0 or current_price <= 0:
            # Fallback to fixed if ATR missing
            print("ATR missing for volatility sizing, falling back to fixed")
            return min(risk_limits.max_position_size, 0.01)
            
        # Risk Amount = Equity * Risk%
        risk_amount = portfolio.equity * settings.risk_per_trade_percent
        
        # Stop Distance = ATR * Multiplier
        stop_distance = atr * settings.atr_stop_multiplier
        
        # Position Size (Units) = Risk Amount / Stop Distance
        # This assumes we lose 'Stop Distance' per unit if stopped out
        if stop_distance == 0:
            return 0.0
            
        position_size = risk_amount / stop_distance
        
        # Cap at max position size
        position_size = min(position_size, risk_limits.max_position_size)
        
        # Also cap at max leverage (e.g. 1x equity / price)
        max_qty_by_leverage = (portfolio.equity * risk_limits.max_leverage) / current_price
        position_size = min(position_size, max_qty_by_leverage)
        
        return position_size

    elif risk_limits.position_sizing_method == "VOL_TARGET":
        # Volatility Targeting: Size = (TargetVol / ForecastVol) * Equity
        # TargetVol is annualized, ForecastVol is usually daily or annualized.
        # Ensure units match.
        
        if vol_forecast is None or vol_forecast <= 0:
            print("Volatility forecast missing for VOL_TARGET, falling back to FIXED")
            return min(risk_limits.max_position_size, 0.01)

        # Assuming vol_forecast is Daily Volatility (from GARCH on daily/minute returns scaled)
        # We need to check the scale of vol_forecast from `statistics.py`. 
        # Usually GARCH on returns gives Variance/StdDev of period returns.
        
        # If Target is 20% annualized -> Daily Target ~ 0.20 / 16 = 1.25% (0.0125)
        # If Forecast is 0.02 (2% daily) -> Size = 0.0125 / 0.02 * Equity = 0.625 * Equity
        
        target_vol_daily = risk_limits.target_volatility / 16.0  # sqrt(252) approx 16
        
        # Cap leverage at max_leverage
        leverage = min(target_vol_daily / vol_forecast, risk_limits.max_leverage)
        
        position_value = portfolio.equity * leverage
        
        if current_price > 0:
            position_size = position_value / current_price
        else:
            position_size = 0.0
            
        # Cap at max size
        return min(position_size, risk_limits.max_position_size)

    else:
        return risk_limits.max_position_size

