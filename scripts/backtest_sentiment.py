#!/usr/bin/env python3
"""
Comprehensive backtest: Momentum v3 with improved trend detection.
- Downtrend detection (proven +17.89pp alpha in bear markets)
- Uptrend detection (improved with multiple confirmations)
- Whipsaw filter (skip trades during EMA compression transitions)
- ATR trailing stops

Refactored to use Backtester class for consistent, DRY logic.
"""
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from app.utils.backtester import Backtester
from app.schemas.models import Signal

DATA_DIR = "data"
INITIAL_BALANCE = 10000.0
FEE = 0.001
POSITION_SIZE = 0.01


def compute_features(df):
    df = df.copy()
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # EMA 200 slope (percent change over last 10 periods)
    ema200_shift = df['ema_200'].shift(10)
    df['ema_200_slope_pct'] = (df['ema_200'] - ema200_shift) / ema200_shift

    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['rsi'] = 100 - (100 / (1 + gain / loss))

    df['tr'] = (df['high'] - df['low']).combine(
        abs(df['high'] - df['close'].shift(1)).combine(
            abs(df['low'] - df['close'].shift(1)), max), max)
    df['atr'] = df['tr'].rolling(14).mean()
    df['returns'] = df['close'].pct_change()
    df['realized_vol'] = df['returns'].rolling(14).std() * np.sqrt(14)

    # ADX
    df['up_move'] = df['high'] - df['high'].shift(1)
    df['down_move'] = df['low'].shift(1) - df['low']
    df['plus_dm'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0)
    df['minus_dm'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0)
    tr_smooth = df['tr'].rolling(14).sum()
    df['plus_di'] = 100 * df['plus_dm'].rolling(14).sum() / tr_smooth
    df['minus_di'] = 100 * df['minus_dm'].rolling(14).sum() / tr_smooth
    dx = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])
    df['adx'] = dx.rolling(14).mean()

    # Volume trend (for confirmation)
    df['vol_sma'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_sma']

    df.dropna(subset=['ema_50', 'ema_200', 'rsi', 'adx', 'atr', 'ema_200_slope_pct'], inplace=True)
    return df


def classify_and_signal(row, prev_position, prev_ema50_cross=None):
    """
    Improved regime + signal with:
    1. Downtrend detection (proven)
    2. Uptrend detection with recovery signal
    3. Whipsaw filter
    4. Volume confirmation
    """
    price = row['close']
    ema_9, ema_20, ema_50, ema_200 = row['ema_9'], row['ema_20'], row['ema_50'], row['ema_200']
    adx, rsi, vol = row['adx'], row['rsi'], row['realized_vol']
    plus_di, minus_di = row['plus_di'], row['minus_di']

    # ─── Whipsaw Filter ────────────────────────────────────────────────
    ema_spread = abs(ema_9 - ema_50) / ema_50
    ema_20_50_spread = abs(ema_20 - ema_50) / ema_50
    if ema_spread < 0.003 and ema_20_50_spread < 0.003:
        return "NEUTRAL"

    # ─── Volatility Filter ─────────────────────────────────────────────
    if vol > 0.035 or vol < 0.003:
        return "NEUTRAL"

    # ─── Trend Structure ───────────────────────────────────────────────
    is_strong_downtrend = price < ema_200 and ema_50 < ema_200 and ema_20 < ema_50
    is_strong_uptrend = price > ema_200 and ema_50 > ema_200 and ema_20 > ema_50
    is_mild_downtrend = price < ema_200 and ema_50 < ema_200
    is_mild_uptrend = price > ema_200 and ema_50 > ema_200
    is_above_ema50 = price > ema_50

    ema_bull_aligned = ema_9 > ema_20 > ema_50
    ema_bear_aligned = ema_9 < ema_20 < ema_50
    di_bullish = plus_di > minus_di
    di_bearish = minus_di > plus_di

    # ─── RANGING (ADX < 15) ────────────────────────────────────────────
    if adx < 15:
        if rsi < 28 and price > ema_200:
            return "LONG"
        elif rsi > 72 and price < ema_200:
            return "SHORT"
        return "NEUTRAL"

    # ─── DOWNTREND SIGNALS ─────────────────────────────────────────────
    # ONLY go SHORT when price is below EMA 200 (confirmed bear market)
    if price < ema_200:
        if is_strong_downtrend and ema_bear_aligned and di_bearish:
            if 25 < rsi < 55:
                return "SHORT"
            elif rsi > 55 and ema_9 < ema_50:
                return "SHORT"
        elif is_mild_downtrend and ema_9 < ema_50 and di_bearish:
            if 30 < rsi < 50:
                return "SHORT"
    # NEVER go SHORT above EMA 200 — that's a bull market pullback, not a downtrend

    # ─── UPTREND SIGNALS (STRONG) ──────────────────────────────────────
    if (is_strong_uptrend and ema_bull_aligned and di_bullish 
        and adx > 30 and row['ema_200_slope_pct'] > 0.0005):
        if rsi > 50:
            return "LONG"
        elif rsi < 40 and ema_9 > ema_20:
            return "LONG"

    # ─── RECOVERY SIGNAL (KEY FIX) ─────────────────────────────────────
    # When price reclaims EMA 50 after being below it, with momentum
    # This catches early uptrends before price > EMA 200
    price_reclaimed_ema50 = is_above_ema50 and prev_ema50_cross == "BELOW"
    if price_reclaimed_ema50:
        # Recovery conditions:
        # 1. Price just crossed above EMA 50
        # 2. EMA 9 > EMA 20 (short-term momentum turning up)
        # 3. RSI > 50 (momentum confirmation)
        # 4. ADX > 18 (some trend present)
        if ema_9 > ema_20 and rsi > 50 and adx > 18:
            return "LONG"
        # Stronger recovery: RSI recovering from oversold
        if ema_9 > ema_50 and rsi > 55 and adx > 15:
            return "LONG"

    # ─── MILD UPTREND (with confirmation) ──────────────────────────────
    if is_mild_uptrend and ema_9 > ema_50:
        if (adx > 30 and di_bullish and rsi > 50 
            and row['ema_200_slope_pct'] > 0.0005):
            return "LONG"

    # ─── ABOVE EMA 50 but below EMA 200 (transition zone) ──────────────
    # Stay NEUTRAL in transition zones — too risky
    # Only trade when clear trend structure is established

    return "NEUTRAL"


def run_backtest(df, atr_mult=3.0):
    """
    Run backtest using Backtester class.
    Returns dict compatible with existing analysis code.
    """
    # Initialize Backtester with equivalent cost model
    # spread+slippage = 0.001 (10 bps) per execution → round trip ~20 bps, matching custom FEE
    backtester = Backtester(
        initial_balance=INITIAL_BALANCE,
        spread_pct=0.0005,
        slippage_pct=0.0005
    )

    # State tracking (preserved from original)
    signal_counts = {"LONG": 0, "SHORT": 0, "NEUTRAL": 0}
    prev_position = "NEUTRAL"
    prev_ema50_cross = None

    # Iterate through dataframe
    for i in range(len(df)):
        row = df.iloc[i]
        price = row['close']
        high = row['high']
        low = row['low']
        atr = row['atr']
        
        # Track EMA 50 crossover state
        is_above_ema50 = price > row['ema_50']
        if prev_ema50_cross is None:
            prev_ema50_cross = "ABOVE" if is_above_ema50 else "BELOW"
        current_ema50_state = "ABOVE" if is_above_ema50 else "BELOW"

        # Generate signal direction from strategy logic
        signal_dir = classify_and_signal(row, prev_position, prev_ema50_cross)
        signal_counts[signal_dir] += 1

        # Build Signal object with trailing stop parameters
        timestamp = row.name if hasattr(row, 'name') and isinstance(row.name, datetime) else datetime.now()
        trail_dist = atr * atr_mult if atr and not np.isnan(atr) else price * 0.01
        
        stop_loss = None
        trailing_stop_distance = None
        if signal_dir in ("LONG", "SHORT"):
            # Compute initial stop loss; Backtester will trail from there
            if signal_dir == "LONG":
                stop_loss = price - trail_dist
            else:
                stop_loss = price + trail_dist
            trailing_stop_distance = trail_dist

        signal = Signal(
            timestamp=timestamp,
            symbol="BTCUSDT",
            strategy="momentum_improved",
            direction=signal_dir,  # type: ignore
            strength=1.0,
            confidence=1.0,
            entry_price=price,
            stop_loss=stop_loss,
            take_profit=None,
            trailing_stop_distance=trailing_stop_distance,
            reasoning=""
        )

        # Process signal
        backtester.process_signal(
            signal=signal,
            current_price=price,
            high=high,
            low=low,
            timestamp=timestamp
        )

        # Update prev state for next iteration
        prev_position = signal_dir if signal_dir != "NEUTRAL" else prev_position
        prev_ema50_cross = current_ema50_state

    # Get results from Backtester
    results = backtester.get_results()
    
    # Extract PnL list compatible with old format (only CLOSE trades)
    pnl_list = [t['pnl'] for t in backtester.trades if t['type'] == 'CLOSE']

    # Build return dict (compatible with existing test_period logic)
    return {
        'final_equity': results['final_equity'],
        'total_return_pct': results['total_return'],  # already percent
        'max_drawdown_pct': results['max_drawdown'],  # already percent
        'sharpe_ratio': results['sharpe_ratio'],
        'total_trades': results['total_trades'],
        'win_rate_pct': results['win_rate'],
        'signal_counts': signal_counts,
        'trades': pnl_list,
        'avg_win_loss_ratio': results.get('avg_win_loss_ratio', 0.0)
    }


def test_period(df, name, start, end):
    mask = (df['timestamp'] >= start) & (df['timestamp'] <= end)
    period = df[mask].copy()
    if len(period) < 100:
        return None
    bnh = (period['close'].iloc[-1] / period['close'].iloc[0] - 1) * 100
    r = run_backtest(period)
    r['buy_hold_pct'] = bnh
    r['name'] = name
    r['candles'] = len(period)
    return r


def run_backtest_file(data_file, label):
    print(f"\n{'═' * 60}")
    print(f"Dataset: {label}")
    print(f"{'═' * 60}")

    df = pd.read_csv(data_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp')
    df = df.resample('15min').agg({
        'symbol': 'first', 'open': 'first', 'high': 'max',
        'low': 'min', 'close': 'last', 'volume': 'sum',
    }).dropna(subset=['open']).reset_index()

    print(f"Resampled: {len(df):,} candles ({df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]})")

    # Fill missing volume with median
    df['volume'] = df['volume'].fillna(df['volume'].median())

    print("Computing features...")
    df = compute_features(df)
    print(f"After features: {len(df):,} candles")

    # Test periods
    periods = [
        ("Full Period", df['timestamp'].min().strftime('%Y-%m-%d'), df['timestamp'].max().strftime('%Y-%m-%d')),
    ]

    # Add 6-month chunks
    start = df['timestamp'].min()
    end = df['timestamp'].max()
    current = start
    while current < end:
        chunk_end = min(current + pd.Timedelta(days=180), end)
        periods.append((
            f"{current.strftime('%Y-%m')} to {chunk_end.strftime('%Y-%m')}",
            current.strftime('%Y-%m-%d'),
            chunk_end.strftime('%Y-%m-%d')
        ))
        current = chunk_end

    results = []
    for name, s, e in periods:
        r = test_period(df, name, s, e)
        if r:
            results.append(r)
            alpha = r['total_return_pct'] - r['buy_hold_pct']
            sym = "✅" if alpha > 0 else "❌"
            print(f"  {sym} {name}: Strategy {r['total_return_pct']:+.1f}% | B&H {r['buy_hold_pct']:+.1f}% | Alpha {alpha:+.1f}pp | Trades {r['total_trades']} | WR {r['win_rate_pct']:.0f}% | Signals {r['signal_counts']}")

    return results


def main():
    print("=" * 70)
    print("IMPROVED MOMENTUM V3: Uptrend + Downtrend + Whipsaw Filter")
    print("=" * 70)

    all_results = []

    # Test on existing data
    r1 = run_backtest_file(f"{DATA_DIR}/BTCUSDT_16m_1m.csv", "Current Data (Dec 2024 - Mar 2026)")
    all_results.extend(r1)

    # Test on historical data if available
    hist_file = f"{DATA_DIR}/BTCUSDT_2023_2024_1m.csv"
    if os.path.exists(hist_file):
        r2 = run_backtest_file(hist_file, "Historical Data (Jan 2023 - Dec 2024)")
        all_results.extend(r2)
    else:
        print(f"\n⏳ Historical data not ready yet ({hist_file})")

    # Summary
    if all_results:
        print(f"\n{'=' * 80}")
        print("FULL SUMMARY")
        print(f"{'=' * 80}")
        print(f"{'Period':<40} {'Strategy':>10} {'Buy&Hold':>10} {'Alpha':>10} {'Trades':>8}")
        print("-" * 80)
        for r in all_results:
            alpha = r['total_return_pct'] - r['buy_hold_pct']
            print(f"{r['name']:<40} {r['total_return_pct']:>+9.2f}% {r['buy_hold_pct']:>+9.2f}% {alpha:>+9.2f}pp {r['total_trades']:>7}")

        pd.DataFrame([{k: v for k, v in r.items() if k != 'signal_counts'} for r in all_results]
                     ).to_csv("results/improved_backtest.csv", index=False)
        print(f"\nSaved to results/improved_backtest.csv")

    print("=" * 70)


if __name__ == "__main__":
    main()
