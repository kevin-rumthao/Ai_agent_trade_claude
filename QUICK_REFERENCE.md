# Quick Reference Guide

## Installation

```bash
cd /Users/kevin/Desktop/Ai_agent_trade_claude
poetry install
```

## Interactive Setup (Recommended)

```bash
poetry run python scripts/quickstart.py
```

## Health Check

```bash
poetry run python -m app.healthcheck
```

Expected output:
```
✅ All health checks passed
```

## Run Trading System

```bash
poetry run python -m app.main
```

## Run Tests

```bash
poetry run pytest -v
```

## Environment Variables

### Essential

| Variable | Description | Example |
|----------|-------------|---------|
| `TRADING_PROVIDER` | Trading backend | `alpaca` or `binance` |
| `GEMINI_API_KEY` | LLM API key | `AI...` |
| `SYMBOL` | Trading pair | `AAPL`, `BTCUSD`, `BTCUSDT` |

### Alpaca (Paper Trading)

| Variable | Description | Where to Get |
|----------|-------------|--------------|
| `ALPACA_API_KEY` | Alpaca key | https://app.alpaca.markets/paper |
| `ALPACA_API_SECRET` | Alpaca secret | https://app.alpaca.markets/paper |

### Binance (Crypto)

| Variable | Description | Where to Get |
|----------|-------------|--------------|
| `BINANCE_API_KEY` | Binance key | https://testnet.binance.vision/ |
| `BINANCE_API_SECRET` | Binance secret | https://testnet.binance.vision/ |
| `TESTNET` | Use testnet? | `true` (safe) or `false` (real $) |

### Risk Parameters

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_POSITION_SIZE` | `0.1` | Max position size (BTC or shares) |
| `MAX_DRAWDOWN_PERCENT` | `10.0` | Stop if drawdown exceeds % |
| `MAX_DAILY_LOSS` | `1000.0` | Stop if daily loss exceeds $ |
| `LOOP_INTERVAL_SECONDS` | `60` | Time between trading cycles |

## Symbol Formats

### Alpaca
- Stocks: `AAPL`, `TSLA`, `NVDA`, `SPY`
- Crypto: `BTCUSD`, `ETHUSD`

### Binance
- Crypto: `BTCUSDT`, `ETHUSDT`, `BNBUSDT`

## Common Commands

### Check Configuration
```bash
cat .env
```

### View Logs
```bash
poetry run python -m app.main 2>&1 | tee trading.log
```

### Stop Trading
Press `Ctrl+C`

### Reset Alpaca Paper Account
1. Go to https://app.alpaca.markets/paper/dashboard/overview
2. Settings → Reset Account
3. Confirm (restores to $100K)

## Example Configurations

### Conservative (Alpaca Paper Trading)
```env
TRADING_PROVIDER="alpaca"
ALPACA_API_KEY="PK..."
ALPACA_API_SECRET="..."
GEMINI_API_KEY="..."
SYMBOL="AAPL"
MAX_POSITION_SIZE=5
MAX_DRAWDOWN_PERCENT=3.0
LOOP_INTERVAL_SECONDS=300
```

### Moderate (Binance Testnet)
```env
TRADING_PROVIDER="binance"
BINANCE_API_KEY="..."
BINANCE_API_SECRET="..."
GEMINI_API_KEY="..."
SYMBOL="BTCUSDT"
TESTNET=true
MAX_POSITION_SIZE=0.01
MAX_DRAWDOWN_PERCENT=10.0
LOOP_INTERVAL_SECONDS=60
```

### Aggressive (Use with Caution!)
```env
TRADING_PROVIDER="binance"
BINANCE_API_KEY="..."
BINANCE_API_SECRET="..."
GEMINI_API_KEY="..."
SYMBOL="BTCUSDT"
TESTNET=false  # REAL MONEY!
MAX_POSITION_SIZE=0.1
MAX_DRAWDOWN_PERCENT=15.0
LOOP_INTERVAL_SECONDS=30
```

## Troubleshooting

### "GEMINI_API_KEY is not set"
→ Add your Gemini key to `.env`

### "alpaca-py library not installed"
→ Run `poetry install`

### "Failed to fetch orderbook"
→ Check API keys are correct in `.env`

### "Symbol not found"
→ Use correct format for your provider (see Symbol Formats above)

### "Unknown trading provider"
→ Set `TRADING_PROVIDER` to `alpaca` or `binance`

### Health checks fail
→ Verify API keys, check network, ensure services are up

## Monitoring

### View Alpaca Account
https://app.alpaca.markets/paper/dashboard/overview

### Check Order History
See dashboard → Orders

### View Positions
See dashboard → Positions

### Performance Metrics
See dashboard → Performance

## Safety Checklist

Before going live with real money:

- [ ] Tested ≥1 week with paper trading
- [ ] Positive results in backtesting
- [ ] Understand all strategy parameters
- [ ] Set conservative risk limits
- [ ] Have monitoring in place
- [ ] Start with tiny positions
- [ ] Can manually intervene if needed
- [ ] Keep API keys secure

## Support

- **Setup Guide**: `docs/SETUP_GUIDE.md`
- **Full Documentation**: `README.md`
- **Improvements**: `IMPROVEMENTS.md`
- **Architecture**: `docs/architecture.md`

## Quick Tips

1. **Always start with paper trading** (Alpaca)
2. **Run health checks** before trading
3. **Monitor the first few hours** closely
4. **Start conservative** - you can always increase position sizes
5. **Keep logs** for debugging
6. **Don't trade on untested code**
7. **Secure your API keys** (never commit to git)

## Architecture

```
Market Data → Features → Regime → Strategy → Risk → Execution
    ↓            ↓          ↓         ↓        ↓       ↓
[Provider]   [Technical] [LLM AI] [Momentum] [Limits] [Orders]
```

## Key Files

- `src/app/main.py` - Main entry point
- `src/app/config.py` - Configuration
- `src/app/healthcheck.py` - Health checks
- `src/app/tools/trading_provider.py` - Provider abstraction
- `src/app/tools/alpaca_tool.py` - Alpaca integration
- `src/app/tools/binance_tool.py` - Binance integration
- `src/app/tools/llm_tool.py` - Gemini LLM

## Development

### Add New Strategy
1. Create node in `src/app/nodes/`
2. Update graph in `src/app/langgraph_graphs/`
3. Add tests in `src/tests/`

### Add New Provider
1. Create tool in `src/app/tools/` implementing `TradingProvider`
2. Update `trading_provider.py` factory
3. Add config in `config.py`
4. Update health checks

## License

MIT - See LICENSE file

