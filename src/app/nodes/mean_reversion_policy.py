"""Mean Reversion trading strategy implementation."""
from typing import TypedDict
from datetime import datetime

from app.schemas.models import MarketFeatures, Signal
from app.config import settings


class MeanReversionState(TypedDict):
    """State for mean reversion strategy."""
    features: MarketFeatures | None
    signal: Signal | None
    symbol: str
    timestamp: datetime


async def mean_reversion_strategy_node(state: MeanReversionState) -> MeanReversionState:
    """
    Generate mean reversion trading signals.

    Strategy:
    - Long when Price < Lower Bollinger Band AND RSI < Oversold
    - Short when Price > Upper Bollinger Band AND RSI > Overbought
    """
    features = state.get("features")
    symbol = state.get("symbol", settings.symbol)

    if not features or features.rsi is None or features.bollinger_upper is None:
        # Insufficient data
        return {
            **state,
            "signal": Signal(
                timestamp=datetime.now(),
                symbol=symbol,
                strategy="mean_reversion",
                direction="NEUTRAL",
                strength=0.0,
                confidence=0.0,
                reasoning="Insufficient feature data (RSI/BB missing)"
            )
        }

    price = features.price
    rsi = features.rsi
    bb_upper = features.bollinger_upper
    bb_lower = features.bollinger_lower
    bb_mid = features.bollinger_mid

    # Determine direction
    direction: str = "NEUTRAL"
    strength = 0.0
    confidence = 0.0
    reasoning = ""
    stop_loss = None
    take_profit = None

    # Long Condition: Oversold
    if price < bb_lower and rsi < settings.rsi_oversold:
        direction = "LONG"
        # Strength increases as RSI goes lower
        strength = min((settings.rsi_oversold - rsi) / 10.0, 1.0)
        confidence = 0.8
        reasoning = f"Oversold: Price {price:.2f} < BB Lower {bb_lower:.2f}, RSI {rsi:.2f} < {settings.rsi_oversold}"
        
        # Target: Mean reversion to mid band
        take_profit = bb_mid
        # Stop: 2% below current price (or could use ATR)
        stop_loss = price * 0.98

    # Short Condition: Overbought
    elif price > bb_upper and rsi > settings.rsi_overbought:
        direction = "SHORT"
        # Strength increases as RSI goes higher
        strength = min((rsi - settings.rsi_overbought) / 10.0, 1.0)
        confidence = 0.8
        reasoning = f"Overbought: Price {price:.2f} > BB Upper {bb_upper:.2f}, RSI {rsi:.2f} > {settings.rsi_overbought}"
        
        # Target: Mean reversion to mid band
        take_profit = bb_mid
        # Stop: 2% above current price
        stop_loss = price * 1.02

    else:
        # Neutral
        direction = "NEUTRAL"
        strength = 0.0
        confidence = 0.5
        reasoning = f"In range: RSI {rsi:.2f}, Price within bands"

    signal = Signal(
        timestamp=datetime.now(),
        symbol=symbol,
        strategy="mean_reversion",
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
