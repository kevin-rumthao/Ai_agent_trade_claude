import asyncio
import os
import ssl
import certifi
import aiohttp
from binance.async_client import AsyncClient
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv

# Load env
load_dotenv(".env")
api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")

async def test_keys():
    print(f"Testing keys: {api_key[:10]}...")
    
    
    # 1. Test Spot Testnet
    print("\n--- Testing Spot Testnet (testnet.binance.vision) ---")
    # New connector for this session
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    connector1 = aiohttp.TCPConnector(ssl=ssl_context)
    
    client = await AsyncClient.create(api_key, api_secret, testnet=True, session_params={"connector": connector1})
    try:
        acct = await client.get_account()
        print("✅ SUCCESS: Keys work for SPOT Testnet")
        print(f"Balances: {len(acct['balances'])}")
    except BinanceAPIException as e:
        print(f"❌ FAILED: {e}")
    except Exception as e:
        print(f"❌ ERROR: {e}")
    finally:
        await client.close_connection()

    # 2. Test Futures Testnet
    print("\n--- Testing Futures Testnet ---")
    # New connector for this session
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    connector2 = aiohttp.TCPConnector(ssl=ssl_context)
    
    # Re-create client
    client = await AsyncClient.create(api_key, api_secret, testnet=True, session_params={"connector": connector2})
    try:
        # This uses https://testnet.binancefuture.com/fapi/v1/...
        acct = await client.futures_account()
        print("✅ SUCCESS: Keys work for FUTURES Testnet")
        print(f"Total Margin Balance: {acct['totalMarginBalance']}")
    except BinanceAPIException as e:
        print(f"❌ FAILED: {e}")
    except Exception as e:
        print(f"❌ ERROR: {e}")
    finally:
        await client.close_connection()

if __name__ == "__main__":
    asyncio.run(test_keys())
