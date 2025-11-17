"""Trading provider abstraction layer.

This module provides a unified interface for different trading backends
(Binance, Alpaca) so the rest of the system doesn't need to know which
provider is being used.
"""
from typing import Protocol, runtime_checkable

from app.schemas.events import TradeEvent, OrderbookUpdate, KlineEvent
from app.schemas.models import Order, ExecutionResult, PortfolioState


@runtime_checkable
class TradingProvider(Protocol):
    """Protocol defining the interface all trading providers must implement."""

    async def initialize(self) -> None:
        """Initialize the provider's client connections."""
        ...

    async def close(self) -> None:
        """Close client connections and cleanup resources."""
        ...

    async def get_orderbook(self, symbol: str, limit: int = 20) -> OrderbookUpdate:
        """Fetch current orderbook snapshot."""
        ...

    async def get_recent_trades(self, symbol: str, limit: int = 100) -> list[TradeEvent]:
        """Fetch recent trades."""
        ...

    async def get_klines(
        self,
        symbol: str,
        interval: str = "1m",
        limit: int = 100
    ) -> list[KlineEvent]:
        """Fetch historical klines/candlesticks."""
        ...

    async def execute_order(self, order: Order) -> ExecutionResult:
        """Execute an order on the exchange."""
        ...

    async def get_portfolio_state(self) -> PortfolioState:
        """Fetch current portfolio state."""
        ...


def get_trading_provider() -> TradingProvider:
    """Factory function to get the configured trading provider.

    Returns the appropriate trading provider instance based on configuration.
    """
    from app.config import settings

    if settings.trading_provider == "alpaca":
        from app.tools.alpaca_tool import alpaca_tool
        return alpaca_tool  # type: ignore
    elif settings.trading_provider == "binance":
        from app.tools.binance_tool import binance_tool
        return binance_tool  # type: ignore
    else:
        raise ValueError(
            f"Unknown trading provider: {settings.trading_provider}. "
            f"Supported providers: binance, alpaca"
        )


# Global instance - use this throughout the application
trading_provider = get_trading_provider()

