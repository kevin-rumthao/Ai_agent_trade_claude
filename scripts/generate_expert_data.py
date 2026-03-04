#!/usr/bin/env python3
"""
Generate expert demonstrations from momentum strategy.
Collects (observation, action) pairs for behavioral cloning.
"""

import os
import sys
import pandas as pd
import numpy as np
import pickle
from tqdm import tqdm

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from src.app.rl.trading_env import TradingEnv
from src.app.utils.data_split import split_data_temporal

def get_momentum_action(env, step_idx):
    """
    Determine momentum strategy action based on current features.
    
    Logic mirrors the momentum strategy:
    - LONG if strong uptrend and positive momentum
    - SHORT if strong downtrend and negative momentum  
    - NEUTRAL otherwise
    """
    # Get normalized features at current step
    features = env.features_normalized[step_idx]
    
    # Extract regime features
    trend_strength = features[7]   # feat_trend_strength (EMA20-EMA50 crossover)
    momentum_20 = features[9]      # feat_momentum_20 (20-period price change)
    vol_regime = features[6]       # feat_vol_regime (current/long-term vol)
    
    # Momentum thresholds
    TREND_THRESHOLD = 0.01
    VOL_THRESHOLD = 1.5  # Avoid trading in very high volatility
    
    # Strong uptrend + positive momentum = LONG
    if trend_strength > TREND_THRESHOLD and momentum_20 > 0 and vol_regime < VOL_THRESHOLD:
        return 1  # LONG
    
    # Strong downtrend + negative momentum = SHORT
    elif trend_strength < -TREND_THRESHOLD and momentum_20 < 0 and vol_regime < VOL_THRESHOLD:
        return 2  # SHORT
    
    # Otherwise stay neutral
    else:
        return 0  # NEUTRAL

def generate_expert_demonstrations(output_path="data/momentum_expert.pkl"):
    """
    Run momentum strategy on training data and collect expert trajectories.
    """
    print("=" * 60)
    print("EXPERT DEMONSTRATION GENERATOR")
    print("=" * 60)
    
    # Load and split data
    DATA_PATH = "data/BTCUSDT_5Y_MASTER.csv"
    MODEL_PATH = "src/app/models/jepa_latest.pth"
    
    print(f"\n1. Loading data from {DATA_PATH}...")
    df = pd.read_csv(DATA_PATH)
    print(f"   Loaded {len(df):,} rows")
    
    print("\n2. Splitting data (90/0/10) - Merging Train & Val for extended training...")
    train_df, val_df, test_df = split_data_temporal(df, train_pct=0.9, val_pct=0.0)
    print(f"   Train: {len(train_df):,} rows")
    print(f"   Val:   {len(val_df):,} rows")
    print(f"   Test:  {len(test_df):,} rows")
    
    # Create environment
    print(f"\n3. Initializing trading environment...")
    env = TradingEnv(train_df, MODEL_PATH)
    print(f"   Environment ready with {len(train_df):,} steps")
    
    # Collect expert trajectories
    print("\n4. Collecting expert demonstrations...")
    expert_trajectories = []
    
    # Reset environment
    obs, _ = env.reset()
    
    # Run through entire training data (avoid last 100 steps and respect array bounds)
    max_steps = min(len(train_df) - 100, len(env.features_normalized))
    for step_idx in tqdm(range(max_steps), desc="   Generating"):
        # Get momentum strategy's action
        action = get_momentum_action(env, step_idx)
        
        # Store (observation, action) pair
        expert_trajectories.append({
            'observation': obs.copy(),
            'action': action,
            'step': step_idx
        })
        
        # Step environment
        obs, reward, done, truncated, info = env.step(action)
        
        # Reset if episode ends
        if done or truncated:
            obs, _ = env.reset()
    
    print(f"\n5. Collected {len(expert_trajectories):,} expert demonstrations")
    
    # Analyze action distribution
    actions = [t['action'] for t in expert_trajectories]
    action_counts = {
        0: actions.count(0),
        1: actions.count(1),
        2: actions.count(2)
    }
    
    print("\n6. Action Distribution:")
    print(f"   NEUTRAL (0): {action_counts[0]:,} ({action_counts[0]/len(actions)*100:.1f}%)")
    print(f"   LONG (1):    {action_counts[1]:,} ({action_counts[1]/len(actions)*100:.1f}%)")
    print(f"   SHORT (2):   {action_counts[2]:,} ({action_counts[2]/len(actions)*100:.1f}%)")
    
    # Save to disk
    print(f"\n7. Saving to {output_path}...")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'wb') as f:
        pickle.dump(expert_trajectories, f)
    
    # Check file size
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"   Saved {file_size_mb:.1f} MB")
    
    print("\n" + "=" * 60)
    print("✅ EXPERT DEMONSTRATION GENERATION COMPLETE")
    print("=" * 60)
    print(f"\nNext step: Run behavioral cloning with:")
    print(f"  python src/app/training/pretrain_rl_imitation.py")
    
    return expert_trajectories

if __name__ == "__main__":
    generate_expert_demonstrations()
