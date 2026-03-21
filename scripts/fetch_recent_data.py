#!/usr/bin/env python3
"""Download missing BTCUSDT 1m data from Binance API (no API key needed for public endpoints)."""
import asyncio
import aiohttp
import ssl
import certifi
import csv
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
EXISTING_FILE = os.path.join(DATA_DIR, "BTCUSDT_1y_1m.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "BTCUSDT_20251216_20260318_1m.csv")
MERGED_FILE = os.path.join(DATA_DIR, "BTCUSDT_16m_1m.csv")

BASE_URL = "https://api.binance.com/api/v3/klines"
SYMBOL = "BTCUSDT"
INTERVAL = "1m"
LIMIT = 1000  # max per request

async def fetch_klines(session, start_ms, end_ms):
    """Fetch klines from Binance."""
    params = {
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": LIMIT
    }
    async with session.get(BASE_URL, params=params) as resp:
        if resp.status == 200:
            return await resp.json()
        else:
            print(f"Error: {resp.status} - {await resp.text()}")
            return []

async def main():
    print("Downloading missing BTCUSDT 1m data from Binance...")
    print(f"Period: 2025-12-16 to 2026-03-18")

    # SSL context using certifi
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=ssl_context)

    # Start from Dec 16, 2025 00:00
    start_dt = datetime(2025, 12, 16, 0, 0, 0)
    # End at Mar 18, 2026 (now)
    end_dt = datetime(2026, 3, 18, 0, 0, 0)

    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)

    all_klines = []
    current_start = start_ms

    async with aiohttp.ClientSession(connector=connector) as session:
        while current_start < end_ms:
            batch = await fetch_klines(session, current_start, end_ms)
            if not batch:
                print(f"  No more data at {datetime.fromtimestamp(current_start/1000)}")
                break

            all_klines.extend(batch)
            current_start = batch[-1][0] + 60000

            total_min = len(all_klines)
            total_days = total_min / (60 * 24)
            print(f"  Downloaded {total_min:,} candles ({total_days:.1f} days)...")

            await asyncio.sleep(0.1)

    print(f"\nTotal new candles: {len(all_klines):,}")

    # Write new data
    print(f"Writing to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "symbol", "open", "high", "low", "close", "volume"])
        for k in all_klines:
            ts = datetime.fromtimestamp(k[0] / 1000).strftime("%Y-%m-%dT%H:%M:%S")
            writer.writerow([
                ts, SYMBOL,
                float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])
            ])

    # Merge with existing data
    print(f"Merging with existing data...")
    rows = []

    with open(EXISTING_FILE, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append([
                row['timestamp'], row['symbol'],
                float(row['open']), float(row['high']),
                float(row['low']), float(row['close']),
                float(row['volume'])
            ])

    with open(OUTPUT_FILE, 'r') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            rows.append(row)

    rows.sort(key=lambda r: r[0])

    seen = set()
    deduped = []
    for row in rows:
        if row[0] not in seen:
            seen.add(row[0])
            deduped.append(row)

    with open(MERGED_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "symbol", "open", "high", "low", "close", "volume"])
        for row in deduped:
            writer.writerow(row)

    print(f"\nMerged file: {MERGED_FILE}")
    print(f"Total candles: {len(deduped):,}")
    print(f"Date range: {deduped[0][0]} to {deduped[-1][0]}")
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
