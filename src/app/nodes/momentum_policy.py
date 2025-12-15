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
    
    # 1. Regime Filter: ADX (Avoid Ranging Markets)
    # If ADX < 25, the market is likely chopping. Sit out.
    if adx and adx < 25:
        return {
            **state,
            "signals": [Signal(
                timestamp=datetime.now(),
                symbol=symbol,
                strategy="momentum",
                direction="NEUTRAL",
                strength=0.0,
                confidence=0.0,
                reasoning=f"Regime Filter: ADX ({adx:.2f}) < 25. Market Ranging."
            )]
        }

    # 2. Trend Filter: EMA 200 (Long only if Price > EMA 200, Short only if Price < EMA 200)
    is_bull_trend = (ema_200 and price > ema_200) if ema_200 else True # Default True if no 200 yet
    is_bear_trend = (ema_200 and price < ema_200) if ema_200 else True
    
    # 3. Momentum Quality Filter: RSI (Avoid Overbought/Oversold Reversals)
    # Long: 50 < RSI < 70 (Strong momentum, room to grow)
    # Short: 30 < RSI < 50 (Weak momentum, room to drop)
    is_rsi_long = (rsi is not None and 50 < rsi < 70) if rsi else True
    is_rsi_short = (rsi is not None and 30 < rsi < 50) if rsi else True


    # --- Logic ---

    # Long Logic
    if ema_9 > ema_50 and price > ema_9:
        if is_bull_trend and is_rsi_long:
            direction = "LONG"
            strength = min(abs(ema_diff_pct) / 2.0, 1.0)
            confidence = 0.8
            reasoning = "LONG: EMA9 > EMA50 & Price > EMA200 & RSI Bullish"
            
            # OFI Boost
            if ofi_sma and ofi_sma > 5.0:
                confidence += 0.1
                reasoning += f" + OFI Buy ({ofi_sma:.2f})"
        else:
             reasoning = "LONG Filtered: Price < EMA 200 or RSI Overbought/Weak"

    # Short Logic
    elif ema_9 < ema_50 and price < ema_9:
        if is_bear_trend and is_rsi_short:
            direction = "SHORT"
            strength = min(abs(ema_diff_pct) / 2.0, 1.0)
            confidence = 0.8
            reasoning = "SHORT: EMA9 < EMA50 & Price < EMA200 & RSI Bearish"
            
            # OFI Boost
            if ofi_sma and ofi_sma < -5.0:
                confidence += 0.1
                reasoning += f" + OFI Sell ({ofi_sma:.2f})"
        else:
             reasoning = "SHORT Filtered: Price > EMA 200 or RSI Oversold/Strong"

    # --- Exits (Trailing Stop) ---
    if direction in ["LONG", "SHORT"]:
        # Fallback if ATR is missing (e.g. early data)
        atr_val = atr if atr else price * 0.01 
        
        # Trailing Stop Distance = 3.0 * ATR
        # Allows for normal volatility but locks in profit on big moves
        trailing_stop_distance = atr_val * 3.0
        
        if direction == "LONG":
            stop_loss = price - trailing_stop_distance
            take_profit = None # Let it run!
        else:
            stop_loss = price + trailing_stop_distance
            take_profit = None # Let it run!
            
        # Sanity
        if stop_loss < 0: stop_loss = None

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

