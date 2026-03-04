import os
import sys
import pandas as pd
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.callbacks import CheckpointCallback

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
from src.app.rl.trading_env import TradingEnv
from src.app.utils.data_split import split_data_temporal

def train():
    print("Setting up Trading Environment...")
    
    # Paths
    DATA_PATH = "data/BTCUSDT_5Y_MASTER.csv"
    MODEL_PATH = "src/app/models/jepa_latest.pth"
    SAVE_PATH = "src/app/models/rl_agent_latest"
    
    # Check if data exists
    if not os.path.exists(DATA_PATH):
        print(f"Error: {DATA_PATH} not found.")
        return

    # Load and split data
    print(f"Loading data from {DATA_PATH}...")
    df = pd.read_csv(DATA_PATH)
    print(f"Loaded {len(df)} rows.")
    
    print("Splitting data (90/0/10) - Merging Train & Val for extended training...")
    train_df, val_df, test_df = split_data_temporal(df, train_pct=0.9, val_pct=0.0)
    
    # Use ONLY training data
    print(f"Using {len(train_df)} training rows for RL training.")

    # Initialize Env with train split
    env = DummyVecEnv([lambda: TradingEnv(train_df, MODEL_PATH)])
    
    print("Initializing PPO Agent...")
    
    # Priority: Pre-trained > Existing > New
    PRETRAINED_PATH = "src/app/models/rl_agent_pretrained"
    
    if os.path.exists(PRETRAINED_PATH + ".zip"):
        print(f"✅ Loading PRE-TRAINED model from {PRETRAINED_PATH} (imitation learning)...")
        model = PPO.load(PRETRAINED_PATH, env=env)
        print("   Model bootstrapped with momentum strategy demonstrations")
    elif os.path.exists(SAVE_PATH + ".zip"):
        print(f"Loading existing agent from {SAVE_PATH} for fine-tuning...")
        model = PPO.load(SAVE_PATH, env=env)
    else:
        print("Creating new PPO agent...")
        model = PPO(
            "MlpPolicy", 
            env, 
            verbose=1, 
            learning_rate=0.00005,  # Reduced from 0.0003 for stability
            n_steps=2048, 
            batch_size=64, 
            ent_coef=0.05,  # Increased from 0.01 for exploration
            clip_range=0.1  # Add clipping for stability
        )
    
    # Checkpoint callback - save every 100K steps
    checkpoint_callback = CheckpointCallback(
        save_freq=100000,
        save_path="src/app/models/checkpoints/",
        name_prefix="rl_agent"
    )
    
    print("Starting RL Fine-Tuning (500K Steps - Reduced to prevent overfitting)...")
    try:
        model.learn(total_timesteps=500000, callback=checkpoint_callback)
    except KeyboardInterrupt:
        print("\n⚠️  Training interrupted by user")
    except Exception as e:
        print(f"Training failed: {e}")
        return

    print("Saving Final Model...")
    model.save(SAVE_PATH)
    print(f"✅ Agent saved to {SAVE_PATH}.zip")

if __name__ == "__main__":
    train()
