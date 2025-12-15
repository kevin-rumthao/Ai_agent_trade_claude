"""Data models for the trading system."""
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class MarketFeatures(BaseModel):
    """Computed features from market data."""

    timestamp: datetime
    symbol: str

    # Price features
    price: float
    ema_9: Optional[float] = None
    ema_50: Optional[float] = None
    ema_200: Optional[float] = None

    # Volatility features
    atr: Optional[float] = None
    realized_volatility: Optional[float] = None
    adx: Optional[float] = None

    # Microstructure features
    orderbook_imbalance: Optional[float] = None
    spread: Optional[float] = None
    vwap: Optional[float] = None
    
    # Statistical features (Phase 2)
    hurst: Optional[float] = None
    is_stationary: Optional[bool] = None
    volatility_forecast: Optional[float] = None
    
    # Microstructure features (Phase 3)
    ofi: Optional[float] = None  # Order Flow Imbalance
    
    # Mean Reversion features
    rsi: Optional[float] = None
    bollinger_upper: Optional[float] = None
    bollinger_mid: Optional[float] = None
    bollinger_lower: Optional[float] = None
    
    # Phase 6: Strategy Optimization
    ofi_sma: Optional[float] = None


class MarketRegime(BaseModel):
    """Market regime classification."""

    regime: Literal["TRENDING", "RANGING", "HIGH_VOLATILITY", "LOW_VOLATILITY", "UNKNOWN"]
    confidence: float = Field(ge=0.0, le=1.0)
    volatility_percentile: Optional[float] = None
    trend_strength: Optional[float] = None
    timestamp: datetime


class Signal(BaseModel):
    """Trading signal from a strategy."""

    timestamp: datetime
    symbol: str
    instrument_type: Literal["SPOT", "FUTURE"] = "SPOT"
    strategy: str  # "momentum", "mean_reversion", "neutral", "hedge"
    direction: Literal["LONG", "SHORT", "NEUTRAL"]
    strength: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_stop_distance: Optional[float] = None
    suggested_quantity: Optional[float] = None
    reasoning: Optional[str] = None

    @model_validator(mode='after')
    def check_exits(self):
        if self.direction in ['LONG', 'SHORT'] and self.stop_loss is None:
            # We allow None for now to avoid breaking existing tests/logic immediately if they don't have it, 
            # but for strict mode we should raise. The requirement says "Mandatory".
            # However, during transition it might break things. I will enforce it.
             raise ValueError("Stop loss is mandatory for directional trades")
        return self


class Position(BaseModel):
    """Current position state."""

    symbol: str
    instrument_type: Literal["SPOT", "FUTURE"] = "SPOT"
    side: Literal["LONG", "SHORT"]
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_stop_distance: Optional[float] = None
    timestamp: datetime

    def get_pnl_percent(self) -> float:
        """Calculate PnL as percentage of entry."""
        if self.entry_price == 0:
            return 0.0
        if self.side == "LONG":
            return ((self.current_price - self.entry_price) / self.entry_price) * 100.0
        else:
            return ((self.entry_price - self.current_price) / self.entry_price) * 100.0


class Order(BaseModel):
    """Order to be executed."""

    symbol: str
    instrument_type: Literal["SPOT", "FUTURE"] = "SPOT"
    side: Literal["BUY", "SELL"]
    order_type: Literal["MARKET", "LIMIT", "STOP_LOSS", "TAKE_PROFIT"]
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    time_in_force: str = "GTC"  # Good Till Cancel
    client_order_id: Optional[str] = None
    execution_style: Literal["PASSIVE", "AGGRESSIVE"] = "AGGRESSIVE"


class ExecutionResult(BaseModel):
    """Result of an order execution."""

    success: bool
    order_id: Optional[str] = None
    filled_quantity: float = 0.0
    filled_price: Optional[float] = None
    status: str
    error_message: Optional[str] = None
    timestamp: datetime


class RiskLimits(BaseModel):
    """Risk management limits."""

    max_position_size: float
    max_drawdown_percent: float = 10.0
    max_daily_loss: float = 1000.0
    max_leverage: float = 1.0
    target_volatility: float = 0.20
    position_sizing_method: Literal["FIXED", "VOLATILITY", "KELLY", "VOL_TARGET"] = "FIXED"


class PortfolioState(BaseModel):
    """Current portfolio state."""

    balance: float
    equity: float
    positions: list[Position] = Field(default_factory=list)
    open_orders: list[Order] = Field(default_factory=list)
    daily_pnl: float = 0.0
    total_pnl: float = 0.0
    timestamp: datetime

    def get_position_count(self) -> int:
        """Get number of open positions."""
        return len(self.positions)

    def get_total_exposure(self) -> float:
        """Get total position exposure."""
        return sum(pos.quantity * pos.current_price for pos in self.positions)

