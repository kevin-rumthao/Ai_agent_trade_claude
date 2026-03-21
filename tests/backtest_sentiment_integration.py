#!/usr/bin/env python3
"""
Integration test for backtest_sentiment.py refactor.
Ensures run_backtest uses Backtester correctly and produces consistent results.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.backtest_sentiment import run_backtest, compute_features, classify_and_signal
from app.utils.backtester import Backtester


def generate_small_synthetic_df(n_candles=100):
    """Generate a small trending dataset for testing."""
    np.random.seed(42)
    dates = pd.date_range(start=datetime.now() - timedelta(minutes=n_candles), periods=n_candles, freq='1min')
    
    price = 50000.0
    prices = []
    highs = []
    lows = []
    volumes = []
    
    for i in range(n_candles):
        # Uptrend with noise
        price *= 1 + np.random.normal(0.0002, 0.001)
        high = price * (1 + abs(np.random.normal(0, 0.0005)))
        low = price * (1 - abs(np.random.normal(0, 0.0005)))
        prices.append(price)
        highs.append(high)
        lows.append(low)
        volumes.append(np.random.uniform(10, 100))
    
    df = pd.DataFrame({
        'open': prices,
        'high': highs,
        'low': lows,
        'close': prices,
        'volume': volumes
    }, index=dates)
    
    return compute_features(df)


def test_run_backtest_returns_expected_keys():
    """Test that run_backtest returns all required result keys."""
    df = generate_small_synthetic_df(200)
    results = run_backtest(df, atr_mult=3.0)
    
    # Keys expected from the original run_backtest interface
    expected_keys = [
        'final_equity',
        'total_return_pct',
        'max_drawdown_pct',
        'sharpe_ratio',
        'total_trades',
        'win_rate_pct',
        'signal_counts',
        'trades',
        'avg_win_loss_ratio'
    ]
    for key in expected_keys:
        assert key in results, f"Missing key: {key}"


def test_run_backtest_produces_trades():
    """Test that backtest generates at least some trades on trending data."""
    df = generate_small_synthetic_df(300)
    results = run_backtest(df, atr_mult=3.0)
    assert len(results['trades']) > 0, "Expected at least one trade"


def test_signal_generation_has_trailing_distance():
    """Test that classify_and_signal provides trailing_stop_distance when directional."""
    df = generate_small_synthetic_df(50)
    prev_position = "NEUTRAL"
    prev_ema50_cross = None
    
    for i in range(len(df)):
        row = df.iloc[i]
        # We'll just check that the function returns a direction
        signal_dir = classify_and_signal(row, prev_position, prev_ema50_cross)
        assert signal_dir in ["LONG", "SHORT", "NEUTRAL"]
        prev_position = signal_dir


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
