
import pandas as pd

input_file = "data/nifty50_15m.csv"
output_file = "data/nifty50_clean.csv"

try:
    print(f"Reading {input_file}...")
    # Skip the first 3 rows which seem to be multi-index header junk
    # Actually, looking at the 'head' output:
    # Row 0: Price,Close,High...
    # Row 1: Ticker,^NSEI...
    # Row 2: Datetime,,,,,
    # Row 3: Data...
    
    # Let's try reading with header=0, skipping rows 1 and 2
    # Or simpler: Read all, set columns manually.
    
    df = pd.read_csv(input_file, header=0, parse_dates=True)
    
    # Drop rows 0 and 1 (Ticker and Datetime text rows)
    df = df.iloc[2:]
    
    # Rename columns based on index
    # The structure saw in head:
    # Index (Datetime), Close, High, Low, Open, Volume
    # Wait, the first column in the file content preview was: "2025-09-19..." which is the index?
    # No, line 4 is data.
    # Col 0: Index (Datetime)
    # Col 1: Close (based on "Price,Close" alignment?)
    # Let's verify column mapping carefully.
    # Line 1: Price,Close,High,Low,Open,Volume
    # So Col 0 matches Price (Empty?), Col 1 matches Close...
    
    # Let's do a cleaner read:
    # Read just the data part (skip 3 lines) and allow pandas to infer columns, but we provide names.
    
    df_clean = pd.read_csv(input_file, 
                           skiprows=3, 
                           names=["timestamp", "close", "high", "low", "open", "volume"])
    
    # Reorder to standard: timestamp, symbol, open, high, low, close, volume
    df_clean["symbol"] = "NIFTY50"
    
    # Ensure float
    cols = ["open", "high", "low", "close", "volume"]
    for c in cols:
        df_clean[c] = pd.to_numeric(df_clean[c], errors='coerce')
        
    # Reorder
    df_final = df_clean[["timestamp", "symbol", "open", "high", "low", "close", "volume"]]
    
    # Fill bid/ask for compatibility
    df_final["bid"] = df_final["close"]
    df_final["ask"] = df_final["close"]
    
    print(f"Saving to {output_file}...")
    df_final.to_csv(output_file, index=False)
    print("Done.")

except Exception as e:
    print(f"Error: {e}")
