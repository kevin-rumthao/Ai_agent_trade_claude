#!/usr/bin/env python3
"""Test Alpaca API connection directly."""
import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Get credentials
api_key = os.getenv("ALPACA_API_KEY")
api_secret = os.getenv("ALPACA_API_SECRET")

print("=" * 70)
print("Testing Alpaca API Connection")
print("=" * 70)
print(f"\nAPI Key: {api_key}")
print(f"API Secret: {api_secret[:10]}...{api_secret[-10:]}")
print(f"Endpoint: https://paper-api.alpaca.markets/v2")
print()

try:
    from alpaca.trading.client import TradingClient

    print("Initializing TradingClient...")
    client = TradingClient(api_key, api_secret, paper=True)

    print("✅ Client initialized successfully!")
    print("\nFetching account info...")

    account = client.get_account()

    print("✅ Account retrieved successfully!")
    print(f"\nAccount Details:")
    print(f"  - Account Number: {account.account_number}")
    print(f"  - Status: {account.status}")
    print(f"  - Cash: ${float(account.cash):,.2f}")
    print(f"  - Portfolio Value: ${float(account.portfolio_value):,.2f}")
    print(f"  - Buying Power: ${float(account.buying_power):,.2f}")
    print(f"  - Pattern Day Trader: {account.pattern_day_trader}")

    print("\n" + "=" * 70)
    print("✅ SUCCESS! Alpaca API is working correctly!")
    print("=" * 70)

except ImportError as e:
    print(f"❌ Error: alpaca-py not installed")
    print(f"   Run: poetry install")

except Exception as e:
    print(f"❌ Error connecting to Alpaca:")
    print(f"   {type(e).__name__}: {e}")
    print(f"\nTroubleshooting:")
    print(f"  1. Verify API keys are correct in .env")
    print(f"  2. Ensure you're using PAPER trading keys (start with PK)")
    print(f"  3. Check if keys are active at https://app.alpaca.markets/paper/dashboard/api-keys")

