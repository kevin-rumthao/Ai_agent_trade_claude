#!/usr/bin/env python3
"""
Paper Trading Script for RL Agent
Executes the trained RL strategy in a live-simulated environment.
"""

import asyncio
import sys
import os
import argparse
import signal
import pandas as pd
import numpy as np
import torch
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from src.app.config import settings
from src.app.tools.trading_provider import trading_provider
from src.app.tools.binance_tool import KlineEvent
from src.app.rl.trading_env import compute_technical_indicators_env
from src.app.nodes.rl_agent_node import load_rl_model, load_feature_scaler
from src.app.nodes.ts_jepa_node import load_jepa_model
from src.app.models.ts_jepa import TS_JEPA

# Global Run Flag
RUNNING = True

def handle_shutdown(signum, frame):
    global RUNNING
    print("\n⚠️ Shutting down paper trader...")
    RUNNING = False

class RLPaperTrader:
    def __init__(self, symbol="BTCUSDT"):
        self.symbol = symbol
        self.feature_columns = [
            'feat_dist_ema50', 'feat_dist_ema200', 'feat_rsi', 
            'feat_vol', 'feat_adx', 'feat_volume_ratio',
            'feat_vol_regime', 'feat_trend_strength', 'feat_momentum_5', 'feat_momentum_20'
        ]
        
        print("Loading models...")
        self.scaler = load_feature_scaler()
        self.rl_model = load_rl_model()
        self.jepa_model = load_jepa_model()
        
        if not all([self.scaler, self.rl_model, self.jepa_model]):
            raise ValueError("Failed to load one or more required models/scalers.")
            
        print("✅ Models loaded successfully.")
        
    def prepare_features(self, df):
        """mimics TradingEnv feature preparation pipeline"""
        # 1. Compute Indicators
        df = compute_technical_indicators_env(df)
        
        # 2. Extract Feature Columns
        # Note: TradingEnv.compute_technical_indicators_env adds specific columns
        # We need to ensure we map them correctly to what the Scaler expects
        # The scaler was fitted on: 
        # ['feat_dist_ema50', 'feat_dist_ema200', 'feat_rsi', 'feat_vol', 'feat_adx', 'feat_volume_ratio', 
        #  'feat_vol_regime', 'feat_trend_strength', 'feat_momentum_5', 'feat_momentum_20']
        
        # Ensure latest row is validated
        current = df.iloc[-1]
        
        # Check for NaN in latest row
        if current[self.feature_columns].isnull().any():
            print("⚠️ Warning: NaNs in computed features (requires at least 200 candles)")
            return None, None
            
        # 3. Create Feature Vector
        features = df[self.feature_columns].values
        
        # 4. Normalize
        features_normalized = self.scaler.transform(features)
        
        # 5. Prepare JEPA Input (12 dims: 10 features + 2 padding)
        # Assuming TradingEnv logic: hstack([X_norm, np.zeros((N, 2))])
        padding = np.zeros((len(features_normalized), 2))
        jepa_input = np.hstack([features_normalized, padding])
        
        return features_normalized[-1], jepa_input[-1]

    def get_action(self, df):
        """Get RL action for the latest candle"""
        # Prepare Data
        feat_norm, jepa_in = self.prepare_features(df)
        
        if feat_norm is None:
            return 0  # Neutral if data insufficient
            
        # Run World Model (JEPA)
        with torch.no_grad():
            t_in = torch.FloatTensor(jepa_in).unsqueeze(0)  # Add batch dim
            latent = self.jepa_model.context_encoder(t_in).numpy().flatten()
            
        # Construct Observation [Features + Latent]
        obs = np.concatenate([feat_norm, latent]).astype(np.float32)
        
        # Run RL Agent
        # deterministic=True for trading (avoid random exploration noise)
        action, _ = self.rl_model.predict(obs, deterministic=True)
        
        return int(action)

async def main():
    parser = argparse.ArgumentParser(description="Run Paper Trading")
    parser.add_argument("--strategy", type=str, default="rl_agent", choices=["rl_agent", "momentum"], help="Strategy to run")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Symbol to trade")
    parser.add_argument("--interval", type=int, default=15, help="Loop interval in seconds")
    args = parser.parse_args()
    
    print(f"🚀 Starting Paper Trader | Strategy: {args.strategy} | Symbol: {args.symbol}")
    
    # Signals
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    # Initialize
    await trading_provider.initialize()
    
    agent = None
    if args.strategy == "rl_agent":
        agent = RLPaperTrader(args.symbol)
    
    # State tracking
    last_processed_time = None
    
    try:
        while RUNNING:
            loop_start = datetime.now()
            
            # 1. Fetch Data (Need enough for EMAs/Vol - e.g., 500 candles of 15m)
            # We fetch 1m candles and resample to ensure consistency with backtest
            required_1m = 500 * 15 # ~7500 candles
            klines_1m = await trading_provider.get_klines(args.symbol, interval="1m", limit=1000) # Provider might limit this
            
            if not klines_1m:
                print("⚠️ No data received")
                await asyncio.sleep(10)
                continue
                
            # Convert to DF
            df_1m = pd.DataFrame([k.model_dump() for k in klines_1m])
            df_1m['timestamp'] = pd.to_datetime(df_1m['timestamp'])
            df_1m.set_index('timestamp', inplace=True)
            df_1m.sort_index(inplace=True)
            
            # Resample to 15m
            ohlc_dict = {'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'}
            df_15m = df_1m.resample('15min').agg(ohlc_dict).dropna()
            
            if len(df_15m) < 50:
                print(f"⚠️ Insufficient data after resampling: {len(df_15m)} rows")
                await asyncio.sleep(10)
                continue
            
            # Latest candle info
            latest_candle = df_15m.iloc[-1]
            latest_time = df_15m.index[-1]
            close_price = latest_candle['close']
            
            # Only process if we have a NEW closed candle (or update strictly on close)
            # For paper trading, we can run every loop, but actions usually happen on candle close.
            # Here we print status every loop, but maybe only act if new candle?
            # Let's act every loop for now (reactive), or check if latest_time > last_processed_time
            
            print(f"[{loop_start.strftime('%H:%M:%S')}] {args.symbol} M15 Close: {close_price:.2f}")
            
            # 2. Get Strategy Action
            if args.strategy == "rl_agent":
                action = agent.get_action(df_15m)
                
                signal_str = ["NEUTRAL", "LONG", "SHORT"][action]
                print(f"   🤖 RL Signal: {signal_str}")
                
                # Execute? (Simulated)
                # In real paper trading we would place dummy orders or log to file
                # For now just log
                if action != 0:
                    print(f"   ✅ EXECUTING {signal_str} at {close_price}")
            
            # Sleep
            elapsed = (datetime.now() - loop_start).total_seconds()
            sleep_time = max(0, args.interval - elapsed)
            
            if RUNNING:
                await asyncio.sleep(sleep_time)
                
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await trading_provider.close()
        print("Paper trader stopped.")

if __name__ == "__main__":
    asyncio.run(main())
