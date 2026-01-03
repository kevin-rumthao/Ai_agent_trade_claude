"""Binance exchange integration tool."""
from datetime import datetime
from typing import Optional

try:
    from binance.async_client import AsyncClient  # type: ignore
    from binance.exceptions import BinanceAPIException  # type: ignore
except Exception:  # pragma: no cover - test stub path
    AsyncClient = object  # type: ignore

    class BinanceAPIException(Exception):  # type: ignore
        """Fallback stub when python-binance is not installed."""

from app.config import settings
from app.schemas.events import TradeEvent, OrderbookUpdate, KlineEvent
from app.schemas.models import Order, ExecutionResult, PortfolioState, Position
from app.utils.resilience import api_retry_policy


class BinanceTool:
    """Tool for interacting with Binance exchange."""

    def __init__(self) -> None:
        self.client: Optional[AsyncClient] = None
        self.testnet = settings.testnet

    async def initialize(self) -> None:
        """Initialize the Binance client."""
        if settings.testnet:
            self.client = await AsyncClient.create(
                api_key=settings.binance_api_key,
                api_secret=settings.binance_api_secret,
                testnet=True
            )
        else:
            self.client = await AsyncClient.create(
                api_key=settings.binance_api_key,
                api_secret=settings.binance_api_secret
            )

    async def close(self) -> None:
        """Close the client connection."""
        if self.client:
            await self.client.close_connection()

    @api_retry_policy()
    async def get_orderbook(self, symbol: str, limit: int = 20) -> OrderbookUpdate:
        """Fetch current orderbook snapshot."""
        if not self.client:
            raise RuntimeError("Client not initialized")

        try:
            data = await self.client.get_order_book(symbol=symbol, limit=limit)

            bids = [(float(price), float(qty)) for price, qty in data['bids']]
            asks = [(float(price), float(qty)) for price, qty in data['asks']]

            return OrderbookUpdate(
                timestamp=datetime.now(),
                symbol=symbol,
                bids=bids,
                asks=asks
            )
        except BinanceAPIException as e:
            raise RuntimeError(f"Failed to fetch orderbook: {e}")

    @api_retry_policy()
    async def get_recent_trades(self, symbol: str, limit: int = 100) -> list[TradeEvent]:
        """Fetch recent trades."""
        if not self.client:
            raise RuntimeError("Client not initialized")

        try:
            trades = await self.client.get_recent_trades(symbol=symbol, limit=limit)

            return [
                TradeEvent(
                    timestamp=datetime.fromtimestamp(trade['time'] / 1000),
                    symbol=symbol,
                    price=float(trade['price']),
                    quantity=float(trade['qty']),
                    side="BUY" if trade['isBuyerMaker'] else "SELL",
                    trade_id=str(trade['id'])
                )
                for trade in trades
            ]
        except BinanceAPIException as e:
            raise RuntimeError(f"Failed to fetch trades: {e}")

    @api_retry_policy()
    async def get_klines(
        self,
        symbol: str,
        interval: str = "1m",
        limit: int = 1000,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> list[KlineEvent]:
        """Fetch historical klines/candlesticks."""
        if not self.client:
            raise RuntimeError("Client not initialized")

        try:
            # Prepare kwargs
            kwargs = {
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            }
            if start_time:
                kwargs["startTime"] = int(start_time.timestamp() * 1000)
            if end_time:
                kwargs["endTime"] = int(end_time.timestamp() * 1000)

            klines = await self.client.get_klines(**kwargs)

            return [
                KlineEvent(
                    timestamp=datetime.fromtimestamp(k[0] / 1000),
                    symbol=symbol,
                    interval=interval,
                    open=float(k[1]),
                    high=float(k[2]),
                    low=float(k[3]),
                    close=float(k[4]),
                    volume=float(k[5]),
                    num_trades=int(k[8])
                )
                for k in klines
            ]
        except BinanceAPIException as e:
            raise RuntimeError(f"Failed to fetch klines: {e}")

    @api_retry_policy()
    async def execute_order(self, order: Order) -> ExecutionResult:
        """Execute an order on the exchange."""
        if not self.client:
            raise RuntimeError("Client not initialized")

        try:
            if order.order_type == "MARKET":
                result = await self.client.create_order(
                    symbol=order.symbol,
                    side=order.side,
                    type="MARKET",
                    quantity=order.quantity
                )
            elif order.order_type == "LIMIT":
                result = await self.client.create_order(
                    symbol=order.symbol,
                    side=order.side,
                    type="LIMIT",
                    quantity=order.quantity,
                    price=str(order.price),
                    timeInForce=order.time_in_force
                )
            else:
                raise ValueError(f"Unsupported order type: {order.order_type}")

            return ExecutionResult(
                success=True,
                order_id=str(result['orderId']),
                filled_quantity=float(result.get('executedQty', 0)),
                filled_price=float(result.get('price', 0)) if result.get('price') else None,
                status=result['status'],
                timestamp=datetime.now()
            )

        except BinanceAPIException as e:
            return ExecutionResult(
                success=False,
                status="FAILED",
                error_message=str(e),
                timestamp=datetime.now()
            )

    @api_retry_policy()
    async def cancel_order(self, order_id: str, symbol: str) -> ExecutionResult:
        """Cancel an open order on Binance."""
        if not self.client:
            raise RuntimeError("Client not initialized")

        try:
            result = await self.client.cancel_order(
                symbol=symbol,
                orderId=order_id
            )
            
            return ExecutionResult(
                success=True,
                order_id=str(result['orderId']),
                filled_quantity=float(result.get('executedQty', 0)),
                filled_price=float(result.get('price', 0)) if float(result.get('price', 0)) > 0 else None,
                status=result['status'],
                timestamp=datetime.now()
            )
        except BinanceAPIException as e:
            return ExecutionResult(
                success=False,
                status="ERROR",
                error_message=str(e),
                timestamp=datetime.now()
            )

    @api_retry_policy()
    async def get_order_status(self, order_id: str, symbol: str) -> ExecutionResult:
        """Get order status from Binance."""
        if not self.client:
            raise RuntimeError("Client not initialized")

        try:
            result = await self.client.get_order(
                symbol=symbol,
                orderId=order_id
            )
            
            return ExecutionResult(
                success=True,
                order_id=str(result['orderId']),
                filled_quantity=float(result.get('executedQty', 0)),
                filled_price=float(result.get('price', 0)) if float(result.get('price', 0)) > 0 else None,
                status=result['status'],
                timestamp=datetime.now()
            )
        except BinanceAPIException as e:
            return ExecutionResult(
                success=False,
                status="ERROR",
                error_message=str(e),
                timestamp=datetime.now()
            )

    @api_retry_policy()
    async def get_account_balance(self) -> float:
        """Get account balance in USDT."""
        if not self.client:
            raise RuntimeError("Client not initialized")

        try:
            account = await self.client.get_account()
            for balance in account['balances']:
                if balance['asset'] == 'USDT':
                    return float(balance['free']) + float(balance['locked'])
            return 0.0
        except BinanceAPIException as e:
            raise RuntimeError(f"Failed to fetch balance: {e}")

    @api_retry_policy()
    async def get_portfolio_state(self, symbol: str) -> PortfolioState:
        """Get current portfolio state."""
        if not self.client:
            raise RuntimeError("Client not initialized")

        try:
            account = await self.client.get_account()
            balance = 0.0
            positions: list[Position] = []

            # Get USDT balance
            for bal in account['balances']:
                if bal['asset'] == 'USDT':
                    balance = float(bal['free']) + float(bal['locked'])

            # Get current position (simplified for spot trading)
            base_asset = symbol.replace('USDT', '')
            for bal in account['balances']:
                if bal['asset'] == base_asset:
                    qty = float(bal['free']) + float(bal['locked'])
                    if qty > 0:
                        # Get current price
                        ticker = await self.client.get_symbol_ticker(symbol=symbol)
                        current_price = float(ticker['price'])

                        positions.append(Position(
                            symbol=symbol,
                            side="LONG",
                            quantity=qty,
                            entry_price=current_price,  # Simplified
                            current_price=current_price,
                            unrealized_pnl=0.0,  # Would need to track entries
                            timestamp=datetime.now()
                        ))

            equity = balance + sum(p.quantity * p.current_price for p in positions)

            return PortfolioState(
                balance=balance,
                equity=equity,
                positions=positions,
                timestamp=datetime.now()
            )

        except BinanceAPIException as e:
            raise RuntimeError(f"Failed to fetch portfolio state: {e}")


# Global instance
binance_tool = BinanceTool()
