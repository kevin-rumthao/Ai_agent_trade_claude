"""Regime classification node with downtrend detection."""
from typing import TypedDict
from datetime import datetime

from app.schemas.models import MarketFeatures, MarketRegime
from app.tools.llm_tool import llm_tool


class RegimeState(TypedDict):
    """State for regime classification."""
    features: MarketFeatures | None
    regime: MarketRegime | None
    symbol: str
    timestamp: datetime


async def classify_regime_node(state: RegimeState) -> RegimeState:
    """
    Classify market regime with downtrend detection.

    Regimes:
    - TRENDING_UP: Price > EMA200, EMA9 > EMA50, ADX > 20
    - TRENDING_DOWN: Price < EMA200, EMA50 < EMA200, ADX > 20
    - RANGING: EMAs compressed, ADX < 20
    - HIGH_VOLATILITY: Realized vol > 0.03
    - LOW_VOLATILITY: Realized vol < 0.01
    - UNKNOWN: Insufficient data
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

    # Rule-based classification
    regime_str = "UNKNOWN"
    confidence = 0.0
    ambiguity = 1.0
    volatility_percentile: float | None = None
    trend_strength: float | None = None

    price = features.price
    ema_9 = features.ema_9
    ema_50 = features.ema_50
    ema_200 = features.ema_200
    adx = features.adx
    rsi = features.rsi
    vol = features.realized_volatility or features.atr or 0.0

    has_trend = ema_9 is not None and ema_50 is not None

    # ─── Step 1: Volatility Check ─────────────────────────────────────────
    if vol > 0.03:
        regime_str = "HIGH_VOLATILITY"
        confidence = 0.7
        ambiguity = 0.3
        volatility_percentile = 0.8
    elif vol < 0.005:
        regime_str = "LOW_VOLATILITY"
        confidence = 0.7
        ambiguity = 0.3
        volatility_percentile = 0.2

    # ─── Step 2: Trend Detection ──────────────────────────────────────────
    if has_trend and regime_str in ("UNKNOWN", "LOW_VOLATILITY"):
        ema_9_val = ema_9 or 0.0
        ema_50_val = ema_50 or 0.0
        ema_200_val = ema_200 or 0.0

        # Calculate EMA separations
        ema_diff_pct = abs(ema_9_val - ema_50_val) / ema_50_val if ema_50_val > 0 else 0.0
        price_vs_ema200 = (price - ema_200_val) / ema_200_val if ema_200_val > 0 else 0.0

        # ADX trend strength
        strong_adx = adx is not None and adx > 20
        moderate_adx = adx is not None and adx > 15

        # Long-term trend filter using EMA 200
        is_above_ema200 = ema_200_val > 0 and price > ema_200_val
        is_below_ema200 = ema_200_val > 0 and price < ema_200_val
        ema50_below_ema200 = ema_200_val > 0 and ema_50_val < ema_200_val
        ema50_above_ema200 = ema_200_val > 0 and ema_50_val > ema_200_val

        # ─── DOWNTREND Detection (NEW) ────────────────────────────────
        # Key signals:
        # 1. Price below EMA 200 (bear market structure)
        # 2. EMA 50 below EMA 200 (medium-term trend confirmed bearish)
        # 3. EMA 9 < EMA 50 (short-term momentum bearish)
        # 4. ADX showing trend strength (not just chop)
        if is_below_ema200 and ema50_below_ema200 and ema_9_val < ema_50_val:
            if strong_adx:
                regime_str = "TRENDING"
                trend_strength = -ema_diff_pct  # Negative for downtrend
                confidence = 0.80
                ambiguity = 0.20
            elif moderate_adx:
                regime_str = "TRENDING"
                trend_strength = -ema_diff_pct
                confidence = 0.65
                ambiguity = 0.35

        # ─── UPTREND Detection ────────────────────────────────────────
        elif is_above_ema200 and ema50_above_ema200 and ema_9_val > ema_50_val:
            if strong_adx:
                regime_str = "TRENDING"
                trend_strength = ema_diff_pct  # Positive for uptrend
                confidence = 0.80
                ambiguity = 0.20
            elif moderate_adx:
                regime_str = "TRENDING"
                trend_strength = ema_diff_pct
                confidence = 0.65
                ambiguity = 0.35

        # ─── Moderate Trend (less strict threshold) ───────────────────
        # Wider threshold: 0.5% EMA separation instead of 2%
        elif ema_diff_pct > 0.005:
            if ema_9_val > ema_50_val:
                regime_str = "TRENDING"
                trend_strength = ema_diff_pct
                confidence = 0.60
                ambiguity = 0.40
            else:
                regime_str = "TRENDING"
                trend_strength = -ema_diff_pct
                confidence = 0.60
                ambiguity = 0.40

        # ─── RANGING ──────────────────────────────────────────────────
        elif ema_diff_pct < 0.005:
            regime_str = "RANGING"
            confidence = 0.65
            ambiguity = 0.35
            trend_strength = 0.0

    # ─── Step 3: Sentiment Overlay ─────────────────────────────────────────
    regime = MarketRegime(
        regime=regime_str,  # type: ignore
        confidence=confidence,
        volatility_percentile=volatility_percentile,
        trend_strength=trend_strength,
        timestamp=datetime.now()
    )
    regime = _apply_sentiment_overlay(regime, features)

    # ─── Step 4: LLM Fallback ──────────────────────────────────────────────
    if regime.confidence < 0.55:
        try:
            llm_regime = await llm_tool.classify_regime_with_llm(features, ambiguity)
            if llm_regime.confidence > regime.confidence:
                regime = _apply_sentiment_overlay(llm_regime, features)
                print(f"  🤖 LLM override: {llm_regime.regime} (conf: {llm_regime.confidence:.2f})")
        except Exception as e:
            print(f"  ⚠️ LLM fallback failed: {e}")

    return {
        **state,
        "regime": regime
    }


def _apply_sentiment_overlay(regime: MarketRegime, features: MarketFeatures) -> MarketRegime:
    """
    Modify regime/confidence based on sentiment data.

    Logic:
    - Extreme Fear + TRENDING (with negative trend strength) → Boost DOWN confidence
    - Extreme Fear + RANGING → Boost confidence for mean reversion BUY
    - Extreme Greed + TRENDING → Caution (crowded trade)
    - Negative funding + uptrend → Boost (short squeeze potential)
    - Positive funding + downtrend → Boost (long squeeze potential)
    """
    fg = features.sentiment_fear_greed  # 0-1
    funding = features.sentiment_funding_bias  # -1 to 1

    if fg is None:
        return regime

    adjustment = 0.0

    # ─── Extreme Fear ──────────────────────────────────────────────────
    if fg < 0.2:
        if regime.regime == "TRENDING" and regime.trend_strength and regime.trend_strength < 0:
            # Extreme fear + downtrend = strong bearish conviction
            adjustment += 0.15
            print(f"  📊 Sentiment: Extreme Fear + DOWNTREND → +15% confidence")
        elif regime.regime == "RANGING":
            # Extreme fear + ranging = contrarian buy opportunity
            adjustment += 0.10
            print(f"  📊 Sentiment: Extreme Fear + RANGING → +10% confidence (contrarian)")

    # ─── Extreme Greed ─────────────────────────────────────────────────
    elif fg > 0.8:
        if regime.regime == "TRENDING" and regime.trend_strength and regime.trend_strength > 0:
            # Extreme greed + uptrend = crowded long, caution
            adjustment -= 0.15
            print(f"  📊 Sentiment: Extreme Greed + UPTREND → -15% confidence (crowded)")

    # ─── Funding Rate ──────────────────────────────────────────────────
    if funding is not None:
        if funding < -0.5 and regime.regime == "TRENDING" and regime.trend_strength and regime.trend_strength > 0:
            # Short-heavy funding + uptrend = squeeze fuel
            adjustment += 0.10
            print(f"  📊 Sentiment: Short-heavy funding + UPTREND → +10% confidence")
        elif funding > 0.5 and regime.regime == "TRENDING" and regime.trend_strength and regime.trend_strength < 0:
            # Long-heavy funding + downtrend = long squeeze incoming
            adjustment += 0.10
            print(f"  📊 Sentiment: Long-heavy funding + DOWNTREND → +10% confidence")

    new_confidence = max(0.1, min(1.0, regime.confidence + adjustment))
    if abs(adjustment) > 0.01:
        regime.confidence = new_confidence

    return regime
