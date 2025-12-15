"""Feature engineering node for computing technical indicators."""
from typing import TypedDict
from datetime import datetime
import numpy as np
from collections import deque

from app.schemas.events import TradeEvent, OrderbookUpdate, KlineEvent
from app.schemas.models import MarketFeatures
from app.config import settings
from app.utils.statistics import check_stationarity, calculate_hurst, forecast_volatility
from app.utils.persistence import persistence


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
        self.ema_200_buffer: deque[float] = deque(maxlen=200 * 2) # Hardcoded 200 for now or add to settings
        
        # Ensure price buffer is large enough for Bollinger Bands and Volatility
        max_price_lookback = max(settings.volatility_lookback, settings.bollinger_period)
        self.price_buffer: deque[float] = deque(maxlen=max_price_lookback)
        
        # Ensure close buffer is large enough for RSI and ADX
        # ADX needs 2x period for smoothing
        max_close_lookback = max(settings.atr_period, settings.rsi_period + 1, 50) 
        self.high_buffer: deque[float] = deque(maxlen=max_close_lookback)
        self.low_buffer: deque[float] = deque(maxlen=max_close_lookback)
        self.close_buffer: deque[float] = deque(maxlen=max_close_lookback)

        self.ema_9: float | None = None
        self.ema_50: float | None = None
        self.ema_200: float | None = None
        
        # OFI Smoothing (Phase 4)
        self.ofi_buffer: deque[float] = deque(maxlen=5) # 5-period SMA
        self.ofi_sma: float | None = None
        
        self.prev_orderbook: OrderbookUpdate | None = None

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
        self.ema_200_buffer.append(price)

        if len(self.ema_9_buffer) >= settings.ema_short_period:
            self.ema_9 = self.compute_ema(list(self.ema_9_buffer), settings.ema_short_period)

        if len(self.ema_50_buffer) >= settings.ema_long_period:
            self.ema_50 = self.compute_ema(list(self.ema_50_buffer), settings.ema_long_period)
            
        if len(self.ema_200_buffer) >= 200:
            self.ema_200 = self.compute_ema(list(self.ema_200_buffer), 200)

    def update_ofi(self, ofi_val: float) -> None:
        """Update OFI buffer and compute SMA."""
        if ofi_val is None:
             return
             
        self.ofi_buffer.append(ofi_val)
        
        # Compute SMA
        if len(self.ofi_buffer) > 0:
            self.ofi_sma = sum(self.ofi_buffer) / len(self.ofi_buffer)

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

    def compute_adx(self, period: int = 14) -> float | None:
        """
        Compute Average Directional Index (ADX).
        
        Uses Wilder's Smoothing.
        """
        if len(self.high_buffer) < period * 2:
            return None

        highs = list(self.high_buffer)
        lows = list(self.low_buffer)
        closes = list(self.close_buffer)
        
        # Need at least period + 1 data points to calculate changes
        if len(highs) < period + 1:
            return None

        tr_list = []
        dm_plus_list = []
        dm_minus_list = []

        for i in range(1, len(highs)):
            # True Range
            h_l = highs[i] - lows[i]
            h_pc = abs(highs[i] - closes[i-1])
            l_pc = abs(lows[i] - closes[i-1])
            tr = max(h_l, h_pc, l_pc)
            tr_list.append(tr)

            # Directional Movement
            up_move = highs[i] - highs[i-1]
            down_move = lows[i-1] - lows[i]

            if up_move > down_move and up_move > 0:
                dm_plus_list.append(up_move)
            else:
                dm_plus_list.append(0.0)

            if down_move > up_move and down_move > 0:
                dm_minus_list.append(down_move)
            else:
                dm_minus_list.append(0.0)

        if len(tr_list) < period:
            return None

        # Wilder's Smoothing
        def smooth(data: list[float], period: int) -> list[float]:
            smoothed = []
            # First value is simple sum (or average? Wilder uses sum for first, then smooth)
            # Standard Wilder's: First = Sum(first N), Subsequent = Prev - (Prev/N) + Current
            
            # Initialize with sum of first 'period' elements
            curr_smooth = sum(data[:period])
            smoothed.append(curr_smooth)
            
            for i in range(period, len(data)):
                curr_smooth = curr_smooth - (curr_smooth / period) + data[i]
                smoothed.append(curr_smooth)
            return smoothed

        tr_smooth = smooth(tr_list, period)
        dm_plus_smooth = smooth(dm_plus_list, period)
        dm_minus_smooth = smooth(dm_minus_list, period)

        dx_list = []
        for i in range(len(tr_smooth)):
            if tr_smooth[i] == 0:
                dx_list.append(0.0)
                continue
                
            di_plus = 100 * (dm_plus_smooth[i] / tr_smooth[i])
            di_minus = 100 * (dm_minus_smooth[i] / tr_smooth[i])
            
            denom = di_plus + di_minus
            if denom == 0:
                dx = 0.0
            else:
                dx = 100 * abs(di_plus - di_minus) / denom
            dx_list.append(dx)

        # ADX is smoothed DX
        # We need at least 'period' DX values to smooth them? 
        # Actually standard ADX usually smooths DX over 'period' as well.
        
        if len(dx_list) < period:
            # Not enough data for full ADX smoothing
            # Fallback: simple average of available DX
            return sum(dx_list) / len(dx_list)
            
        # Smooth DX to get ADX
        # Initialize ADX with average of first 'period' DX values
        adx = sum(dx_list[:period]) / period
        
        # Smooth remaining
        for i in range(period, len(dx_list)):
            adx = ((adx * (period - 1)) + dx_list[i]) / period
            
        return adx

    def compute_ofi(self, current: OrderbookUpdate) -> float | None:
        """
        Compute Order Flow Imbalance (OFI).
        
        OFI = Change in Bid Depth - Change in Ask Depth
        Tracks aggressive buying/selling pressure at the Best Bid/Ask.
        """
        if not self.prev_orderbook:
            return None
            
        if not current.bids or not current.asks or not self.prev_orderbook.bids or not self.prev_orderbook.asks:
            return None

        # Best Bid/Ask (Price, Qty)
        bb_curr_p, bb_curr_q = current.bids[0]
        bb_prev_p, bb_prev_q = self.prev_orderbook.bids[0]
        
        bo_curr_p, bo_curr_q = current.asks[0]
        bo_prev_p, bo_prev_q = self.prev_orderbook.asks[0]
        
        # Bid Side Impact
        if bb_curr_p > bb_prev_p:
            bid_impact = bb_curr_q
        elif bb_curr_p < bb_prev_p:
            bid_impact = -bb_prev_q
        else: # Price unchanged
            bid_impact = bb_curr_q - bb_prev_q
            
        # Ask Side Impact (Ask going DOWN is bearish/positive alpha for short)
        if bo_curr_p < bo_prev_p:
            ask_impact = bo_curr_q
        elif bo_curr_p > bo_prev_p:
            ask_impact = -bo_prev_q
        else: # Price unchanged
            ask_impact = bo_curr_q - bo_prev_q
            
        # OFI = Net Buying Pressure
        return bid_impact - ask_impact

    def to_dict(self) -> dict:
        """Serialize state to dict."""
        return {
            "ema_9_buffer": list(self.ema_9_buffer),
            "ema_50_buffer": list(self.ema_50_buffer),
            "ema_200_buffer": list(self.ema_200_buffer),
            "price_buffer": list(self.price_buffer),
            "high_buffer": list(self.high_buffer),
            "low_buffer": list(self.low_buffer),
            "close_buffer": list(self.close_buffer),
            "ema_9": self.ema_9,
            "ema_50": self.ema_50,
            "ema_200": self.ema_200,
            "ofi_buffer": list(self.ofi_buffer),
            "ofi_sma": self.ofi_sma
        }

    def from_dict(self, data: dict) -> None:
        """Restore state from dict."""
        if not data:
            return
            
        try:
            if "ema_9_buffer" in data:
                self.ema_9_buffer.extend(data["ema_9_buffer"])
            if "ema_50_buffer" in data:
                self.ema_50_buffer.extend(data["ema_50_buffer"])
            if "ema_200_buffer" in data:
                self.ema_200_buffer.extend(data["ema_200_buffer"])
            if "price_buffer" in data:
                self.price_buffer.extend(data["price_buffer"])
            if "high_buffer" in data:
                self.high_buffer.extend(data["high_buffer"])
            if "low_buffer" in data:
                self.low_buffer.extend(data["low_buffer"])
            if "close_buffer" in data:
                self.close_buffer.extend(data["close_buffer"])
            
            self.ema_9 = data.get("ema_9")
            self.ema_50 = data.get("ema_50")
            self.ema_200 = data.get("ema_200")
            
            if "ofi_buffer" in data:
                 self.ofi_buffer.extend(data["ofi_buffer"])
            self.ofi_sma = data.get("ofi_sma")
        except Exception as e:
            print(f"Error restoring feature state: {e}")

# ... (Global instance and compute_features_node)

async def compute_features_node(state: FeatureState) -> FeatureState:
    # ... (Initialization logic remains same)
    global _features_loaded
    symbol = state.get("symbol", settings.symbol)
    
    # Load state on first run
    if not _features_loaded:
        saved_state = persistence.load_state(f"features_{symbol}")
        if saved_state:
            feature_engine.from_dict(saved_state)
            print(f"Restored feature state for {symbol}")
        _features_loaded = True

    klines = state.get("klines", [])
    orderbook = state.get("orderbook")
    trades = state.get("trades", [])

    # ... (Price determination logic remains same)
    current_price = 0.0
    if orderbook and orderbook.get_mid_price():
        current_price = orderbook.get_mid_price() or 0.0
    elif trades:
        current_price = trades[-1].price
    elif klines:
        current_price = klines[-1].close

    if current_price == 0.0:
        return state

    # Update price buffers with kline data
    lookback_needed = 50
    for kline in klines[-lookback_needed:]:
        feature_engine.high_buffer.append(kline.high)
        feature_engine.low_buffer.append(kline.low)
        feature_engine.close_buffer.append(kline.close)
        feature_engine.price_buffer.append(kline.close)

    # Compute EMA values from available klines to avoid long warm-up delays.
    closes = [k.close for k in klines]

    ema9_val = None
    ema50_val = None
    ema200_val = None

    if len(closes) >= settings.ema_short_period:
        ema9_val = feature_engine.compute_ema(
            closes[-settings.ema_short_period :], settings.ema_short_period
        )
    if len(closes) >= settings.ema_long_period:
        ema50_val = feature_engine.compute_ema(
            closes[-settings.ema_long_period :], settings.ema_long_period
        )
    if len(closes) >= 200:
        ema200_val = feature_engine.compute_ema(
            closes[-200:], 200
        )

    # Assign computed EMAs if available
    if ema9_val is not None:
        feature_engine.ema_9 = ema9_val
    if ema50_val is not None:
        feature_engine.ema_50 = ema50_val
    if ema200_val is not None:
        feature_engine.ema_200 = ema200_val

    # Also keep incremental update
    feature_engine.update_ema(current_price)

    # ... (Rest of indicator computation remains same)
    atr = feature_engine.compute_atr()
    realized_vol = feature_engine.compute_realized_volatility()
    
    # ... (skip to features object creation)
    
    # Compute ADX
    adx = feature_engine.compute_adx(period=14)
    
    # ... (Stationarity/Hurst logic)
    closes_list = list(feature_engine.close_buffer)
    is_stat, p_val = check_stationarity(closes_list)
    hurst = calculate_hurst(closes_list)
    
    if len(closes_list) > 2:
        returns = [(closes_list[i] - closes_list[i-1])/closes_list[i-1] for i in range(1, len(closes_list))]
        vol_forecast = forecast_volatility(returns)
    else:
        vol_forecast = None
        
    # Orderbook/OFI/Spread logic
    ob_imbalance = None
    spread = None
    ofi = None
    if orderbook:
        ob_imbalance = orderbook.get_imbalance()
        spread = orderbook.get_spread()
        ofi = feature_engine.compute_ofi(orderbook)
        
    vwap = feature_engine.compute_vwap(trades[-100:])
    
    rsi = feature_engine.compute_rsi(
        list(feature_engine.close_buffer), settings.rsi_period
    )
    
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
        ema_200=feature_engine.ema_200, # Added field
        atr=atr,
        realized_volatility=realized_vol,
        adx=adx,
        orderbook_imbalance=ob_imbalance,
        spread=spread,
        vwap=vwap,
        rsi=rsi,
        bollinger_upper=bb_upper,
        bollinger_mid=bb_mid,
        bollinger_lower=bb_lower,
        hurst=hurst,
        is_stationary=is_stat,
        volatility_forecast=vol_forecast,
        ofi=ofi
    )
    
    # Update previous orderbook
    if orderbook:
        feature_engine.prev_orderbook = orderbook
    
    # Persist state
    persistence.save_state(f"features_{symbol}", feature_engine.to_dict())

    return {
        **state,
        "features": features
    }


# Global feature engine instance
feature_engine = FeatureEngine()
# Flag to track if state has been initialized/loaded
_features_loaded = False

async def compute_features_node(state: FeatureState) -> FeatureState:
    """
    Compute technical features from market data.

    Features computed:
    - EMA(9), EMA(50), EMA(200)
    - ATR
    - Realized volatility
    - Orderbook imbalance
    - VWAP
    """
    global _features_loaded
    symbol = state.get("symbol", settings.symbol)
    
    # Load state on first run
    if not _features_loaded:
        saved_state = persistence.load_state(f"features_{symbol}")
        if saved_state:
            feature_engine.from_dict(saved_state)
            print(f"Restored feature state for {symbol}")
        _features_loaded = True

    klines = state.get("klines", [])
    orderbook = state.get("orderbook")
    trades = state.get("trades", [])

    # Get current price (Prioritize Live Data: Orderbook -> Trades -> Klines)
    current_price = 0.0
    if orderbook and orderbook.get_mid_price():
        current_price = orderbook.get_mid_price() or 0.0
    elif trades:
        # Use last trade if no orderbook
        current_price = trades[-1].price
    elif klines:
        # Fallback to last closed candle (least preferred for live trading)
        current_price = klines[-1].close

    if current_price == 0.0:
        return state

    # Update price buffers with kline data
    lookback_needed = 200 # Need deeper lookback for 200 EMA
    for kline in klines[-lookback_needed:]:
        feature_engine.high_buffer.append(kline.high)
        feature_engine.low_buffer.append(kline.low)
        feature_engine.close_buffer.append(kline.close)
        feature_engine.price_buffer.append(kline.close)
        feature_engine.ema_200_buffer.append(kline.close) # Ensure buffer is fed

    # Compute EMA values from available klines to avoid long warm-up delays.
    closes = [k.close for k in klines]

    ema9_val = None
    ema50_val = None
    ema200_val = None

    if len(closes) >= settings.ema_short_period:
        ema9_val = feature_engine.compute_ema(
            closes[-settings.ema_short_period :], settings.ema_short_period
        )
    if len(closes) >= settings.ema_long_period:
        ema50_val = feature_engine.compute_ema(
            closes[-settings.ema_long_period :], settings.ema_long_period
        )
    if len(closes) >= 200:
        ema200_val = feature_engine.compute_ema(
            closes[-200 :], 200
        )

    # Assign computed EMAs if available
    if ema9_val is not None:
        feature_engine.ema_9 = ema9_val
    if ema50_val is not None:
        feature_engine.ema_50 = ema50_val
    if ema200_val is not None:
        feature_engine.ema_200 = ema200_val

    # Also keep incremental update
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
        
    # Compute OFI (Microstructure Alpha)
    ofi = None
    if orderbook:
        ofi = feature_engine.compute_ofi(orderbook)

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

    # Compute ADX
    adx = feature_engine.compute_adx(period=14)

    # Phase 2: Statistical Features
    # We need a list of closes for these tests
    closes_list = list(feature_engine.close_buffer)
    
    # Stationarity (ADF)
    is_stat, p_val = check_stationarity(closes_list)
    
    # Hurst
    hurst = calculate_hurst(closes_list)
    
    # Volatility Forecast (GARCH)
    # Start with simple returns
    if len(closes_list) > 2:
        returns = [(closes_list[i] - closes_list[i-1])/closes_list[i-1] for i in range(1, len(closes_list))]
        vol_forecast = forecast_volatility(returns)
    else:
        vol_forecast = None

    features = MarketFeatures(
        timestamp=datetime.now(),
        symbol=symbol,
        price=current_price,
        ema_9=feature_engine.ema_9,
        ema_50=feature_engine.ema_50,
        ema_200=feature_engine.ema_200, 
        atr=atr,
        realized_volatility=realized_vol,
        adx=adx,
        orderbook_imbalance=ob_imbalance,
        spread=spread,
        vwap=vwap,
        rsi=rsi,
        bollinger_upper=bb_upper,
        bollinger_mid=bb_mid,
        bollinger_lower=bb_lower,
        hurst=hurst,
        is_stationary=is_stat,
        volatility_forecast=vol_forecast,
        ofi=ofi
    )
    
    # Update previous orderbook
    if orderbook:
        feature_engine.prev_orderbook = orderbook
    
    # Persist state
    persistence.save_state(f"features_{symbol}", feature_engine.to_dict())

    return {
        **state,
        "features": features
    }
