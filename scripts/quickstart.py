#!/usr/bin/env python3
"""Quick start script to help configure the trading system.

This interactive script guides you through the setup process.
"""
import os
from pathlib import Path


def main():
    print("=" * 70)
    print("   LangGraph Trading Agent - Quick Start Setup")
    print("=" * 70)
    print()

    # Check if .env already exists
    env_path = Path(".env")
    if env_path.exists():
        print("⚠️  .env file already exists!")
        overwrite = input("Do you want to overwrite it? (y/N): ").strip().lower()
        if overwrite != 'y':
            print("Exiting without changes.")
            return
        print()

    print("Let's configure your trading system.\n")

    # Step 1: Choose provider
    print("Step 1: Choose Trading Provider")
    print("-" * 70)
    print("1. Alpaca (Recommended for beginners - FREE paper trading)")
    print("2. Binance (Crypto trading - testnet available)")
    print()

    while True:
        provider_choice = input("Enter choice (1 or 2): ").strip()
        if provider_choice in ['1', '2']:
            break
        print("Invalid choice. Please enter 1 or 2.")

    provider = "alpaca" if provider_choice == '1' else "binance"
    print(f"✓ Selected: {provider.upper()}\n")

    # Step 2: Get API keys
    print("Step 2: Enter API Credentials")
    print("-" * 70)

    config = {
        'TRADING_PROVIDER': provider
    }

    if provider == "alpaca":
        print("Get your Alpaca paper trading keys from:")
        print("https://app.alpaca.markets/paper/dashboard/overview")
        print()
        alpaca_key = input("Enter Alpaca API Key: ").strip()
        alpaca_secret = input("Enter Alpaca API Secret: ").strip()
        config['ALPACA_API_KEY'] = alpaca_key
        config['ALPACA_API_SECRET'] = alpaca_secret
        config['BINANCE_API_KEY'] = ""
        config['BINANCE_API_SECRET'] = ""

        print("\nStep 3: Choose Trading Symbol")
        print("-" * 70)
        print("Examples: AAPL (Apple), TSLA (Tesla), BTCUSD (Bitcoin)")
        symbol = input("Enter symbol (default: AAPL): ").strip() or "AAPL"
        config['SYMBOL'] = symbol
        config['TESTNET'] = "true"

    else:  # binance
        print("Get your Binance testnet keys from:")
        print("https://testnet.binance.vision/")
        print()
        binance_key = input("Enter Binance API Key: ").strip()
        binance_secret = input("Enter Binance API Secret: ").strip()
        config['BINANCE_API_KEY'] = binance_key
        config['BINANCE_API_SECRET'] = binance_secret
        config['ALPACA_API_KEY'] = ""
        config['ALPACA_API_SECRET'] = ""

        print("\nStep 3: Choose Trading Symbol")
        print("-" * 70)
        print("Examples: BTCUSDT (Bitcoin), ETHUSDT (Ethereum)")
        symbol = input("Enter symbol (default: BTCUSDT): ").strip() or "BTCUSDT"
        config['SYMBOL'] = symbol

        use_testnet = input("Use testnet? (Y/n): ").strip().lower()
        config['TESTNET'] = "false" if use_testnet == 'n' else "true"

    print("\nStep 4: Gemini LLM API Key")
    print("-" * 70)
    print("Get your Gemini API key from: https://ai.google.dev/")
    gemini_key = input("Enter Gemini API Key: ").strip()
    config['GEMINI_API_KEY'] = gemini_key

    # Step 5: Risk parameters
    print("\nStep 5: Risk Parameters (optional - press Enter for defaults)")
    print("-" * 70)

    if provider == "alpaca":
        max_pos = input("Max position size in shares (default: 10): ").strip() or "10"
    else:
        max_pos = input("Max position size in BTC (default: 0.01): ").strip() or "0.01"

    config['MAX_POSITION_SIZE'] = max_pos

    max_dd = input("Max drawdown percent (default: 10.0): ").strip() or "10.0"
    config['MAX_DRAWDOWN_PERCENT'] = max_dd

    max_loss = input("Max daily loss USD (default: 1000.0): ").strip() or "1000.0"
    config['MAX_DAILY_LOSS'] = max_loss

    loop_interval = input("Loop interval seconds (default: 60): ").strip() or "60"
    config['LOOP_INTERVAL_SECONDS'] = loop_interval

    config['LOG_LEVEL'] = "INFO"

    # Step 6: Write .env file
    print("\n" + "=" * 70)
    print("Creating .env file...")

    env_content = f"""# Trading Provider Selection
# Options: "binance" or "alpaca"
TRADING_PROVIDER="{config['TRADING_PROVIDER']}"

# Binance API Keys (for testnet or mainnet)
BINANCE_API_KEY="{config['BINANCE_API_KEY']}"
BINANCE_API_SECRET="{config['BINANCE_API_SECRET']}"

# Alpaca API Keys (always uses paper trading)
ALPACA_API_KEY="{config['ALPACA_API_KEY']}"
ALPACA_API_SECRET="{config['ALPACA_API_SECRET']}"

# Gemini LLM API Key
GEMINI_API_KEY="{config['GEMINI_API_KEY']}"

# Trading Configuration
SYMBOL="{config['SYMBOL']}"
TESTNET={config['TESTNET']}

# Risk Parameters
MAX_POSITION_SIZE={config['MAX_POSITION_SIZE']}
MAX_DRAWDOWN_PERCENT={config['MAX_DRAWDOWN_PERCENT']}
MAX_DAILY_LOSS={config['MAX_DAILY_LOSS']}

# Strategy Parameters
EMA_SHORT_PERIOD=9
EMA_LONG_PERIOD=50
ATR_PERIOD=14
VOLATILITY_LOOKBACK=20

# Application Settings
LOG_LEVEL="{config['LOG_LEVEL']}"
ENABLE_BACKTESTING=false
LOOP_INTERVAL_SECONDS={config['LOOP_INTERVAL_SECONDS']}

# LLM Configuration
LLM_MODEL="gemini-1.5-pro"
LLM_TEMPERATURE=0.0
LLM_MAX_TOKENS=1024
"""

    with open(".env", "w") as f:
        f.write(env_content)

    print("✓ .env file created successfully!")
    print()

    # Step 7: Next steps
    print("=" * 70)
    print("   Setup Complete! Next Steps:")
    print("=" * 70)
    print()
    print("1. Run health checks to verify configuration:")
    print("   poetry run python -m app.healthcheck")
    print()
    print("2. If health checks pass, start trading:")
    print("   poetry run python -m app.main")
    print()
    print("3. Monitor the output and check your paper trading account")
    print()

    if provider == "alpaca":
        print("View your Alpaca paper trading dashboard:")
        print("https://app.alpaca.markets/paper/dashboard/overview")
    else:
        testnet_msg = "testnet" if config['TESTNET'] == "true" else "MAINNET (REAL MONEY!)"
        print(f"You're using Binance {testnet_msg}")
        if config['TESTNET'] == "false":
            print("⚠️  WARNING: You are using REAL MONEY. Start with small positions!")

    print()
    print("For detailed documentation, see:")
    print("- README.md - Overview and quick start")
    print("- docs/SETUP_GUIDE.md - Complete setup guide")
    print()
    print("Happy trading! 🚀")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        print("Please check your inputs and try again.")

