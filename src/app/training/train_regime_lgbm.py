#!/usr/bin/env python3
"""
Train a LightGBM regime classifier on historical BTCUSDT data.

Regimes:
  TRENDING      — Strong directional move (ADX > 25, EMA crossover)
  RANGING       — Sideways/choppy market (ADX < 20, tight EMA bands)
  HIGH_VOLATILITY — Realised vol > 3% (14-period)
  LOW_VOLATILITY  — Realised vol < 0.5% (breakout coiling)

Training approach:
  - Labels generated with deterministic rules (human-validated thresholds)
  - LightGBM learns to generalise those patterns from 12 features
  - TimeSeriesSplit(5) — strict temporal CV, zero look-ahead

Usage:
  python src/app/training/train_regime_lgbm.py
"""
import os
import sys
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import classification_report, confusion_matrix
from lightgbm import LGBMClassifier

# ─── Paths ────────────────────────────────────────────────────────────────────
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
sys.path.insert(0, project_root)

DATA_PATH  = "data/BTCUSDT_5Y_1m.csv"  # Use largest available dataset
MODEL_PATH = "src/app/models/regime_lgbm.pkl"


# ─── Feature Engineering ──────────────────────────────────────────────────────
def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all 12 features used by the regime classifier."""
    df = df.copy()

    # 1. EMAs
    df["ema_20"]  = df["close"].ewm(span=20,  adjust=False).mean()
    df["ema_50"]  = df["close"].ewm(span=50,  adjust=False).mean()
    df["ema_200"] = df["close"].ewm(span=200, adjust=False).mean()

    # 2. RSI (14)
    delta = df["close"].diff()
    gain  = delta.where(delta > 0, 0).rolling(14).mean()
    loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df["feat_rsi"] = 100 - (100 / (1 + gain / loss.replace(0, 1e-9)))

    # 3. Realised Volatility (14-period annualised)
    df["returns"]  = df["close"].pct_change()
    df["feat_vol"] = df["returns"].rolling(14).std() * np.sqrt(14)

    # 4. ADX (14) — proper implementation
    df["h_l"]   = df["high"]  - df["low"]
    df["h_pc"]  = abs(df["high"] - df["close"].shift(1))
    df["l_pc"]  = abs(df["low"]  - df["close"].shift(1))
    df["tr"]    = df[["h_l", "h_pc", "l_pc"]].max(axis=1)
    df["tr14"]  = df["tr"].rolling(14).sum()

    df["up_move"]   = df["high"] - df["high"].shift(1)
    df["down_move"] = df["low"].shift(1) - df["low"]
    df["plus_dm"]   = np.where((df["up_move"] > df["down_move"]) & (df["up_move"] > 0),   df["up_move"],   0)
    df["minus_dm"]  = np.where((df["down_move"] > df["up_move"]) & (df["down_move"] > 0), df["down_move"], 0)

    df["plus_di"]  = 100 * df["plus_dm"].rolling(14).sum()  / df["tr14"].replace(0, 1e-9)
    df["minus_di"] = 100 * df["minus_dm"].rolling(14).sum() / df["tr14"].replace(0, 1e-9)
    dx             = 100 * abs(df["plus_di"] - df["minus_di"]) / (df["plus_di"] + df["minus_di"]).replace(0, 1e-9)
    df["feat_adx"] = dx.rolling(14).mean() / 100.0  # Normalise to [0, 1]

    # 5. EMA deviation & trend strength
    df["feat_ema_dev"]        = (df["close"] - df["ema_50"]) / df["ema_50"].replace(0, 1e-9)
    df["feat_trend_strength"] = (df["ema_20"] - df["ema_50"]) / df["ema_50"].replace(0, 1e-9)

    # 6. Vol regime (short-term vol / long-term vol)
    df["vol_100"]          = df["returns"].rolling(100).std()
    df["feat_vol_regime"]  = df["feat_vol"] / df["vol_100"].replace(0, 1e-9)

    # 7. Momentum
    df["feat_momentum_5"]  = df["close"].pct_change(5)
    df["feat_momentum_20"] = df["close"].pct_change(20)

    # 8. Sentiment placeholders (neutral — override if CSV has sentiment columns)
    for col, default in [
        ("feat_sentiment_fg",           0.5),
        ("feat_sentiment_funding",       0.0),
        ("feat_sentiment_funding_bias",  0.0),
        ("feat_sentiment_fg_regime",     0.5),
    ]:
        df[col] = df[col] if col in df.columns else default

    return df


FEATURE_COLS = [
    "feat_adx", "feat_rsi", "feat_ema_dev", "feat_vol",
    "feat_vol_regime", "feat_trend_strength",
    "feat_momentum_5", "feat_momentum_20",
    "feat_sentiment_fg", "feat_sentiment_funding",
    "feat_sentiment_funding_bias", "feat_sentiment_fg_regime",
]


# ─── Label Generation ─────────────────────────────────────────────────────────
def label_regimes(df: pd.DataFrame) -> pd.Series:
    """
    Generate regime labels calibrated for 1-minute BTCUSDT bars.

    Priority: HIGH_VOLATILITY > TRENDING > RANGING > LOW_VOLATILITY

    1-min bars have lower per-bar vol, so thresholds are scaled down:
      HIGH_VOLATILITY : realized_vol > 0.005  (strong intra-minute moves)
      TRENDING        : ADX > 20 AND ema_diff > 0.003
      RANGING         : ADX < 18 AND ema_diff < 0.003
      LOW_VOLATILITY  : everything else (catch-all / coiling)
    """
    adx_raw      = df["feat_adx"] * 100
    ema_diff_pct = abs(df["ema_20"] - df["ema_50"]) / df["ema_50"].replace(0, 1e-9)

    conditions = [
        df["feat_vol"] > 0.005,
        (adx_raw > 20) & (ema_diff_pct > 0.003),
        (adx_raw < 18) & (ema_diff_pct < 0.003),
    ]
    choices = ["HIGH_VOLATILITY", "TRENDING", "RANGING"]

    labels = np.select(conditions, choices, default="LOW_VOLATILITY")
    return pd.Series(labels, index=df.index)



# ─── Main ─────────────────────────────────────────────────────────────────────
def train():
    print("=" * 65)
    print("LIGHTGBM REGIME CLASSIFIER — TRAINING")
    print("=" * 65)

    # 1. Load data
    if not os.path.exists(DATA_PATH):
        print(f"❌ Data not found: {DATA_PATH}")
        return
    df = pd.read_csv(DATA_PATH)
    print(f"\n✅ Loaded {len(df):,} rows from {DATA_PATH}")

    # 2. Compute features
    print("   Computing features...")
    df = compute_features(df)

    # Drop NaN rows (from rolling windows)
    required = FEATURE_COLS + ["feat_vol", "feat_adx"]
    df.dropna(subset=required, inplace=True)
    print(f"   Rows after dropna: {len(df):,}")

    # 3. Labels
    df["regime"] = label_regimes(df)
    dist = df["regime"].value_counts()
    print(f"\n   Label distribution:")
    for regime, count in dist.items():
        print(f"     {regime:<20} {count:>7,}  ({count/len(df)*100:.1f}%)")

    X = df[FEATURE_COLS].astype(np.float32)
    y = df["regime"]

    # 4. Temporal cross-validation
    print("\n   Running TimeSeriesSplit(5) cross-validation...")
    tscv    = TimeSeriesSplit(n_splits=5)
    model   = LGBMClassifier(
        n_estimators=500,
        learning_rate=0.05,
        max_depth=6,
        num_leaves=31,
        class_weight="balanced",
        random_state=42,
        verbose=-1,
    )

    fold_accs = []
    for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
        # Fit only on train split — no eval_set to avoid unseen-label errors
        model.fit(X.iloc[train_idx], y.iloc[train_idx])
        acc = model.score(X.iloc[val_idx], y.iloc[val_idx])
        fold_accs.append(acc)
        print(f"     Fold {fold+1}: accuracy = {acc:.3f}")

    print(f"\n   Mean CV accuracy: {np.mean(fold_accs):.3f} ± {np.std(fold_accs):.3f}")

    # 5. Final full-data retrain
    print("\n   Retraining on full dataset for production model...")
    model.fit(X, y)

    # Classification report on full data (in-sample sanity check)
    y_pred = model.predict(X)
    print("\n   In-sample classification report:")
    print(classification_report(y, y_pred, zero_division=0))

    # Feature importance top-5
    importances = pd.Series(model.feature_importances_, index=FEATURE_COLS)
    print("   Top-5 feature importances:")
    for feat, imp in importances.nlargest(5).items():
        print(f"     {feat:<35} {imp:.0f}")

    # 6. Save
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"\n✅ Model saved → {MODEL_PATH}")

    print("\n" + "=" * 65)
    print("TRAINING COMPLETE")
    print("=" * 65)
    print("\nNext: python src/app/training/train_regime_lgbm.py is done.")
    print("Run:  python scripts/run_backtest.py to validate the pipeline.")


if __name__ == "__main__":
    train()
