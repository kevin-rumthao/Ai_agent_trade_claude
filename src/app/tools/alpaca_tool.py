"""Alpaca exchange integration tool for paper trading."""
from datetime import datetime, timedelta
from typing import Optional

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, StopLossRequest, TakeProfitRequest
    from alpaca.trading.enums import OrderSide, TimeInForce, OrderType, OrderClass
    from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest, CryptoBarsRequest, StockTradesRequest, CryptoTradesRequest, CryptoSnapshotRequest, StockSnapshotRequest
    from alpaca.data.timeframe import TimeFrame
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    TradingClient = object  # type: ignore
    StockHistoricalDataClient = object  # type: ignore
    CryptoHistoricalDataClient = object  # type: ignore

from app.config import settings
from app.schemas.events import TradeEvent, OrderbookUpdate, KlineEvent
from app.schemas.models import Order, ExecutionResult, PortfolioState, Position
from app.utils.resilience import api_retry_policy


class AlpacaTool:
    """Tool for interacting with Alpaca exchange (paper trading)."""

    def __init__(self) -> None:
        self.trading_client: Optional[TradingClient] = None
        self.data_client: Optional[object] = None
        self.is_crypto = settings.symbol.endswith("USD") or settings.symbol.endswith("USDT")

    async def initialize(self) -> None:
        """Initialize the Alpaca clients."""
        if not ALPACA_AVAILABLE:
            raise RuntimeError("alpaca-py library not installed. Install with: pip install alpaca-py")

        # Trading client (always uses paper trading mode)
        self.trading_client = TradingClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_api_secret,
            paper=True  # Always use paper trading
        )

        # Data client - choose based on asset type
        if self.is_crypto:
            self.data_client = CryptoHistoricalDataClient(
                api_key=settings.alpaca_api_key,
                secret_key=settings.alpaca_api_secret,
            )
        else:
            self.data_client = StockHistoricalDataClient(
                api_key=settings.alpaca_api_key,
                secret_key=settings.alpaca_api_secret,
            )

    async def close(self) -> None:
        """Close the client connection."""
        # Alpaca SDK doesn't require explicit cleanup
        pass

    def _convert_symbol(self, symbol: str) -> str:
        """Convert Binance-style symbol to Alpaca format.

        Examples:
            BTCUSDT -> BTC/USD
            BTC/USD -> BTC/USD (already in Alpaca format)
            AAPL -> AAPL (unchanged for stocks)
        """
        # If symbol already has a slash, it's already in Alpaca format
        if "/" in symbol:
            return symbol

        if self.is_crypto:
            # Convert BTCUSDT to BTC/USD
            if symbol.endswith("USDT"):
                base = symbol[:-4]
                return f"{base}/USD"
            elif symbol.endswith("USD"):
                base = symbol[:-3]
                return f"{base}/USD"
        return symbol

    async def get_orderbook(self, symbol: str, limit: int = 20) -> OrderbookUpdate:
        """Fetch current orderbook snapshot.

        Strategy:
        1. Try Real Snapshot (L1 Best Bid/Ask) - Preferred
        2. Fallback to Synthetic from Bars (Approximation) - If Snapshot fails
        """
        alpaca_symbol = self._convert_symbol(symbol)
        
        # 1. Try Real Snapshot (Best Bid/Ask)
        try:
            if self.is_crypto:
                request = CryptoSnapshotRequest(symbol_or_symbols=[alpaca_symbol])
                snapshot = self.data_client.get_crypto_snapshot(request) # type: ignore
                data = snapshot[alpaca_symbol]
                quote = data.latest_quote
            else:
                request = StockSnapshotRequest(symbol_or_symbols=[alpaca_symbol])
                snapshot = self.data_client.get_stock_snapshot(request) # type: ignore
                data = snapshot[alpaca_symbol]
                quote = data.latest_quote

            if quote and quote.bid_price and quote.ask_price:
                 return OrderbookUpdate(
                    timestamp=datetime.now(),
                    symbol=symbol,
                    bids=[(float(quote.bid_price), float(quote.bid_size))],
                    asks=[(float(quote.ask_price), float(quote.ask_size))]
                 )
            # If no quote, fall through to synthetic
            print(f"No quote data for {symbol}, falling back to synthetic...")
            
        except Exception as e:
            print(f"Snapshot fetch failed ({e}), falling back to synthetic...")

        # 2. Synthetic Fallback (Old Logic)
        try:
            if self.is_crypto:
                request = CryptoBarsRequest(
                    symbol_or_symbols=[alpaca_symbol],
                    timeframe=TimeFrame.Minute,
                    limit=1
                )
                bars = self.data_client.get_crypto_bars(request)  # type: ignore
                bar_data = bars[alpaca_symbol][0]

                mid_price = (bar_data.high + bar_data.low) / 2
                spread = (bar_data.high - bar_data.low) / 2

            else:
                request = StockBarsRequest(
                    symbol_or_symbols=[alpaca_symbol],
                    timeframe=TimeFrame.Minute,
                    limit=1
                )
                bars = self.data_client.get_stock_bars(request)  # type: ignore
                bar_data = bars[alpaca_symbol][0]

                mid_price = (bar_data.high + bar_data.low) / 2
                spread = (bar_data.high - bar_data.low) / 2

            # Create synthetic bids and asks
            bids = [(mid_price - spread * (i + 1) / limit, 1.0) for i in range(limit)]
            asks = [(mid_price + spread * (i + 1) / limit, 1.0) for i in range(limit)]

            return OrderbookUpdate(
                timestamp=datetime.now(),
                symbol=symbol,
                bids=bids,
                asks=asks
            )
        except Exception as e:
            raise RuntimeError(f"Failed to fetch orderbook (Real & Synthetic both failed): {e}")

    async def get_recent_trades(self, symbol: str, limit: int = 100) -> list[TradeEvent]:
        """Fetch recent trades."""
        alpaca_symbol = self._convert_symbol(symbol)

        try:
            end = datetime.now()
            start = end - timedelta(hours=1)

            if self.is_crypto:
                request = CryptoTradesRequest(
                    symbol_or_symbols=[alpaca_symbol],
                    start=start,
                    end=end,
                    limit=limit
                )
                trades_response = self.data_client.get_crypto_trades(request)  # type: ignore
            else:
                request = StockTradesRequest(
                    symbol_or_symbols=[alpaca_symbol],
                    start=start,
                    end=end,
                    limit=limit
                )
                trades_response = self.data_client.get_stock_trades(request)  # type: ignore

            trade_events = []

            # Check if the symbol exists in the response
            if alpaca_symbol not in trades_response:
                # Return empty list if no trades found (this is normal for some symbols/times)
                return []

            for trade in trades_response[alpaca_symbol]:
                trade_events.append(TradeEvent(
                    timestamp=trade.timestamp,
                    symbol=symbol,
                    price=float(trade.price),
                    quantity=float(trade.size),
                    side="BUY" if hasattr(trade, 'taker_side') and trade.taker_side == "buy" else "SELL",
                    trade_id=str(getattr(trade, 'id', hash(trade)))
                ))

            return trade_events[:limit]
        except Exception as e:
            raise RuntimeError(f"Failed to fetch trades: {e}")

    async def get_klines(
        self,
        symbol: str,
        interval: str = "1m",
        limit: int = 100
    ) -> list[KlineEvent]:
        """Fetch historical klines/candlesticks."""
        alpaca_symbol = self._convert_symbol(symbol)

        # Map interval string to Alpaca TimeFrame
        interval_map = {
            "1m": TimeFrame.Minute,
            "5m": TimeFrame(5, "Min"),
            "15m": TimeFrame(15, "Min"),
            "1h": TimeFrame.Hour,
            "1d": TimeFrame.Day,
        }
        timeframe = interval_map.get(interval, TimeFrame.Minute)

        try:
            end = datetime.now()
            start = end - timedelta(days=1)  # Get last day of data

            if self.is_crypto:
                request = CryptoBarsRequest(
                    symbol_or_symbols=[alpaca_symbol],
                    timeframe=timeframe,
                    start=start,
                    end=end,
                    limit=limit
                )
                bars = self.data_client.get_crypto_bars(request)  # type: ignore
            else:
                request = StockBarsRequest(
                    symbol_or_symbols=[alpaca_symbol],
                    timeframe=timeframe,
                    start=start,
                    end=end,
                    limit=limit
                )
                bars = self.data_client.get_stock_bars(request)  # type: ignore

            klines = []
            for bar in bars[alpaca_symbol]:
                klines.append(KlineEvent(
                    timestamp=bar.timestamp,
                    symbol=symbol,
                    interval=interval,
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=float(bar.volume),
                    num_trades=getattr(bar, 'trade_count', 0)
                ))

            return klines[:limit]
        except Exception as e:
            raise RuntimeError(f"Failed to fetch klines: {e}")

    @api_retry_policy()
    async def execute_order(self, order: Order) -> ExecutionResult:
        """Execute an order on Alpaca (paper trading)."""
        if not self.trading_client:
            raise RuntimeError("Client not initialized")

        alpaca_symbol = self._convert_symbol(order.symbol)

        try:
            # Convert order side
            side = OrderSide.BUY if order.side == "BUY" else OrderSide.SELL

            # Create order request based on type
            if order.order_type == "MARKET":
                # Check for bracket order params
                req_params = {
                    "symbol": alpaca_symbol,
                    "qty": order.quantity,
                    "side": side,
                    "time_in_force": TimeInForce.GTC
                }
                
                if order.stop_loss and order.take_profit:
                    req_params["order_class"] = OrderClass.BRACKET
                    req_params["stop_loss"] = StopLossRequest(stop_price=order.stop_loss)
                    req_params["take_profit"] = TakeProfitRequest(limit_price=order.take_profit)
                
                order_request = MarketOrderRequest(**req_params)

            elif order.order_type == "LIMIT":
                if order.price is None:
                    raise ValueError("LIMIT order requires price")
                
                req_params = {
                    "symbol": alpaca_symbol,
                    "qty": order.quantity,
                    "side": side,
                    "time_in_force": TimeInForce.GTC,
                    "limit_price": order.price
                }

                if order.stop_loss and order.take_profit:
                    req_params["order_class"] = OrderClass.BRACKET
                    req_params["stop_loss"] = StopLossRequest(stop_price=order.stop_loss)
                    req_params["take_profit"] = TakeProfitRequest(limit_price=order.take_profit)

                order_request = LimitOrderRequest(**req_params)
            else:
                raise ValueError(f"Unsupported order type: {order.order_type}")

            # Submit order
            alpaca_order = self.trading_client.submit_order(order_request)

            return ExecutionResult(
                success=True,
                order_id=str(alpaca_order.id),
                filled_quantity=float(alpaca_order.filled_qty or 0),
                filled_price=float(alpaca_order.filled_avg_price) if alpaca_order.filled_avg_price else None,
                status=str(alpaca_order.status),
                timestamp=datetime.now()
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                status="ERROR",
                error_message=str(e),
                timestamp=datetime.now()
            )

    async def cancel_order(self, order_id: str, symbol: str) -> ExecutionResult:
        """Cancel an open order on Alpaca."""
        if not self.trading_client:
            raise RuntimeError("Client not initialized")

        try:
            self.trading_client.cancel_order_by_id(order_id)
            
            # Fetch updated status
            alpaca_order = self.trading_client.get_order_by_id(order_id)
            
            return ExecutionResult(
                success=True,
                order_id=str(alpaca_order.id),
                filled_quantity=float(alpaca_order.filled_qty or 0),
                filled_price=float(alpaca_order.filled_avg_price) if alpaca_order.filled_avg_price else None,
                status=str(alpaca_order.status),
                timestamp=datetime.now()
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                status="ERROR",
                error_message=str(e),
                timestamp=datetime.now()
            )

    async def get_order_status(self, order_id: str, symbol: str) -> ExecutionResult:
        """Get order status from Alpaca."""
        if not self.trading_client:
            raise RuntimeError("Client not initialized")

        try:
            alpaca_order = self.trading_client.get_order_by_id(order_id)
            
            return ExecutionResult(
                success=True,
                order_id=str(alpaca_order.id),
                filled_quantity=float(alpaca_order.filled_qty or 0),
                filled_price=float(alpaca_order.filled_avg_price) if alpaca_order.filled_avg_price else None,
                status=str(alpaca_order.status),
                timestamp=datetime.now()
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                status="ERROR",
                error_message=str(e),
                timestamp=datetime.now()
            )

    async def get_portfolio_state(self) -> PortfolioState:
        """Fetch current portfolio state from Alpaca."""
        if not self.trading_client:
            raise RuntimeError("Client not initialized")

        try:
            account = self.trading_client.get_account()
            positions = self.trading_client.get_all_positions()

            position_list = []
            for pos in positions:
                current_price = float(pos.current_price)
                entry_price = float(pos.avg_entry_price)
                qty = float(pos.qty)

                position_list.append(Position(
                    symbol=pos.symbol,
                    side="LONG" if float(pos.qty) > 0 else "SHORT",
                    quantity=abs(qty),
                    entry_price=entry_price,
                    current_price=current_price,
                    unrealized_pnl=float(pos.unrealized_pl),
                    timestamp=datetime.now()
                ))

            return PortfolioState(
                balance=float(account.cash),
                equity=float(account.equity),
                positions=position_list,
                daily_pnl=float(account.equity) - float(account.last_equity),
                total_pnl=float(account.equity) - float(account.cash),
                timestamp=datetime.now()
            )
        except Exception as e:
            raise RuntimeError(f"Failed to fetch portfolio state: {e}")


# Global instance
alpaca_tool = AlpacaTool()

