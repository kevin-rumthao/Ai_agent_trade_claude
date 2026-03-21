"""Sentiment data aggregation tool.

Fetches market sentiment indicators from multiple free sources:
- Crypto Fear & Greed Index (alternative.me)
- Binance Funding Rates
- Binance Open Interest
"""
import ssl
import certifi
import aiohttp
import asyncio
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SentimentData:
    """Aggregated sentiment snapshot."""
    timestamp: datetime
    symbol: str

    # Fear & Greed Index (0-100, higher = more greedy)
    fear_greed_value: Optional[float] = None      # 0-100
    fear_greed_label: Optional[str] = None         # "Extreme Fear" ... "Extreme Greed"

    # Funding Rate (per 8h interval)
    funding_rate: Optional[float] = None           # e.g., 0.0001 = 0.01% longs pay shorts
    funding_rate_8h_pct: Optional[float] = None    # as percentage

    # Open Interest
    open_interest: Optional[float] = None          # BTC value
    open_interest_usd: Optional[float] = None      # USD value
    oi_change_24h_pct: Optional[float] = None      # 24h OI change %

    # Derived signals
    funding_bias: Optional[str] = None             # "LONG_HEAVY", "SHORT_HEAVY", "NEUTRAL"
    fg_regime: Optional[str] = None                # "EXTREME_FEAR", "FEAR", "NEUTRAL", "GREED", "EXTREME_GREED"


class SentimentTool:
    """Fetches and aggregates sentiment data from free sources."""

    FNG_URL = "https://api.alternative.me/fng/"
    BINANCE_FUNDING_URL = "https://fapi.binance.com/fapi/v1/fundingRate"
    BINANCE_OI_URL = "https://fapi.binance.com/fapi/v1/openInterest"
    BINANCE_OI_STATS_URL = "https://fapi.binance.com/fapi/v1/openInterest/statistics"

    def __init__(self) -> None:
        self._ssl_context = ssl.create_default_context(cafile=certifi.where())

    async def _fetch_json(self, url: str, params: Optional[dict] = None) -> Optional[dict | list]:
        """Fetch JSON from URL with SSL."""
        connector = aiohttp.TCPConnector(ssl=self._ssl_context)
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    return None
        except Exception as e:
            print(f"⚠️ Sentiment fetch error ({url}): {e}")
            return None

    async def get_fear_greed(self) -> tuple[Optional[float], Optional[str]]:
        """Fetch latest Fear & Greed Index."""
        data = await self._fetch_json(self.FNG_URL, {"limit": 1})
        if data and "data" in data and len(data["data"]) > 0:
            entry = data["data"][0]
            return float(entry["value"]), entry["value_classification"]
        return None, None

    async def get_fear_greed_history(self, days: int = 90) -> list[dict]:
        """Fetch historical Fear & Greed data for backtesting."""
        data = await self._fetch_json(self.FNG_URL, {"limit": days, "format": "json"})
        if data and "data" in data:
            return [
                {
                    "timestamp": datetime.fromtimestamp(int(d["timestamp"])),
                    "value": float(d["value"]),
                    "label": d["value_classification"]
                }
                for d in data["data"]
            ]
        return []

    async def get_funding_rate(self, symbol: str = "BTCUSDT") -> Optional[float]:
        """Fetch latest funding rate from Binance."""
        data = await self._fetch_json(
            self.BINANCE_FUNDING_URL,
            {"symbol": symbol, "limit": 1}
        )
        if data and len(data) > 0:
            return float(data[0]["fundingRate"])
        return None

    async def get_funding_history(self, symbol: str = "BTCUSDT", limit: int = 30) -> list[dict]:
        """Fetch funding rate history for backtesting."""
        data = await self._fetch_json(
            self.BINANCE_FUNDING_URL,
            {"symbol": symbol, "limit": limit}
        )
        if data:
            return [
                {
                    "timestamp": datetime.fromtimestamp(d["fundingTime"] / 1000),
                    "rate": float(d["fundingRate"]),
                    "mark_price": float(d["markPrice"])
                }
                for d in data
            ]
        return []

    async def get_open_interest(self, symbol: str = "BTCUSDT") -> Optional[float]:
        """Fetch current open interest from Binance."""
        data = await self._fetch_json(
            self.BINANCE_OI_URL,
            {"symbol": symbol}
        )
        if data and "openInterest" in data:
            return float(data["openInterest"])
        return None

    def classify_fear_greed(self, value: float) -> str:
        """Classify Fear & Greed value into regime."""
        if value <= 20:
            return "EXTREME_FEAR"
        elif value <= 40:
            return "FEAR"
        elif value <= 60:
            return "NEUTRAL"
        elif value <= 80:
            return "GREED"
        else:
            return "EXTREME_GREED"

    def classify_funding_bias(self, rate: float) -> str:
        """Classify funding rate bias."""
        if rate > 0.0005:  # > 0.05% per 8h = longs paying shorts (crowded longs)
            return "LONG_HEAVY"
        elif rate < -0.0005:  # < -0.05% = shorts paying longs (crowded shorts)
            return "SHORT_HEAVY"
        else:
            return "NEUTRAL"

    async def get_sentiment_snapshot(self, symbol: str = "BTCUSDT") -> SentimentData:
        """Fetch all sentiment data in parallel."""
        fg_result, funding, oi = await asyncio.gather(
            self.get_fear_greed(),
            self.get_funding_rate(symbol),
            self.get_open_interest(symbol),
            return_exceptions=True
        )

        # Handle gather results
        if isinstance(fg_result, tuple):
            fg_value, fg_label = fg_result
        else:
            fg_value, fg_label = None, None

        if isinstance(funding, Exception):
            funding = None
        if isinstance(oi, Exception):
            oi = None

        now = datetime.now()

        return SentimentData(
            timestamp=now,
            symbol=symbol,
            fear_greed_value=fg_value,
            fear_greed_label=fg_label,
            funding_rate=funding,
            funding_rate_8h_pct=funding * 100 if funding else None,
            open_interest=oi,
            fg_regime=self.classify_fear_greed(fg_value) if fg_value else None,
            funding_bias=self.classify_funding_bias(funding) if funding else None,
        )

    def to_feature_dict(self, sentiment: SentimentData) -> dict:
        """Convert sentiment to feature dict for MarketFeatures."""
        # Normalize Fear & Greed to 0-1
        fg_normalized = sentiment.fear_greed_value / 100.0 if sentiment.fear_greed_value else 0.5

        # Funding rate as percentage (already small number)
        funding = sentiment.funding_rate if sentiment.funding_rate else 0.0

        # Encode FG regime as numeric
        fg_regime_map = {
            "EXTREME_FEAR": 0.0,
            "FEAR": 0.25,
            "NEUTRAL": 0.5,
            "GREED": 0.75,
            "EXTREME_GREED": 1.0,
        }
        fg_regime_num = fg_regime_map.get(sentiment.fg_regime, 0.5) if sentiment.fg_regime else 0.5

        # Funding bias as numeric (-1 to 1)
        funding_bias_map = {
            "SHORT_HEAVY": -1.0,
            "NEUTRAL": 0.0,
            "LONG_HEAVY": 1.0,
        }
        funding_bias_num = funding_bias_map.get(sentiment.funding_bias, 0.0) if sentiment.funding_bias else 0.0

        return {
            "sentiment_fear_greed": fg_normalized,
            "sentiment_funding_rate": funding,
            "sentiment_funding_bias": funding_bias_num,
            "sentiment_fg_regime": fg_regime_num,
        }


# Global instance
sentiment_tool = SentimentTool()
