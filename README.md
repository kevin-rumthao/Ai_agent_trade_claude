# LangGraph Trading Agent

This project implements a **modular, event‑driven trading agent** built on **LangGraph**. It runs a full pipeline:

> Market Ingest → Feature Engineering → Regime Classification → Strategy Router → Momentum Strategy → Risk Manager → Execution Agent

The system supports **multiple trading backends**:
- **Binance** (testnet/mainnet for crypto)
- **Alpaca** (paper trading for stocks and crypto)

It's designed to support **backtesting** and **simulation** via a LOB simulator and metrics utilities.

---

## 1. Key Features

✅ **Multi-Provider Support**: Switch between Binance and Alpaca with a single config change  
✅ **Paper Trading**: Test strategies risk-free using Alpaca's paper trading  
✅ **LLM-Powered**: Uses Google Gemini for intelligent regime classification  
✅ **Health Checks**: Validates all API connections before trading starts  
✅ **Modular Architecture**: Easy to extend with new strategies or providers  
✅ **Comprehensive Testing**: Unit tests for all major components  

---

## 2. Project Layout

- `src/app/config.py` – application settings (env‑driven via `pydantic-settings`).
- `src/app/main.py` – main entrypoint, runs the full LangGraph trading loop.
- `src/app/langgraph_graphs/`
  - `ingest_graph.py` – market data ingestion subgraph.
  - `momentum_graph.py` – feature + momentum strategy subgraph.
  - `full_mvp_graph.py` – full end‑to‑end trading graph.
- `src/app/nodes/` – pipeline nodes:
  - `market_ingest.py` – load market data (Binance or CSV stub).
  - `feature_engineering.py` – compute EMA(9/50), ATR, realized volatility, OB imbalance, VWAP.
  - `regime_classifier.py` – rule‑based regime classifier with LLM fallback.
  - `strategy_router.py` – route to momentum / neutral strategy.
  - `momentum_policy.py` – EMA‑crossover momentum strategy.
  - `risk_manager.py` – risk checks + position sizing.
  - `execution_agent.py` – place orders via Binance tool.
- `src/app/schemas/` – Pydantic models for events (`TradeEvent`, `OrderbookUpdate`, `KlineEvent`) and domain models (`MarketFeatures`, `Signal`, `Order`, `PortfolioState`, etc.).
- `src/app/tools/`
  - `binance_tool.py` – async Binance client wrapper.
  - `llm_tool.py` – Anthropic LLM wrapper for regime classification / advice.
- `src/app/utils/`
  - `backtester.py` – simple backtesting engine driven by strategy signals.
  - `lob_simulator.py` – limit order book simulator.
  - `metrics.py` – Sharpe / max drawdown / win‑rate and other metrics.
- `src/tests/` – minimal tests for ingest, features, momentum policy, and execution agent.

- `src/app/tools/`
  - `binance_tool.py` – async Binance client wrapper.
  - `alpaca_tool.py` – Alpaca paper trading client wrapper.
  - `trading_provider.py` – abstraction layer for switching between providers.
  - `llm_tool.py` – Google Gemini LLM wrapper for regime classification / advice.
- `src/app/utils/`
  - `backtester.py` – simple backtesting engine driven by strategy signals.
  - `lob_simulator.py` – limit order book simulator.
  - `metrics.py` – Sharpe / max drawdown / win‑rate and other metrics.
- `src/tests/` – minimal tests for ingest, features, momentum policy, and execution agent.

---

## 3. Requirements

- Python **3.11+**
- Recommended: **Poetry** for dependency management

Python dependencies are defined in `pyproject.toml` including:
- LangGraph, LangChain
- Pydantic v2
- `python-binance` (for Binance support)
- `alpaca-py` (for Alpaca paper trading)
- `langchain-google-genai` (for Gemini LLM)
- `pytest` and development tools

---

## 4. Quick Setup (Easiest)

For first-time setup, use our interactive configuration script:

```bash
cd /Users/kevin/Desktop/Ai_agent_trade_claude
poetry install
poetry run python scripts/quickstart.py
```

This will guide you through:
- Choosing a trading provider (Alpaca or Binance)
- Entering API credentials
- Setting risk parameters
- Creating your `.env` file

Then jump to **Section 5** to start trading!

---

## 4. Manual Setup (Alternative)

### 4.1 Install Dependencies

Using Poetry (recommended):

```bash
cd /Users/kevin/Desktop/Ai_agent_trade_claude
poetry install
```

Or using pip directly:

```bash
python -m venv .venv
source .venv/bin/activate  # macOS / Linux
pip install -e .
```

### 4.2 Get API Credentials

#### For Alpaca Paper Trading (Recommended for Testing):
1. Go to https://alpaca.markets/
2. Sign up for a free account
3. Navigate to Paper Trading dashboard
4. Copy your API Key and Secret Key

#### For Binance (Crypto Trading):
1. Go to https://testnet.binance.vision/ (testnet) or binance.com (mainnet)
2. Create API keys
3. Enable spot trading permissions

#### For Gemini LLM:
1. Go to https://ai.google.dev/
2. Get your Gemini API key

### 4.3 Environment Variables

Create a `.env` file in the project root:

```env
# Trading Provider Selection
# Options: "binance" or "alpaca"
TRADING_PROVIDER="alpaca"

# Binance API Keys (for testnet or mainnet)
BINANCE_API_KEY="your-binance-testnet-key"
BINANCE_API_SECRET="your-binance-testnet-secret"

# Alpaca API Keys (always uses paper trading)
ALPACA_API_KEY="your-alpaca-paper-key"
ALPACA_API_SECRET="your-alpaca-paper-secret"

# Gemini LLM API Key
GEMINI_API_KEY="your-gemini-key"

# Trading Configuration
SYMBOL="BTCUSD"  # Use BTCUSD for crypto on Alpaca, AAPL for stocks, or BTCUSDT for Binance
TESTNET=true  # Only applies to Binance

# Logging
LOG_LEVEL="INFO"
```

**Important Notes:**
- **Alpaca** always uses paper trading (safe for testing)
- **Binance** can use testnet (safe) or mainnet (real money) - set `TESTNET=true` for safety
- Symbol formats differ: 
  - Alpaca: `BTCUSD` (crypto), `AAPL` (stocks)
  - Binance: `BTCUSDT` (crypto)

All settings are defined in `src/app/config.py` and loaded via `Settings`.

### 4.4 Run Health Checks

Before running the trading system, validate that all APIs are working:

```bash
poetry run python -m app.healthcheck
```

This will verify:
- ✅ Trading provider connectivity (Binance or Alpaca)
- ✅ Market data access
- ✅ Portfolio state retrieval
- ✅ Gemini LLM connectivity

Expected output:
```
Running external health checks (ALPACA, Gemini)...
✅ All health checks passed
{'trading_provider': {'provider': 'alpaca', 'symbol': 'BTCUSD', 'ok': True, ...}, 'llm': {'model': 'gemini-1.5-pro', 'ok': True, ...}}
```

---

## 5. Running the Trading System

### 5.1 Start Trading Loop

After health checks pass, start the main trading loop:

```bash
poetry run python -m app.main
```

The system will:
1. Run health checks on all APIs
2. Initialize the trading provider
3. Compile the LangGraph trading pipeline
4. Execute the trading loop every 60 seconds (configurable)

### 5.2 Switching Between Providers

To switch from Alpaca to Binance (or vice versa), just update `.env`:

```env
# For Alpaca paper trading (safe):
TRADING_PROVIDER="alpaca"
SYMBOL="BTCUSD"

# For Binance testnet (safe):
TRADING_PROVIDER="binance"
SYMBOL="BTCUSDT"
TESTNET=true

# For Binance mainnet (REAL MONEY - BE CAREFUL):
TRADING_PROVIDER="binance"
SYMBOL="BTCUSDT"
TESTNET=false
```

### 5.3 Monitor Trading Activity

The system logs all activity including:
- Market data ingestion
- Feature calculations
- Regime classification (with LLM reasoning)
- Strategy signals
- Risk checks
- Order execution results

Example output:
```
2025-11-16 10:30:00 - INFO - Connected to ALPACA (PAPER TRADING)
2025-11-16 10:30:05 - INFO - Trading Loop Iteration 1
2025-11-16 10:30:06 - INFO - Price: 43250.50
2025-11-16 10:30:06 - INFO - Regime: TRENDING (confidence: 0.85)
2025-11-16 10:30:07 - INFO - Signal: LONG (strength: 0.75)
2025-11-16 10:30:07 - INFO - Executing order: BUY 0.01 BTCUSD
2025-11-16 10:30:08 - INFO - Order executed successfully: order_123456
```

---

## 6. Running Tests

Tests live under `src/tests` and are configured via `pytest.ini`.

```bash
# from project root
poetry run pytest -q

# Run with verbose output
poetry run pytest -v

# Run specific test file
poetry run pytest src/tests/test_ingest.py
```

Tests are designed to be **offline** and should not hit external APIs; tools are mocked or stubbed where needed.

---

## 7. Architecture Highlights

### 7.1 Trading Provider Abstraction

The `TradingProvider` protocol in `trading_provider.py` provides a unified interface:

```python
from app.tools.trading_provider import trading_provider

# Works with both Binance and Alpaca
orderbook = await trading_provider.get_orderbook(symbol)
result = await trading_provider.execute_order(order)
```

### 7.2 Health Check System

Before trading starts, the system validates:
- API credentials are correct
- Market data is accessible
- Orders can be placed (paper trading mode)
- LLM is responding correctly

This prevents runtime failures and wasted time.

### 7.3 LangGraph Pipeline

The trading logic is implemented as a directed graph:

```
Market Ingest → Feature Engineering → Regime Classifier
                                            ↓
                                    Strategy Router
                                            ↓
                              Momentum Policy (or other strategies)
                                            ↓
                                      Risk Manager
                                            ↓
                                    Execution Agent
```

Each node is independently testable and can be swapped out.

---

## 8. Configuration Options

Key settings in `.env`:

| Variable | Description | Default | Options |
|----------|-------------|---------|---------|
| `TRADING_PROVIDER` | Which exchange to use | `binance` | `binance`, `alpaca` |
| `SYMBOL` | Trading pair | `BTCUSDT` | Any valid symbol for provider |
| `TESTNET` | Use testnet (Binance only) | `true` | `true`, `false` |
| `GEMINI_API_KEY` | Gemini LLM key | - | Required |
| `MAX_POSITION_SIZE` | Max position size | `0.1` | Any float |
| `MAX_DRAWDOWN_PERCENT` | Max drawdown % | `10.0` | Any float |
| `LOOP_INTERVAL_SECONDS` | Time between iterations | `60` | Any integer |
| `LLM_MODEL` | Gemini model | `gemini-1.5-pro` | Any Gemini model |

---

## 9. Safety Features

✅ **Paper Trading First**: Alpaca provider always uses paper trading  
✅ **Health Checks**: Validates APIs before trading  
✅ **Risk Limits**: Configurable position size and drawdown limits  
✅ **Error Handling**: Graceful degradation on API failures  
✅ **Testnet Support**: Binance testnet for safe crypto testing  
✅ **Comprehensive Logging**: Full audit trail of all decisions  

---

## 10. Next Steps

1. **Test with Paper Trading**: Start with Alpaca paper trading to validate strategy
2. **Backtest**: Enable backtesting mode with historical data
3. **Add Strategies**: Implement additional strategies beyond momentum
4. **Tune Parameters**: Optimize EMA periods, risk limits, etc.
5. **Monitor Performance**: Track Sharpe ratio, win rate, drawdown
6. **Go Live (Carefully)**: Only after extensive testing with paper trading

---

## 11. Troubleshooting

**Health checks fail**: Check API keys in `.env`, verify network connectivity

**"Provider not found" error**: Ensure `TRADING_PROVIDER` is set to `binance` or `alpaca`

**Symbol format error**: Use correct format for provider (BTCUSDT for Binance, BTCUSD for Alpaca)

**LLM errors**: Verify `GEMINI_API_KEY` is valid and you have API quota

**Import errors**: Run `poetry install` to ensure all dependencies are installed

---

## 12. Contributing

To add a new trading provider:

1. Create a tool in `src/app/tools/` implementing the `TradingProvider` protocol
2. Add provider selection logic in `trading_provider.py`
3. Add configuration variables in `config.py`
4. Update health checks in `healthcheck.py`
5. Add tests

---

## License

MIT License - see LICENSE file for details.

---

## 5. Running the trading agent

> ⚠️ Always start on **Binance testnet** and with small sizes.

From the project root:

```bash
python -m app.main
```

`main.py` will:

1. Initialize the Binance tool (testnet or mainnet according to config).
2. Compile the `full_mvp_graph` LangGraph.
3. Enter an infinite loop executing one full pipeline iteration per minute:
   - Ingest market data.
   - Compute features.
   - Classify market regime.
   - Route strategy.
   - Generate momentum signal (or neutral).
   - Apply risk checks and generate orders.
   - Execute approved orders and log results.

To run a **single iteration** (useful for debugging), you can call `run_single_iteration()` from an interactive session or add a small CLI wrapper.

---

## 6. Backtesting & metrics

For offline strategy evaluation:

- Use `Backtester` (`src/app/utils/backtester.py`) to simulate position opens/closes based on `Signal`s.
- Use `LOB-simulator` (`src/app/utils/lob_simulator.py`) to model order‑book‑level fills.
- Use `metrics` (`src/app/utils/metrics.py`) to compute performance statistics:
  - Sharpe ratio
  - Max drawdown
  - Win rate
  - Profit factor

A typical backtest loop:

1. Load historical candles from CSV.
2. Feed them into feature + momentum nodes.
3. Pass resulting signals into `Backtester.process_signal`.
4. At the end, call `Backtester.get_results()` and `metrics.generate_performance_report()`.

You can later wrap this into a dedicated script (e.g. `scripts/run_backtest.py`).

---

## 7. Deployment notes

### 7.1 Docker

The `docker/` folder contains a `Dockerfile` and `docker-compose.yml`. A typical workflow:

```bash
docker compose up --build
```

Ensure the container sets `PYTHONPATH=/src` (already handled in the Dockerfile) so that `import app` works.

### 7.2 Kubernetes

The `k8s/` manifests provide a basic deployment and service for running the agent in a cluster. You will want to:

- Mount configuration / secrets via Kubernetes Secrets and ConfigMaps.
- Ensure resource limits, liveness/readiness probes, and logging are configured for your environment.

### 7.3 CI

The `ci/github-actions.yaml` workflow is intended to:

- Install Python and dependencies.
- Run `pytest` on every push / PR.

Make sure secrets for live integrations are **not** required for CI (tests should work offline).

---

## 8. Roadmap / potential improvements

- Add a dedicated backtest runner script and CLI.
- Enhance `RiskManager` with volatility‑based sizing and daily drawdown tracking.
- Add more strategies (e.g. mean‑reversion) and integrate via `strategy_router`.
- Expand test coverage for the full LangGraph pipeline, backtester, and metrics.
- Add richer monitoring / logging, e.g. Prometheus metrics and dashboards.

This README will evolve as the system grows; contributions and refinements are welcome.

