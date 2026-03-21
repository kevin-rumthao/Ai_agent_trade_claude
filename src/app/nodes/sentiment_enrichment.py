"""Sentiment enrichment node for the trading pipeline.

Fetches sentiment data (Fear & Greed, Funding Rate) and merges
it into the MarketFeatures for downstream strategy decisions.
"""
from datetime import datetime
from typing import TypedDict
from app.tools.sentiment_tool import sentiment_tool
from app.schemas.models import MarketFeatures


class SentimentState(TypedDict):
    """State containing features to enrich with sentiment."""
    features: MarketFeatures | None
    sentiment_fear_greed: float | None
    sentiment_funding_rate: float | None


async def enrich_sentiment_node(state: SentimentState) -> SentimentState:
    """
    LangGraph Node: Fetch sentiment and attach to features.

    Runs in parallel with regime classification — sentiment is an
    overlay, not a dependency. If fetch fails, pipeline continues
    with neutral sentiment defaults.
    """
    features = state.get("features")
    if not features:
        return state

    symbol = state.get("symbol", "BTCUSDT")

    try:
        # Fetch sentiment snapshot (non-blocking, has timeout via aiohttp)
        sentiment = await sentiment_tool.get_sentiment_snapshot(symbol)
        sentiment_dict = sentiment_tool.to_feature_dict(sentiment)

        # Attach to features
        features.sentiment_fear_greed = sentiment_dict["sentiment_fear_greed"]
        features.sentiment_funding_rate = sentiment_dict["sentiment_funding_rate"]
        features.sentiment_funding_bias = sentiment_dict["sentiment_funding_bias"]
        features.sentiment_fg_regime = sentiment_dict["sentiment_fg_regime"]

        fg_val = sentiment.fear_greed_value or 50
        fg_label = sentiment.fg_regime or "NEUTRAL"
        fr = sentiment.funding_rate or 0
        fr_bias = sentiment.funding_bias or "NEUTRAL"

        print(f"📊 Sentiment: Fear&Greed={fg_val:.0f} ({fg_label}) | "
              f"Funding={fr*100:.4f}% ({fr_bias})")

    except Exception as e:
        print(f"⚠️ Sentiment fetch failed, using defaults: {e}")
        # Defaults (neutral)
        features.sentiment_fear_greed = 0.5
        features.sentiment_funding_rate = 0.0
        features.sentiment_funding_bias = 0.0
        features.sentiment_fg_regime = 0.5

    return {
        **state,
        "features": features,
        "sentiment_fear_greed": features.sentiment_fear_greed,
        "sentiment_funding_rate": features.sentiment_funding_rate,
    }
