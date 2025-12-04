"""Kotak Neo exchange integration tool."""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import asyncio
import json

try:
    import neo_api_client
    from neo_api_client import NeoAPI
    KOTAK_AVAILABLE = True
except ImportError:
    KOTAK_AVAILABLE = False
    NeoAPI = object  # type: ignore

from app.config import settings
from app.schemas.events import TradeEvent, OrderbookUpdate, KlineEvent
from app.schemas.models import Order, ExecutionResult, PortfolioState, Position


class KotakNeoTool:
    """Tool for interacting with Kotak Neo exchange."""

    def __init__(self) -> None:
        self.client: Optional[NeoAPI] = None
        self.is_initialized = False

    async def initialize(self) -> None:
        """Initialize the Kotak Neo client."""
        if not KOTAK_AVAILABLE:
            raise RuntimeError("neo_api_client library not installed.")

        if not settings.kotak_consumer_key:
            raise ValueError("KOTAK_CONSUMER_KEY not set in configuration")

        # Initialize client
        self.client = NeoAPI(
            consumer_key=settings.kotak_consumer_key,
            consumer_secret=settings.kotak_totp_secret, # Using totp secret as consumer secret if needed, or just for TOTP
            environment='prod'
        )

        # Login flow
        # Note: This is a simplified login flow. In a real scenario, we might need to handle
        # OTP generation or use a pre-generated access token if available.
        # For now, we assume the user provides necessary credentials for the standard flow.
        
        try:
            # If we have an access token, we might skip login, but the SDK usually requires login
            # We'll attempt the login flow described in docs
            if settings.kotak_mobile_number and settings.kotak_password:
                self.client.login(
                    mobilenumber=settings.kotak_mobile_number,
                    password=settings.kotak_password
                )
                
                # If 2FA is required and we have a secret, we might need to handle it.
                # The SDK docs mention `session_2fa` or similar depending on version.
                # We will assume for now that login() handles the primary authentication
                # and if a session token is needed, it's managed.
                
                # Verify session
                # self.client.session_2fa(OTP) # This would require an OTP generator
                pass
                
            self.is_initialized = True
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Kotak Neo client: {e}")

    async def close(self) -> None:
        """Close the client connection."""
        if self.client:
            try:
                self.client.logout()
            except Exception:
                pass
        self.is_initialized = False

    def _get_exchange_segment(self, symbol: str) -> str:
        """Determine exchange segment from symbol.
        
        Expected format: "EXCHANGE|SYMBOL" e.g., "NSE_CM|RELIANCE-EQ"
        If no pipe, defaults to NSE_CM.
        """
        if "|" in symbol:
            return symbol.split("|")[0]
        return "nse_cm"

    def _get_trading_symbol(self, symbol: str) -> str:
        """Extract trading symbol.
        
        Expected format: "EXCHANGE|SYMBOL" e.g., "NSE_CM|RELIANCE-EQ"
        """
        if "|" in symbol:
            return symbol.split("|")[1]
        return symbol

    async def get_orderbook(self, symbol: str, limit: int = 20) -> OrderbookUpdate:
        """Fetch current orderbook snapshot.
        
        Kotak Neo might not provide a full orderbook via REST API easily.
        We will use `quote` to get best 5 bids/asks if available, or just LTP.
        """
        if not self.client:
            raise RuntimeError("Client not initialized")

        exchange_segment = self._get_exchange_segment(symbol)
        trading_symbol = self._get_trading_symbol(symbol)
        
        # Need instrument token for quotes. 
        # This is complex because we need to search scrip master or have a mapping.
        # For this implementation, we'll assume we can get a quote by symbol if supported,
        # or we might need to implement a scrip search first.
        
        # Simplified: Return a dummy or basic quote for now as full implementation 
        # requires scrip master management.
        
        # TODO: Implement scrip master search to get token
        
        return OrderbookUpdate(
            timestamp=datetime.now(),
            symbol=symbol,
            bids=[],
            asks=[]
        )

    async def get_recent_trades(self, symbol: str, limit: int = 100) -> list[TradeEvent]:
        """Fetch recent trades."""
        # Kotak Neo API doesn't easily expose public trade history via simple REST call
        # without subscription.
        return []

    async def get_klines(
        self,
        symbol: str,
        interval: str = "1m",
        limit: int = 100
    ) -> list[KlineEvent]:
        """Fetch historical klines/candlesticks."""
        # Check if historical data is supported
        return []

    async def execute_order(self, order: Order) -> ExecutionResult:
        """Execute an order on Kotak Neo."""
        if not self.client:
            raise RuntimeError("Client not initialized")

        try:
            exchange_segment = self._get_exchange_segment(order.symbol)
            trading_symbol = self._get_trading_symbol(order.symbol)
            
            transaction_type = "B" if order.side == "BUY" else "S"
            product = "MIS" # Default to Intraday, make configurable?
            order_type = "MKT" if order.order_type == "MARKET" else "L"
            validity = "DAY"
            
            response = self.client.place_order(
                exchange_segment=exchange_segment,
                product=product,
                price=str(order.price) if order.price else "0",
                order_type=order_type,
                quantity=str(order.quantity),
                validity=validity,
                trading_symbol=trading_symbol,
                transaction_type=transaction_type
            )
            
            # Response format needs to be checked
            order_id = response.get("nOrdNo", "")
            
            return ExecutionResult(
                success=True,
                order_id=str(order_id),
                filled_quantity=0.0, # Async fill
                filled_price=None,
                status="OPEN",
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
        """Cancel an open order."""
        if not self.client:
            raise RuntimeError("Client not initialized")

        try:
            self.client.cancel_order(order_id=order_id)
            return ExecutionResult(
                success=True,
                order_id=order_id,
                status="CANCELLED",
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
        """Get order status."""
        if not self.client:
            raise RuntimeError("Client not initialized")

        try:
            history = self.client.order_history(order_id=order_id)
            # Parse history to get latest status
            latest = history['data'][0] # Assumption on structure
            
            return ExecutionResult(
                success=True,
                order_id=order_id,
                filled_quantity=float(latest.get('fldQty', 0)),
                filled_price=float(latest.get('avgPrc', 0)) if latest.get('avgPrc') else None,
                status=latest.get('ordSt', 'UNKNOWN'),
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
        """Fetch current portfolio state."""
        if not self.client:
            raise RuntimeError("Client not initialized")

        try:
            limits = self.client.limits()
            positions_resp = self.client.positions()
            
            # Parse limits for balance
            cash = 0.0 # Extract from limits
            
            position_list = []
            if positions_resp and 'data' in positions_resp:
                for pos in positions_resp['data']:
                    position_list.append(Position(
                        symbol=pos.get('trdSym', ''),
                        side="LONG" if int(pos.get('netQty', 0)) > 0 else "SHORT",
                        quantity=abs(float(pos.get('netQty', 0))),
                        entry_price=float(pos.get('avgPrc', 0)),
                        current_price=float(pos.get('ltp', 0)), # Might need separate quote call
                        unrealized_pnl=float(pos.get('urPnl', 0)),
                        timestamp=datetime.now()
                    ))

            return PortfolioState(
                balance=cash,
                equity=cash, # + pnl
                positions=position_list,
                daily_pnl=0.0,
                total_pnl=0.0,
                timestamp=datetime.now()
            )
        except Exception as e:
            raise RuntimeError(f"Failed to fetch portfolio state: {e}")


# Global instance
kotak_neo_tool = KotakNeoTool()
