#!/usr/bin/env python3
"""
Pre-train RL agent via behavioral cloning (imitation learning).
Trains policy to mimic expert (momentum strategy) demonstrations.
"""

import os
import sys
import pandas as pd
import numpy as np
import pickle
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
sys.path.insert(0, project_root)

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from app.rl.trading_env import TradingEnv
from app.utils.data_split import split_data_temporal

class ExpertDataset(Dataset):
    """PyTorch dataset for expert demonstrations."""
    
    def __init__(self, trajectories):
        self.observations = np.array([t['observation'] for t in trajectories], dtype=np.float32)
        self.actions = np.array([t['action'] for t in trajectories], dtype=np.int64)
    
    def __len__(self):
        return len(self.observations)
    
    def __getitem__(self, idx):
        return {
            'observation': torch.FloatTensor(self.observations[idx]),
            'action': torch.LongTensor([self.actions[idx]])
        }

def pretrain_behavioral_cloning(
    expert_data_path="data/momentum_expert.pkl",
    output_model_path="src/app/models/rl_agent_pretrained",
    epochs=10,
    batch_size=512,
    learning_rate=1e-3
):
    """
    Pre-train RL policy using behavioral cloning.
    """
    print("=" * 70)
    print("BEHAVIORAL CLONING PRE-TRAINING")
    print("=" * 70)
    
    # 1. Load expert demonstrations
    print(f"\n1. Loading expert demonstrations from {expert_data_path}...")
    with open(expert_data_path, 'rb') as f:
        trajectories = pickle.load(f)
    
    print(f"   Loaded {len(trajectories):,} expert demonstrations")
    
    # Analyze action distribution
    actions = [t['action'] for t in trajectories]
    action_counts = {
        0: actions.count(0),
        1: actions.count(1),
        2: actions.count(2)
    }
    
    print(f"\n   Action Distribution:")
    print(f"   - NEUTRAL: {action_counts[0]:,} ({action_counts[0]/len(actions)*100:.1f}%)")
    print(f"   - LONG:    {action_counts[1]:,} ({action_counts[1]/len(actions)*100:.1f}%)")
    print(f"   - SHORT:   {action_counts[2]:,} ({action_counts[2]/len(actions)*100:.1f}%)")
    
    # 2. Create dataset and dataloader
    print(f"\n2. Creating PyTorch dataset...")
    dataset = ExpertDataset(trajectories)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=0)
    print(f"   Dataset size: {len(dataset):,} samples")
    print(f"   Batch size: {batch_size}")
    print(f"   Total batches per epoch: {len(dataloader):,}")
    
    # 3. Initialize PPO policy (for architecture)
    print(f"\n3. Initializing PPO policy architecture...")
    DATA_PATH = "data/BTCUSDT_5Y_MASTER.csv"
    MODEL_PATH = "src/app/models/jepa_latest.pth"
    
    df = pd.read_csv(DATA_PATH)
    # Use 90% train + 0% val (validation is effectively implicit in pre-training or skipped)
    train_df, _, _ = split_data_temporal(df, train_pct=0.9, val_pct=0.0)
    env = DummyVecEnv([lambda: TradingEnv(train_df, MODEL_PATH)])
    
    model = PPO("MlpPolicy", env, verbose=0)
    policy = model.policy
    
    print(f"   Policy architecture: MlpPolicy")
    print(f"   Observation space: {env.observation_space.shape}")
    print(f"   Action space: {env.action_space.n} discrete actions")
    
    # 4. Setup training
    print(f"\n4. Setting up behavioral cloning training...")
    optimizer = torch.optim.Adam(policy.parameters(), lr=learning_rate)
    criterion = nn.CrossEntropyLoss()
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    policy = policy.to(device)
    
    print(f"   Device: {device}")
    print(f"   Optimizer: Adam (lr={learning_rate})")
    print(f"   Loss: CrossEntropyLoss")
    print(f"   Epochs: {epochs}")
    
    # 5. Training loop
    print(f"\n5. Starting behavioral cloning training...")
    print("   " + "-" * 60)
    
    best_accuracy = 0.0
    
    for epoch in range(epochs):
        total_loss = 0
        correct_predictions = 0
        total_predictions = 0
        
        for batch_idx, batch in enumerate(dataloader):
            # Move to device
            obs = batch['observation'].to(device)
            actions = batch['action'].squeeze().to(device)
            
            # Forward pass through policy network
            with torch.no_grad():
                features = policy.extract_features(obs)
            latent_pi = policy.mlp_extractor.forward_actor(features)
            action_logits = policy.action_net(latent_pi)
            
            # Compute loss
            loss = criterion(action_logits, actions)
            
            # Backward pass
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            # Track metrics
            total_loss += loss.item()
            predictions = torch.argmax(action_logits, dim=1)
            correct_predictions += (predictions == actions).sum().item()
            total_predictions += len(actions)
        
        # Epoch metrics
        avg_loss = total_loss / len(dataloader)
        accuracy = correct_predictions / total_predictions * 100
        
        print(f"   Epoch {epoch+1}/{epochs} | Loss: {avg_loss:.4f} | Accuracy: {accuracy:.2f}%")
        
        # Save best model
        if accuracy > best_accuracy:
            best_accuracy = accuracy
            model.save(output_model_path + "_best")
    
    print("   " + "-" * 60)
    
    # 6. Save final pre-trained model
    print(f"\n6. Saving pre-trained model...")
    model.save(output_model_path)
    print(f"   Saved to: {output_model_path}.zip")
    print(f"   Best accuracy: {best_accuracy:.2f}%")
    
    print("\n" + "=" * 70)
    print("✅ BEHAVIORAL CLONING PRE-TRAINING COMPLETE")
    print("=" * 70)
    print(f"\nNext steps:")
    print(f"1. Fine-tune with RL: python src/app/training/train_rl.py")
    print(f"2. Validate: python scripts/run_backtest.py --strategy rl_agent --split val")
    
    return model

if __name__ == "__main__":
    pretrain_behavioral_cloning()
