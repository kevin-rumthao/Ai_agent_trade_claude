
import asyncio
import aiohttp
import os
import zipfile
import argparse
from datetime import datetime
from pathlib import Path

BASE_URL = "https://data.binance.vision/data/spot/daily"

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
    parser = argparse.ArgumentParser(description="Download Binance Depth Data")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Trading symbol")
    parser.add_argument("--date", type=str, required=True, help="Date in YYYY-MM-DD or YYYY-MM format")
    parser.add_argument("--period", type=str, choices=["daily", "monthly"], default="daily", help="Data period")
    parser.add_argument("--output", type=str, default="data/raw", help="Output directory")
    
    args = parser.parse_args()
    
    symbol = args.symbol.upper()
    date_str = args.date
    period = args.period
    
    # URL Construction
    if period == "monthly":
        # Format: data/spot/monthly/depthUpdate/BTCUSDT/BTCUSDT-depthUpdate-2023-01.zip
        base_path = f"{BASE_URL.replace('daily', 'monthly')}"
        update_filename = f"{symbol}-depthUpdate-{date_str}.zip"
        # Monthly usually doesn't have a single "depth" snapshot for the month, 
        # but sometimes they archive daily snapshots in monthly? 
        # Actually, for reconstruction, we might need to rely on just updates if snapshot is missing, 
        # but that is impossible without a generic snapshot.
        # Let's assume user wants updates. Snapshot might be tricky in monthly.
        # We will try to download the update file.
        snapshot_filename = f"{symbol}-depth-{date_str}.zip" 
    else:
        # Daily
        base_path = BASE_URL
        update_filename = f"{symbol}-depthUpdate-{date_str}.zip"
        snapshot_filename = f"{symbol}-depth-{date_str}.zip"

    # Setup paths
    output_dir = Path(args.output) / symbol / period / date_str
    output_dir.mkdir(parents=True, exist_ok=True)

    update_url = f"{base_path}/depthUpdate/{symbol}/{update_filename}"
    # Snapshot path is tricky for monthly, let's try same pattern
    snapshot_url = f"{base_path}/depth/{symbol}/{snapshot_filename}"
    
    print(f"Target URL (Update): {update_url}")
    print(f"Target URL (Snapshot): {snapshot_url}")
    
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
        # Download Updates
        success_update = await download_file(session, update_url, output_dir / update_filename)
        
        # Download Snapshots
        success_snapshot = await download_file(session, snapshot_url, output_dir / snapshot_filename)
        
        if success_update:
            print(f"Successfully downloaded updates to {output_dir}")
            try:
                with zipfile.ZipFile(output_dir / update_filename, 'r') as zip_ref:
                    zip_ref.extractall(output_dir)
                    print(f"Extracted updates.")
            except Exception as e:
                print(f"Extraction error: {e}")
        
        if success_snapshot:
            print(f"Successfully downloaded snapshot to {output_dir}")
            try:
                with zipfile.ZipFile(output_dir / snapshot_filename, 'r') as zip_ref:
                    zip_ref.extractall(output_dir)
                    print(f"Extracted snapshot.")
            except Exception as e:
                print(f"Extraction error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
