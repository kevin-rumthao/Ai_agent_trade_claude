
import pickle
import numpy as np
import torch
import os

def inspect_expert_data():
    path = "data/momentum_expert.pkl"
    print(f"Loading {path}...")
    with open(path, 'rb') as f:
        data = pickle.load(f)
    
    print(f"Loaded {len(data)} trajectories.")
    
    # Check first item
    first = data[0]
    obs = first['observation']
    action = first['action']
    
    print(f"\nSample 0:")
    print(f"Action: {action}")
    print(f"Obs Shape: {obs.shape}")
    print(f"Obs Mean: {np.mean(obs):.4f}")
    print(f"Obs Std: {np.std(obs):.4f}")
    print(f"Obs Raw (First 10): {obs[:10]}")
    
    # Check for NaNs
    obs_array = np.array([t['observation'] for t in data])
    nans = np.isnan(obs_array).sum()
    print(f"\nTotal NaNs in observations: {nans}")
    
    # Check Action Distribution again
    actions = [t['action'] for t in data]
    print(f"Actions: 0={actions.count(0)}, 1={actions.count(1)}, 2={actions.count(2)}")

if __name__ == "__main__":
    inspect_expert_data()
