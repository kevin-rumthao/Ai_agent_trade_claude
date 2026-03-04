
import csv
import requests
import time
import os
import sys
from datetime import datetime, timedelta

MASTER_FILE = "data/BTCUSDT_5Y_MASTER.csv"
NEW_FILE = "data/BTCUSDT_GAP_FILLED.csv"
SYMBOL = "BTCUSDT"
INTERVAL = "1m"

def get_last_timestamp(filename):
    """Reads the last line of the CSV to get the last timestamp."""
    try:
        with open(filename, 'rb') as f:
            try:
                f.seek(-2, os.SEEK_END)
                while f.read(1) != b'\n':
                    f.seek(-2, os.SEEK_CUR)
            except OSError:
                f.seek(0)
            last_line = f.readline().decode()
            
            if not last_line:
                return None
                
            # Parse last line
            # Format: timestamp,open,high,low,close,volume,...
            # Example: 2025-12-15 12:06:00+00:00,...
            parts = last_line.split(',')
            ts_str = parts[0]
            
            # Simple ISO format parsing (stripping timezone for simplicity if needed, or using fromisoformat)
            try:
                dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            except ValueError:
                # Fallback for standard string
                dt = datetime.strptime(ts_str.split('+')[0], "%Y-%m-%d %H:%M:%S")
                
            return int(dt.timestamp() * 1000)
    except FileNotFoundError:
        print(f"Error: {filename} not found.")
        sys.exit(1)

def fetch_klines(symbol, interval, start_time, end_time):
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
        print(f"Error: {e}")
        time.sleep(1)
        return []

def main():
    print(f"Reading last timestamp from {MASTER_FILE}...")
    last_ts = get_last_timestamp(MASTER_FILE)
    
    if last_ts is None:
        print("Could not verify last timestamp. Exiting.")
        return

    start_ts = last_ts + 60000 # Start 1 min after last data
    end_ts = int(datetime.now().timestamp() * 1000)
    
    print(f"Last Data: {datetime.fromtimestamp(last_ts/1000)}")
    print(f"Fetch Range: {datetime.fromtimestamp(start_ts/1000)} -> {datetime.fromtimestamp(end_ts/1000)}")
    
    all_klines = []
    current_start = start_ts
    
    while current_start < end_ts:
        print(f"Fetching from {datetime.fromtimestamp(current_start/1000)}...", end='\r')
        klines = fetch_klines(SYMBOL, INTERVAL, current_start, end_ts)
        
        if not klines:
            break
            
        all_klines.extend(klines)
        current_start = klines[-1][6] + 1
        time.sleep(0.1)
        
    print(f"\nFetched {len(all_klines)} new candles.")
    
    if len(all_klines) == 0:
        print("No new data to append.")
        return

    # Append to Master File
    print(f"Appending to {MASTER_FILE}...")
    
    with open(MASTER_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        # No header, just append
        for k in all_klines:
            ts = datetime.fromtimestamp(k[0] / 1000).isoformat()
            open_p, high_p, low_p, close_p, volume = k[1], k[2], k[3], k[4], k[5]
            
            # Match existing format: variable cols usually (timestamp,open,high,low,close,volume,symbol,bid,ask)
            # We must be careful to match the master columns exactly.
            # Master header: timestamp,open,high,low,close,volume,symbol,bid,ask
            
            bid = float(close_p) * 0.9999
            ask = float(close_p) * 1.0001
            
            writer.writerow([
                ts,
                open_p, high_p, low_p, close_p, volume,
                SYMBOL,
                bid, ask
            ])
            
    print("✅ Update Complete.")

if __name__ == "__main__":
    main()
