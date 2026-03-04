
import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pandas as pd
import torch
import copy
from app.utils.backtester import Backtester
from app.schemas.models import Signal
from app.nodes.ts_jepa_node import load_jepa_model, TS_JEPA

# Feature Engineering Helper (Duplicated from train_jepa.py for independence)
def compute_technical_indicators_env(df):
    """
    Compute technical indicators matching FeatureEngine logic.
    """
    df = df.copy()
    
    # 1. EMAs
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    # 2. RSI (14)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # 3. Realized Volatility
    df['returns'] = df['close'].pct_change()
    df['volatility'] = df['returns'].rolling(window=14).std() * np.sqrt(14)
    
    # 4. ADX (Simplified)
    df['tr'] = df['high'] - df['low'] # Approximated
    df['adx'] = df['tr'].rolling(window=14).mean() # Very rough proxy if full ADX logic is heavy
    # Let's trust the logic from train_jepa.py is better, but for brevity:
    # Re-implementing correctly:
    df['h-l'] = df['high'] - df['low']
    df['h-pc'] = abs(df['high'] - df['close'].shift(1))
    df['l-pc'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['h-l', 'h-pc', 'l-pc']].max(axis=1)
    df['tr_smooth'] = df['tr'].rolling(window=14).sum()
    
    df['up_move'] = df['high'] - df['high'].shift(1)
    df['down_move'] = df['low'].shift(1) - df['low']
    df['plus_dm'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0)
    df['minus_dm'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0)
    
    df['plus_dm_smooth'] = df['plus_dm'].rolling(window=14).sum()
    df['minus_dm_smooth'] = df['minus_dm'].rolling(window=14).sum()
    
    df['plus_di'] = 100 * (df['plus_dm_smooth'] / df['tr_smooth'])
    df['minus_di'] = 100 * (df['minus_dm_smooth'] / df['tr_smooth'])
    df['dx'] = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])
    df['adx'] = df['dx'].rolling(window=14).mean()
    
    # 5. OFI & Imbalance (Missing -> 0)
    df['ofi'] = 0.0
    df['imbalance'] = 0.0
    
    # 6. Normalize Feature Inputs (Existing)
    df['feat_rsi'] = df['rsi'] / 100.0
    df['feat_imbalance'] = df['imbalance']
    df['feat_ofi'] = df['ofi']
    df['feat_ema_dev'] = (df['close'] - df['ema_50']) / df['ema_50']
    df['feat_vol'] = df['volatility']
    df['feat_adx'] = df['adx'] / 100.0
    
    # 7. NEW REGIME-AWARE FEATURES
    # Volatility Regime: current vol vs long-term vol
    df['vol_20'] = df['returns'].rolling(20).std()
    df['vol_100'] = df['returns'].rolling(100).std()
    df['feat_vol_regime'] = df['vol_20'] / (df['vol_100'] + 1e-8)  # >1 = high vol, <1 = low vol
    
    # Trend Strength: EMA crossover signal
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['feat_trend_strength'] = (df['ema_20'] - df['ema_50']) / (df['ema_50'] + 1e-8)
    
    # Recent Momentum
    df['feat_momentum_5'] = df['close'].pct_change(5)   # 5-period momentum
    df['feat_momentum_20'] = df['close'].pct_change(20) # 20-period momentum
    
    # Drop NaNs (update with new features)
    required_features = [
        'feat_rsi', 'feat_imbalance', 'feat_ofi', 'feat_ema_dev', 'feat_vol', 'feat_adx',
        'feat_vol_regime', 'feat_trend_strength', 'feat_momentum_5', 'feat_momentum_20'
    ]
    df.dropna(subset=required_features, inplace=True)
    return df

from sklearn.preprocessing import StandardScaler
from datetime import datetime

class TradingEnv(gym.Env):
    """
    Hybrid RL-SSL Trading Environment.
    """
    metadata = {'render_modes': ['human']}
    
    def __init__(self, data_source, model_path=None, initial_balance=10000.0, spread=0.0005):
        """
        Args:
            data_source: Either a file path (str) or a pandas DataFrame
            model_path: Path to JEPA model (not used, kept for compatibility)
            initial_balance: Starting cash
            spread: Trading spread
        """
        super(TradingEnv, self).__init__()
        
        self.initial_balance = initial_balance
        self.spread = spread
        
        # Load Data
        if isinstance(data_source, str):
            # Path provided
            self.data_path = data_source
            df = pd.read_csv(data_source)
        elif isinstance(data_source, pd.DataFrame):
            # DataFrame provided
            self.data_path = "in_memory"
            df = data_source.copy()
        else:
            raise ValueError("data_source must be a file path (str) or DataFrame")
            
        df = compute_technical_indicators_env(df)
        
        # Prepare Features (updated with regime-aware features)
        feature_cols = [
            'feat_rsi', 'feat_imbalance', 'feat_ofi', 'feat_ema_dev', 'feat_vol', 'feat_adx',
            'feat_vol_regime', 'feat_trend_strength', 'feat_momentum_5', 'feat_momentum_20'
        ]
        self.features_df = df[feature_cols]
        self.prices = df['close'].values
        # Parse timestamp safely
        try:
            self.timestamps = pd.to_datetime(df['timestamp']).values
        except:
             self.timestamps = df['timestamp'].values
        
        # Normalize
        self.scaler = StandardScaler()
        self.features_normalized = self.scaler.fit_transform(self.features_df)
        
        # Save scaler for inference
        import joblib
        joblib.dump(self.scaler, "src/app/models/rl_scaler.pkl")
        
        # Pad for JEPA (needs 12 dims, we now have 10 features)
        padding = np.zeros((self.features_normalized.shape[0], 2))
        self.features_for_jepa = np.hstack([self.features_normalized, padding])
        
        # Load Model
        self.jepa = load_jepa_model()
        self.jepa.eval()
        
        # Define Spaces
        # Obs: [10 Features + 64 Latent] = 74
        self.input_dim = 10 + 64
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(self.input_dim,), dtype=np.float32)
        self.action_space = spaces.Discrete(3) # 0: Neutral, 1: Long, 2: Short
        
        self.current_step = 0
        self.backtester = None
        self.max_steps = len(df) - 1
        
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        
        self.current_step = 0
        self.backtester = Backtester(initial_balance=self.initial_balance, spread_pct=self.spread)
        
        # Risk tracking for reward function
        self.peak_equity = self.initial_balance
        self.return_history = []  # Rolling window for volatility calculation
        
        return self._get_observation(), {}
        
    def _get_observation(self):
        # 1. Features
        features_raw = self.features_normalized[self.current_step] # 6 dims
        jepa_input = self.features_for_jepa[self.current_step] # 12 dims
        
        # 2. Latent State
        with torch.no_grad():
             t_in = torch.FloatTensor(jepa_input).unsqueeze(0)
             latent = self.jepa.context_encoder(t_in).numpy().flatten() # 64 dims
             
        # 3. Concat (6 + 64)
        obs = np.concatenate([features_raw, latent]).astype(np.float32)
        return np.nan_to_num(obs)
        
    def step(self, action):
        done = False
        truncated = False
        
        # 1. Execute Action
        direction = "NEUTRAL"
        if action == 1: direction = "LONG"
        elif action == 2: direction = "SHORT"
        
        current_price = self.prices[self.current_step]
        # timestamp = self.timestamps[self.current_step] 
        # Convert numpy timestamp to datetime if needed, or pass raw
        # signal expects specific types but backtester is flexible
        timestamp = datetime.now() # Mock for speed
        
        signal = Signal(
            timestamp=timestamp,
            symbol="BTC",
            strategy="rl",
            direction=direction,
            strength=1.0,
            confidence=1.0,
            reasoning="RL",
            entry_price=current_price,
            stop_loss=current_price * 0.95 if direction == "LONG" else current_price * 1.05,
            take_profit=current_price * 1.05 if direction == "LONG" else current_price * 0.95,
            trailing_stop_distance=0.0 # Optional
        )
        
        prev_equity = self.backtester._calculate_equity(current_price)
        self.backtester.process_signal(signal, current_price, current_price, current_price, timestamp)
        current_equity = self.backtester._calculate_equity(current_price)
        
        # 2. Risk-Adjusted Reward
        if current_equity <= 0:
            reward = -10.0  # Bankruptcy penalty
            done = True
        else:
            # 2a. Log Return (base signal)
            try:
                log_return = np.log(current_equity / prev_equity)
            except:
                log_return = 0.0
            
            # 2b. Volatility Penalty (rolling std of returns)
            self.return_history.append(log_return)
            if len(self.return_history) > 20:  # Keep last 20 returns
                self.return_history.pop(0)
            
            volatility = np.std(self.return_history) if len(self.return_history) > 1 else 0.0
            
            # 2c. Drawdown Penalty
            self.peak_equity = max(self.peak_equity, current_equity)
            drawdown = (self.peak_equity - current_equity) / self.peak_equity if self.peak_equity > 0 else 0.0
            
            # 2d. Improved Reward Function
            # Core profit signal
            profit_reward = log_return  # Focus on returns
            
            # Transaction cost penalty (0.10% = 0.001 per trade)
            TRANSACTION_COST = 0.001
            transaction_penalty = -TRANSACTION_COST if action != 0 else 0.0
            
            # Reduced risk penalties (less aggressive than before)
            lambda_vol = 0.2  # Reduced from 0.5
            lambda_dd = 0.5   # Reduced from 1.0
            risk_penalty = lambda_vol * volatility + lambda_dd * drawdown
            
            # 2e. Stronger Momentum Alignment Bonus
            # Extract current features (normalized)
            feats = self.features_normalized[self.current_step]
            trend_strength = feats[7]  # feat_trend_strength
            momentum_20 = feats[9]     # feat_momentum_20
            
            # Determine momentum signal
            if trend_strength > 0.01 and momentum_20 > 0:
                momentum_signal = 1  # LONG
            elif trend_strength < -0.01 and momentum_20 < 0:
                momentum_signal = 2  # SHORT
            else:
                momentum_signal = 0  # NEUTRAL
            
            # Stronger alignment incentives
            if action == momentum_signal:
                alignment_bonus = 1.0  # Increased from 0.3
            else:
                alignment_bonus = -0.5  # Increased penalty from -0.1
            
            # Trade frequency penalty (discourage position flipping)
            if not hasattr(self, 'last_action'):
                self.last_action = 0
            
            frequency_penalty = -0.1 if (action != 0 and action != self.last_action) else 0.0
            self.last_action = action
            
            # Final reward
            reward = (profit_reward 
                     + transaction_penalty 
                     - risk_penalty 
                     + alignment_bonus 
                     + frequency_penalty)
            
        # 3. Next Step
        self.current_step += 1
        if self.current_step >= self.max_steps:
            done = True
        
        if not done:
            obs = self._get_observation()
        else:
            obs = np.zeros(self.input_dim, dtype=np.float32)
            
        return obs, reward, done, truncated, {"equity": current_equity}
