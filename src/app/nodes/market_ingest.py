"""Market data ingestion node."""
from typing import TypedDict
from datetime import datetime
import csv
from pathlib import Path

from app.schemas.events import TradeEvent, OrderbookUpdate, KlineEvent
from app.tools.trading_provider import trading_provider
from app.config import settings


class IngestState(TypedDict):
    """State for market ingestion."""
    trades: list[TradeEvent]
    orderbook: OrderbookUpdate | None
    klines: list[KlineEvent]
    symbol: str
    timestamp: datetime


async def ingest_market_data_node(state: IngestState) -> IngestState:
    """
    Ingest market data from exchange or CSV.

    For now, uses CSV stub for backtesting, otherwise fetches from Binance.
    """
    symbol = state.get("symbol", settings.symbol)

    # If backtesting enabled and data path provided, load from CSV
    if settings.enable_backtesting and settings.backtest_data_path:
        return await _load_from_csv(state, settings.backtest_data_path)

    # Otherwise fetch live data from trading provider
    try:
        # Fetch orderbook
        orderbook = await trading_provider.get_orderbook(symbol, limit=20)

        # Fetch recent trades
        trades = await trading_provider.get_recent_trades(symbol, limit=100)

        # Fetch recent klines
        klines = await trading_provider.get_klines(symbol, interval="1m", limit=100)

        return {
            "trades": trades,
            "orderbook": orderbook,
            "klines": klines,
            "symbol": symbol,
            "timestamp": datetime.now()
        }

    except Exception as e:
        # Return empty state on error
        print(f"Error ingesting market data: {e}")
        return {
            "trades": state.get("trades", []),
            "orderbook": state.get("orderbook"),
            "klines": state.get("klines", []),
            "symbol": symbol,
            "timestamp": datetime.now()
        }


async def _load_from_csv(state: IngestState, csv_path: str) -> IngestState:
    """
    Load market data from CSV file (stub implementation).

    CSV format expected:
    timestamp,symbol,price,volume,bid,ask,bid_qty,ask_qty
    """
    path = Path(csv_path)

    if not path.exists():
        print(f"CSV file not found: {csv_path}")
        return state

    trades: list[TradeEvent] = []
    klines: list[KlineEvent] = []
    orderbook: OrderbookUpdate | None = None

    try:
        with open(path, 'r') as f:
            reader = csv.DictReader(f)

            for row in reader:
                timestamp = datetime.fromisoformat(row['timestamp'])
                symbol = row['symbol']
                price = float(row['price'])
                volume = float(row['volume'])

                # Create trade event
                trades.append(TradeEvent(
                    timestamp=timestamp,
                    symbol=symbol,
                    price=price,
                    quantity=volume,
                    side="BUY",  # Simplified
                    trade_id=f"{timestamp.timestamp()}"
                ))

                # Create orderbook from bid/ask
                if 'bid' in row and 'ask' in row:
                    bid = float(row['bid'])
                    ask = float(row['ask'])
                    bid_qty = float(row.get('bid_qty', 1.0))
                    ask_qty = float(row.get('ask_qty', 1.0))

                    orderbook = OrderbookUpdate(
                        timestamp=timestamp,
                        symbol=symbol,
                        bids=[(bid, bid_qty)],
                        asks=[(ask, ask_qty)]
                    )

        # Take last 100 trades
        trades = trades[-100:] if len(trades) > 100 else trades

        return {
            "trades": trades,
            "orderbook": orderbook,
            "klines": klines,
            "symbol": state.get("symbol", settings.symbol),
            "timestamp": datetime.now()
        }

    except Exception as e:
        print(f"Error loading CSV: {e}")
        return state

