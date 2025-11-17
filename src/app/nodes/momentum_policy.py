"""Momentum trading strategy implementation."""
from typing import TypedDict
from datetime import datetime

from app.schemas.models import MarketFeatures, Signal
from app.config import settings


class MomentumState(TypedDict):
    """State for momentum strategy."""
    features: MarketFeatures | None
    signal: Signal | None
    symbol: str
    timestamp: datetime


async def momentum_strategy_node(state: MomentumState) -> MomentumState:
    """
    Generate momentum-based trading signals.

    Strategy:
    - Long when EMA(9) > EMA(50) and price > EMA(9)
    - Short when EMA(9) < EMA(50) and price < EMA(9)
    - Signal strength based on EMA separation
    """
    features = state.get("features")
    symbol = state.get("symbol", settings.symbol)

    if not features or not features.ema_9 or not features.ema_50:
        # Insufficient data for momentum strategy
        return {
            **state,
            "signal": Signal(
                timestamp=datetime.now(),
                symbol=symbol,
                strategy="momentum",
                direction="NEUTRAL",
                strength=0.0,
                confidence=0.0,
                reasoning="Insufficient feature data"
            )
        }

    price = features.price
    ema_9 = features.ema_9
    ema_50 = features.ema_50

    # Calculate trend strength
    ema_diff_pct = (ema_9 - ema_50) / ema_50 * 100
    price_vs_ema9_pct = (price - ema_9) / ema_9 * 100

    # Determine direction
    direction: str = "NEUTRAL"
    strength = 0.0
    confidence = 0.0
    reasoning = ""

    # Long condition: EMA(9) > EMA(50) and price > EMA(9)
    if ema_9 > ema_50 and price > ema_9:
        direction = "LONG"
        strength = min(abs(ema_diff_pct) / 2.0, 1.0)  # Cap at 1.0
        confidence = min(abs(price_vs_ema9_pct) / 1.0 + 0.5, 0.95)
        reasoning = f"Uptrend: EMA9 {ema_diff_pct:.2f}% above EMA50, price above EMA9"

        # Calculate stop loss and take profit
        stop_loss = ema_9 * 0.98  # 2% below EMA9
        take_profit = price * 1.03  # 3% profit target

    # Short condition: EMA(9) < EMA(50) and price < EMA(9)
    elif ema_9 < ema_50 and price < ema_9:
        direction = "SHORT"
        strength = min(abs(ema_diff_pct) / 2.0, 1.0)
        confidence = min(abs(price_vs_ema9_pct) / 1.0 + 0.5, 0.95)
        reasoning = f"Downtrend: EMA9 {abs(ema_diff_pct):.2f}% below EMA50, price below EMA9"

        stop_loss = ema_9 * 1.02  # 2% above EMA9
        take_profit = price * 0.97  # 3% profit target

    else:
        # No clear momentum signal
        direction = "NEUTRAL"
        strength = 0.3
        confidence = 0.4
        reasoning = "No clear momentum signal"
        stop_loss = None
        take_profit = None

    # Adjust confidence based on volatility
    if features.atr and features.atr > 0:
        # Lower confidence in high volatility
        atr_pct = features.atr / price * 100
        if atr_pct > 3.0:  # High volatility
            confidence *= 0.8

    signal = Signal(
        timestamp=datetime.now(),
        symbol=symbol,
        strategy="momentum",
        direction=direction,  # type: ignore
        strength=strength,
        confidence=confidence,
        entry_price=price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        reasoning=reasoning
    )

    return {
        **state,
        "signal": signal
    }

