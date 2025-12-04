"""Hedge Agent node implementation."""
from typing import TypedDict
from datetime import datetime

from app.schemas.models import Signal, PortfolioState, MarketFeatures
from app.config import settings


class HedgeAgentState(TypedDict):
    """State for hedge agent."""
    signals: list[Signal]
    portfolio: PortfolioState | None
    symbol: str
    timestamp: datetime


def hedge_agent_node(state: HedgeAgentState) -> HedgeAgentState:
    """
    Hedge Agent logic.
    
    Analyzes current signals and portfolio to determine if hedging is needed.
    If a SPOT Long signal is present or a SPOT Long position exists, 
    it may generate a FUTURE Short signal to hedge exposure.
    """
    signals = state.get("signals", [])
    portfolio = state.get("portfolio")
    symbol = state.get("symbol", settings.symbol)
    
    # If no portfolio state, we can't really hedge existing positions, 
    # but we can hedge new signals.
    
    # 1. Calculate current Spot Exposure
    current_spot_qty = 0.0
    if portfolio and portfolio.positions:
        for pos in portfolio.positions:
            if pos.symbol == symbol and pos.instrument_type == "SPOT" and pos.side == "LONG":
                current_spot_qty += pos.quantity
                
    # 2. Calculate Incoming Spot Exposure (from signals)
    incoming_spot_qty = 0.0
    for signal in signals:
        if signal.symbol == symbol and signal.instrument_type == "SPOT" and signal.direction == "LONG":
            # We don't know the exact quantity yet as Risk Manager calculates it.
            # But we can signal the INTENT to hedge.
            # Or, we can wait for the next cycle? 
            # Ideally, we want to hedge immediately.
            # Since we don't know the quantity, we might issue a "HEDGE_RATIO" signal?
            # Or we can estimate based on signal strength/risk limits?
            # For MVP, let's assume we want to hedge existing positions mostly.
            pass

    # 3. Calculate Current Hedge (Future Short)
    current_hedge_qty = 0.0
    if portfolio and portfolio.positions:
        for pos in portfolio.positions:
            if pos.symbol == symbol and pos.instrument_type == "FUTURE" and pos.side == "SHORT":
                current_hedge_qty += pos.quantity

    # 4. Determine Desired Hedge
    # Strategy: Delta Neutral? Or Partial Hedge?
    # Let's assume we want to be Delta Neutral for now (1:1 hedge).
    
    # Total Spot Exposure = Current Spot + Incoming Spot (Unknown)
    # We can only reliably hedge what we HAVE.
    # If we want to hedge the incoming signal, we need to know the size.
    # But Risk Manager runs AFTER us.
    # So we can only hedge EXISTING positions.
    
    # However, if we only hedge existing, we lag by one cycle.
    # That might be acceptable for MVP.
    
    desired_hedge_qty = current_spot_qty
    
    # Calculate difference
    hedge_diff = desired_hedge_qty - current_hedge_qty
    
    new_signals = []
    
    # Threshold to avoid tiny adjustments
    if abs(hedge_diff) > 0.0001: # Arbitrary small number
        direction = "SHORT" if hedge_diff > 0 else "LONG" # If diff > 0, we need MORE short (Sell Future). If diff < 0, we have too much short (Buy Future to reduce).
        
        # Wait, if hedge_diff > 0, it means Desired > Current. We need to increase Short position.
        # Increasing Short position means SELLING.
        # If hedge_diff < 0, it means Desired < Current. We need to decrease Short position.
        # Decreasing Short position means BUYING (Closing Short).
        
        # But wait, "LONG" direction usually means "Open Long". 
        # For Futures, "LONG" means Buy, "SHORT" means Sell.
        # So if we need to reduce Short, we Buy (LONG).
        
        # Let's clarify the signal direction.
        # If we want to ADD to hedge (increase short), we send SHORT signal.
        # If we want to REDUCE hedge (decrease short), we send LONG signal.
        
        # But we need to be careful not to flip to Net Long Future if we just want to close short.
        # The Risk Manager handles "Closing" if we send the opposite signal?
        # Our Risk Manager logic:
        # "If signal.direction == LONG ... and has SHORT position ... close it?"
        # Yes, standard logic might handle it.
        
        # However, we need to specify the QUANTITY or Strength.
        # Signal doesn't carry Quantity usually (Risk Manager calculates it).
        # But for Hedging, the quantity is specific (to match spot).
        # We might need to pass a hint or use a specific strategy name that Risk Manager understands?
        # Or we update Risk Manager to look at "reasoning" or a new field?
        # Or we just rely on Risk Manager to calculate size, but that might not match Spot size.
        
        # ISSUE: Risk Manager calculates size based on Risk Limits (Stop Loss, etc.).
        # Hedge size should be based on Spot Exposure, NOT Volatility Risk.
        
        # We might need to update Risk Manager to handle "HEDGE" strategy differently.
        
        signal_direction = "SHORT" if hedge_diff > 0 else "LONG"
        
        hedge_signal = Signal(
            timestamp=datetime.now(),
            symbol=symbol,
            instrument_type="FUTURE",
            strategy="hedge",
            direction=signal_direction,
            strength=1.0,
            confidence=1.0,
            suggested_quantity=abs(hedge_diff),
            reasoning=f"Balancing Hedge: Spot {current_spot_qty:.4f}, Future Short {current_hedge_qty:.4f}, Diff {hedge_diff:.4f}"
        )
        new_signals.append(hedge_signal)

    return {
        **state,
        "signals": signals + new_signals
    }
