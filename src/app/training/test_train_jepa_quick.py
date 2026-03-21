
import os
import sys
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler
import joblib
import warnings

# Add project root to path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
from src.app.models.ts_jepa import TS_JEPA
from src.app.utils.data_split import split_data_temporal

warnings.filterwarnings("ignore")

# --- Configuration (PATCHED FOR QUICK TEST) ---
DATA_PATH = "data/BTCUSDT_5Y_1m.csv"
MODEL_SAVE_PATH = "src/app/models/jepa_quick_test.pth"
BATCH_SIZE = 16
EPOCHS = 1  # Quick test
LEARNING_RATE = 1e-4
SEQ_LEN = 1  
EMBED_DIM = 64
MOMENTUM_ALPHA = 0.99

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

# --- Feature Engineering Helper ---
def compute_technical_indicators(df):
    """
    Compute technical indicators matching FeatureEngine logic.
    """
    df = df.copy()
    
    # 1. EMAs
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # 2. RSI (14)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # 3. Realized Volatility (approx 14 period std dev of returns)
    df['returns'] = df['close'].pct_change()
    df['volatility'] = df['returns'].rolling(window=14).std() * np.sqrt(14)
    
    # 4. ADX (14) - Simplified
    # Calculate True Range
    df['h-l'] = df['high'] - df['low']
    df['h-pc'] = abs(df['high'] - df['close'].shift(1))
    df['l-pc'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['h-l', 'h-pc', 'l-pc']].max(axis=1)
    
    # Directional Movement
    df['up_move'] = df['high'] - df['high'].shift(1)
    df['down_move'] = df['low'].shift(1) - df['low']
    df['plus_dm'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0)
    df['minus_dm'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0)
    
    # Smoothed
    df['tr_smooth'] = df['tr'].rolling(window=14).sum()  # Wilder's smoothing is better but SMA is okay for proxy
    df['plus_dm_smooth'] = df['plus_dm'].rolling(window=14).sum()
    df['minus_dm_smooth'] = df['minus_dm'].rolling(window=14).sum()
    
    df['plus_di'] = 100 * (df['plus_dm_smooth'] / df['tr_smooth'])
    df['minus_di'] = 100 * (df['minus_dm_smooth'] / df['tr_smooth'])
    df['dx'] = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])
    df['adx'] = df['dx'].rolling(window=14).mean()
    
    # 5. OFI & Imbalance (Missing in CSV -> fill 0)
    df['ofi'] = 0.0
    df['imbalance'] = 0.0
    
    # 6. Normalize Feature Inputs
    # We need: rsi/100, imbalance, ofi, (price-ema50)/ema50, volatility, adx/100
    df['feat_rsi'] = df['rsi'] / 100.0
    df['feat_imbalance'] = df['imbalance']
    df['feat_ofi'] = df['ofi']
    df['feat_ema_dev'] = (df['close'] - df['ema_50']) / df['ema_50']
    df['feat_vol'] = df['volatility']
    df['feat_adx'] = df['adx'] / 100.0
    
    # Drop NaNs only in feature columns
    df.dropna(subset=['feat_rsi', 'feat_imbalance', 'feat_ofi', 'feat_ema_dev', 'feat_vol', 'feat_adx'], inplace=True)
    
    return df

# --- Dataset Class ---
class MarketDataset(Dataset):
    def __init__(self, features):
        self.features = torch.FloatTensor(features)
        
    def __len__(self):
        return len(self.features) - 1
    
    def __getitem__(self, idx):
        # Predict t+1 from t
        x_t = self.features[idx]
        x_next = self.features[idx + 1]
        return x_t, x_next


def train():
    print(f"Loading data from {DATA_PATH}...", flush=True)
    if not os.path.exists(DATA_PATH):
        print(f"Error: Data file not found at {DATA_PATH}", flush=True)
        return

    # Load Full Dataset (LIMIT TO 1000 ROWS FOR QUICK TEST)
    df = pd.read_csv(DATA_PATH).head(2000) 
    print(f"Loaded {len(df)} rows for quick test.")
    
    # Split data temporally (90% train, 5% val, 5% test)
    print("Splitting data...")
    train_df, val_df, test_df = split_data_temporal(df, train_pct=0.9, val_pct=0.05)
    
    # Use ONLY training data
    print(f"Using {len(train_df)} training rows for TS-JEPA training.")
    df = train_df
    
    print("Computing technical indicators...")
    df = compute_technical_indicators(df)
    print(f"Processed {len(df)} rows after cleaning.")
    
    # aligned with ts_jepa_node.py inputs:
    # [rsi, imbalance, ofi, ema_dev, vol, adx, 0,0,0,0,0,0] -> 12 dims
    feature_cols = ['feat_rsi', 'feat_imbalance', 'feat_ofi', 'feat_ema_dev', 'feat_vol', 'feat_adx']
    data_matrix = df[feature_cols].values
    
    # Pad to 12 dims
    padding = np.zeros((data_matrix.shape[0], 6))
    data_matrix = np.hstack([data_matrix, padding])
    
    # Normalize (strictly speaks, some like RSI are bounded, but standardization helps NN)
    scaler = StandardScaler()
    data_matrix = scaler.fit_transform(data_matrix)
    
    dataset = MarketDataset(data_matrix)
    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)
    
    print("Initializing Model...")
    model = TS_JEPA(input_dim=12, embed_dim=EMBED_DIM)
    optimizer = optim.AdamW(list(model.context_encoder.parameters()) + list(model.predictor.parameters()), lr=LEARNING_RATE)
    criterion = nn.MSELoss()
    
    print("Starting Training...")
    model.train()
    
    for epoch in range(EPOCHS):
        total_loss = 0
        for x_t, x_next in dataloader:
            # 1. Forward Pass
            # Context Encoder: z_t
            z_t = model.context_encoder(x_t)
            
            # Predictor: z_hat_next
            z_hat_next = model.predictor(z_t)
            
            # Target Encoder: z_next (Teacher) check NO GRAD
            with torch.no_grad():
                z_next = model.target_encoder(x_next)
                
            # 2. Loss: Regress prediction to target
            loss = criterion(z_hat_next, z_next)
            
            # 3. Optimize
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            # 4. Momentum Update Target Encoder
            with torch.no_grad():
                for param_q, param_k in zip(model.context_encoder.parameters(), model.target_encoder.parameters()):
                    param_k.data = param_k.data * MOMENTUM_ALPHA + param_q.data * (1. - MOMENTUM_ALPHA)
            
            total_loss += loss.item()
            
        avg_loss = total_loss / len(dataloader)
        print(f"Epoch {epoch+1}/{EPOCHS} | Loss: {avg_loss:.6f}")
        
    print("Test finished successfully.")

if __name__ == "__main__":
    train()
