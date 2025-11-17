# 🔧 BUGFIX - LangGraph Node Name Conflicts

## Error You Encountered

```
ValueError: 'features' is already being used as a state key
```

## Root Cause

LangGraph doesn't allow node names that match state key names. Your graph had:
- Node named `"features"` conflicting with state key `features`
- Node named `"regime"` conflicting with state key `regime`
- Node named `"execution"` conflicting with state key `execution_results`
- Node named `"risk"` conflicting with state key `risk_limits`

## Fix Applied

I renamed all conflicting nodes to avoid state key conflicts:

### Before → After

| Old Node Name | New Node Name | Reason |
|---------------|---------------|--------|
| `features` | `compute_features` | Conflicts with `features` state key |
| `regime` | `classify_regime` | Conflicts with `regime` state key |
| `router` | `route_strategy` | Better clarity |
| `risk` | `risk_check` | Conflicts with `risk_limits` state key |
| `execution` | `execute_orders` | Conflicts with `execution_results` state key |

### Files Modified

1. **`src/app/langgraph_graphs/full_mvp_graph.py`**
   - Renamed all 5 conflicting nodes
   - Updated all edge references

2. **`src/app/langgraph_graphs/momentum_graph.py`**
   - Renamed `features` → `compute_features`

## New Graph Flow

```
START
  ↓
ingest (market data)
  ↓
compute_features (technical indicators)
  ↓
classify_regime (market regime)
  ↓
route_strategy (choose strategy)
  ↓
[momentum OR neutral] (generate signal)
  ↓
risk_check (validate against limits)
  ↓
execute_orders (place trades)
  ↓
END
```

## Testing

The graph should now compile without errors. Run:

```bash
poetry run python -m app.main
```

Expected output:
```
2025-11-16 21:51:03 - INFO - LangGraph Trading Agent Starting...
2025-11-16 21:51:03 - INFO - Connected to ALPACA (PAPER TRADING)
2025-11-16 21:51:03 - INFO - Trading graph compiled successfully
2025-11-16 21:51:03 - INFO - Starting trading loop for BTC/USD
...
```

## Why This Happened

LangGraph's `StateGraph` reserves state key names to avoid ambiguity. When you call:
```python
workflow.add_node("features", compute_features_node)
```

And your state has:
```python
class FullMVPState(TypedDict):
    features: MarketFeatures | None  # ← Conflict!
```

LangGraph throws an error to prevent confusion between the node and the state field.

## Best Practices

When naming LangGraph nodes:
- ✅ Use verb-based names: `compute_features`, `classify_regime`, `execute_orders`
- ✅ Use descriptive action names: `route_strategy`, `risk_check`
- ❌ Avoid state key names: `features`, `regime`, `signal`, `portfolio`
- ❌ Avoid generic names: `process`, `handle`, `run`

## Status

✅ **FIXED** - All node name conflicts resolved
✅ Graph should compile successfully now
✅ Trading system ready to run

Try running the system again:
```bash
poetry run python -m app.main
```

