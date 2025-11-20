"""
Script to run backtest using local CSV data.
"""
import asyncio
import csv
from datetime import datetime
from pathlib import Path

from app.utils.backtester import Backtester
from app.nodes.feature_engineering import compute_features_node, FeatureState, feature_engine
from app.nodes.regime_classifier import classify_regime_node, RegimeState
from app.nodes.strategy_router import route_strategy_node, RouterState
from app.nodes.momentum_policy import momentum_strategy_node, MomentumState
from app.nodes.mean_reversion_policy import mean_reversion_strategy_node, MeanReversionState
from app.schemas.events import TradeEvent, OrderbookUpdate, KlineEvent
from app.schemas.models import MarketFeatures, MarketRegime, Signal
from app.config import settings
from app.tools.llm_tool import llm_tool

# Mock LLM for backtesting speed
async def mock_classify_regime(features: MarketFeatures, ambiguity: float) -> MarketRegime:
    # Simple logic for backtest:
    # If ADX/Trend strength is high -> TRENDING
    # Else -> RANGING
    
    # Use EMA separation as proxy for trend strength
    if features.ema_9 and features.ema_50:
        diff = abs(features.ema_9 - features.ema_50) / features.ema_50 if features.ema_50 else 0
        if diff > 0.01:
            return MarketRegime(regime="TRENDING", confidence=0.9, timestamp=features.timestamp, reasoning="Mock LLM: Strong trend")
            
    return MarketRegime(regime="RANGING", confidence=0.8, timestamp=features.timestamp, reasoning="Mock LLM: Ranging")

# Monkeypatch
llm_tool.classify_regime_with_llm = mock_classify_regime

# Configuration
DATA_FILE = "data/backtest_data.csv"
INITIAL_BALANCE = 10000.0

async def run_backtest():
    print(f"Starting backtest using {DATA_FILE}...")
    
    # Initialize backtester
    backtester = Backtester(initial_balance=INITIAL_BALANCE)
    
    # Load data
    rows = []
    with open(DATA_FILE, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
    print(f"Loaded {len(rows)} data points.")
    
    # State containers
    klines_buffer: list[KlineEvent] = []
    trades_buffer: list[TradeEvent] = []
    
    # Iterate through data
    for i, row in enumerate(rows):
        timestamp = datetime.fromisoformat(row['timestamp'])
        price = float(row['price'])
        symbol = row['symbol']
        
        # Create events
        trade = TradeEvent(
            timestamp=timestamp,
            symbol=symbol,
            price=price,
            quantity=float(row['volume']),
            side="BUY",
            trade_id=str(i)
        )
        trades_buffer.append(trade)
        if len(trades_buffer) > 100:
            trades_buffer.pop(0)
            
        # Create kline (simplified, using price as close)
        kline = KlineEvent(
            timestamp=timestamp,
            symbol=symbol,
            interval="1h",
            open=price, high=price, low=price, close=price,
            volume=float(row['volume']),
            num_trades=1
        )
        klines_buffer.append(kline)
        # Keep enough klines for indicators (50 for EMA + buffer)
        if len(klines_buffer) > 100:
            klines_buffer.pop(0)
            
        # Create orderbook
        orderbook = OrderbookUpdate(
            timestamp=timestamp,
            symbol=symbol,
            bids=[(float(row['bid']), 1.0)],
            asks=[(float(row['ask']), 1.0)]
        )
        
        # 1. Feature Engineering
        feature_state: FeatureState = {
            "trades": trades_buffer,
            "orderbook": orderbook,
            "klines": klines_buffer,
            "features": None,
            "symbol": symbol,
            "timestamp": timestamp
        }
        
        # Reset feature engine buffers if first iteration (optional, but good for clean state)
        if i == 0:
            feature_engine.ema_9_buffer.clear()
            feature_engine.ema_50_buffer.clear()
            feature_engine.price_buffer.clear()
        
        feature_result = await compute_features_node(feature_state)
        features = feature_result.get("features")
        
        if not features:
            continue
            
        # 2. Regime Classification
        regime_state: RegimeState = {
            "features": features,
            "regime": None,
            "symbol": symbol,
            "timestamp": timestamp
        }
        regime_result = await classify_regime_node(regime_state)
        regime = regime_result.get("regime")
        
        # 3. Strategy Routing
        router_state: RouterState = {
            "regime": regime,
            "selected_strategy": None,
            "timestamp": timestamp
        }
        router_result = await route_strategy_node(router_state)
        strategy_name = router_result.get("selected_strategy")
        
        # 4. Strategy Execution
        signal = None
        
        if strategy_name == "momentum":
            mom_state: MomentumState = {
                "features": features,
                "signal": None,
                "symbol": symbol,
                "timestamp": timestamp
            }
            mom_result = await momentum_strategy_node(mom_state)
            signal = mom_result.get("signal")
            
        elif strategy_name == "mean_reversion":
            mr_state: MeanReversionState = {
                "features": features,
                "signal": None,
                "symbol": symbol,
                "timestamp": timestamp
            }
            mr_result = await mean_reversion_strategy_node(mr_state)
            signal = mr_result.get("signal")
            
        # 5. Backtest Execution
        if signal:
            backtester.process_signal(signal, price, timestamp)
            
        # Progress log
        if i % 100 == 0:
            print(f"Processed {i}/{len(rows)} | Equity: {backtester.balance:.2f}")

    # Final Report
    results = backtester.get_results()
    print("\n" + "="*50)
    print("BACKTEST RESULTS")
    print("="*50)
    print(f"Initial Balance: ${INITIAL_BALANCE:,.2f}")
    print(f"Final Equity:    ${results['final_equity']:,.2f}")
    print(f"Total Return:    {results['total_return']:.2f}%")
    print(f"Total Trades:    {results['total_trades']}")
    print(f"Win Rate:        {results['win_rate']:.2f}%")
    print(f"Max Drawdown:    {results['max_drawdown']:.2f}%")
    print(f"Sharpe Ratio:    {results['sharpe_ratio']:.2f}")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(run_backtest())
