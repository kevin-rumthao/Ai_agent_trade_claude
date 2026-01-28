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
        # Insufficient data
        return {
            **state,
            "signals": [Signal(
                timestamp=datetime.now(),
                symbol=symbol,
                strategy="momentum",
                direction="NEUTRAL",
                strength=0.0,
                confidence=0.0,
                reasoning="Insufficient feature data"
            )]
        }

    price = features.price
    ema_9 = features.ema_9
    ema_50 = features.ema_50
    ema_200 = features.ema_200
    adx = features.adx
    atr = features.atr
    rsi = features.rsi
    ofi_sma = features.ofi_sma

    # Calculate trend strength
    ema_diff_pct = (ema_9 - ema_50) / ema_50 * 100
    price_vs_ema9_pct = (price - ema_9) / ema_9 * 100

    direction: str = "NEUTRAL"
    strength = 0.0
    confidence = 0.0
    reasoning = ""
    stop_loss = None
    take_profit = None
    trailing_stop_distance = None

    # --- Filters ---
    
    # --- Hysteresis Logic ---
    # Check if we are currently in a trade
    previous_signal = state.get("signal")
    current_direction = previous_signal.direction if previous_signal else "NEUTRAL"

    # Define Thresholds
    # Entry (Strict)
    ENTRY_ADX_THRESHOLD = 25.0
    ENTRY_RSI_LONG_MIN = 50.0
    ENTRY_RSI_LONG_MAX = 70.0
    ENTRY_RSI_SHORT_MIN = 30.0
    ENTRY_RSI_SHORT_MAX = 50.0
    
    # Maintain (Relaxed - Hysteresis)
    MAINTAIN_ADX_THRESHOLD = 20.0
    MAINTAIN_RSI_LONG_MIN = 45.0
    MAINTAIN_RSI_LONG_MAX = 80.0
    MAINTAIN_RSI_SHORT_MIN = 20.0
    MAINTAIN_RSI_SHORT_MAX = 55.0

    # 1. Regime Check
    # Use relaxed threshold if we are already in a trade
    adx_threshold = MAINTAIN_ADX_THRESHOLD if current_direction != "NEUTRAL" else ENTRY_ADX_THRESHOLD
    
    if adx and adx < adx_threshold:
        return {
            **state,
            "signals": [Signal(
                timestamp=datetime.now(),
                symbol=symbol,
                strategy="momentum",
                direction="NEUTRAL",
                strength=0.0,
                confidence=0.0,
                reasoning=f"Regime Filter: ADX ({adx:.2f}) < {adx_threshold}. Chop."
            )]
        }

    # 2. Trend Filter (EMA 200) - Keep strict for now
    is_bull_trend = (ema_200 and price > ema_200) if ema_200 else True 
    is_bear_trend = (ema_200 and price < ema_200) if ema_200 else True

    # 3. Momentum Logic
    
    # State: LONG
    if current_direction == "LONG":
        # Check Maintain Conditions
        # We stay LONG if:
        # 1. Price is still somewhat bullish (e.g. > EMA 50 or just > EMA 200) - Let's use EMA 9 > EMA 50 as primary trend
        #    Actually, if EMA9 crosses below EMA50, that's a clear exit signal.
        # 2. RSI is within relaxed bounds
        
        crossover_still_valid = (ema_9 > ema_50)
        
        # Relaxed RSI check
        rsi_valid = (rsi is not None and MAINTAIN_RSI_LONG_MIN < rsi < MAINTAIN_RSI_LONG_MAX) if rsi else True
        
        if crossover_still_valid and rsi_valid:
            # MAINTAIN LONG
            direction = "LONG"
            strength = previous_signal.strength if previous_signal else 1.0
            confidence = 0.9
            reasoning = "MAINTAIN LONG: Hysteresis Active"
        else:
            # EXIT
            direction = "NEUTRAL"
            reasoning = "EXIT LONG: Crossover invalid or RSI out of bounds"

    # State: SHORT
    elif current_direction == "SHORT":
        # Check Maintain Conditions
        crossover_still_valid = (ema_9 < ema_50)
        
        # Relaxed RSI check
        rsi_valid = (rsi is not None and MAINTAIN_RSI_SHORT_MIN < rsi < MAINTAIN_RSI_SHORT_MAX) if rsi else True
        
        if crossover_still_valid and rsi_valid:
            # MAINTAIN SHORT
            direction = "SHORT"
            strength = previous_signal.strength if previous_signal else 1.0
            confidence = 0.9
            reasoning = "MAINTAIN SHORT: Hysteresis Active"
        else:
            # EXIT
            direction = "NEUTRAL"
            reasoning = "EXIT SHORT: Crossover invalid or RSI out of bounds"

    # State: NEUTRAL (Look for New Entry)
    else:
        # Check Strict Entry Conditions
        
        # RSI Entry
        is_rsi_long_entry = (rsi is not None and ENTRY_RSI_LONG_MIN < rsi < ENTRY_RSI_LONG_MAX) if rsi else True
        is_rsi_short_entry = (rsi is not None and ENTRY_RSI_SHORT_MIN < rsi < ENTRY_RSI_SHORT_MAX) if rsi else True

        # Long Entry
        if ema_9 > ema_50 and price > ema_9:
            if is_bull_trend and is_rsi_long_entry:
                direction = "LONG"
                strength = min(abs(ema_diff_pct) / 2.0, 1.0)
                confidence = 0.8
                reasoning = "ENTRY LONG: EMA Cross + Trend + RSI"
                
                if ofi_sma and ofi_sma > 5.0:
                    confidence += 0.1
                    reasoning += f" + OFI ({ofi_sma:.2f})"
        
        # Short Entry
        elif ema_9 < ema_50 and price < ema_9:
            if is_bear_trend and is_rsi_short_entry:
                direction = "SHORT"
                strength = min(abs(ema_diff_pct) / 2.0, 1.0)
                confidence = 0.8
                reasoning = "ENTRY SHORT: EMA Cross + Trend + RSI"
                
                if ofi_sma and ofi_sma < -5.0:
                    confidence += 0.1
                    reasoning += f" + OFI ({ofi_sma:.2f})"

    # --- Exits (Trailing Stop setup for NEW positions) ---
    # Only set SL/TP for NEW entries. 
    # For maintained positions, we rely on the Backtester/Execution engine to manage the SL/TP 
    # OR we can update them here if we want dynamic trailing. 
    # For simplicity, we re-emit the trailing parameters so state is preserved.
    
    if direction in ["LONG", "SHORT"]:
        # Fallback if ATR is missing
        atr_val = atr if atr else price * 0.01 
        
        trailing_stop_distance = atr_val * 3.0
        
        if direction == "LONG":
            # If we are maintaining, we might want to keep the old SL logic handled by the engine
            # But the engine waits for our signal.
            # If we return a signal with stop_loss=None, the engine might keep the old one?
            # Let's provide the current calculated SL based on price? 
            # No, standard trailing logic usually handled by engine.
            # We just provide the DISTANCE.
            pass 
        else:
            pass
            
        # Calculate initial SL for new entries
        if current_direction == "NEUTRAL":
             if direction == "LONG":
                 stop_loss = price - trailing_stop_distance
             else:
                 stop_loss = price + trailing_stop_distance
        else:
             # Maintain existing SL/TP
             # We must provide a valid SL for the Signal validation check
             if previous_signal and previous_signal.stop_loss:
                 stop_loss = previous_signal.stop_loss
                 take_profit = previous_signal.take_profit
             else:
                 # Fallback if somehow missing (shouldn't happen for active trade)
                 # Recalculate based on current price to pass validation
                 if direction == "LONG":
                     stop_loss = price - trailing_stop_distance
                 else:
                     stop_loss = price + trailing_stop_distance
                 take_profit = None


    return {
        **state,
        "signals": [Signal(
            timestamp=datetime.now(),
            symbol=symbol,
            strategy="momentum",
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

