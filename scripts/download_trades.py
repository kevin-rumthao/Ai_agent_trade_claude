
import asyncio
import aiohttp
import os
import zipfile
import argparse
from datetime import datetime
from pathlib import Path

BASE_URL = "https://data.binance.vision/data/spot"

async def download_file(session: aiohttp.ClientSession, url: str, dest_path: Path):
    """Download a file from URL to destination."""
    print(f"Downloading {url}...")
    try:
        async with session.get(url) as response:
            if response.status != 200:
                print(f"Failed to download {url}: Status {response.status}")
                return False
            
            with open(dest_path, 'wb') as f:
                while True:
                    chunk = await response.content.read(1024*1024) # 1MB chunks
                    if not chunk:
                        break
                    f.write(chunk)
        print(f"Saved to {dest_path}")
        return True
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return False

async def main():
    parser = argparse.ArgumentParser(description="Download Binance Trade Data")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Trading symbol")
    parser.add_argument("--date", type=str, required=True, help="Date in YYYY-MM-DD or YYYY-MM format")
    parser.add_argument("--period", type=str, choices=["daily", "monthly"], default="daily", help="Data period")
    parser.add_argument("--output", type=str, default="data/raw_trades", help="Output directory")
    
    args = parser.parse_args()
    
    symbol = args.symbol.upper()
    date_str = args.date
    period = args.period
    
    # URL Construction
    # Monthly: data/spot/monthly/trades/BTCUSDT/BTCUSDT-trades-2023-01.zip
    # Daily: data/spot/daily/trades/BTCUSDT/BTCUSDT-trades-2023-01-01.zip
    
    if period == "monthly":
        base_path = f"{BASE_URL}/monthly/trades/{symbol}"
        filename = f"{symbol}-trades-{date_str}.zip"
    else:
        base_path = f"{BASE_URL}/daily/trades/{symbol}"
        filename = f"{symbol}-trades-{date_str}.zip"

    # Setup paths
    output_dir = Path(args.output) / symbol / period / date_str
    output_dir.mkdir(parents=True, exist_ok=True)

    url = f"{base_path}/{filename}"
    
    print(f"Target URL: {url}")
    
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
        # Download
        success = await download_file(session, url, output_dir / filename)
        
        if success:
            print(f"Successfully downloaded to {output_dir}")
            try:
                print("Extracting...")
                with zipfile.ZipFile(output_dir / filename, 'r') as zip_ref:
                    zip_ref.extractall(output_dir)
                print(f"Extracted archive.")
            except Exception as e:
                print(f"Extraction error: {e}")
        else:
            print("\nWARNING: Download failed.")
            print("Check if the date exists on Binance Vision.")

if __name__ == "__main__":
    asyncio.run(main())
