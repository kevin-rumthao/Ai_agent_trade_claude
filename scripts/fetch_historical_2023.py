#!/usr/bin/env python3
"""Download BTCUSDT 1m data for 2023-2024 from Binance."""
import asyncio
import aiohttp
import ssl
import certifi
import csv
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUTPUT_FILE = os.path.join(DATA_DIR, "BTCUSDT_2023_2024_1m.csv")
BASE_URL = "https://api.binance.com/api/v3/klines"

async def fetch_klines(session, start_ms, end_ms):
    params = {"symbol": "BTCUSDT", "interval": "1m", "startTime": start_ms, "endTime": end_ms, "limit": 1000}
    async with session.get(BASE_URL, params=params) as resp:
        return await resp.json() if resp.status == 200 else []

async def main():
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=ssl_context)

    start_ms = int(datetime(2023, 1, 1).timestamp() * 1000)
    end_ms = int(datetime(2025, 1, 1).timestamp() * 1000)

    all_klines = []
    current = start_ms

    async with aiohttp.ClientSession(connector=connector) as session:
        while current < end_ms:
            batch = await fetch_klines(session, current, end_ms)
            if not batch: break
            all_klines.extend(batch)
            current = batch[-1][0] + 60000
            days = len(all_klines) / (60 * 24)
            print(f"  {len(all_klines):,} candles ({days:.0f} days)...")
            await asyncio.sleep(0.1)

    print(f"\nTotal: {len(all_klines):,} candles")
    with open(OUTPUT_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "symbol", "open", "high", "low", "close", "volume"])
        for k in all_klines:
            ts = datetime.fromtimestamp(k[0] / 1000).strftime("%Y-%m-%dT%H:%M:%S")
            writer.writerow([ts, "BTCUSDT", float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])])
    print(f"Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
