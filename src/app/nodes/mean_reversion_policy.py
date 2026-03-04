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
                # Calculate Dynamic Risk/Reward
                atr_val = features.atr if features.atr else price * 0.005 # Fallback 0.5%
                
                # Stop Loss: Tight, based on volatility (1.5 ATR)
                stop_distance = atr_val * 1.5
                stop_loss = price - stop_distance
                
                # Target: Mid Band
                take_profit = bb_mid
                potential_reward = take_profit - price
                
                # R:R Filter
                if potential_reward > (stop_distance * 0.8): # Accept 0.8 R:R min due to high WR
                    direction = "LONG"
                    # Strength scaling
                    strength = 0.9 if (ofi and ofi > 0) else 0.7
                    confidence = 0.9 if (ofi and ofi > 0) else 0.75
                    
                    reasoning_base = "Mean Reversion Long"
                    reasoning_extra = f"(Confirmed by OFI {ofi:.2f})" if (ofi and ofi > 0) else "(No OFI)"
                    reasoning = f"{reasoning_base} {reasoning_extra}: Volatility Risk {stop_distance:.2f}, Reward {potential_reward:.2f}"
                else:
                     direction = "NEUTRAL"
                     reasoning = f"Skipped Long: Poor R:R (Risk {stop_distance:.2f} > Reward {potential_reward:.2f})"
                     stop_loss = None
                     take_profit = None

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
                
                # Calculate Dynamic Risk/Reward
                atr_val = features.atr if features.atr else price * 0.005
                
                # Stop Loss: Tight (1.5 ATR)
                stop_distance = atr_val * 1.5
                stop_loss = price + stop_distance
                
                # Target: Mid Band
                take_profit = bb_mid
                potential_reward = price - take_profit
                
                # R:R Filter
                if potential_reward > (stop_distance * 0.8):
                    direction = "SHORT"
                    
                    strength = 0.9 if (ofi and ofi < 0) else 0.7
                    confidence = 0.9 if (ofi and ofi < 0) else 0.75
                    
                    reasoning_base = "Mean Reversion Short"
                    reasoning_extra = f"(Confirmed by OFI {ofi:.2f})" if (ofi and ofi < 0) else "(No OFI)"
                    reasoning = f"{reasoning_base} {reasoning_extra}: Volatility Risk {stop_distance:.2f}, Reward {potential_reward:.2f}"
                else:
                    direction = "NEUTRAL"
                    reasoning = f"Skipped Short: Poor R:R (Risk {stop_distance:.2f} > Reward {potential_reward:.2f})"
                    stop_loss = None
                    take_profit = None

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
