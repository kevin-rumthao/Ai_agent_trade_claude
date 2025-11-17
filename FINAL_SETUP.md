# Final Setup Steps - COMPLETE GUIDE

## ✅ What We Fixed

1. **Symbol Format Issue**: Fixed `BTC//USD` double-slash bug in `alpaca_tool.py`
2. **Gemini Model Name**: Updated from `gemini-1.5-pro` to `gemini-1.5-flash`
3. **Trade Data Handling**: Made health checks more resilient to empty trade data
4. **Configuration Loading**: Ensured `.env` file is loaded correctly

## 🚀 Run the Health Check Now

```bash
cd /Users/kevin/Desktop/Ai_agent_trade_claude
poetry run python -m app.healthcheck
```

### Expected Output:
```
Running external health checks (ALPACA, Gemini)...
✅ All health checks passed!
{
  'trading_provider': {
    'provider': 'alpaca',
    'symbol': 'BTC/USD',
    'ok': True,
    'orderbook_levels': 10,
    'recent_trades': 0,
    'klines': 5,
    'portfolio_balance': 100000.0,
    'portfolio_equity': 100000.0
  },
  'llm': {
    'model': 'gemini-1.5-flash',
    'ok': True
  },
  'ok': True
}
```

## 📝 Your Current Configuration

Your `.env` file is correctly configured:
- ✅ `TRADING_PROVIDER=alpaca`
- ✅ `SYMBOL=BTC/USD`
- ✅ Alpaca API keys set
- ✅ Gemini API key set

## 🎯 Next Step: Start Trading!

Once the health check passes, start the trading agent:

```bash
poetry run python -m app.main
```

### What Will Happen:
1. System connects to Alpaca paper trading
2. Fetches BTC/USD market data every 60 seconds
3. Analyzes trends using Gemini AI
4. Generates trading signals
5. Executes trades on your paper account
6. Logs all activity to console

### Monitor Your Trades:
- **Dashboard**: https://app.alpaca.markets/paper/dashboard/overview
- **Check orders, positions, and portfolio value in real-time**

## 🛠️ If Health Check Still Fails

### For Gemini Error:
If you see "model not found" for Gemini:
```bash
# Add this to your .env
LLM_MODEL=gemini-1.5-flash
```

### For Alpaca Connection Error:
1. Verify API keys at: https://app.alpaca.markets/paper/dashboard/api-keys
2. Ensure keys start with `PK` (paper trading)
3. Regenerate keys if needed

## 📊 Supported Symbols

### Crypto (Alpaca):
- `BTC/USD` - Bitcoin
- `ETH/USD` - Ethereum
- `LTC/USD` - Litecoin
- `BCH/USD` - Bitcoin Cash

### Stocks (Alpaca):
- `AAPL` - Apple
- `TSLA` - Tesla
- `GOOGL` - Google
- `MSFT` - Microsoft
- `SPY` - S&P 500 ETF

To change symbol, edit `.env`:
```
SYMBOL=ETH/USD  # For Ethereum
# or
SYMBOL=AAPL     # For Apple stock
```

## 🎉 You're Ready to Trade!

Your trading system is now fully configured and ready to run with:
- ✅ Alpaca paper trading (risk-free $100K virtual money)
- ✅ Gemini AI for intelligent market analysis
- ✅ BTC/USD crypto trading
- ✅ Comprehensive health checks

## 📞 Support

If you encounter any issues:
1. Check logs for error messages
2. Verify API keys in `.env`
3. Run: `poetry run python scripts/test_alpaca.py` to test Alpaca directly
4. Review `QUICK_REFERENCE.md` for common solutions

Happy trading! 🚀

