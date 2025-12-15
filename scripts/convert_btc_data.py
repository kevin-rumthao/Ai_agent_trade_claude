
import pandas as pd
import sys

input_file = "data/data_btc.xlsx"
output_file = "data/data_btc.csv"

try:
    print(f"Reading {input_file}...")
    df = pd.read_excel(input_file)
    
    print(f"Writing to {output_file}...")
    # Convert timestamp to standard string format before saving to match csv expectations if needed,
    # but to_csv usually handles datetime objects fine.
    df.to_csv(output_file, index=False)
    print("Conversion complete.")

except Exception as e:
    print(f"Error converting file: {e}")
