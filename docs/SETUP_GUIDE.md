# Complete Setup Guide

This guide walks you through setting up the trading system from scratch, with special focus on Alpaca paper trading for safe testing.

## Prerequisites

- Python 3.11 or higher
- macOS, Linux, or Windows with WSL
- Internet connection
- Basic understanding of trading concepts

## Step 1: Clone and Install

```bash
# Navigate to project directory
cd /Users/kevin/Desktop/Ai_agent_trade_claude

# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install project dependencies
poetry install

# Activate virtual environment
poetry shell
```

## Step 2: Get Alpaca Paper Trading Credentials (Recommended)

Alpaca provides **free paper trading** - perfect for testing without risking real money.

1. **Sign up for Alpaca**:
   - Go to https://alpaca.markets/
   - Click "Sign Up" and create an account
   - Verify your email

2. **Access Paper Trading**:
   - Log in to your account
   - You'll automatically have a paper trading account
   - Go to https://app.alpaca.markets/paper/dashboard/overview

3. **Generate API Keys**:
   - Click on "API Keys" in the left sidebar
   - Click "Generate New Key"
   - **Important**: Save both the API Key and Secret Key immediately
   - You won't be able to see the secret key again!

4. **Paper Trading Features**:
   - Start with $100,000 virtual cash
   - Real-time market data
   - Realistic order execution
   - Reset account anytime
   - No risk to real money

## Step 3: Get Gemini API Key

Google's Gemini LLM powers the intelligent regime classification.

1. **Get API Key**:
   - Go to https://ai.google.dev/
   - Click "Get API Key"
   - Sign in with Google account
   - Create a new API key

2. **Free Tier**:
   - Generous free quota for testing
   - Rate limits apply
   - Upgrade if needed for production

## Step 4: Configure Environment Variables

Create a `.env` file in the project root:

```bash
# Copy the example and edit
cp .env .env.local
nano .env
```

**For Alpaca Paper Trading (Recommended for Beginners)**:

```env
# Trading Provider
TRADING_PROVIDER="alpaca"

# Alpaca Paper Trading Keys
ALPACA_API_KEY="PK..."  # Your paper trading key
ALPACA_API_SECRET="..."  # Your paper trading secret

# Gemini LLM
GEMINI_API_KEY="..."  # Your Gemini API key

# Trading Configuration
SYMBOL="AAPL"  # Start with stocks (AAPL, TSLA, etc.) or BTCUSD for crypto
TESTNET=true  # Ignored for Alpaca (always paper)

# Risk Parameters (conservative defaults)
MAX_POSITION_SIZE=10  # Max 10 shares for stocks
MAX_DRAWDOWN_PERCENT=5.0  # Stop if losing more than 5%
MAX_DAILY_LOSS=500.0  # Stop if daily loss exceeds $500

# Strategy Parameters
EMA_SHORT_PERIOD=9
EMA_LONG_PERIOD=50
LOOP_INTERVAL_SECONDS=60  # Run every 60 seconds

# Logging
LOG_LEVEL="INFO"
```

**For Binance Testnet (Crypto Testing)**:

```env
# Trading Provider
TRADING_PROVIDER="binance"

# Binance Testnet Keys
BINANCE_API_KEY="..."  # From testnet.binance.vision
BINANCE_API_SECRET="..."

# Gemini LLM
GEMINI_API_KEY="..."

# Trading Configuration
SYMBOL="BTCUSDT"
TESTNET=true  # MUST be true for testnet

# Risk Parameters
MAX_POSITION_SIZE=0.01  # Max 0.01 BTC
MAX_DRAWDOWN_PERCENT=10.0
MAX_DAILY_LOSS=1000.0

# Logging
LOG_LEVEL="INFO"
```

## Step 5: Run Health Checks

Verify everything is configured correctly:

```bash
poetry run python -m app.healthcheck
```

**Expected Output** (Alpaca):
```
Running external health checks (ALPACA, Gemini)...
✅ All health checks passed
{
  'trading_provider': {
    'provider': 'alpaca',
    'symbol': 'AAPL',
    'ok': True,
    'orderbook_levels': 10,
    'recent_trades': 5,
    'klines': 5,
    'portfolio_balance': 100000.0,
    'portfolio_equity': 100000.0
  },
  'llm': {
    'model': 'gemini-1.5-pro',
    'regime': 'TRENDING',
    'confidence': 0.85,
    'ok': True
  },
  'ok': True
}
```

**Common Issues**:

| Error | Solution |
|-------|----------|
| `GEMINI_API_KEY is not set` | Add your Gemini key to `.env` |
| `Failed to fetch orderbook` | Check API keys are correct |
| `Symbol not found` | Use valid symbol: AAPL (stocks), BTCUSD (crypto on Alpaca) |
| `alpaca-py library not installed` | Run `poetry install` again |
| `Connection error` | Check internet connection |

## Step 6: Run Your First Test Trade

Start the trading system:

```bash
poetry run python -m app.main
```

**What Happens**:
1. Health checks run automatically
2. System connects to Alpaca paper trading
3. Trading graph is compiled
4. Main loop starts (runs every 60 seconds by default)

**Monitor the Output**:
```
2025-11-16 10:00:00 - INFO - Connected to ALPACA (PAPER TRADING)
2025-11-16 10:00:01 - INFO - Trading graph compiled successfully
2025-11-16 10:00:02 - INFO - Starting trading loop for AAPL
2025-11-16 10:00:02 - INFO - ============================================================
2025-11-16 10:00:02 - INFO - Trading Loop Iteration 1
2025-11-16 10:00:02 - INFO - ============================================================
2025-11-16 10:00:03 - INFO - Symbol: AAPL
2025-11-16 10:00:03 - INFO - Price: 189.50
2025-11-16 10:00:03 - INFO - EMA(9): 190.20, EMA(50): 188.10
2025-11-16 10:00:04 - INFO - Regime: TRENDING (confidence: 0.78)
2025-11-16 10:00:04 - INFO - Strategy: momentum
2025-11-16 10:00:05 - INFO - Signal: LONG (strength: 0.65, confidence: 0.70)
2025-11-16 10:00:05 - INFO - Risk check: PASSED
2025-11-16 10:00:06 - INFO - Executing order: BUY 5.0 AAPL
2025-11-16 10:00:07 - INFO - Order executed successfully: a7f9b234-...
```

**Stop the System**:
Press `Ctrl+C` to gracefully stop the trading loop.

## Step 7: Check Your Paper Trading Results

1. Go to https://app.alpaca.markets/paper/dashboard/overview
2. View your account balance and positions
3. Check order history
4. Review performance metrics

**Reset Your Account**:
If you want to start fresh:
- Go to Alpaca paper trading dashboard
- Settings → Reset Account
- Confirms reset (restores to $100,000)

## Step 8: Customize Your Strategy

### Adjust Symbol

Edit `.env`:
```env
# For stocks
SYMBOL="TSLA"  # Tesla
SYMBOL="NVDA"  # NVIDIA
SYMBOL="SPY"   # S&P 500 ETF

# For crypto (on Alpaca)
SYMBOL="BTCUSD"  # Bitcoin
SYMBOL="ETHUSD"  # Ethereum
```

### Tune Risk Parameters

More conservative:
```env
MAX_POSITION_SIZE=5  # Smaller positions
MAX_DRAWDOWN_PERCENT=3.0  # Tighter stop
LOOP_INTERVAL_SECONDS=300  # Check less frequently
```

More aggressive:
```env
MAX_POSITION_SIZE=50
MAX_DRAWDOWN_PERCENT=15.0
LOOP_INTERVAL_SECONDS=30
```

### Adjust Strategy Parameters

Edit `.env`:
```env
# Faster momentum (more signals)
EMA_SHORT_PERIOD=5
EMA_LONG_PERIOD=20

# Slower momentum (fewer signals)
EMA_SHORT_PERIOD=20
EMA_LONG_PERIOD=100
```

## Step 9: Run Tests

Ensure everything works:

```bash
# Run all tests
poetry run pytest -v

# Run specific test
poetry run pytest src/tests/test_ingest.py -v

# Run with coverage
poetry run pytest --cov=app --cov-report=html
```

## Step 10: Advanced Configuration

### Enable Backtesting

```env
ENABLE_BACKTESTING=true
BACKTEST_DATA_PATH="./data/historical_aapl.csv"
```

CSV format:
```csv
timestamp,symbol,price,volume,bid,ask,bid_qty,ask_qty
2025-11-16T10:00:00,AAPL,189.50,1000,189.48,189.52,100,100
```

### Customize LLM Model

```env
LLM_MODEL="gemini-1.5-flash"  # Faster, cheaper
LLM_TEMPERATURE=0.1  # More creative (0.0 = deterministic)
LLM_MAX_TOKENS=2048  # Longer responses
```

### Production Checklist (Before Real Money)

- [ ] Tested extensively with paper trading (1+ week)
- [ ] Positive results in backtesting
- [ ] Understand all strategy parameters
- [ ] Set appropriate risk limits
- [ ] Monitor system 24/7 or use stop-loss
- [ ] Start with very small position sizes
- [ ] Have manual override process
- [ ] Keep API keys secure

## Getting Help

**Check Logs**: All activity is logged - review for errors

**Run Health Checks**: `python -m app.healthcheck`

**Test Individual Components**:
```bash
# Test just the LLM
poetry run python -c "from app.tools.llm_tool import llm_tool; import asyncio; asyncio.run(llm_tool.classify_regime_with_llm(...))"

# Test just the provider
poetry run python -c "from app.tools.trading_provider import trading_provider; import asyncio; asyncio.run(trading_provider.initialize())"
```

**Community Support**: Check documentation in `/docs` folder

## Summary

You now have:
- ✅ A fully configured trading system
- ✅ Paper trading account for safe testing  
- ✅ LLM-powered market analysis
- ✅ Automated health checks
- ✅ Comprehensive logging and monitoring

**Remember**: Always test thoroughly with paper trading before risking real money!

