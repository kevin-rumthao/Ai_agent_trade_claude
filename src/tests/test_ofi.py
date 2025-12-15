"""Tests for OFI (Order Flow Imbalance) logic."""
import pytest
from datetime import datetime

from app.nodes.feature_engineering import FeatureEngine
from app.schemas.events import OrderbookUpdate

def test_ofi_logic():
    """Test Microstructure Alpha (OFI) calculation."""
    engine = FeatureEngine()
    
    # 1. Initial State
    # Bids: Best @ 50000 (1.0)
    # Asks: Best @ 50010 (1.0)
    ob1 = OrderbookUpdate(
        timestamp=datetime.now(),
        symbol="BTCUSDT",
        bids=[(50000.0, 1.0)],
        asks=[(50010.0, 1.0)]
    )
    
    # Set as previous
    engine.prev_orderbook = ob1
    
    # 2. Bullish Update: Bid Price Improving (Aggressive Buying)
    # Bids: Best @ 50005 (1.0) -> New Limit Bid inside spread
    # Asks: Unchanged
    ob2 = OrderbookUpdate(
        timestamp=datetime.now(),
        symbol="BTCUSDT",
        bids=[(50005.0, 1.0)],
        asks=[(50010.0, 1.0)]
    )
    
    ofi_bullish = engine.compute_ofi(ob2)
    # Logic: Bid Price > Prev (50005 > 50000) -> ofi += current_bid_qty (1.0)
    # Ask Price == Prev -> ofi -= (curr_ask - prev_ask) = 0
    # Expected: 1.0
    assert ofi_bullish == 1.0, f"Expected OFI 1.0, got {ofi_bullish}"

    # Update state
    engine.prev_orderbook = ob2
    
    # 3. Bearish Update: Ask Price Drops (Aggressive Selling)
    # Bids: Unchanged
    # Asks: Best @ 50008 (1.0) -> Seller lowers offer
    ob3 = OrderbookUpdate(
        timestamp=datetime.now(),
        symbol="BTCUSDT",
        bids=[(50005.0, 1.0)],
        asks=[(50008.0, 1.0)]
    )
    
    ofi_bearish = engine.compute_ofi(ob3)
    
    # Logic: Bid Price == Prev -> 0
    # Ask Price < Prev (50008 < 50010) -> ask_impact = curr_ask_qty (1.0)
    # OFI = bid_impact - ask_impact = 0 - 1.0 = -1.0
    # Expected: -1.0
    assert ofi_bearish == -1.0, f"Expected OFI -1.0, got {ofi_bearish}"
