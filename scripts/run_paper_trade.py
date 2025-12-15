import asyncio
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import signal

# Add project root to path
sys.path.append(str(Path.cwd() / "src"))
sys.path.append(str(Path.cwd()))

from app.config import settings
from app.tools.trading_provider import trading_provider
from app.tools.binance_tool import OrderbookUpdate, KlineEvent
from app.nodes.feature_engineering import feature_engine, compute_features_node
from app.nodes.momentum_policy import momentum_strategy_node
from app.nodes.mean_reversion_policy import mean_reversion_strategy_node
from app.nodes.regime_classifier import classify_regime_node
from app.nodes.strategy_router import route_strategy_node
from app.nodes.risk_manager import risk_management_node
from app.nodes.execution_agent import execution_agent_node
from app.utils.persistence import persistence

# Run flag
RUNNING = True

def handle_shutdown(signum, frame):
    global RUNNING
    print("\nShutting down paper trader...")
    RUNNING = False

async def main():
    print(f"Starting Paper Trader for {settings.symbol}...")
    
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Initialize Provider
    await trading_provider.initialize()
    
    # Initialize State
    current_state = {
        "symbol": settings.symbol,
        "timestamp": datetime.now(),
        "klines": [],
        "trades": [],
        "orderbook": None,
        "features": None,
        "regime": "UNKNOWN",
        "signals": [],
        "approved_orders": [],
        "portfolio": None
    }

    try:
        while RUNNING:
            start_time = datetime.now()
            print(f"\n--- Loop Start: {start_time.strftime('%H:%M:%S')} ---")
            
            # 1. Ingest Data
            # Note: real ingestion should use WebSocket or polling
            # For this simple runner, we poll snapshots
            
            try:
                # Poll Orderbook
                ob = await trading_provider.get_orderbook(settings.symbol)
                current_state["orderbook"] = ob
                print(f"Orderbook: Bid {ob.bids[0][0]} / Ask {ob.asks[0][0]}")
                
                # Poll Recent Trades (Simulated stream)
                trades = await trading_provider.get_recent_trades(settings.symbol, limit=50)
                current_state["trades"] = trades
                
                # Poll Klines (1m)
                # Poll Klines (1m) - Fetch enough to resample
                klines_1m = await trading_provider.get_klines(settings.symbol, interval="1m", limit=1000)
                
                # --- Resampling Logic (1m -> 15m) ---
                if len(klines_1m) > 0:
                    df_m1 = pd.DataFrame([k.dict() for k in klines_1m])
                    df_m1['timestamp'] = pd.to_datetime(df_m1['timestamp'])
                    df_m1.set_index('timestamp', inplace=True)
                    
                    ohlc_dict = {
                        'open': 'first',
                        'high': 'max',
                        'low': 'min',
                        'close': 'last',
                        'volume': 'sum'
                    }
                    df_m15 = df_m1.resample('15min').agg(ohlc_dict).dropna()
                    
                    # Convert back to KlineEvents for Strategy
                    klines_15m = []
                    for ts, row in df_m15.iterrows():
                         klines_15m.append(KlineEvent(
                             timestamp=ts,
                             symbol=settings.symbol,
                             interval="15m",
                             open=row['open'],
                             high=row['high'],
                             low=row['low'],
                             close=row['close'],
                             volume=row['volume']
                         ))
                    
                    current_state["klines"] = klines_15m
                    print(f"Klines: Loaded {len(klines_1m)} M1 -> Resampled to {len(klines_15m)} M15 candles. Last Close: {klines_15m[-1].close}")
                else:
                    current_state["klines"] = []
                    print("Warning: No klines fetched.")

                # 2. Compute Features (OFI, Volatility, etc.)
                current_state = await compute_features_node(current_state)
                features = current_state.get("features")
                if features:
                    print(f"Features: OFI={features.ofi}, VolForecast={features.volatility_forecast}")

                # 3. Classify Regime
                current_state = await classify_regime_node(current_state)
                print(f"Regime: {current_state.get('regime').regime}")

                # 4. Route Strategy (Generates Signals)
                # Router calls the appropriate strategy policy
                # We need to manually invoke the router logic or call the nodes?
                # The `strategy_router_node` returns the name of the next node.
                # Here we just run both for simplicity and let router decide? 
                # Actually, let's run both and let Risk Manager filter based on confidence.
                
                mom_state = await momentum_strategy_node(current_state)
                mr_state = await mean_reversion_strategy_node(current_state)
                
                # Merge signals
                all_signals = mom_state.get("signals", []) + mr_state.get("signals", [])
                current_state["signals"] = all_signals
                
                for s in all_signals:
                    if s.direction != "NEUTRAL":
                         print(f"Signal: {s.strategy} {s.direction} Conf={s.confidence:.2f} Reason={s.reasoning}")

                # 5. Risk Management (Sizing & Filtering)
                current_state = await risk_management_node(current_state)
                approved = current_state.get("approved_orders", [])
                if approved:
                    print(f"Approved Orders: {len(approved)}")
                    for o in approved:
                        print(f"  {o.side} {o.quantity} {o.execution_style}")

                # 6. Execution
                current_state = await execution_agent_node(current_state)

            except Exception as e:
                print(f"Error in loop: {e}")
                # Don't crash main loop
            
            # Sleep remainder of loop
            elapsed = (datetime.now() - start_time).total_seconds()
            sleep_time = max(0, settings.loop_interval_seconds - elapsed)
            print(f"Sleeping {sleep_time:.1f}s...")
            if RUNNING:
                await asyncio.sleep(sleep_time)

    finally:
        print("Closing provider...")
        await trading_provider.close()

if __name__ == "__main__":
    asyncio.run(main())
