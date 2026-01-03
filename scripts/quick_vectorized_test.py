import pandas as pd
import numpy as np

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def compute_adx(high, low, close, period=14):
    # Simplified ADX
    plus_dm = high.diff()
    minus_dm = low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    
    tr1 = pd.DataFrame(high - low)
    tr2 = pd.DataFrame(abs(high - close.shift(1)))
    tr3 = pd.DataFrame(abs(low - close.shift(1)))
    frames = [tr1, tr2, tr3]
    tr = pd.concat(frames, axis=1, join='inner').max(axis=1)
    
    atr = tr.rolling(period).mean()
    
    plus_di = 100 * (plus_dm.ewm(alpha=1/period).mean() / atr)
    minus_di = 100 * (abs(minus_dm).ewm(alpha=1/period).mean() / atr)
    
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.rolling(period).mean()
    return adx

def run_vectorized_backtest():
    print("Loading data...")
    df = pd.read_csv('data/BTCUSDT_5Y_MASTER.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    
    # Resample to 15m
    print("Resampling to 15m...")
    ohlc = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }
    df_15m = df.resample('15min').agg(ohlc).dropna()
    
    print(f"Candles: {len(df_15m)}")
    
    # Indicators
    close = df_15m['close']
    ema9 = close.ewm(span=9, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()
    rsi = compute_rsi(close)
    adx = compute_adx(df_15m['high'], df_15m['low'], close)
    
    # Logic
    # Long: EMA9 > EMA50 & Price > EMA9 & Price > EMA200 & RSI(50-70) & ADX > 25
    # Short: EMA9 < EMA50 & Price < EMA9 & Price < EMA200 & RSI(30-50) & ADX > 25
    
    long_condition = (ema9 > ema50) & (close > ema9) & (close > ema200) & (rsi > 50) & (rsi < 70) & (adx > 25)
    short_condition = (ema9 < ema50) & (close < ema9) & (close < ema200) & (rsi > 30) & (rsi < 50) & (adx > 25)
    
    # Positions (1 = Long, -1 = Short, 0 = Neutral)
    # This is a simplification. The event-driven has state (holds until exit).
    # Vectorized usually assumes "always in market" or "flip".
    # We will simulate "Entry" logic and hold until "Exit" logic? 
    # That's hard in pure vector.
    # Let's do simple: If signal, hold for 1 candle? No.
    # Let's do: Signal = 1/0/-1. Fill forward until exit signal?
    # Strategy exit: "Let winners run" until signal flip or SL/TP.
    # Real test: simple signal following. 
    # If Long Cond -> 1. If Short Cond -> -1. Else -> NaN (Hold).
    
    # Simplest: If EMA9 > EMA50 -> Bull Regime. If EMA9 < EMA50 -> Bear Regime.
    # Filtered by EMA200.
    
    signals = pd.Series(0, index=df_15m.index)
    signals[long_condition] = 1
    signals[short_condition] = -1
    
    # Shift signals by 1 to avoid lookahead (Trade on Next Open)
    # Actually backtester uses Same Bar Close execution.
    # Let's match backtester: Signal at Close -> Trade at Close.
    # So returns = Signal * PctChange? 
    # But backtester holds position.
    
    # Let's iterate simply (faster than event driven)
    position = 0
    balance = 10000.0
    initial_balance = 10000.0
    equity = []
    
    # Position Params
    position_size_btc = 0.1 # 10x the original 0.01
    
    # Simple Loop
    print("Running Loop...")
    closes = df_15m['close'].values
    highs = df_15m['high'].values
    lows = df_15m['low'].values
    
    # Convert series to numpy for speed
    s_long = long_condition.values
    s_short = short_condition.values
    
    # ATR for SL
    tr = abs(df_15m['high'] - df_15m['low']) # approx
    atr = tr.rolling(14).mean().values
    
    entry_price = 0.0
    stop_loss = 0.0
    
    for i in range(len(closes)):
        price = closes[i]
        
        # Check Exits first
        if position != 0:
            # Trailing SL (Simplified: 3*ATR)
            # Logic: Update SL if price moves favorable
            curr_atr = atr[i] if not np.isnan(atr[i]) else price*0.01
            dist = 3.0 * curr_atr
            
            pnl = 0
            closed = False
            
            if position == 1: # Long
                new_sl = price - dist # This is "Tighten on Close" - strategy does "High - dist"
                # Strategy: if high - dist > sl: sl = high - dist
                # We use simple close-based check for speed
                
                # Check SL Hit (Simulated on Low)
                if lows[i] < stop_loss:
                    exit_p = stop_loss
                    pnl = (exit_p - entry_price) * position_size_btc
                    balance += pnl
                    position = 0
                    closed = True
                else:
                    # Trailing update (on Close)
                    if (price - dist) > stop_loss:
                        stop_loss = price - dist
                        
            elif position == -1: # Short
                # Check SL Hit (Simulated on High)
                if highs[i] > stop_loss:
                    exit_p = stop_loss
                    pnl = (entry_price - exit_p) * position_size_btc
                    balance += pnl
                    position = 0
                    closed = True
                else:
                    # Trailing update
                    if (price + dist) < stop_loss:
                        stop_loss = price + dist
            
            # Check Signal Flip (only if not closed by SL)
            if not closed:
                if position == 1 and s_short[i]:
                    # Flip Short
                    pnl = (price - entry_price) * position_size_btc
                    balance += pnl
                    position = -1
                    entry_price = price
                    stop_loss = price + (3.0 * curr_atr)
                elif position == -1 and s_long[i]:
                    # Flip Long
                    pnl = (entry_price - price) * position_size_btc
                    balance += pnl
                    position = 1
                    entry_price = price
                    stop_loss = price - (3.0 * curr_atr)
                    
        else:
            # No position, check entry
            curr_atr = atr[i] if not np.isnan(atr[i]) else price*0.01
            if s_long[i]:
                position = 1
                entry_price = price
                stop_loss = price - (3.0 * curr_atr)
            elif s_short[i]:
                position = -1
                entry_price = price
                stop_loss = price + (3.0 * curr_atr)
                
        # Calculate Equity
        unrealized = 0
        if position == 1:
            unrealized = (price - entry_price) * position_size_btc
        elif position == -1:
            unrealized = (entry_price - price) * position_size_btc
            
        current_equity = balance + unrealized
        equity.append(current_equity)

    final_equity = equity[-1]
    total_ret = (final_equity - initial_balance) / initial_balance * 100
    
    # Max Drawdown
    eq_series = pd.Series(equity)
    cummax = eq_series.cummax()
    dd = (cummax - eq_series) / cummax * 100
    max_dd = dd.max()
    
    print("\n=== Quick Backtest Results (0.1 BTC Position) ===")
    print(f"Final Equity: ${final_equity:,.2f}")
    print(f"Total Return: {total_ret:.2f}%")
    print(f"Max Drawdown: {max_dd:.2f}%")
    print(f"Candles Processed: {len(equity)}")

run_vectorized_backtest()
