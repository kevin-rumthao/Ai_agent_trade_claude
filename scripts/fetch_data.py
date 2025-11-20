"""
Script to fetch historical klines from Binance for backtesting.
Uses public API endpoints (no keys required).
"""
import csv
import requests
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
SYMBOL = "BTCUSDT"
INTERVAL = "1h"
DAYS = 30
OUTPUT_FILE = "data/backtest_data.csv"

def fetch_klines(symbol: str, interval: str, start_time: int, end_time: int):
    """Fetch klines from Binance."""
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_time,
        "endTime": end_time,
        "limit": 1000
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def main():
    # Create data directory
    Path("data").mkdir(exist_ok=True)
    
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=DAYS)
    
    start_ts = int(start_dt.timestamp() * 1000)
    end_ts = int(end_dt.timestamp() * 1000)
    
    print(f"Fetching {DAYS} days of {INTERVAL} data for {SYMBOL}...")
    
    all_klines = []
    current_start = start_ts
    
    while current_start < end_ts:
        print(f"Fetching from {datetime.fromtimestamp(current_start/1000)}...")
        klines = fetch_klines(SYMBOL, INTERVAL, current_start, end_ts)
        
        if not klines:
            break
            
        all_klines.extend(klines)
        
        # Update start time for next batch (last close time + 1ms)
        current_start = klines[-1][6] + 1
        
    print(f"Fetched {len(all_klines)} klines.")
    
    # Save to CSV
    # Format: timestamp,symbol,price,volume,bid,ask,bid_qty,ask_qty
    # We use Close price for price/bid/ask to simulate
    
    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "symbol", "price", "volume", "bid", "ask", "bid_qty", "ask_qty"])
        
        for k in all_klines:
            # Binance kline format:
            # [0] Open time, [1] Open, [2] High, [3] Low, [4] Close, [5] Volume, ...
            ts = datetime.fromtimestamp(k[0] / 1000).isoformat()
            close_price = float(k[4])
            volume = float(k[5])
            
            # Simulate bid/ask with small spread
            bid = close_price * 0.9999
            ask = close_price * 1.0001
            
            writer.writerow([
                ts,
                SYMBOL,
                close_price,
                volume,
                bid,
                ask,
                1.0, # dummy bid qty
                1.0  # dummy ask qty
            ])
            
    print(f"Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
