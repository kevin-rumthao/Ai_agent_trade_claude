
import json
import csv
import glob
import os
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime

class OrderBook:
    """
    Maintains a local Order Book state (Bids and Asks).
    """
    def __init__(self):
        self.bids: Dict[float, float] = {}  # Price -> Qty
        self.asks: Dict[float, float] = {}  # Price -> Qty
        self.last_update_id = 0
        self.timestamp = 0

    def apply_snapshot(self, snapshot: dict):
        """
        Initialize book from snapshot JSON.
        Snapshot format: {"lastUpdateId": 123, "bids": [[price, qty], ...], "asks": ...}
        """
        self.last_update_id = snapshot['lastUpdateId']
        # Clear existing
        self.bids = {}
        self.asks = {}
        
        # Load bids
        for price_str, qty_str in snapshot['bids']:
            self.bids[float(price_str)] = float(qty_str)
            
        # Load asks
        for price_str, qty_str in snapshot['asks']:
            self.asks[float(price_str)] = float(qty_str)
            
        print(f"Snapshot applied. ID: {self.last_update_id}. Bids: {len(self.bids)}, Asks: {len(self.asks)}")

    def update(self, update_data: dict):
        """
        Apply a depth update.
        Update format (derived from CSV):
        {
            "U": first_update_id,
            "u": final_update_id,
            "b": [[price, qty], ...],
            "a": [[price, qty], ...]
        }
        """
        # Validation
        if update_data['u'] <= self.last_update_id:
            return  # Skip old update
            
        # Check continuity? (Optional for now, assuming correct stream)
        # In a strictly compliant replayer, we should check U <= last_update_id + 1
        
        self.last_update_id = update_data['u']
        
        # Apply Bids
        for price, qty in update_data['b']:
            price_f = float(price)
            qty_f = float(qty)
            if qty_f == 0.0:
                if price_f in self.bids:
                    del self.bids[price_f]
            else:
                self.bids[price_f] = qty_f
                
        # Apply Asks
        for price, qty in update_data['a']:
            price_f = float(price)
            qty_f = float(qty)
            if qty_f == 0.0:
                if price_f in self.asks:
                    del self.asks[price_f]
            else:
                self.asks[price_f] = qty_f

    def get_best_bid_ask(self) -> Tuple[float, float, float, float]:
        """Return (best_bid, best_ask, bid_qty, ask_qty)."""
        if not self.bids or not self.asks:
            return 0.0, 0.0, 0.0, 0.0
            
        best_bid = max(self.bids.keys())
        best_ask = min(self.asks.keys())
        return best_bid, best_ask, self.bids[best_bid], self.asks[best_ask]

    def get_mid_price(self) -> float:
        bb, ba, _, _ = self.get_best_bid_ask()
        if bb == 0 or ba == 0:
            return 0.0
        return (bb + ba) / 2.0

class OFICalculator:
    """
    Calculates Order Flow Imbalance (OFI).
    """
    def __init__(self):
        self.prev_best_bid = 0.0
        self.prev_best_ask = 0.0
        self.prev_bid_qty = 0.0
        self.prev_ask_qty = 0.0
        
    def calculate(self, best_bid: float, best_ask: float, bid_qty: float, ask_qty: float) -> float:
        """
        Calculate Step-OFI based on change from previous state.
        OFI = q_b_change - q_a_change
        """
        if self.prev_best_bid == 0:
            # First tick
            self.prev_best_bid = best_bid
            self.prev_best_ask = best_ask
            self.prev_bid_qty = bid_qty
            self.prev_ask_qty = ask_qty
            return 0.0
            
        # Bid Contribution
        if best_bid > self.prev_best_bid:
            ofi_bid = bid_qty
        elif best_bid < self.prev_best_bid:
            ofi_bid = -self.prev_bid_qty
        else: # Unchanged
            ofi_bid = bid_qty - self.prev_bid_qty
            
        # Ask Contribution
        if best_ask > self.prev_best_ask:
            ofi_ask = -self.prev_ask_qty
        elif best_ask < self.prev_best_ask:
            ofi_ask = ask_qty
        else: # Unchanged
            ofi_ask = ask_qty - self.prev_ask_qty
            
        # Total OFI
        ofi = ofi_bid - ofi_ask
        
        # Update State
        self.prev_best_bid = best_bid
        self.prev_best_ask = best_ask
        self.prev_bid_qty = bid_qty
        self.prev_ask_qty = ask_qty
        
        return ofi

def run_replay(data_dir: str, output_file: str):
    """
    Replay raw data to generate features.
    """
    path = Path(data_dir)
    print(f"Scanning {path} for data...")
    
    # 1. Find Files
    # Expecting output from downloader: /symbol/daily/date/...
    # Trying to find ANY json/csv
    jsons = list(path.glob("**/*.json"))
    if not jsons:
         # Try ZIPs if not extracted? But user should extract.
         # Actually downloader extracted.
         # Binance snapshots might be text files not .json extension inside zip?
         # Common name: 'BTCUSDT_depth_...'
         jsons = list(path.glob("**/*depth*.txt")) + list(path.glob("**/*depth*.json"))
    
    csvs = list(path.glob("**/*depthUpdate*.csv"))
    if not csvs:
         # Try text
         csvs = list(path.glob("**/*depthUpdate*.txt"))

    if not jsons or not csvs:
        print("Error: Could not find Snapshot (json/txt) and Update (csv/txt) files.")
        return

    snapshot_file = sorted(jsons)[0]
    update_file = sorted(csvs)[0]
    
    print(f"Using Snapshot: {snapshot_file.name}")
    print(f"Using Updates: {update_file.name}")
    
    # 2. Load Snapshot
    ob = OrderBook()
    with open(snapshot_file, 'r') as f:
        # Sometimes format is pure JSON, sometimes line-based?
        # Binance Vision snapshot is usually a single JSON object.
        try:
            snapshot = json.load(f)
        except json.JSONDecodeError:
            # Maybe it's a TXT with one line?
            f.seek(0)
            content = f.read()
            snapshot = json.loads(content)
            
    ob.apply_snapshot(snapshot)
    
    # 3. Stream Updates
    ofi_calc = OFICalculator()
    results = []
    
    # Chunk reading for memory efficiency
    chunk_size = 10000 
    
    # We need to sample OFI at 1-minute bars ideally.
    # Accumulate OFI within the minute? Or just last value?
    # Usually "Accumulated OFI" (sum of tick OFIs) or "Average OFI" per minute.
    # Let's sum it.
    
    current_minute_ts = 0
    minute_ofi_sum = 0.0
    minute_ticks = 0
    
    # CSV Headers: event_time, first_update_id, final_update_id, symbol, bids, asks
    # Warning: Binance CSVs often have no header! We must check.
    # Assuming standard columns: timestamp(ms), first_id, final_id, symbol, bids, asks (6 cols)
    
    print("Starting Replay...")
    
    for chunk in pd.read_csv(update_file, chunksize=chunk_size, header=None, names=['ts', 'U', 'u', 's', 'b', 'a']):
        for _, row in chunk.iterrows():
            ts = int(row['ts'])
            
            # Parse Bids/Asks (Stringified JSON)
            bids = json.loads(row['b'])
            asks = json.loads(row['a'])
            
            updates = {
                'u': row['u'],
                'b': bids,
                'a': asks
            }
            
            ob.update(updates)
            
            # Calculate OFI
            bb, ba, bq, aq = ob.get_best_bid_ask()
            tick_ofi = ofi_calc.calculate(bb, ba, bq, aq)
            
            # Aggregation logic
            # TS is ms.
            minute_ts = (ts // 60000) * 60
            
            if current_minute_ts == 0:
                current_minute_ts = minute_ts
                
            if minute_ts > current_minute_ts:
                # Close bar
                mid = ob.get_mid_price()
                results.append({
                    'timestamp': datetime.fromtimestamp(current_minute_ts),
                    'ofi': minute_ofi_sum,
                    'mid_price': mid,
                    'ticks': minute_ticks
                })
                
                # Reset
                current_minute_ts = minute_ts
                minute_ofi_sum = 0.0
                minute_ticks = 0
                
            minute_ofi_sum += tick_ofi
            minute_ticks += 1
            
        print(f"Processed ~{chunk_size} rows. Current Time: {datetime.fromtimestamp(current_minute_ts)}")

    # Save
    df = pd.DataFrame(results)
    df.to_csv(output_file, index=False)
    print(f"Exported {len(df)} 1-minute samples to {output_file}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python reconstruct_orderbook.py <input_dir> <output_file>")
    else:
        run_replay(sys.argv[1], sys.argv[2])
