"""Swing trading strategy implementation (Trend Pullback)."""
from typing import TypedDict
from datetime import datetime

from app.schemas.models import MarketFeatures, Signal
from app.config import settings


class SwingState(TypedDict):
    """State for swing trading strategy."""
    features: MarketFeatures | None
    signal: Signal | None
    symbol: str
    timestamp: datetime


async def swing_strategy_node(state: SwingState) -> SwingState:
    """
    Generate swing trading signals based on Trend Pullbacks.

    Strategy:
    - Trend Filter: EMA(50) > EMA(200) (Bullish) / EMA(50) < EMA(200) (Bearish)
    - Pullback Zone: Price touches or crosses EMA(20) / Lower BB
    - Trigger: RSI Oversold (<40) curling up or Price Candle Closure > EMA(20)
    - Exit: Target previous swing high/low or trailing stop
    """
    features = state.get("features")
    symbol = state.get("symbol", settings.symbol)

    if not features or not features.ema_50 or not features.ema_200:
        return {
            **state,
            "signals": [Signal(
                timestamp=datetime.now(),
                symbol=symbol,
                strategy="swing",
                direction="NEUTRAL",
                strength=0.0,
                confidence=0.0,
                reasoning="Insufficient trend data (EMA 50/200 missing)"
            )]
        }

    price = features.price
    ema_20 = features.ema_20  # Fast MA for dynamic support
    ema_50 = features.ema_50
    ema_200 = features.ema_200
    rsi = features.rsi
    atr = features.atr
    ofi_sma = features.ofi_sma

    direction: str = "NEUTRAL"
    strength = 0.0
    confidence = 0.0
    reasoning = ""
    stop_loss = None
    take_profit = None
    trailing_stop_distance = None

    # --- Trend Identification ---
    is_uptrend = ema_50 > ema_200
    is_downtrend = ema_50 < ema_200

    # --- Hysteresis Logic ---
    previous_signal = state.get("signal")
    current_direction = previous_signal.direction if previous_signal else "NEUTRAL"

    # Maintain Existing Position
    if current_direction == "LONG":
        # Exit if trend breaks significantly (e.g. Price < EMA 50) or Target Hit
        if price < ema_50:
            direction = "NEUTRAL"
            reasoning = "EXIT LONG: Trend Broken (Price < EMA 50)"
        else:
            direction = "LONG"
            strength = previous_signal.strength if previous_signal else 1.0
            confidence = 0.9
            reasoning = "MAINTAIN LONG: Trend Intact"

    elif current_direction == "SHORT":
        if price > ema_50:
            direction = "NEUTRAL"
            reasoning = "EXIT SHORT: Trend Broken (Price > EMA 50)"
        else:
            direction = "SHORT"
            strength = previous_signal.strength if previous_signal else 1.0
            confidence = 0.9
            reasoning = "MAINTAIN SHORT: Trend Intact"

    # New Entry Logic
    else:
        # Long Setup: Uptrend + Pullback
        if is_uptrend:
            # Pullback Condition: Price close to EMA 20 (within 0.5% or below it) but above EMA 50
            dist_to_ema20 = (price - ema_20) / ema_20
            is_pullback = -0.015 < dist_to_ema20 < 0.005  # Slight dip below or near touch
            
            # Trigger: RSI Oversold in Uptrend (e.g., < 45) but not crashed (< 20)
            rsi_setup = (rsi is not None and 30 < rsi < 55) if rsi else False
            
            if is_pullback and rsi_setup and price > ema_50:
                direction = "LONG"
                strength = 0.8
                confidence = 0.75
                reasoning = "ENTRY LONG: Pullback to EMA 20 in Uptrend + RSI Reset"
                
                # OFI Confirmation
                if ofi_sma and ofi_sma > 0:
                    confidence += 0.15
                    reasoning += f" + OFI Bullish ({ofi_sma:.2f})"

        # Short Setup: Downtrend + Rally
        elif is_downtrend:
            # Rally Condition: Price close to EMA 20 but below EMA 50
            dist_to_ema20 = (price - ema_20) / ema_20
            is_rally = -0.005 < dist_to_ema20 < 0.015
            
            # Trigger: RSI Overbought in Downtrend (e.g., > 45)
            rsi_setup = (rsi is not None and 45 < rsi < 70) if rsi else False
            
            if is_rally and rsi_setup and price < ema_50:
                direction = "SHORT"
                strength = 0.8
                confidence = 0.75
                reasoning = "ENTRY SHORT: Rally to EMA 20 in Downtrend + RSI Reset"
                
                if ofi_sma and ofi_sma < 0:
                    confidence += 0.15
                    reasoning += f" + OFI Bearish ({ofi_sma:.2f})"

    # --- Risk Management (ATR Based) ---
    if direction in ["LONG", "SHORT"] and current_direction == "NEUTRAL":
        atr_val = atr if atr else price * 0.01
        stop_distance = atr_val * 2.0  # Wider stop for swings
        reward_distance = atr_val * 4.0  # 1:2 R:R
        
        if direction == "LONG":
            stop_loss = price - stop_distance
            take_profit = price + reward_distance
        else:
            stop_loss = price + stop_distance
            take_profit = price - reward_distance
            
        trailing_stop_distance = stop_distance * 1.5

    return {
        **state,
        "signals": [Signal(
            timestamp=datetime.now(),
            symbol=symbol,
            strategy="swing",
            direction=direction,  # type: ignore
            strength=strength,
            confidence=confidence,
            entry_price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_stop_distance=trailing_stop_distance,
            reasoning=reasoning
        )]
    }
