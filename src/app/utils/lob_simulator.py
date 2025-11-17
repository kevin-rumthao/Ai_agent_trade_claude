"""Limit order book simulator for testing."""
from datetime import datetime
from collections import defaultdict
from typing import Literal
import heapq

from app.schemas.events import OrderbookUpdate


class LOBSimulator:
    """
    Simple Limit Order Book simulator for testing and backtesting.

    Maintains bid and ask queues with price-time priority.
    """

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        # Bids: max heap (negative prices for max heap behavior)
        self.bids: list[tuple[float, float, int]] = []  # (-price, quantity, timestamp)
        # Asks: min heap
        self.asks: list[tuple[float, float, int]] = []  # (price, quantity, timestamp)
        self.order_counter = 0

    def add_limit_order(
        self,
        side: Literal["BUY", "SELL"],
        price: float,
        quantity: float
    ) -> None:
        """Add a limit order to the book."""
        timestamp = self.order_counter
        self.order_counter += 1

        if side == "BUY":
            heapq.heappush(self.bids, (-price, quantity, timestamp))
        else:
            heapq.heappush(self.asks, (price, quantity, timestamp))

    def execute_market_order(
        self,
        side: Literal["BUY", "SELL"],
        quantity: float
    ) -> tuple[float, float]:
        """
        Execute a market order and return (avg_price, filled_quantity).

        Args:
            side: "BUY" to buy from asks, "SELL" to sell to bids
            quantity: Quantity to execute

        Returns:
            Tuple of (average fill price, filled quantity)
        """
        remaining = quantity
        total_cost = 0.0
        filled = 0.0

        if side == "BUY":
            # Buy from asks
            while remaining > 0 and self.asks:
                ask_price, ask_qty, _ = heapq.heappop(self.asks)

                fill_qty = min(remaining, ask_qty)
                total_cost += fill_qty * ask_price
                filled += fill_qty
                remaining -= fill_qty

                # Put back remaining quantity
                if ask_qty > fill_qty:
                    heapq.heappush(self.asks, (ask_price, ask_qty - fill_qty, self.order_counter))
                    self.order_counter += 1
        else:
            # Sell to bids
            while remaining > 0 and self.bids:
                neg_bid_price, bid_qty, _ = heapq.heappop(self.bids)
                bid_price = -neg_bid_price

                fill_qty = min(remaining, bid_qty)
                total_cost += fill_qty * bid_price
                filled += fill_qty
                remaining -= fill_qty

                # Put back remaining quantity
                if bid_qty > fill_qty:
                    heapq.heappush(self.bids, (neg_bid_price, bid_qty - fill_qty, self.order_counter))
                    self.order_counter += 1

        avg_price = total_cost / filled if filled > 0 else 0.0
        return avg_price, filled

    def get_best_bid(self) -> tuple[float, float] | None:
        """Get best bid (price, quantity)."""
        if not self.bids:
            return None
        neg_price, qty, _ = self.bids[0]
        return (-neg_price, qty)

    def get_best_ask(self) -> tuple[float, float] | None:
        """Get best ask (price, quantity)."""
        if not self.asks:
            return None
        price, qty, _ = self.asks[0]
        return (price, qty)

    def get_mid_price(self) -> float | None:
        """Get mid price between best bid and ask."""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()

        if best_bid and best_ask:
            return (best_bid[0] + best_ask[0]) / 2.0
        return None

    def get_spread(self) -> float | None:
        """Get bid-ask spread."""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()

        if best_bid and best_ask:
            return best_ask[0] - best_bid[0]
        return None

    def get_orderbook_snapshot(self, depth: int = 10) -> OrderbookUpdate:
        """
        Get orderbook snapshot.

        Args:
            depth: Number of levels to include on each side

        Returns:
            OrderbookUpdate with current state
        """
        # Extract top levels without popping
        bid_levels: list[tuple[float, float]] = []
        ask_levels: list[tuple[float, float]] = []

        # Aggregate bids by price
        bid_dict: defaultdict[float, float] = defaultdict(float)
        for neg_price, qty, _ in self.bids:
            price = -neg_price
            bid_dict[price] += qty

        # Sort and take top depth
        sorted_bids = sorted(bid_dict.items(), reverse=True)[:depth]
        bid_levels = [(price, qty) for price, qty in sorted_bids]

        # Aggregate asks by price
        ask_dict: defaultdict[float, float] = defaultdict(float)
        for price, qty, _ in self.asks:
            ask_dict[price] += qty

        # Sort and take top depth
        sorted_asks = sorted(ask_dict.items())[:depth]
        ask_levels = [(price, qty) for price, qty in sorted_asks]

        return OrderbookUpdate(
            timestamp=datetime.now(),
            symbol=self.symbol,
            bids=bid_levels,
            asks=ask_levels
        )

    def clear(self) -> None:
        """Clear the order book."""
        self.bids.clear()
        self.asks.clear()
        self.order_counter = 0

