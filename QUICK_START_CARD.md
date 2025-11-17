# 🚀 Quick Start Card

## Start Trading
```bash
poetry run python -m app.main
```

## Stop Trading
**Press:** `Ctrl + C`

---

## ⚙️ Essential .env Settings

```env
# Trading Provider
TRADING_PROVIDER=alpaca

# Symbol
SYMBOL=BTC/USD  # or AAPL, ETH/USD, etc.

# API Keys
ALPACA_API_KEY=your-key-here
ALPACA_API_SECRET=your-secret-here
GEMINI_API_KEY=your-gemini-key

# Loop Control
LOOP_INTERVAL_SECONDS=60    # How often to check markets
MAX_ITERATIONS=0            # 0 = unlimited, or set limit
TIME_LIMIT_HOURS=0          # 0 = unlimited, or set hours
```

---

## 📊 API Usage per Hour

| Interval | Iterations | Alpaca Calls | Gemini Calls |
|----------|------------|--------------|--------------|
| 60s | 60 | 240-360 | 60-120 |
| 120s | 30 | 120-180 | 30-60 |
| 300s | 12 | 48-72 | 12-24 |

---

## 🎯 Recommended First Run

```env
LOOP_INTERVAL_SECONDS=180
MAX_ITERATIONS=10
```
**Result**: ~30 minutes, ~40-60 Alpaca calls, ~10-20 Gemini calls

---

## 📍 Monitor Trades
https://app.alpaca.markets/paper/dashboard/overview

---

## 🆘 Help
- **Control Guide**: `CONTROL_GUIDE.md`
- **Setup Guide**: `FINAL_CONFIGURATION.md`
- **Quick Reference**: `QUICK_REFERENCE.md`

