
import pandas as pd
import sys

def analyze_ofi(file_path):
    df = pd.read_csv(file_path)
    print(f"Analyzing {len(df)} rows...")
    
    # Calculate simple stats
    print("\nDescriptive Statistics for OFI (Net Buy Vol - Sell Vol):")
    print(df['ofi'].describe())
    
    # Percentiles
    p25 = df['ofi'].quantile(0.25)
    p75 = df['ofi'].quantile(0.75)
    p90 = df['ofi'].quantile(0.90)
    p10 = df['ofi'].quantile(0.10)
    
    print(f"\nBuying Pressure (Above 0): {(df['ofi'] > 0).mean()*100:.1f}% of time")
    print(f"Selling Pressure (Below 0): {(df['ofi'] < 0).mean()*100:.1f}% of time")
    
    print(f"\nProposed Thresholds:")
    print(f"Strong Buy (> 75th percentile): {p75:.4f}")
    print(f"Strong Sell (< 25th percentile): {p25:.4f}")
    print(f"Extreme Buy (> 90th percentile): {p90:.4f}")
    print(f"Extreme Sell (< 10th percentile): {p10:.4f}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        analyze_ofi(sys.argv[1])
    else:
        print("Usage: python analyze_ofi.py <csv_file>")
