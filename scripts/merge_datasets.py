
import pandas as pd
import os

def merge_datasets():
    # Define file paths
    file_1 = "data/data_btc.csv"             # Nov 2020 - Nov 2022
    file_2 = "data/BTCUSDT_2022_2024_gap.csv" # Nov 2022 - Dec 2024
    file_3 = "data/BTCUSDT_1y_1m.csv"         # Dec 2024 - Dec 2025
    
    output_file = "data/BTCUSDT_5Y_MASTER.csv"
    
    print("Loading datasets...")
    
    dfs = []
    
    # Load File 1
    if os.path.exists(file_1):
        print(f"Reading {file_1}...")
        df1 = pd.read_csv(file_1)
        dfs.append(df1)
    else:
        print(f"⚠️ Warning: {file_1} not found!")

    # Load File 2
    if os.path.exists(file_2):
        print(f"Reading {file_2}...")
        df2 = pd.read_csv(file_2)
        dfs.append(df2)
    else:
        print(f"⚠️ Warning: {file_2} not found!")

    # Load File 3
    if os.path.exists(file_3):
        print(f"Reading {file_3}...")
        df3 = pd.read_csv(file_3)
        dfs.append(df3)
    else:
        print(f"⚠️ Warning: {file_3} not found!")

    if not dfs:
        print("No data loaded. Aborting.")
        return

    print("Concatenating...")
    master_df = pd.concat(dfs, ignore_index=True)
    
    # Ensure timestamp is datetime
    print("Processing timestamps...")
    master_df['timestamp'] = pd.to_datetime(master_df['timestamp'], format='mixed', utc=True)
    
    # Sort
    print("Sorting chronologically...")
    master_df = master_df.sort_values('timestamp')
    
    # Deduplicate
    initial_len = len(master_df)
    print(f"Initial rows: {initial_len}")
    
    print("Deduplicating...")
    master_df = master_df.drop_duplicates(subset=['timestamp'], keep='first')
    final_len = len(master_df)
    
    print(f"Removed {initial_len - final_len} duplicate rows.")
    print(f"Final dataset size: {final_len} rows.")
    print(f"Date Range: {master_df['timestamp'].min()} -> {master_df['timestamp'].max()}")
    
    # Save
    print(f"Saving to {output_file}...")
    master_df.to_csv(output_file, index=False)
    print("Done.")

if __name__ == "__main__":
    merge_datasets()
