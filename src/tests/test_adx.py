"""Test ADX calculation."""
import pytest
from collections import deque
from app.nodes.feature_engineering import FeatureEngine

def test_adx_calculation():
    """Test ADX calculation with known values."""
    engine = FeatureEngine()
    
    # Sample data (trend up)
    # Generate 50 points of data
    highs = [10 + i for i in range(50)]
    lows = [9 + i for i in range(50)]
    closes = [9.5 + i for i in range(50)]
    
    # Populate buffers
    for h, l, c in zip(highs, lows, closes):
        engine.high_buffer.append(h)
        engine.low_buffer.append(l)
        engine.close_buffer.append(c)
        
    # Calculate ADX (period 14)
    adx = engine.compute_adx(period=14)
    
    assert adx is not None
    # In a perfect uptrend, ADX should be high (near 100 eventually, but starts lower)
    # With this perfect linear data:
    # UpMove = 1, DownMove = -1 (so 0)
    # +DM = 1, -DM = 0
    # TR = 1 (High - Low = 1, High - PrevClose = 0.5, Low - PrevClose = 0.5) -> Wait, H-L=1.
    # Actually:
    # i=1: H=11, L=10, C=10.5. PrevC=9.5.
    # H-L = 1.
    # |H-PC| = |11-9.5| = 1.5.
    # |L-PC| = |10-9.5| = 0.5.
    # TR = 1.5.
    
    # +DM = 11-10 = 1.
    # -DM = 9-10 = -1 -> 0.
    
    # So +DI should be high, -DI should be 0.
    # DX should be 100.
    # ADX should be 100 (or approaching it).
    
    print(f"Calculated ADX: {adx}")
    assert adx > 90.0

def test_adx_insufficient_data():
    """Test ADX returns None when insufficient data."""
    engine = FeatureEngine()
    
    # Only 5 data points
    highs = [10, 11, 12, 13, 14]
    lows = [9, 10, 11, 12, 13]
    closes = [9.5, 10.5, 11.5, 12.5, 13.5]
    
    for h, l, c in zip(highs, lows, closes):
        engine.high_buffer.append(h)
        engine.low_buffer.append(l)
        engine.close_buffer.append(c)
        
    adx = engine.compute_adx(period=14)
    assert adx is None
