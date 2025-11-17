# ✅ COMPLETE - Your Questions Answered

## How to Stop the Program

### Simple Answer
**Press `Ctrl + C` in the terminal**

The program will shut down gracefully:
```
^C
2025-11-16 10:45:00 - INFO - Shutting down trading system (Ctrl+C pressed)...
2025-11-16 10:45:01 - INFO - Trading system stopped cleanly
2025-11-16 10:45:01 - INFO - Total iterations completed: 23
```

### New Feature: Automatic Stop

I've added two new options to automatically stop the system:

**Option 1: Limit Iterations**
```env
MAX_ITERATIONS=50  # Stops after 50 trading cycles
```

**Option 2: Limit Time**
```env
TIME_LIMIT_HOURS=1.0  # Stops after 1 hour
```

Add these to your `.env` file and the system will stop automatically!

---

## API Call Frequency

### Per Trading Cycle (Every 60 seconds by default)

#### Alpaca Calls: **4-6 calls**
1. `get_orderbook()` - 1 call
2. `get_recent_trades()` - 1 call
3. `get_klines()` - 1 call
4. `get_portfolio_state()` - 1 call
5. `execute_order()` - 0-2 calls (only if trading)

#### Gemini Calls: **1-2 calls**
1. `classify_regime_with_llm()` - 0-1 call (only if needed)
2. `get_trading_advice()` - 0-1 call (rarely used)

### Per Hour (Default 60s interval)

| Metric | Count |
|--------|-------|
| **Iterations** | 60 |
| **Alpaca API Calls** | 240-360 |
| **Gemini API Calls** | 60-120 |

### Per Day (24 hours continuous)

| Metric | Count |
|--------|-------|
| **Iterations** | 1,440 |
| **Alpaca API Calls** | 5,760-8,640 |
| **Gemini API Calls** | 1,440-2,880 |

⚠️ **Gemini Free Tier Limit**: 1,500 requests/day
- You'll hit this limit with default settings if running 24/7
- Solution: Increase `LOOP_INTERVAL_SECONDS` or set `TIME_LIMIT_HOURS`

---

## Recommended Configurations

### First-Time Test (30 minutes)
```env
LOOP_INTERVAL_SECONDS=180  # Every 3 minutes
MAX_ITERATIONS=10          # Stop after 10 cycles
```
**Total API calls**: ~40-60 Alpaca, ~10-20 Gemini ✅ Safe!

### Day Trading Session (6 hours)
```env
LOOP_INTERVAL_SECONDS=120  # Every 2 minutes
TIME_LIMIT_HOURS=6         # Stop after 6 hours
```
**Total API calls**: ~720-1,080 Alpaca, ~180-360 Gemini ✅ Safe!

### Extended Testing (Within free tier)
```env
LOOP_INTERVAL_SECONDS=300  # Every 5 minutes
MAX_ITERATIONS=0           # Unlimited
```
**API calls per day**: ~576-864 Alpaca, ~144-288 Gemini ✅ Safe!

### Production 24/7 (Requires paid tier)
```env
LOOP_INTERVAL_SECONDS=60   # Every minute
MAX_ITERATIONS=0           # Unlimited
```
**API calls per day**: ~5,760-8,640 Alpaca, ~1,440-2,880 Gemini
⚠️ **Exceeds Gemini free tier!**

---

## Cost & Limits

### Alpaca (Paper Trading)
- ✅ **Free forever**
- ✅ **Limit**: 200 requests/minute
- ✅ **Your usage**: ~4-6 calls/minute
- ✅ **No concerns!**

### Gemini (Free Tier)
- ✅ **Free**: 15 requests/minute
- ✅ **Free**: 1,500 requests/day
- ⚠️ **Your usage**: 60-120 calls/hour (with 60s interval)
- ⚠️ **Daily**: ~1,440-2,880 calls (24/7 = EXCEEDS FREE TIER)

**Solutions**:
1. Use `TIME_LIMIT_HOURS` to limit runtime
2. Increase `LOOP_INTERVAL_SECONDS` to 120-300
3. Set `MAX_ITERATIONS` for controlled runs
4. Upgrade to Gemini paid tier for production

---

## Files Updated

I've made the following improvements:

### 1. Added New Configuration Options
**File**: `src/app/config.py`
- `MAX_ITERATIONS` - Stop after N trading cycles
- `TIME_LIMIT_HOURS` - Stop after N hours

### 2. Updated Main Loop
**File**: `src/app/main.py`
- Checks iteration limit
- Checks time limit
- Better shutdown messages
- Reports total iterations completed

### 3. Created Documentation
- `CONTROL_GUIDE.md` - Complete guide on stopping and API usage
- `QUICK_START_CARD.md` - One-page reference
- Updated `.env` - Added new options with comments

---

## Quick Commands

### Run Trading System
```bash
poetry run python -m app.main
```

### Stop Trading System
Press `Ctrl + C`

### Test Gemini API
```bash
poetry run python scripts/test_gemini.py
```

### Test Alpaca API
```bash
poetry run python scripts/test_alpaca.py
```

### View All Guides
- `CONTROL_GUIDE.md` - Detailed control and API info
- `QUICK_START_CARD.md` - Quick reference
- `FINAL_CONFIGURATION.md` - Setup summary
- `QUICK_REFERENCE.md` - Command reference

---

## Your System Is Ready! 🎉

Everything is now configured with:
✅ Graceful shutdown with `Ctrl + C`
✅ Optional automatic stop limits
✅ Clear API call tracking
✅ Safe default configurations
✅ Comprehensive documentation

**Run your first test:**
```bash
# Edit .env first:
# MAX_ITERATIONS=10
# LOOP_INTERVAL_SECONDS=180

poetry run python -m app.main
```

This will run for ~30 minutes and make ~40-60 API calls total. Perfect for learning! 🚀

