"""Mock trading provider for testing and dry runs."""
from datetime import datetime, timedelta
import random
import asyncio

from app.schemas.events import TradeEvent, OrderbookUpdate, KlineEvent
from app.schemas.models import Order, ExecutionResult, PortfolioState, Position

class MockTradingProvider:
    """Mock provider generating synthetic data."""
    
    def __init__(self):
        self.symbol = "BTCUSDT"
        self.price = 50000.0
        self.orders: dict[str, Order] = {}
        self.positions: dict[str, Position] = {}
        self.balance = 10000.0
        self.equity = 10000.0
        
    async def initialize(self) -> None:
        print("Mock Provider Initialized")
        
    async def close(self) -> None:
        print("Mock Provider Closed")
        
    async def get_orderbook(self, symbol: str, limit: int = 20) -> OrderbookUpdate:
        # Simulate price walk
        self.price += random.gauss(0, 10)
        
        # Generate spread around price
        best_bid = self.price - 1.0
        best_ask = self.price + 1.0
        
        return OrderbookUpdate(
            timestamp=datetime.now(),
            symbol=symbol,
            bids=[(best_bid, 1.0), (best_bid - 5, 2.0)],
            asks=[(best_ask, 1.0), (best_ask + 5, 2.0)]
        )

    async def get_recent_trades(self, symbol: str, limit: int = 100) -> list[TradeEvent]:
        return [
            TradeEvent(
                timestamp=datetime.now(),
                symbol=symbol,
                price=self.price,
                quantity=0.1,
                side=random.choice(["BUY", "SELL"]),
                trade_id=f"trade_{int(datetime.now().timestamp())}"
            )
        ]

    async def get_klines(self, symbol: str, interval: str = "1m", limit: int = 100) -> list[KlineEvent]:
        # Generate sequence of klines
        klines = []
        base_price = self.price - (limit * 5)
        now = datetime.now()
        
        for i in range(limit):
            open_p = base_price
            close_p = base_price + random.gauss(0, 20)
            high_p = max(open_p, close_p) + 5
            low_p = min(open_p, close_p) - 5
            
            klines.append(KlineEvent(
                timestamp=now - timedelta(minutes=limit-i),
                symbol=symbol,
                interval=interval,
                open=open_p,
                high=high_p,
                low=low_p,
                close=close_p,
                volume=100.0
            ))
            base_price = close_p
            
        return klines

    async def execute_order(self, order: Order) -> ExecutionResult:
        order_id = f"mock_ord_{int(datetime.now().timestamp())}"
        
        # Simulate fill
        filled_price = order.price if order.price else self.price
        
        # Update mock portfolio
        cost = filled_price * order.quantity
        if order.side == "BUY":
            self.balance -= cost
        else:
            self.balance += cost
            
        return ExecutionResult(
            success=True,
            order_id=order_id,
            filled_quantity=order.quantity,
            filled_price=filled_price,
            status="FILLED",
            timestamp=datetime.now()
        )

    async def get_portfolio_state(self) -> PortfolioState:
        return PortfolioState(
            timestamp=datetime.now(),
            equity=self.balance, # Simplified
            balance=self.balance,
            positions=[], # TODO: track positions if needed
            daily_pnl=0.0
        )

    async def cancel_order(self, order_id: str, symbol: str) -> ExecutionResult:
        return ExecutionResult(
            success=True,
            status="CANCELED",
            timestamp=datetime.now()
        )

    async def get_order_status(self, order_id: str, symbol: str) -> ExecutionResult:
        return ExecutionResult(
            success=True,
            status="FILLED",
            timestamp=datetime.now()
        )

mock_tool = MockTradingProvider()
