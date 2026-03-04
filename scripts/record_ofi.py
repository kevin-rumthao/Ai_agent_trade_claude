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
from app.nodes.feature_engineering import feature_engine

# Global flag for graceful shutdown
RUNNING = True

def handle_shutdown(signum, frame):
    global RUNNING
    print("\nShutting down OFI recorder...")
    RUNNING = False

async def record_ofi(symbol: str, duration_minutes: int = 60, interval_seconds: int = 5):
    """
    Record OFI (Order Flow Imbalance) data by polling orderbook snapshots.
    
    Args:
        symbol: Trading pair (e.g., BTCUSDT)
        duration_minutes: How long to record (default: 60 minutes)
        interval_seconds: Polling frequency (default: 5 seconds)
    """
    print(f"Recording OFI for {symbol} ({duration_minutes} minutes, {interval_seconds}s interval)...")
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    # Initialize provider
    await trading_provider.initialize()
    
    # Storage
    ofi_records = []
    prev_orderbook = None
    
    start_time = datetime.now()
    iterations = (duration_minutes * 60) // interval_seconds
    
    try:
        for i in range(iterations):
            if not RUNNING:
                break
                
            current_time = datetime.now()
            
            try:
                # Fetch orderbook snapshot
                orderbook = await trading_provider.get_orderbook(symbol, limit=20)
                
                # Calculate OFI
                ofi = None
                if prev_orderbook:
                    ofi = feature_engine.compute_ofi(orderbook)
                    feature_engine.prev_orderbook = orderbook
                else:
                    feature_engine.prev_orderbook = orderbook
                
                # Get current price
                mid_price = orderbook.get_mid_price()
                spread = orderbook.get_spread()
                imbalance = orderbook.get_imbalance()
                
                # Record
                record = {
                    'timestamp': current_time,
                    'symbol': symbol,
                    'mid_price': mid_price,
                    'spread': spread,
                    'orderbook_imbalance': imbalance,
                    'ofi': ofi if ofi is not None else 0.0,
                    'bid_price': orderbook.bids[0][0] if orderbook.bids else None,
                    'bid_qty': orderbook.bids[0][1] if orderbook.bids else None,
                    'ask_price': orderbook.asks[0][0] if orderbook.asks else None,
                    'ask_qty': orderbook.asks[0][1] if orderbook.asks else None,
                }
                
                ofi_records.append(record)
                
                # Progress
                if (i + 1) % 12 == 0:  # Every minute (assuming 5s interval)
                    elapsed = (current_time - start_time).total_seconds() / 60
                    print(f"[{elapsed:.1f}m] Recorded {len(ofi_records)} snapshots. Latest OFI: {ofi:.2f if ofi else 0.0}")
                
                prev_orderbook = orderbook
                
            except Exception as e:
                print(f"Error fetching orderbook: {e}")
            
            # Sleep for interval
            if RUNNING and i < iterations - 1:
                await asyncio.sleep(interval_seconds)
        
        # Save to CSV
        df = pd.DataFrame(ofi_records)
        output_file = f"data/ofi_{symbol}_{start_time.strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(output_file, index=False)
        print(f"\n✅ Saved {len(df)} OFI records to {output_file}")
        
        # Show statistics
        if len(df) > 0:
            print("\n--- OFI Statistics ---")
            print(f"Duration: {(df['timestamp'].max() - df['timestamp'].min()).total_seconds() / 60:.1f} minutes")
            print(f"OFI Mean: {df['ofi'].mean():.4f}")
            print(f"OFI Std: {df['ofi'].std():.4f}")
            print(f"OFI Range: [{df['ofi'].min():.4f}, {df['ofi'].max():.4f}]")
        
    finally:
        await trading_provider.close()

if __name__ == "__main__":
    import sys
    
    # Parse arguments
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    interval = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    
    print(f"OFI Recorder")
    print(f"Symbol: {symbol}")
    print(f"Duration: {duration} minutes")
    print(f"Interval: {interval} seconds")
    print(f"Press Ctrl+C to stop early\n")
    
    asyncio.run(record_ofi(symbol, duration, interval))
