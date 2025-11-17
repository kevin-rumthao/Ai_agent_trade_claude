"""Regime classification node."""
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
    Classify market regime using rule-based approach with LLM fallback.

    Rules:
    1. Check volatility percentile
    2. Check trend strength (EMA relationship)
    3. If ambiguity > 0.2, call LLM
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

    # Check if we have enough features
    has_volatility = features.atr is not None or features.realized_volatility is not None
    has_trend = features.ema_9 is not None and features.ema_50 is not None

    if has_volatility:
        # Simplified volatility classification
        vol = features.realized_volatility or features.atr or 0.0

        # Estimate percentile (simplified - would need historical data)
        if vol > 0.03:  # High volatility threshold
            regime_str = "HIGH_VOLATILITY"
            confidence = 0.7
            ambiguity = 0.3
            volatility_percentile = 0.8
        elif vol < 0.01:  # Low volatility threshold
            regime_str = "LOW_VOLATILITY"
            confidence = 0.7
            ambiguity = 0.3
            volatility_percentile = 0.2

    if has_trend and regime_str == "UNKNOWN":
        # Trend classification based on EMA crossover
        ema_9 = features.ema_9 or 0.0
        ema_50 = features.ema_50 or 0.0
        price = features.price

        # Calculate trend strength
        if ema_50 > 0:
            trend_strength = abs(ema_9 - ema_50) / ema_50

        if ema_9 > ema_50 * 1.02:  # Strong uptrend
            regime_str = "TRENDING"
            confidence = 0.75
            ambiguity = 0.25
        elif ema_9 < ema_50 * 0.98:  # Strong downtrend
            regime_str = "TRENDING"
            confidence = 0.75
            ambiguity = 0.25
        elif abs(ema_9 - ema_50) / ema_50 < 0.005:  # EMAs close together
            regime_str = "RANGING"
            confidence = 0.65
            ambiguity = 0.35
        else:
            # Uncertain
            ambiguity = 0.5
            confidence = 0.5

    # If ambiguity is high, call LLM
    if ambiguity > 0.2 and features:
        try:
            regime = await llm_tool.classify_regime_with_llm(features, ambiguity)
            return {
                **state,
                "regime": regime
            }
        except Exception as e:
            print(f"LLM classification failed: {e}")
            # Fall through to rule-based result

    # Return rule-based classification
    regime = MarketRegime(
        regime=regime_str,  # type: ignore
        confidence=confidence,
        volatility_percentile=volatility_percentile,
        trend_strength=trend_strength,
        timestamp=datetime.now()
    )

    return {
        **state,
        "regime": regime
    }

