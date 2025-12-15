"""Mean Reversion trading strategy implementation."""
from typing import TypedDict
from datetime import datetime

from app.schemas.models import MarketFeatures, Signal
from app.schemas.events import KlineEvent
from app.nodes.feature_engineering import feature_engine
from app.config import settings


class MeanReversionState(TypedDict):
    """State for mean reversion strategy."""
    features: MarketFeatures | None
    klines: list[KlineEvent]
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
    ofi = features.ofi


    # Determine direction
    # Determine direction
    direction: str = "NEUTRAL"
    strength = 0.0
    confidence = 0.0
    reasoning = ""
    stop_loss = None
    take_profit = None

    klines = state.get("klines", [])
    
    # We need at least 2 candles to check confirmation
    if len(klines) < 2:
        # Insufficient history for confirmation
        pass
    else:
        prev_kline = klines[-2]
        
        # Compute previous bands
        prev_bb_lower = None
        prev_bb_upper = None
        
        if len(klines) >= settings.bollinger_period + 1:
            # Extract closes for previous window
            # Current window uses klines[-period:]
            # Previous window uses klines[-(period+1):-1]
            prev_closes = [k.close for k in klines[-(settings.bollinger_period + 1):-1]]
            
            if len(prev_closes) == settings.bollinger_period:
                res = feature_engine.compute_bollinger_bands(
                    prev_closes, 
                    settings.bollinger_period, 
                    settings.bollinger_std_dev
                )
                if res:
                    prev_bb_upper, _, prev_bb_lower = res

        # LONG SIGNAL Logic
        # 1. Previous Close < Prev Lower Band (Was Oversold)
        # 2. Current Close > Current Lower Band (Returned to Range)
        # 3. RSI is low (e.g. < 40) - allowing some recovery from < 30
        
        if prev_bb_lower is not None:
            was_below = prev_kline.close < prev_bb_lower
            is_above = price > bb_lower
            
            # Allow RSI to be slightly higher than strict oversold during the turn
            rsi_threshold_long = settings.rsi_oversold + 10 
            
            if was_below and is_above and rsi < rsi_threshold_long:
                # Phase 4 Alpha: Check OFI Confirmation
                # We need buying pressure (OFI > 0) to confirm the reversal
                if ofi is not None and ofi > 0:
                    direction = "LONG"
                    strength = 0.9 # High confidence reversal
                    confidence = 0.90
                    reasoning = (
                        f"Mean Reversion Long (Confirmed): Price returned to band with Buying Pressure "
                        f"(OFI {ofi:.2f}). RSI {rsi:.2f}"
                    )
                elif ofi is None:
                    # Fallback
                    direction = "LONG"
                    strength = 0.7
                    confidence = 0.75
                    reasoning = (
                        f"Mean Reversion Long (Unconfirmed): Price returned to band (No OFI). RSI {rsi:.2f}"
                    )
                else: 
                     # OFI < 0: Selling pressure still dominant
                     reasoning = (
                        f"Mean Reversion Long Rejected: Price returned but Selling Pressure remains (OFI {ofi:.2f})"
                     )
                     # Stay Neutral or take very small position? Stay Neutral.
                     direction = "NEUTRAL"

                take_profit = bb_mid
                stop_loss = price * 0.98  # 2% stop or use ATR

        # SHORT SIGNAL Logic
        # 1. Previous Close > Prev Upper Band (Was Overbought)
        # 2. Current Close < Current Upper Band (Returned to Range)
        # 3. RSI is high (e.g. > 60)
        
        if prev_bb_upper is not None:
            was_above = prev_kline.close > prev_bb_upper
            is_below = price < bb_upper
            
            # Allow RSI to be slightly lower than strict overbought during the turn
            rsi_threshold_short = settings.rsi_overbought - 10
            
            if was_above and is_below and rsi > rsi_threshold_short:
                 # Phase 4 Alpha: Check OFI
                 # We need selling pressure (OFI < 0) to confirm the reversal
                if ofi is not None and ofi < 0:
                    direction = "SHORT"
                    strength = 0.9
                    confidence = 0.90
                    reasoning = (
                        f"Mean Reversion Short (Confirmed): Price returned to band with Selling Pressure "
                        f"(OFI {ofi:.2f}). RSI {rsi:.2f}"
                    )
                elif ofi is None:
                    direction = "SHORT"
                    strength = 0.7
                    confidence = 0.75
                    reasoning = (
                        f"Mean Reversion Short (Unconfirmed): Price returned to band (No OFI). RSI {rsi:.2f}"
                    )
                else:
                    # OFI > 0: Buying pressure still dominant
                    reasoning = (
                        f"Mean Reversion Short Rejected: Price returned but Buying Pressure remains (OFI {ofi:.2f})"
                    )
                    direction = "NEUTRAL"

                take_profit = bb_mid
                stop_loss = price * 1.02 # 2% stop

    # If still Neutral, provide reasoning if near bands
    if direction == "NEUTRAL":
        if price < bb_lower:
            reasoning = "Price below lower band, waiting for confirmation (close inside)"
        elif price > bb_upper:
            reasoning = "Price above upper band, waiting for confirmation (close inside)"
        else:
            reasoning = f"In range: RSI {rsi:.2f}, Price within bands"
            confidence = 0.5

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
        "signals": [signal]
    }
