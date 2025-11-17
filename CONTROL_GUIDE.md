# 🎮 Trading System Control Guide

## How to Stop the Trading System

### Method 1: Keyboard Interrupt (Recommended)
Press **`Ctrl + C`** in the terminal where the program is running.

```bash
# While running...
poetry run python -m app.main

# Press: Ctrl + C

# You'll see:
^C
KeyboardInterrupt
System shutting down gracefully...
```

### Method 2: Kill Process (If Ctrl+C doesn't work)
```bash
# Find the process
ps aux | grep "app.main"

# Kill it
kill <PID>

# Or force kill
kill -9 <PID>
```

### Method 3: Close Terminal
Simply close the terminal window (not recommended as it may not clean up resources properly).

---

## 📊 API Call Frequency

### Current Configuration (Default)

Your system runs in a loop every **60 seconds** (configurable in `.env`):

```env
LOOP_INTERVAL_SECONDS=60  # Change this to adjust frequency
```

### API Calls Per Iteration (Every 60 Seconds)

#### **Alpaca API Calls** - Approximately **4-6 calls per iteration**

1. **Market Data Ingestion** (~3 calls):
   - `get_orderbook()` - 1 call
   - `get_recent_trades()` - 1 call  
   - `get_klines()` - 1 call

2. **Portfolio Check** (~1 call):
   - `get_portfolio_state()` - 1 call

3. **Order Execution** (0-2 calls):
   - `execute_order()` - Only if trading signal is generated
   - Usually 0-2 calls (depends on strategy decisions)

**Total Alpaca calls per hour (default 60s interval):**
- Minimum: ~240 calls/hour (4 calls × 60 iterations)
- Maximum: ~360 calls/hour (6 calls × 60 iterations)

#### **Gemini API Calls** - Approximately **1-2 calls per iteration**

1. **Regime Classification** (~1 call):
   - `classify_regime_with_llm()` - 1 call per iteration
   - Only called when rule-based classifier has ambiguity

2. **Trading Advice** (0-1 call):
   - `get_trading_advice()` - Optional, only if needed
   - Usually 0 calls (only for complex scenarios)

**Total Gemini calls per hour (default 60s interval):**
- Minimum: ~0 calls/hour (if rule-based classifier is confident)
- Typical: ~60 calls/hour (1 call × 60 iterations)
- Maximum: ~120 calls/hour (2 calls × 60 iterations)

---

## 💰 Cost Estimation

### Gemini API Costs (Free Tier)

Google Gemini has a generous free tier:
- **Free quota**: 15 requests per minute
- **Free quota**: 1,500 requests per day
- **Your usage**: ~60-120 calls/hour = ~1,440-2,880 calls/day

⚠️ **You may hit free tier limits if running continuously!**

**Recommendation**: Use slower intervals for extended testing:
```env
LOOP_INTERVAL_SECONDS=120  # Every 2 minutes = ~720 calls/day
LOOP_INTERVAL_SECONDS=300  # Every 5 minutes = ~288 calls/day
```

### Alpaca API Limits (Paper Trading)

Alpaca paper trading has generous limits:
- **Market Data**: 200 requests/minute
- **Trading**: Unlimited for paper trading
- **Your usage**: ~4-6 calls/minute (well within limits)

✅ **No concerns with Alpaca limits**

---

## ⚙️ Adjusting API Call Frequency

### Option 1: Change Loop Interval

Edit `.env`:
```env
# Run every 2 minutes (30 iterations/hour)
LOOP_INTERVAL_SECONDS=120

# Run every 5 minutes (12 iterations/hour)
LOOP_INTERVAL_SECONDS=300

# Run every 15 minutes (4 iterations/hour)
LOOP_INTERVAL_SECONDS=900
```

**Impact on API calls:**
| Interval | Iterations/Hour | Alpaca Calls/Hour | Gemini Calls/Hour |
|----------|----------------|-------------------|-------------------|
| 60s (default) | 60 | 240-360 | 60-120 |
| 120s (2 min) | 30 | 120-180 | 30-60 |
| 300s (5 min) | 12 | 48-72 | 12-24 |
| 900s (15 min) | 4 | 16-24 | 4-8 |

### Option 2: Run for Limited Time

**NEW FEATURE**: You can now set automatic limits in `.env`:

```env
# Stop after 100 iterations
MAX_ITERATIONS=100

# Stop after 1 hour
TIME_LIMIT_HOURS=1.0

# Stop after 30 minutes
TIME_LIMIT_HOURS=0.5

# Or use both (whichever comes first)
MAX_ITERATIONS=50
TIME_LIMIT_HOURS=2.0
```

Then run normally:
```bash
poetry run python -m app.main
# System will stop automatically when limit is reached
```

**Using `timeout` command (Alternative)**:
```bash
# Run for 1 hour
timeout 3600 poetry run python -m app.main

# Run for 30 minutes
timeout 1800 poetry run python -m app.main
```

---

## 🔧 Automatic Stop Features (NEW!)

### Limit by Iterations

Add to `.env`:
```env
MAX_ITERATIONS=50  # Stop after 50 trading cycles
```

**Example**: With 60-second intervals:
- 50 iterations = ~50 minutes of runtime
- Alpaca calls: ~200-300 total
- Gemini calls: ~50-100 total

### Limit by Time

Add to `.env`:
```env
TIME_LIMIT_HOURS=1.0  # Stop after 1 hour
```

**Example**: With 60-second intervals:
- 1 hour = ~60 iterations
- Alpaca calls: ~240-360 total
- Gemini calls: ~60-120 total

### Combine Both Limits

```env
MAX_ITERATIONS=100
TIME_LIMIT_HOURS=2.0
# Stops when EITHER limit is reached
```

### Unlimited (Default)

```env
MAX_ITERATIONS=0  # 0 = unlimited
TIME_LIMIT_HOURS=0  # 0 = unlimited
# Runs until you press Ctrl+C
```

---

## 📈 Monitoring API Usage

### View Real-Time Activity

The system logs every API call:
```
2025-11-16 10:30:00 - INFO - Fetching orderbook for BTC/USD
2025-11-16 10:30:01 - INFO - Fetching recent trades
2025-11-16 10:30:02 - INFO - Fetching klines
2025-11-16 10:30:03 - INFO - Calling Gemini for regime classification
2025-11-16 10:30:05 - INFO - Executing order: BUY 0.01 BTC/USD
```

### Check Gemini Usage

Visit: https://aistudio.google.com/app/apikey
- View your API quota
- See remaining free tier requests

### Check Alpaca Usage

Visit: https://app.alpaca.markets/paper/dashboard/overview
- All API calls are tracked in the dashboard

---

## 🎯 Recommendations

### For Testing (First Time)
```env
LOOP_INTERVAL_SECONDS=300  # Every 5 minutes
# Run for 30 minutes to 1 hour
# Total Gemini calls: ~6-12 (well within free tier)
```

### For Extended Testing (Day Trading)
```env
LOOP_INTERVAL_SECONDS=120  # Every 2 minutes
# Monitor Gemini usage to stay within free tier
# Total Gemini calls: ~360/day (within 1,500 limit)
```

### For Production (24/7 Trading)
```env
LOOP_INTERVAL_SECONDS=60  # Every minute
# Consider upgrading Gemini to paid tier
# Or use rule-based classifier more (fewer LLM calls)
```

---

## 🚨 Emergency Stop

If the system is stuck or not responding to Ctrl+C:

```bash
# Find all Python processes
ps aux | grep python

# Kill the specific process
kill -9 <PID>

# Or kill all Python processes (careful!)
pkill -9 python
```

---

## Summary

✅ **Stop the system**: Press `Ctrl + C`  
✅ **API calls per minute**: ~4-6 Alpaca + ~1-2 Gemini  
✅ **API calls per hour**: ~240-360 Alpaca + ~60-120 Gemini  
✅ **Default interval**: 60 seconds (configurable)  
✅ **Recommended for testing**: 120-300 seconds  
✅ **Free tier safe**: Up to 5-minute intervals  
✅ **NEW**: Auto-stop with `MAX_ITERATIONS` or `TIME_LIMIT_HOURS`

---

## 📋 Configuration Examples

### Example 1: Quick Test (30 minutes)
```env
LOOP_INTERVAL_SECONDS=300  # Every 5 minutes
MAX_ITERATIONS=6           # 6 × 5 min = 30 minutes
# Total: ~24-36 Alpaca calls, ~6-12 Gemini calls
```

### Example 2: Day Trading Session (6 hours)
```env
LOOP_INTERVAL_SECONDS=120  # Every 2 minutes
TIME_LIMIT_HOURS=6         # Stop after 6 hours
# Total: ~720-1080 Alpaca calls, ~180-360 Gemini calls
```

### Example 3: Conservative Testing
```env
LOOP_INTERVAL_SECONDS=600  # Every 10 minutes
MAX_ITERATIONS=12          # 2 hours total
# Total: ~48-72 Alpaca calls, ~12-24 Gemini calls
```

### Example 4: Production 24/7 (Unlimited)
```env
LOOP_INTERVAL_SECONDS=60   # Every minute
MAX_ITERATIONS=0           # Unlimited
TIME_LIMIT_HOURS=0         # Unlimited
# Runs until manually stopped with Ctrl+C
# Consider Gemini paid tier for this!
```

### Example 5: First-Time Testing (Recommended)
```env
LOOP_INTERVAL_SECONDS=180  # Every 3 minutes
MAX_ITERATIONS=10          # ~30 minutes total
# Total: ~40-60 Alpaca calls, ~10-20 Gemini calls
# Perfect for learning how the system works!
```

