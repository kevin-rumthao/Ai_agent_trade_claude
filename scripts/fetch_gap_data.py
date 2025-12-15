"""
Script to fetch historical klines from Binance for a SPECIFIC DATE RANGE.
Uses public API endpoints (no keys required).
"""
import csv
import requests
import argparse
import time
from datetime import datetime, timedelta
from pathlib import Path

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
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching data: {e}")
        time.sleep(1) # Backoff
        return []

def main():
    # HARDCODED RANGE FOR THE GAP
    symbol = "BTCUSDT"
    interval = "1m"
    
    # Range: Nov 26, 2022 to Dec 14, 2024
    start_dt = datetime(2022, 11, 26)
    end_dt = datetime(2024, 12, 14)
    
    output_file = "data/BTCUSDT_2022_2024_gap.csv"
    
    start_ts = int(start_dt.timestamp() * 1000)
    end_ts = int(end_dt.timestamp() * 1000)
    
    print(f"Fetching GAP data for {symbol}...")
    print(f"Range: {start_dt} -> {end_dt}")
    print(f"Output: {output_file}")
    
    all_klines = []
    current_start = start_ts
    
    while current_start < end_ts:
        print(f"Fetching from {datetime.fromtimestamp(current_start/1000)}...", end='\r')
        klines = fetch_klines(symbol, interval, current_start, end_ts)
        
        if not klines:
            if current_start > end_ts:
                break
            break
            
        all_klines.extend(klines)
        
        # Update start time for next batch (last close time + 1ms)
        # kline[6] is Close Time
        current_start = klines[-1][6] + 1
        
        # Rate limit/niceness
        time.sleep(0.1)
        
    print(f"\nFetched {len(all_klines)} klines.")
    
    # Save to CSV
    with open(output_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "symbol", "open", "high", "low", "close", "volume", "bid", "ask"])
        
        for k in all_klines:
            # Binance kline format
            ts = datetime.fromtimestamp(k[0] / 1000).isoformat()
            open_p = float(k[1])
            high_p = float(k[2])
            low_p = float(k[3])
            close_p = float(k[4])
            volume = float(k[5])
            
            # Simulate bid/ask
            bid = close_p * 0.9999
            ask = close_p * 1.0001
            
            writer.writerow([
                ts,
                symbol,
                open_p,
                high_p,
                low_p,
                close_p,
                volume,
                bid,
                ask
            ])
            
    print(f"Saved to {output_file}")

if __name__ == "__main__":
    main()
