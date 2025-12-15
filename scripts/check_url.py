
import aiohttp
import asyncio

BASE_URL = "https://data.binance.vision/data/spot"

async def check(session, url):
    try:
        async with session.head(url) as response:
            print(f"[{response.status}] {url}")
            return response.status == 200
    except Exception as e:
        print(f"[ERR] {url}: {e}")
        return False

async def main():
    urls = [
        # Control: Monthly Klines (Should exist)
        f"{BASE_URL}/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2024-01.zip",
        
        # Target: Monthly Depth Update
        f"{BASE_URL}/monthly/depthUpdate/BTCUSDT/BTCUSDT-depthUpdate-2024-01.zip",
        
        # Target: Daily Depth Update (First day of month)
        f"{BASE_URL}/daily/depthUpdate/BTCUSDT/BTCUSDT-depthUpdate-2024-01-01.zip",
        
        # Alternate: trades (Should exist)
        f"{BASE_URL}/monthly/trades/BTCUSDT/BTCUSDT-trades-2024-01.zip",
        
        # Alternate: aggTrades
        f"{BASE_URL}/monthly/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2024-01.zip"
    ]
    
    print("Probing Binance Data Vision...")
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
        for url in urls:
            await check(session, url)

if __name__ == "__main__":
    asyncio.run(main())
