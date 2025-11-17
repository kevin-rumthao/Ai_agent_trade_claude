#!/usr/bin/env python3
"""Test configuration loading."""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Load environment
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).parent.parent / ".env"
print(f"Loading .env from: {env_path}")
print(f".env exists: {env_path.exists()}")
load_dotenv(dotenv_path=env_path)

# Check raw env vars
print("\n=== Raw Environment Variables ===")
print(f"TRADING_PROVIDER: {os.getenv('TRADING_PROVIDER')}")
print(f"SYMBOL: {os.getenv('SYMBOL')}")
print(f"ALPACA_API_KEY: {os.getenv('ALPACA_API_KEY', 'NOT SET')[:20]}...")
print(f"GEMINI_API_KEY: {os.getenv('GEMINI_API_KEY', 'NOT SET')[:20]}...")

# Check settings object
print("\n=== Settings Object ===")
from app.config import settings
print(f"trading_provider: {settings.trading_provider}")
print(f"symbol: {settings.symbol}")
print(f"alpaca_api_key: {settings.alpaca_api_key[:20]}...")
print(f"gemini_api_key: {settings.gemini_api_key[:20]}...")

print("\n✅ Configuration test complete!")

