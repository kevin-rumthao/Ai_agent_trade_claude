#!/usr/bin/env python3
"""
Script to process raw tick-by-tick trades into OHLCV candles.
Reads large CSV files in chunks to avoid memory issues.
"""
import pandas as pd
import argparse
import os
from datetime import datetime

# Default input/output
INPUT_FILE = "data/raw_trades/BTCUSDT/monthly/2024-01/BTCUSDT-trades-2024-01.csv"
OUTPUT_FILE = "data/BTCUSDT_2024_01_1m.csv"
CHUNK_SIZE = 1_000_000 # Rows per chunk

def process_trades(input_file: str, output_file: str, interval: str = "1min"):
    print(f"Processing {input_file}...")
    print(f"Output: {output_file}")
    print(f"Interval: {interval}")
    print(f"Chunk Size: {CHUNK_SIZE}")
    
    if not os.path.exists(input_file):
        print(f"Error: Input file not found: {input_file}")
        return

    # Check headers - raw data usually doesn't have headers or has specific ones
    # The file viewed earlier has: id, price, qty, quote_qty, time, is_buyer_maker, is_best_match
    # No header row in the sample viewed.
    
    # We'll use an iterator to read in chunks
    # Headers: id, price, qty, quote_qty, time, is_buyer_maker, is_best_match
    headers = ['id', 'price', 'qty', 'quote_qty', 'time', 'is_buyer_maker', 'is_best_match']
    
    processed_chunks = []
    
    try:
        reader = pd.read_csv(
            input_file, 
            names=headers, 
            chunksize=CHUNK_SIZE,
            iterator=True
        )
        
        total_rows = 0
        
        for i, chunk in enumerate(reader):
            # Convert time (ms) to datetime
            chunk['timestamp'] = pd.to_datetime(chunk['time'], unit='ms')
            chunk.set_index('timestamp', inplace=True)
            
            # Resample this chunk
            # Note: We need to be careful with boundaries. 
            # Ideally, we should group by time, but chunks might split a minute.
            # However, for 1m simulation from 50M rows, slight boundary artifacts are acceptable 
            # OR we can aggregate fully at the end.
            # Better approach for memory: Resample reducing to 1m, then concat, then resample again.
            
            chunk_ohlcv = chunk['price'].resample(interval).ohlc()
            chunk_vol = chunk['qty'].resample(interval).sum()
            
            combined = pd.concat([chunk_ohlcv, chunk_vol], axis=1)
            combined.columns = ['open', 'high', 'low', 'close', 'volume']
            
            processed_chunks.append(combined)
            
            total_rows += len(chunk)
            print(f"Processed chunk {i+1} ({len(chunk)} rows)... Total: {total_rows}")
            
    except Exception as e:
        print(f"Error processing file: {e}")
        return

    print("Aggregating chunks...")
    # Concatenate all processed chunks
    full_df = pd.concat(processed_chunks)
    
    # Resample again to handle chunk boundaries (e.g., minute 10:00 split across chunks)
    # Group by index (timestamp) and aggregate
    final_df = full_df.groupby(full_df.index).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    })
    
    # Sort
    final_df = final_df.sort_index()
    
    # Filter empty rows (minutes with no trades)
    final_df = final_df[final_df['volume'] > 0]
    
    # Save
    final_df.to_csv(output_file)
    print(f"Saved {len(final_df)} candles to {output_file}")
    
    # Show sample
    print("\nSample Data:")
    print(final_df.head())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process raw trades to candles")
    parser.add_argument("--input", type=str, default=INPUT_FILE, help="Input raw CSV")
    parser.add_argument("--output", type=str, default=OUTPUT_FILE, help="Output candles CSV")
    
    args = parser.parse_args()
    
    process_trades(args.input, args.output)
