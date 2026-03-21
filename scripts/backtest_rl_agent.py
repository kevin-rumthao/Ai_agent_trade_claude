#!/usr/bin/env python3
"""
Backtest the RL Agent and compare against Momentum strategy.

Evaluates:
1. All 20 RL checkpoints (100K to 2M steps)
2. Momentum v3 (our best traditional strategy)
3. Outputs: Return, Sharpe, Max DD, Win Rate, Trade Count, Action Distribution
"""

import os
import sys
import pandas as pd
import numpy as np
import joblib
import torch
from datetime import datetime
from stable_baselines3 import PPO

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from src.app.models.ts_jepa import TS_JEPA
from src.app.utils.data_split import split_data_temporal

# ─── Config ────────────────────────────────────────────────────────────────────
DATA_PATH = "data/BTCUSDT_5Y_1m.csv"
JEPA_MODEL_PATH = "src/app/models/jepa_latest.pth"
SCALER_PATH = "src/app/models/rl_scaler.pkl"
CHECKPOINTS_DIR = "src/app/models/checkpoints/"
INITIAL_BALANCE = 10000.0
SPREAD = 0.0005  # 0.05%
FEE = 0.001  # 0.1% per trade


# ─── Feature Computation (mirrors trading_env.py) ─────────────────────────────
def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute technical features matching training environment."""
    df = df.copy()

    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()

    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # Realized volatility
    df['returns'] = df['close'].pct_change()
    df['volatility'] = df['returns'].rolling(window=14).std() * np.sqrt(14)

    # ADX
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

    # OFI & imbalance (0 for OHLCV data)
    df['ofi'] = 0.0
    df['imbalance'] = 0.0

    # Feature engineering
    df['feat_rsi'] = df['rsi'] / 100.0
    df['feat_imbalance'] = df['imbalance']
    df['feat_ofi'] = df['ofi']
    df['feat_ema_dev'] = (df['close'] - df['ema_50']) / df['ema_50']
    df['feat_vol'] = df['volatility']
    df['feat_adx'] = df['adx'] / 100.0

    # Regime features
    df['vol_20'] = df['returns'].rolling(20).std()
    df['vol_100'] = df['returns'].rolling(100).std()
    df['feat_vol_regime'] = df['vol_20'] / (df['vol_100'] + 1e-8)

    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['feat_trend_strength'] = (df['ema_20'] - df['ema_50']) / (df['ema_50'] + 1e-8)

    df['feat_momentum_5'] = df['close'].pct_change(5)
    df['feat_momentum_20'] = df['close'].pct_change(20)

    required = ['feat_rsi', 'feat_imbalance', 'feat_ofi', 'feat_ema_dev',
                'feat_vol', 'feat_adx', 'feat_vol_regime', 'feat_trend_strength',
                'feat_momentum_5', 'feat_momentum_20']
    df.dropna(subset=required, inplace=True)
    return df


# ─── JEPA Latent Extraction ───────────────────────────────────────────────────
def load_jepa():
    model = TS_JEPA(input_dim=12, embed_dim=64)
    try:
        model.load_state_dict(torch.load(JEPA_MODEL_PATH, map_location='cpu'))
        print(f"✅ JEPA loaded from {JEPA_MODEL_PATH}")
    except Exception as e:
        print(f"⚠️ JEPA not found, using random weights: {e}")
    model.eval()
    return model


def get_observations(df: pd.DataFrame, scaler, jepa_model) -> np.ndarray:
    """Build observation matrix: [10 features + 64 latent] for all rows."""
    feature_cols = ['feat_rsi', 'feat_imbalance', 'feat_ofi', 'feat_ema_dev',
                    'feat_vol', 'feat_adx', 'feat_vol_regime', 'feat_trend_strength',
                    'feat_momentum_5', 'feat_momentum_20']

    features = df[feature_cols].values.astype(np.float32)

    # Scale features
    if scaler is not None:
        features = scaler.transform(features)

    # JEPA latent (batch inference)
    jepa_input = np.zeros((len(df), 12), dtype=np.float32)
    jepa_input[:, :6] = features[:, :6]  # Copy first 6 features
    # Remaining 6 are padding (zeros)

    with torch.no_grad():
        t_input = torch.FloatTensor(jepa_input)
        latent = jepa_model.context_encoder(t_input).numpy()

    obs = np.concatenate([features, latent], axis=1).astype(np.float32)
    return np.nan_to_num(obs)


# ─── Backtest Engine ──────────────────────────────────────────────────────────
def backtest_rl(observations: np.ndarray, prices: np.ndarray, model) -> dict:
    """Run RL backtest and return metrics."""
    balance = INITIAL_BALANCE
    position = 0.0  # BTC held
    entry_price = 0.0
    peak_equity = INITIAL_BALANCE
    trades = []
    equity_curve = []
    actions_taken = {0: 0, 1: 0, 2: 0}  # NEUTRAL, LONG, SHORT

    for i in range(len(observations)):
        obs = observations[i]
        price = prices[i]

        # Get action from model
        action, _ = model.predict(obs, deterministic=True)
        actions_taken[int(action)] += 1

        current_equity = balance + position * price
        equity_curve.append(current_equity)

        if current_equity > peak_equity:
            peak_equity = current_equity

        # Execute action
        if action == 1 and position <= 0:  # LONG (close short, open long)
            if position < 0:
                # Close short
                pnl = (entry_price - price) * abs(position) * (1 - FEE)
                balance += pnl
                trades.append({'type': 'CLOSE_SHORT', 'pnl': pnl, 'price': price})
                position = 0.0

            # Open long
            qty = (balance * 0.95) / price  # Use 95% of balance
            cost = qty * price * FEE
            balance -= (qty * price + cost)
            position = qty
            entry_price = price * (1 + SPREAD)

        elif action == 2 and position >= 0:  # SHORT (close long, open short)
            if position > 0:
                # Close long
                pnl = (price - entry_price) * position * (1 - FEE)
                balance += pnl
                trades.append({'type': 'CLOSE_LONG', 'pnl': pnl, 'price': price})
                position = 0.0

            # Open short (simplified - track notional)
            qty = (balance * 0.95) / price
            cost = qty * price * FEE
            balance -= cost
            position = -qty
            entry_price = price * (1 - SPREAD)

        elif action == 0 and position != 0:  # NEUTRAL (close position)
            if position > 0:
                pnl = (price - entry_price) * position * (1 - FEE)
                balance += (position * price * (1 - FEE))
                trades.append({'type': 'CLOSE_LONG', 'pnl': pnl, 'price': price})
            elif position < 0:
                pnl = (entry_price - price) * abs(position) * (1 - FEE)
                balance += pnl
                trades.append({'type': 'CLOSE_SHORT', 'pnl': pnl, 'price': price})
            position = 0.0

    # Close final position
    final_price = prices[-1]
    if position > 0:
        pnl = (final_price - entry_price) * position * (1 - FEE)
        balance += position * final_price * (1 - FEE)
        trades.append({'type': 'FINAL_CLOSE', 'pnl': pnl, 'price': final_price})
    elif position < 0:
        pnl = (entry_price - final_price) * abs(position) * (1 - FEE)
        balance += pnl
        trades.append({'type': 'FINAL_CLOSE', 'pnl': pnl, 'price': final_price})

    # Calculate metrics
    equity = np.array(equity_curve)
    returns = np.diff(equity) / equity[:-1]
    returns = returns[np.isfinite(returns)]

    total_return = (balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100
    max_dd = 0.0
    peak = equity[0]
    for val in equity:
        if val > peak:
            peak = val
        dd = (peak - val) / peak
        if dd > max_dd:
            max_dd = dd

    winning = [t for t in trades if t['pnl'] > 0]
    losing = [t for t in trades if t['pnl'] <= 0]
    win_rate = len(winning) / len(trades) * 100 if trades else 0

    sharpe = 0.0
    if len(returns) > 1 and np.std(returns) > 0:
        sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(252 * 24 * 60)  # Annualized

    total_trades = len(trades)
    action_total = sum(actions_taken.values())
    action_dist = {
        'NEUTRAL': actions_taken[0] / action_total * 100 if action_total > 0 else 0,
        'LONG': actions_taken[1] / action_total * 100 if action_total > 0 else 0,
        'SHORT': actions_taken[2] / action_total * 100 if action_total > 0 else 0,
    }

    return {
        'final_equity': balance,
        'total_return_pct': total_return,
        'max_drawdown_pct': max_dd * 100,
        'sharpe_ratio': sharpe,
        'total_trades': total_trades,
        'win_rate_pct': win_rate,
        'action_distribution': action_dist,
        'equity_curve': equity_curve,
    }


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("=" * 70)
    print("RL AGENT BACKTEST")
    print("=" * 70)

    # Load data
    print(f"\nLoading data from {DATA_PATH}...")
    df = pd.read_csv(DATA_PATH)
    print(f"Total rows: {len(df):,}")

    # Split: last 90 days for test (out-of-sample)
    train_df, val_df, test_df = split_data_temporal(df, train_pct=0.8, val_pct=0.05)
    print(f"Train: {len(train_df):,} | Val: {len(val_df):,} | Test (OOS): {len(test_df):,}")

    # Compute features on test set
    print("\nComputing features...")
    test_df = compute_features(test_df)
    print(f"Test rows after feature computation: {len(test_df):,}")
    print(f"Test period: {test_df['timestamp'].iloc[0]} to {test_df['timestamp'].iloc[-1]}")

    # Load JEPA
    jepa = load_jepa()

    # Load scaler
    scaler = None
    try:
        scaler = joblib.load(SCALER_PATH)
        print(f"✅ Scaler loaded from {SCALER_PATH}")
    except Exception as e:
        print(f"⚠️ Scaler not found: {e}")

    # Build observations
    print("\nBuilding observation matrix...")
    observations = get_observations(test_df, scaler, jepa)
    prices = test_df['close'].values.astype(np.float64)
    print(f"Observation shape: {observations.shape}")
    print(f"Prices shape: {prices.shape}")

    # Test each checkpoint
    print("\n" + "=" * 70)
    print("CHECKPOINT COMPARISON")
    print("=" * 70)

    results = []

    for steps in range(100000, 2100000, 100000):
        ckpt_path = os.path.join(CHECKPOINTS_DIR, f"rl_agent_{steps}_steps.zip")
        if not os.path.exists(ckpt_path):
            continue

        print(f"\n--- Checkpoint: {steps:,} steps ---")
        try:
            model = PPO.load(ckpt_path, device="cpu")
            metrics = backtest_rl(observations, prices, model)

            print(f"  Return:      {metrics['total_return_pct']:+.2f}%")
            print(f"  Final Eq:    ${metrics['final_equity']:,.2f}")
            print(f"  Max DD:      {metrics['max_drawdown_pct']:.2f}%")
            print(f"  Sharpe:      {metrics['sharpe_ratio']:.2f}")
            print(f"  Trades:      {metrics['total_trades']}")
            print(f"  Win Rate:    {metrics['win_rate_pct']:.1f}%")
            print(f"  Actions:     NEUTRAL={metrics['action_distribution']['NEUTRAL']:.1f}% "
                  f"LONG={metrics['action_distribution']['LONG']:.1f}% "
                  f"SHORT={metrics['action_distribution']['SHORT']:.1f}%")

            results.append({'checkpoint': steps, **metrics})
        except Exception as e:
            print(f"  ❌ Failed to load: {e}")

    # Also test the latest model
    latest_path = os.path.join("src/app/models", "rl_agent_latest.zip")
    if os.path.exists(latest_path):
        print(f"\n--- Latest Model ---")
        try:
            model = PPO.load(latest_path, device="cpu")
            metrics = backtest_rl(observations, prices, model)

            print(f"  Return:      {metrics['total_return_pct']:+.2f}%")
            print(f"  Final Eq:    ${metrics['final_equity']:,.2f}")
            print(f"  Max DD:      {metrics['max_drawdown_pct']:.2f}%")
            print(f"  Sharpe:      {metrics['sharpe_ratio']:.2f}")
            print(f"  Trades:      {metrics['total_trades']}")
            print(f"  Win Rate:    {metrics['win_rate_pct']:.1f}%")
            print(f"  Actions:     NEUTRAL={metrics['action_distribution']['NEUTRAL']:.1f}% "
                  f"LONG={metrics['action_distribution']['LONG']:.1f}% "
                  f"SHORT={metrics['action_distribution']['SHORT']:.1f}%")

            results.append({'checkpoint': 'latest', **metrics})
        except Exception as e:
            print(f"  ❌ Failed to load: {e}")

    # Summary table
    print("\n" + "=" * 70)
    print("SUMMARY TABLE")
    print("=" * 70)
    print(f"{'Checkpoint':<15} {'Return':>10} {'Max DD':>10} {'Sharpe':>10} {'Trades':>8} {'Win%':>8} {'NEU%':>7} {'LONG%':>7} {'SHORT%':>8}")
    print("-" * 95)
    for r in sorted(results, key=lambda x: x['checkpoint']):
        name = str(r['checkpoint'])
        print(f"{name:<15} {r['total_return_pct']:>+9.2f}% {r['max_drawdown_pct']:>9.2f}% "
              f"{r['sharpe_ratio']:>9.2f} {r['total_trades']:>7} {r['win_rate_pct']:>7.1f}% "
              f"{r['action_distribution']['NEUTRAL']:>6.1f}% {r['action_distribution']['LONG']:>6.1f}% "
              f"{r['action_distribution']['SHORT']:>7.1f}%")

    # Save results
    results_df = pd.DataFrame([{k: v for k, v in r.items() if k != 'equity_curve'} for r in results])
    results_df.to_csv("results/rl_backtest_results.csv", index=False)
    print(f"\nResults saved to results/rl_backtest_results.csv")

    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()
