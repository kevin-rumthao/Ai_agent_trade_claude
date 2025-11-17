"""Event schemas for the trading system."""
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


class TradeEvent(BaseModel):
    """Event representing a trade execution."""

    timestamp: datetime
    symbol: str
    price: float
    quantity: float
    side: Literal["BUY", "SELL"]
    trade_id: str


class OrderbookUpdate(BaseModel):
    """Event representing an orderbook snapshot or update."""

    timestamp: datetime
    symbol: str
    bids: list[tuple[float, float]]  # [(price, quantity), ...]
    asks: list[tuple[float, float]]

    def get_mid_price(self) -> Optional[float]:
        """Calculate mid price from best bid/ask."""
        if not self.bids or not self.asks:
            return None
        best_bid = self.bids[0][0]
        best_ask = self.asks[0][0]
        return (best_bid + best_ask) / 2.0

    def get_spread(self) -> Optional[float]:
        """Calculate bid-ask spread."""
        if not self.bids or not self.asks:
            return None
        return self.asks[0][0] - self.bids[0][0]

    def get_imbalance(self) -> float:
        """Calculate orderbook imbalance at best level."""
        if not self.bids or not self.asks:
            return 0.0
        bid_qty = self.bids[0][1]
        ask_qty = self.asks[0][1]
        total = bid_qty + ask_qty
        if total == 0:
            return 0.0
        return (bid_qty - ask_qty) / total


class KlineEvent(BaseModel):
    """Event representing a completed kline/candlestick."""

    timestamp: datetime
    symbol: str
    interval: str  # e.g., "1m", "5m", "1h"
    open: float
    high: float
    low: float
    close: float
    volume: float
    num_trades: int = 0

    def get_typical_price(self) -> float:
        """Calculate typical price (HLC/3)."""
        return (self.high + self.low + self.close) / 3.0

