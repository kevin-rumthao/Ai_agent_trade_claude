import pandas as pd
import matplotlib.pyplot as plt
import os

def load_and_plot(file_path):
    print(f"Loading data from {file_path}...")
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    try:
        # Load the CSV
        df = pd.read_csv(file_path, low_memory=False)
        
        # Convert timestamp to datetime
        # The timestamp format in the file is like '2020-11-27 00:25:00+00:00'
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            print("Timestamp column processed and set as index.")
        else:
            print("Warning: 'timestamp' column not found. Plotting using index.")

        # Plotting
        plt.figure(figsize=(12, 6))
        
        if 'close' in df.columns:
            plt.plot(df.index, df['close'], label='Close Price', linewidth=1)
            plt.title('BTCUSDT Close Price Over Time')
            plt.ylabel('Price (USDT)')
            plt.xlabel('Date')
            plt.legend()
            plt.grid(True)
            
            # formatting date on x-axis slightly better if possible, but automatic is usually fine
            plt.tight_layout()
            
            print("Plot generated. Displaying...")
            plt.show()
        else:
            print("Error: 'close' column not found in data.")
            print("Available columns:", df.columns)

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    # Path relative to the project root, assuming script is run from project root
    # or adapted if run from scripts folder.
    # We'll try to resolve the path dynamically or assume project root execution.
    
    # Defaulting to the path provided by the user relative to project root
    file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'BTCUSDT_5Y_MASTER.csv')
    
    # Fallback if running from root
    if not os.path.exists(file_path):
        file_path = 'data/BTCUSDT_5Y_MASTER.csv'
        
    load_and_plot(file_path)
