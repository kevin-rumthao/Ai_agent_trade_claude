#!/usr/bin/env python3
"""
Backtest Runner Script.

Usage:
    python scripts/run_backtest.py --symbol BTCUSDT --days 7 --strategy momentum
"""
import asyncio
import argparse
import sys
import os
import ssl
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# Handle macOS SSL certificate issues
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# Aggressive Monkeypatch for aiohttp / python-binance
# aiohttp often creates a new context using create_default_context
original_create_default_context = ssl.create_default_context

def unverified_create_default_context(*args, **kwargs):
    context = original_create_default_context(*args, **kwargs)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context

ssl.create_default_context = unverified_create_default_context



# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.tools.binance_tool import binance_tool
from app.utils.backtester import Backtester
from app.nodes.feature_engineering import FeatureEngine, compute_features_node
from app.nodes.momentum_policy import momentum_strategy_node
from app.nodes.mean_reversion_policy import mean_reversion_strategy_node
from app.utils.statistics import forecast_volatility
from app.schemas.events import KlineEvent
from app.schemas.models import MarketFeatures, Signal
import random
import math

def generate_synthetic_data(symbol: str, days: int) -> list[KlineEvent]:
    """Generate synthetic trending/ranging data."""
    klines = []
    base_price = 50000.0
    now = datetime.now()
    
    # Generate 1440 mins per day
    total_minutes = days * 1440
    
    price = base_price
    for i in range(total_minutes):
        timestamp = now - timedelta(minutes=total_minutes - i)
        
        # Random walk with drift (sine wave for range/trend mix)
        trend = math.sin(i / 1000) * 0.0005
        noise = random.normalvariate(0, 0.001)
        change = trend + noise
        
        price = price * (1 + change)
        
        # OHLVC
        open_p = price
        close_p = price * (1 + random.normalvariate(0, 0.0005))
        high_p = max(open_p, close_p) * (1 + abs(random.normalvariate(0, 0.0002)))
        low_p = min(open_p, close_p) * (1 - abs(random.normalvariate(0, 0.0002)))
        
        kline = KlineEvent(
            timestamp=timestamp,
            symbol=symbol,
            open=open_p,
            high=high_p,
            low=low_p,
            close=close_p,
            volume=random.uniform(10, 100),
            interval="1m"
        )
        klines.append(kline)
        
    print(f"Generated {len(klines)} synthetic candles.")
    return klines

async def fetch_data(symbol: str, days: int, provider: str, start_time: datetime = None, end_time: datetime = None, data_file: str = None):
    """Fetch historical klines."""
    if data_file:
         print(f"Loading data from local file: {data_file}...")
         if not os.path.exists(data_file):
             print(f"Error: File {data_file} not found.")
             return []
             
         try:
             df = pd.read_csv(data_file)
             df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
             df = df.sort_values('timestamp')
             
             # Filter by symbol if present
             if 'symbol' in df.columns:
                 df = df[df['symbol'] == symbol]
                 
             # Filter by time range if provided
             if start_time:
                 df = df[df['timestamp'] >= start_time]
             if end_time:
                 df = df[df['timestamp'] <= end_time]
                 
             klines = []
             for _, row in df.iterrows():
                 # Handle different formats
                 # 1. Standard OHLCV
                 if all(c in row for c in ['open', 'high', 'low', 'close']):
                     open_p = float(row['open'])
                     high_p = float(row['high'])
                     low_p = float(row['low'])
                     close_p = float(row['close'])
                 # 2. "Price" only (fetch_data.py format)
                 elif 'price' in row:
                     p = float(row['price'])
                     open_p = high_p = low_p = close_p = p
                 else:
                     continue
                     
                 vol = float(row['volume']) if 'volume' in row else 0.0
                 
                 klines.append(KlineEvent(
                     timestamp=row['timestamp'],
                     symbol=symbol,
                     open=open_p,
                     high=high_p,
                     low=low_p,
                     close=close_p,
                     volume=vol,
                     interval="1m" # Assumption
                 ))
                 
             print(f"Loaded {len(klines)} candles from file.")
             return klines
             
         except Exception as e:
             print(f"Error reading data file: {e}")
             return []

    print(f"Fetching {days} days of data for {symbol} from {provider}...")
    
    limit = days * 24 * 60  # Minutes
    # Note: Providers might have limits on how many klines per request.
    # For simplicity, we'll fetch a smaller batch or loop.
    # Binance limit is 1000. Alpaca is similar.
    limit = days * 24 * 60  # Minutes
    if start_time and end_time:
         # Limit is handled by range usually, but API takes limit per request.
         # For simplicity in this demo, we'll ask for a large limit or rely on provider default.
         # Binance API limit is 1000. 
         # To get full range we need pagination, or just ask for 1000 from start.
         # Let's try to ask for 1000 from start_time.
         # Ideally we should loop.
         limit = 1000 
    # To get days, we'd need pagination.
    
    if days > 1:
        print("Warning: Simple fetcher only retrieves last 1000 candles (approx 16 hours).")
    
    if provider == "binance":
        # Force Mainnet for historical data
        original_testnet = settings.testnet
        settings.testnet = False
        
        try:
            await binance_tool.initialize()
            
            all_klines = []
            current_start = start_time
            
            # Determine total duration if start/end provided (to show progress)
            if start_time and end_time:
                total_duration = (end_time - start_time).total_seconds()
            
            while True:
                # If no range provided (default simple mode), use simple fetch
                if not start_time or not end_time:
                    klines = await binance_tool.get_klines(symbol, interval="1m", limit=limit)
                    all_klines.extend(klines)
                    break
                    
                # Range mode: Fetch chunk
                print(f"Fetching chunk from {current_start}...")
                klines = await binance_tool.get_klines(
                    symbol, 
                    interval="1m", 
                    limit=1000, 
                    start_time=current_start,
                    end_time=end_time 
                )
                
                if not klines:
                    break
                    
                all_klines.extend(klines)
                last_kline_time = klines[-1].timestamp
                
                # Progress update
                if total_duration > 0:
                     progress = (last_kline_time - start_time).total_seconds() / total_duration * 100
                     print(f"Progress: {progress:.1f}% ({len(all_klines)} candles)")
                
                # Break if we reached end_time or got fewer candles than limit
                if last_kline_time >= end_time or len(klines) < 1000:
                    break

                current_start = last_kline_time + timedelta(minutes=1)
                
                # Safety break
                if len(all_klines) > 50000: 
                     print("Hit safety limit (50k candles). Stopping.")
                     break
        finally:
             await binance_tool.close()
             settings.testnet = original_testnet # Restore
             
        klines = all_klines # Assign back variable
        
    elif provider == "mock":
        return generate_synthetic_data(symbol, days)
    else:
        await alpaca_tool.initialize()
        klines = await alpaca_tool.get_klines(symbol, interval="1m", limit=1000)
        await alpaca_tool.close()
        
    print(f"Fetched {len(klines)} candles.")
    return klines

async def run_backtest(symbol: str, days: int, strategy_name: str, provider: str, spread: float, slippage: float, features_file: str = None, data_file: str = None):
    # 1. Determine Range from Features (if any)
    start_time = None
    end_time = None
    
    # 1.5 Load Features File
    feature_map = {}
    if features_file:
        print(f"Loading features from {features_file}...")
        try:
            df_feat = pd.read_csv(features_file)
            # Ensure timestamp parse
            df_feat['timestamp'] = pd.to_datetime(df_feat['timestamp'], utc=True)
            
            # Create dict for fast lookup: timestamp -> dict
            # We assume features are 1m aligned.
            feature_map = {row['timestamp']: row for row in df_feat.to_dict('records')}
            print(f"Loaded {len(feature_map)} external feature rows.")
            
            # Determine Time Range
            if not df_feat.empty:
                start_time = df_feat['timestamp'].min()
                end_time = df_feat['timestamp'].max()
                print(f"Aligning backtest to feature range: {start_time} -> {end_time}")
                
        except Exception as e:
            print(f"Error loading features file: {e}")
            return

    # 1. Fetch Data
    klines = await fetch_data(symbol, days, provider, start_time, end_time, data_file)
    
    if not klines:
        print("No data fetched. Exiting.")
        return
    # Features already loaded above.

    # 2. Initialize Backtester
    backtester = Backtester(initial_balance=10000.0, spread_pct=spread, slippage_pct=slippage)
    
    # 3. Run Loop
    print(f"Running backtest with strategy: {strategy_name}...")
    
    # We need to simulate the state
    # Feature engine is stateful (buffers). We need to feed it one by one.
    
    # Reset feature engine buffers if possible, or just create a new one?
    # The global `feature_engine` is used by nodes.
    # We should probably clear it.
    # Instantiate LOCAL feature engine to ensure clean state
    feature_engine = FeatureEngine()
    
    # processed_klines = [] # We will now loop over M15 klines
    plot_times = []
    plot_prices = []
    plot_equity = []
    
    # 2.5 Resample Logic (The "Quant Pivot")
    # Convert list of KlineEvent to DataFrame for easy resampling
    print("Resampling data to 15-Minute Candles (Trend Following Mode)...")
    
    df_m1 = pd.DataFrame([k.dict() for k in klines])
    df_m1['timestamp'] = pd.to_datetime(df_m1['timestamp'])
    df_m1.set_index('timestamp', inplace=True)
    
    # Resample OHLCV
    ohlc_dict = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }
    df_m15 = df_m1.resample('15min').agg(ohlc_dict).dropna()
    print(f"Resampled {len(df_m1)} M1 candles -> {len(df_m15)} M15 candles.")
    
    # Resample External Features (OFI)
    # We need to Aggregate OFI for the 15 minutes. Sum? Mean?
    # OFI is flow, so Sum makes sense (Total Flow over 15m).
    # But our threshold (12.0) was calibrated for 1m.
    # If we sum, the values will be ~15x larger.
    # Let's use MEAN to keep the scale similar to our existing threshold logic.
    input_ofi_resampled = {}
    if feature_map:
        # Create DataFrame from feature_map values
        df_feat = pd.DataFrame(list(feature_map.values()))
        df_feat['timestamp'] = pd.to_datetime(df_feat['timestamp'])
        df_feat.set_index('timestamp', inplace=True)
        
        # Resample features (Mean)
        df_feat_m15 = df_feat.resample('15min').mean().dropna()
        
        # Re-map
        # We need to map M15 timestamp -> OFI Row
        input_ofi_resampled = {ts: row for ts, row in df_feat_m15.iterrows()}
        print(f"Resampled {len(df_feat)} Feature rows -> {len(df_feat_m15)} M15 rows.")

    # Convert back to KlineEvents
    klines_m15 = []
    for ts, row in df_m15.iterrows():
         klines_m15.append(KlineEvent(
             timestamp=ts,
             symbol=symbol,
             interval="15m",
             open=row['open'],
             high=row['high'],
             low=row['low'],
             close=row['close'],
             volume=row['volume']
         ))
         
    # Use M15 for the loop
    for kline in klines_m15:
        # processed_klines.append(kline) # We need to append to history for strategy to see
        # Strategy expects list of dictionaries or objects? 
        # Strategy compares klines[-2] etc.
        # We need to pass the history of M15 candles.
        pass # handled in loop logic below
        
    processed_klines = []
    
    for kline in klines_m15:
        processed_klines.append(kline)
        
        # Track data for visualization
        plot_times.append(kline.timestamp)
        plot_prices.append(kline.close)
        # Calculate current equity (balance + unrealized PnL)
        current_equity = backtester._calculate_equity(kline.close)
        plot_equity.append(current_equity)

        # 3.1 Compute Features
        
        # 3.0 Load External Features (if provided)
        input_ofi = None
        if input_ofi_resampled:
             # Look for timestamp in resampled map
             # M15 timestamp should match kline.timestamp
             if kline.timestamp in input_ofi_resampled:
                 input_ofi = float(input_ofi_resampled[kline.timestamp].get('ofi', 0.0))
        
        # ... Rest of loop is same, but running on M15 data ...
        
        # 3.1 Compute Features
        # We can reuse compute_features_node logic, or call feature_engine directly.
        # Calling feature_engine directly is easier for simulation loop.
        
        # Update buffers
        feature_engine.high_buffer.append(kline.high)
        feature_engine.low_buffer.append(kline.low)
        feature_engine.close_buffer.append(kline.close)
        feature_engine.price_buffer.append(kline.close)
        feature_engine.update_ema(kline.close)
        
        # Phase 6: Update OFI Smoothing
        feature_engine.update_ofi(input_ofi)
        
        # Compute indicators
        atr = feature_engine.compute_atr()
        realized_vol = feature_engine.compute_realized_volatility()
        rsi = feature_engine.compute_rsi(list(feature_engine.close_buffer), settings.rsi_period)
        adx = feature_engine.compute_adx(period=14)
        
        # --- GARCH DYNAMIC BANDS LOGIC ---
        std_dev_mult = settings.bollinger_std_dev
        closes_list = list(feature_engine.close_buffer)
        
        if len(closes_list) > 30:
            returns = [(closes_list[i] - closes_list[i-1])/closes_list[i-1] for i in range(1, len(closes_list))]
            try:
                vol_forecast = forecast_volatility(returns, method='GARCH')
            except:
                vol_forecast = None
            
            # Dynamic Logic
            if vol_forecast is not None:
                # Calculate recent realized sigma (1-period)
                if len(closes_list) > 1:
                    r_slice = returns
                    if r_slice:
                        recent_sigma = float(np.std(r_slice))
                        
                        if recent_sigma > 0:
                            ratio = vol_forecast / recent_sigma
                            if ratio > 1.05: # Threshold
                                ratio = min(ratio, 2.0)
                                std_dev_mult = settings.bollinger_std_dev * ratio

        bb_res = feature_engine.compute_bollinger_bands(
            list(feature_engine.price_buffer),
            settings.bollinger_period,
            std_dev_mult # Dynamic
        )
        bb_upper, bb_mid, bb_lower = bb_res if bb_res else (None, None, None)
        
        features = MarketFeatures(
            timestamp=kline.timestamp,
            symbol=symbol,
            price=kline.close,
            ema_9=feature_engine.ema_9,
            ema_50=feature_engine.ema_50,
            atr=atr,
            realized_volatility=realized_vol,
            adx=adx,
            orderbook_imbalance=input_ofi if input_ofi is not None else None, # Inject OFI
            spread=None,
            vwap=None,
            rsi=rsi,
            bollinger_upper=bb_upper,
            bollinger_mid=bb_mid,
            bollinger_lower=bb_lower,
            ofi=input_ofi if input_ofi is not None else None,
            ofi_sma=feature_engine.ofi_sma # Injected Smoothed OFI
        )
        
        # 3.2 Run Strategy
        state = {
            "features": features,
            "klines": processed_klines, # Strategy needs history for confirmation
            "symbol": symbol,
            "timestamp": kline.timestamp,
            "signals": []
        }
        
        if strategy_name == "momentum":
            result = await momentum_strategy_node(state) # type: ignore
        elif strategy_name == "mean_reversion":
            result = await mean_reversion_strategy_node(state) # type: ignore
        else:
            print(f"Unknown strategy: {strategy_name}")
            return
            
        signals = result.get("signals", [])
        
        # 3.3 Process Signals
        for signal in signals:
            if signal.direction != "NEUTRAL":
                backtester.process_signal(signal, kline.close, kline.high, kline.low, kline.timestamp)
                
    # 4. Results
    results = backtester.get_results()
    
    print("\n=== Backtest Results ===")
    print(f"Total Return: {results['total_return']:.2f}%")
    print(f"Final Equity: ${results['final_equity']:.2f}")
    print(f"Total Trades: {results['total_trades']}")
    print(f"Win Rate:     {results['win_rate']:.2f}%")
    print(f"Max Drawdown: {results['max_drawdown']:.2f}%")
    print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
    print("========================")

    if args.visual:
        print("Generating visualization...")
        
        # Use tracked data
        times = plot_times
        equity = plot_equity
        prices = plot_prices
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
        
        # Plot Price and Trades
        ax1.plot(times, prices, label='Price', color='gray', alpha=0.5)
        
        for trade in backtester.trades:
            timestamp = trade['timestamp']
            price = trade['price']
            side = trade['side'] # LONG or SHORT
            
            if trade['type'] == 'OPEN':
                # Mark Entry
                color = 'g' if side == 'LONG' else 'r'
                marker = '^' if side == 'LONG' else 'v'
                # Only label once
                label = 'Entry' if 'Entry' not in ax1.get_legend_handles_labels()[1] else ""
                ax1.scatter(timestamp, price, c=color, marker=marker, s=100, label=label, zorder=5)
            
            elif trade['type'] == 'CLOSE':
                 # Mark Exit
                 # Only label once
                 label = 'Exit' if 'Exit' not in ax1.get_legend_handles_labels()[1] else ""
                 ax1.scatter(timestamp, price, c='black', marker='x', s=100, label=label, zorder=5)
                
        ax1.set_title(f'Backtest: {symbol} - {strategy_name}')
        ax1.set_ylabel('Price')
        ax1.legend()
        
        # Plot Equity Curve
        ax2.plot(times, equity, label='Equity', color='blue')
        ax2.set_ylabel('Portfolio Value ($)')
        ax2.set_xlabel('Time')
        ax2.legend()
        
        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Backtest")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Trading symbol")
    parser.add_argument("--days", type=int, default=1, help="Days of data to fetch")
    parser.add_argument("--strategy", type=str, default="momentum", choices=["momentum", "mean_reversion"], help="Strategy to test")
    parser.add_argument("--provider", type=str, default="binance", choices=["binance", "alpaca", "mock"], help="Data provider")
    parser.add_argument("--spread", type=float, default=0.0005, help="Spread percentage (0.0005 = 0.05%)")
    parser.add_argument("--slippage", type=float, default=0.0005, help="Slippage percentage (0.0005 = 0.05%)")
    parser.add_argument("--visual", action="store_true", help="Show visualization plot")
    parser.add_argument("--features_file", type=str, default=None, help="Path to external CSV with pre-calculated features (OFI)")
    parser.add_argument("--data_file", type=str, default=None, help="Path to local CSV data file (e.g., data/backtest_data.csv)")
    
    args = parser.parse_args()
    
    asyncio.run(run_backtest(args.symbol, args.days, args.strategy, args.provider, args.spread, args.slippage, args.features_file, args.data_file))
