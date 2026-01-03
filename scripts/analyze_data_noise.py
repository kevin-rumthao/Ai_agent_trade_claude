import pandas as pd
import numpy as np

file_path = 'data/BTCUSDT_5Y_MASTER.csv'
try:
    df = pd.read_csv(file_path)
    print(f"Total Rows: {len(df)}")
    print(f"Columns: {df.columns.tolist()}")
    
    # Check for NaNs
    print(f"NaNs:\n{df.isna().sum()}")
    
    # Check for duplicate timestamps
    if 'timestamp' in df.columns:
        dupes = df.duplicated(subset=['timestamp']).sum()
        print(f"Duplicate Timestamps: {dupes}")
        
    # Check for flat candles (Open = High = Low = Close)
    # Ensure columns are numeric
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        
    flat_candles = df[(df['open'] == df['close']) & (df['high'] == df['low']) & (df['open'] == df['high'])]
    print(f"Flat Candles (Zero Volatility): {len(flat_candles)}")
    
    # Check for Zero Volume
    zero_vol = df[df['volume'] == 0]
    print(f"Zero Volume Candles: {len(zero_vol)}")
    
    # Check for Price Jumps (Noise?)
    # Calculate % change
    df['pct_change'] = df['close'].pct_change()
    outliers = df[abs(df['pct_change']) > 0.10] # > 10% move in 1 minute?
    print(f"Extreme Moves (>10% in 1m): {len(outliers)}")
    
    if len(outliers) > 0:
        print("Sample Outliers:")
        print(outliers[['timestamp', 'close', 'pct_change']].head())

except Exception as e:
    print(f"Error: {e}")
