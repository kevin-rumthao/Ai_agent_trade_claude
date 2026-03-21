"""Regime classification node powered by LightGBM."""
import os
import joblib
import numpy as np
from typing import TypedDict
from datetime import datetime

from app.schemas.models import MarketFeatures, MarketRegime


# ─── Model Cache ──────────────────────────────────────────────────────────────
_lgbm_model = None
MODEL_PATH   = "src/app/models/regime_lgbm.pkl"

# Feature order MUST match train_regime_lgbm.py FEATURE_COLS exactly
FEATURE_COLS = [
    "feat_adx", "feat_rsi", "feat_ema_dev", "feat_vol",
    "feat_vol_regime", "feat_trend_strength",
    "feat_momentum_5", "feat_momentum_20",
    "feat_sentiment_fg", "feat_sentiment_funding",
    "feat_sentiment_funding_bias", "feat_sentiment_fg_regime",
]


def load_lgbm():
    """Load LightGBM model (cached after first call)."""
    global _lgbm_model
    if _lgbm_model is not None:
        return _lgbm_model
    if not os.path.exists(MODEL_PATH):
        print(f"⚠️  Regime model not found at {MODEL_PATH}. "
              f"Run: python src/app/training/train_regime_lgbm.py")
        return None
    _lgbm_model = joblib.load(MODEL_PATH)
    print(f"✅ LightGBM regime model loaded from {MODEL_PATH}")
    return _lgbm_model


def _build_feature_vector(f: MarketFeatures) -> list[float]:
    """
    Build the 12-dim feature vector from a MarketFeatures object.
    Mirrors the feature columns in train_regime_lgbm.py.
    Safe defaults used when a feature is None.
    """
    # EMA-based derived values
    ema_50  = f.ema_50  or 0.0
    ema_20  = getattr(f, "ema_20",  None) or 0.0
    price   = f.price   or 0.0
    vol_14  = f.realized_volatility or 0.0

    ema_dev        = (price - ema_50) / ema_50 if ema_50 else 0.0
    trend_strength = (ema_20 - ema_50) / ema_50 if ema_50 else 0.0

    # Vol regime: short-term / long-term vol  (approximated from feat_vol_regime if present)
    vol_regime = getattr(f, "vol_regime", None) or 1.0

    # Momentum
    momentum_5  = getattr(f, "momentum_5",  None) or 0.0
    momentum_20 = getattr(f, "momentum_20", None) or 0.0

    # Sentiment (neutral defaults)
    sentiment_fg      = f.sentiment_fear_greed   if hasattr(f, "sentiment_fear_greed")   and f.sentiment_fear_greed   is not None else 0.5
    sentiment_funding = f.sentiment_funding_rate  if hasattr(f, "sentiment_funding_rate") and f.sentiment_funding_rate is not None else 0.0
    sentiment_bias    = f.sentiment_funding_bias  if hasattr(f, "sentiment_funding_bias") and f.sentiment_funding_bias is not None else 0.0
    sentiment_fg_reg  = f.sentiment_fg_regime     if hasattr(f, "sentiment_fg_regime")    and f.sentiment_fg_regime    is not None else 0.5

    return [
        (f.adx / 100.0) if f.adx else 0.0,     # feat_adx (normalised)
        (f.rsi / 100.0) if f.rsi else 0.5,     # feat_rsi (normalised)
        ema_dev,                                # feat_ema_dev
        vol_14,                                 # feat_vol
        vol_regime,                             # feat_vol_regime
        trend_strength,                         # feat_trend_strength
        momentum_5,                             # feat_momentum_5
        momentum_20,                            # feat_momentum_20
        sentiment_fg,                           # feat_sentiment_fg
        sentiment_funding,                      # feat_sentiment_funding
        sentiment_bias,                         # feat_sentiment_funding_bias
        sentiment_fg_reg,                       # feat_sentiment_fg_regime
    ]


# ─── State ────────────────────────────────────────────────────────────────────
class RegimeState(TypedDict):
    features: MarketFeatures | None
    regime: MarketRegime | None
    symbol: str
    timestamp: datetime


# ─── Node ─────────────────────────────────────────────────────────────────────
async def classify_regime_node(state: RegimeState) -> RegimeState:
    """
    Classify market regime using the LightGBM model.

    Regimes:
      TRENDING        — Strong directional move
      RANGING         — Sideways / mean-reverting
      HIGH_VOLATILITY — Extreme vol, reduce exposure
      LOW_VOLATILITY  — Coiling, breakout expected

    Falls back to RANGING (confidence 0.3) if model unavailable.
    """
    features = state.get("features")

    if not features:
        return {
            **state,
            "regime": MarketRegime(
                regime="UNKNOWN",
                confidence=0.0,
                timestamp=datetime.now()
            )
        }

    model = load_lgbm()

    if model is None:
        # Graceful degradation: no model trained yet
        regime = MarketRegime(
            regime="RANGING",
            confidence=0.3,
            timestamp=datetime.now()
        )
        print("⚠️  No regime model — defaulting to RANGING (0.3 confidence)")
        return {**state, "regime": regime}

    # Build feature vector & run inference
    feature_vec = _build_feature_vector(features)
    feature_arr = np.array(feature_vec, dtype=np.float32).reshape(1, -1)

    proba      = model.predict_proba(feature_arr)[0]
    regime_idx = int(proba.argmax())
    regime_str = model.classes_[regime_idx]
    confidence = float(proba[regime_idx])

    # Derive trend_strength for sentiment overlay compatibility
    ema_50  = features.ema_50 or 0.0
    ema_20  = getattr(features, "ema_20", None) or 0.0
    trend_strength = (ema_20 - ema_50) / ema_50 if ema_50 else None

    regime = MarketRegime(
        regime=regime_str,          # type: ignore
        confidence=confidence,
        trend_strength=trend_strength,
        timestamp=datetime.now()
    )

    # Apply sentiment overlay (fine-tunes confidence — existing logic kept)
    regime = _apply_sentiment_overlay(regime, features)

    print(f"📊 Regime: {regime.regime} (confidence: {regime.confidence:.2f}) "
          f"[proba: {dict(zip(model.classes_, proba.round(2)))}]")

    return {**state, "regime": regime}


# ─── Sentiment Overlay (unchanged from original) ──────────────────────────────
def _apply_sentiment_overlay(regime: MarketRegime, features: MarketFeatures) -> MarketRegime:
    """
    Fine-tune regime confidence based on sentiment signals.

    Rules:
    - Extreme Fear + DOWNTREND   → +15% confidence (bearish conviction)
    - Extreme Fear + RANGING     → +10% confidence (contrarian buy zone)
    - Extreme Greed + UPTREND    → -15% confidence (crowded long, caution)
    - Short-heavy funding + UP   → +10% confidence (short squeeze fuel)
    - Long-heavy funding + DOWN  → +10% confidence (long squeeze risk)
    """
    fg      = features.sentiment_fear_greed  if hasattr(features, "sentiment_fear_greed")  else None
    funding = features.sentiment_funding_bias if hasattr(features, "sentiment_funding_bias") else None

    if fg is None:
        return regime

    adjustment = 0.0

    if fg < 0.2:
        if regime.regime == "TRENDING" and regime.trend_strength and regime.trend_strength < 0:
            adjustment += 0.15
            print("  📊 Sentiment: Extreme Fear + DOWNTREND → +15% confidence")
        elif regime.regime == "RANGING":
            adjustment += 0.10
            print("  📊 Sentiment: Extreme Fear + RANGING → +10% confidence (contrarian)")
    elif fg > 0.8:
        if regime.regime == "TRENDING" and regime.trend_strength and regime.trend_strength > 0:
            adjustment -= 0.15
            print("  📊 Sentiment: Extreme Greed + UPTREND → -15% confidence (crowded)")

    if funding is not None:
        if funding < -0.5 and regime.regime == "TRENDING" and regime.trend_strength and regime.trend_strength > 0:
            adjustment += 0.10
            print("  📊 Sentiment: Short-heavy funding + UPTREND → +10% confidence")
        elif funding > 0.5 and regime.regime == "TRENDING" and regime.trend_strength and regime.trend_strength < 0:
            adjustment += 0.10
            print("  📊 Sentiment: Long-heavy funding + DOWNTREND → +10% confidence")

    if abs(adjustment) > 0.01:
        regime.confidence = float(np.clip(regime.confidence + adjustment, 0.1, 1.0))

    return regime
