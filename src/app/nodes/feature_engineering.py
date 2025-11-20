"""Feature engineering node for computing technical indicators."""
from typing import TypedDict
from datetime import datetime
import numpy as np
from collections import deque

from app.schemas.events import TradeEvent, OrderbookUpdate, KlineEvent
from app.schemas.models import MarketFeatures
from app.config import settings


class FeatureState(TypedDict):
    """State for feature engineering."""
    trades: list[TradeEvent]
    orderbook: OrderbookUpdate | None
    klines: list[KlineEvent]
    features: MarketFeatures | None
    symbol: str
    timestamp: datetime


class FeatureEngine:
    """Stateful feature computation engine."""

    def __init__(self) -> None:
        self.ema_9_buffer: deque[float] = deque(maxlen=settings.ema_short_period * 2)
        self.ema_50_buffer: deque[float] = deque(maxlen=settings.ema_long_period * 2)
        
        # Ensure price buffer is large enough for Bollinger Bands and Volatility
        max_price_lookback = max(settings.volatility_lookback, settings.bollinger_period)
        self.price_buffer: deque[float] = deque(maxlen=max_price_lookback)
        
        # Ensure close buffer is large enough for RSI
        max_close_lookback = max(settings.atr_period, settings.rsi_period + 1)
        self.high_buffer: deque[float] = deque(maxlen=settings.atr_period)
        self.low_buffer: deque[float] = deque(maxlen=settings.atr_period)
        self.close_buffer: deque[float] = deque(maxlen=max_close_lookback)

        self.ema_9: float | None = None
        self.ema_50: float | None = None

    def compute_ema(self, prices: list[float], period: int) -> float | None:
        """Compute Exponential Moving Average."""
        if len(prices) < period:
            return None

        multiplier = 2.0 / (period + 1)
        ema = prices[0]

        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))

        return ema

    def update_ema(self, price: float) -> None:
        """Update EMAs incrementally."""
        self.ema_9_buffer.append(price)
        self.ema_50_buffer.append(price)

        if len(self.ema_9_buffer) >= settings.ema_short_period:
            self.ema_9 = self.compute_ema(list(self.ema_9_buffer), settings.ema_short_period)

        if len(self.ema_50_buffer) >= settings.ema_long_period:
            self.ema_50 = self.compute_ema(list(self.ema_50_buffer), settings.ema_long_period)

    def compute_atr(self) -> float | None:
        """Compute Average True Range."""
        if len(self.high_buffer) < settings.atr_period:
            return None

        highs = list(self.high_buffer)
        lows = list(self.low_buffer)
        closes = list(self.close_buffer)

        true_ranges: list[float] = []

        for i in range(1, len(highs)):
            high_low = highs[i] - lows[i]
            high_close = abs(highs[i] - closes[i-1])
            low_close = abs(lows[i] - closes[i-1])
            true_ranges.append(max(high_low, high_close, low_close))

        return sum(true_ranges) / len(true_ranges) if true_ranges else None

    def compute_realized_volatility(self) -> float | None:
        """Compute realized volatility from recent prices."""
        if len(self.price_buffer) < 2:
            return None

        prices = list(self.price_buffer)
        returns = [
            (prices[i] - prices[i-1]) / prices[i-1]
            for i in range(1, len(prices))
        ]

        if not returns:
            return None

        return float(np.std(returns)) * np.sqrt(len(returns))

    def compute_vwap(self, trades: list[TradeEvent]) -> float | None:
        """Compute Volume Weighted Average Price."""
        if not trades:
            return None

        total_volume = sum(t.quantity for t in trades)
        if total_volume == 0:
            return None

        vwap = sum(t.price * t.quantity for t in trades) / total_volume
        return vwap

    def compute_rsi(self, prices: list[float], period: int = 14) -> float | None:
        """Compute Relative Strength Index."""
        if len(prices) < period + 1:
            return None

        gains = []
        losses = []

        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change >= 0:
                gains.append(change)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(change))

        # Simple average for first step (could use EMA for smoother RSI)
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi

    def compute_bollinger_bands(
        self, prices: list[float], period: int = 20, std_dev: float = 2.0
    ) -> tuple[float, float, float] | None:
        """Compute Bollinger Bands (Upper, Mid, Lower)."""
        if len(prices) < period:
            return None

        recent_prices = prices[-period:]
        sma = sum(recent_prices) / period
        std = float(np.std(recent_prices))

        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)

        return upper, sma, lower


# Global feature engine instance
feature_engine = FeatureEngine()


async def compute_features_node(state: FeatureState) -> FeatureState:
    """
    Compute technical features from market data.

    Features computed:
    - EMA(9), EMA(50)
    - ATR
    - Realized volatility
    - Orderbook imbalance
    - VWAP
    """
    klines = state.get("klines", [])
    orderbook = state.get("orderbook")
    trades = state.get("trades", [])
    symbol = state.get("symbol", settings.symbol)

    # Get current price
    current_price = 0.0
    if klines:
        current_price = klines[-1].close
    elif orderbook and orderbook.get_mid_price():
        current_price = orderbook.get_mid_price() or 0.0
    elif trades:
        current_price = trades[-1].price

    if current_price == 0.0:
        # No data available
        return state

    # Update price buffers with kline data
    for kline in klines[-settings.atr_period:]:
        feature_engine.high_buffer.append(kline.high)
        feature_engine.low_buffer.append(kline.low)
        feature_engine.close_buffer.append(kline.close)
        feature_engine.price_buffer.append(kline.close)

    # Compute EMA values from available klines to avoid long warm-up delays.
    # If sufficient klines exist, compute EMAs statelessly from closes;
    # otherwise fall back to incremental update buffers.
    closes = [k.close for k in klines]

    ema9_val = None
    ema50_val = None

    if len(closes) >= settings.ema_short_period:
        ema9_val = feature_engine.compute_ema(
            closes[-settings.ema_short_period :], settings.ema_short_period
        )
    if len(closes) >= settings.ema_long_period:
        ema50_val = feature_engine.compute_ema(
            closes[-settings.ema_long_period :], settings.ema_long_period
        )

    # Assign computed EMAs if available
    if ema9_val is not None:
        feature_engine.ema_9 = ema9_val
    if ema50_val is not None:
        feature_engine.ema_50 = ema50_val

    # Also keep incremental update to smoothly evolve between iterations
    feature_engine.update_ema(current_price)

    # Compute ATR
    atr = feature_engine.compute_atr()

    # Compute realized volatility
    realized_vol = feature_engine.compute_realized_volatility()

    # Compute orderbook imbalance
    ob_imbalance = None
    spread = None
    if orderbook:
        ob_imbalance = orderbook.get_imbalance()
        spread = orderbook.get_spread()

    # Compute VWAP
    vwap = feature_engine.compute_vwap(trades[-100:])

    # Compute RSI
    rsi = feature_engine.compute_rsi(
        list(feature_engine.close_buffer), settings.rsi_period
    )

    # Compute Bollinger Bands
    bb_upper = None
    bb_mid = None
    bb_lower = None
    bb_res = feature_engine.compute_bollinger_bands(
        list(feature_engine.price_buffer),
        settings.bollinger_period,
        settings.bollinger_std_dev
    )
    if bb_res:
        bb_upper, bb_mid, bb_lower = bb_res

    features = MarketFeatures(
        timestamp=datetime.now(),
        symbol=symbol,
        price=current_price,
        ema_9=feature_engine.ema_9,
        ema_50=feature_engine.ema_50,
        atr=atr,
        realized_volatility=realized_vol,
        orderbook_imbalance=ob_imbalance,
        spread=spread,
        vwap=vwap,
        rsi=rsi,
        bollinger_upper=bb_upper,
        bollinger_mid=bb_mid,
        bollinger_lower=bb_lower
    )

    return {
        **state,
        "features": features
    }

