# Decoupled AI Trading Agent

This project implements a **modular, event‑driven AI trading agent** built on **LangGraph**. It combines real-time market data from trading platforms, AI-powered decision-making via Google Gemini, risk management, and automated execution on paper/live trading accounts.

Recently, the architecture has been upgraded to a **two-speed decoupled** system using Redis, managed by a FastAPI server, and visualized via a modern React/Vite dashboard.

---

## 🏗️ 1. Architecture

The system features a **two-speed Decoupled Trading Architecture**:

1. **Fast Trading Engine (`fast_trading_engine.py`)**:
   - Runs at high frequency (e.g., tick or minute level).
   - Ingests market data (Binance, Alpaca).
   - Computes technical indicators (EMA, ATR, Volatility).
   - Executes fast strategies (Momentum, Mean Reversion).

2. **Slow Macro Graph (`slow_macro_graph.py`)**:
   - Runs synchronously at lower frequency (e.g., every 15 mins or hourly).
   - Uses **LangGraph** & **Google Gemini** for intelligent market regime classification.
   - Computes macro filters and updates global states.

3. **Redis IPC & State Layer**:
   - Both loops run completely asynchronously.
   - Redis manages Pub/Sub streams for inter-process communication.
   - Market state and AI regime classifications are published here.

4. **FastAPI Backend (`api/server.py`)**:
   - Provides a REST API and WebSockets for real-time state extraction.
   - Manages the start/stop orchestration of the trading engines.

5. **Frontend Dashboard (`frontend/`)**:
   - Built with **React** + **Vite** + **TypeScript**.
   - Premium glassmorphism UI interacting dynamically with the FastAPI backend.

---

## 🚀 2. Quick Setup

### Prerequisites

- **Python 3.11+**
- **Docker & Redis** (Required for IPC)
- **Node.js 18+** (For the frontend)
- **Poetry** (For Python dependency management)

### Step 1: Clone and Install Backend

```bash
git clone <repository>
cd Ai_agent_trade_claude

# Install dependencies using Poetry
poetry install
poetry shell
```

### Step 2: Install Frontend

```bash
cd frontend
npm install
cd ..
```

### Step 3: Configure Environment

Copy `.env.example` or create `.env` in the root:

```env
# Trading Provider: "alpaca" or "binance"
TRADING_PROVIDER="alpaca"

# API Keys (Alpaca Paper Trading recommended)
ALPACA_API_KEY="PK..."
ALPACA_API_SECRET="..."

# Binance Keys
BINANCE_API_KEY="..."
BINANCE_API_SECRET="..."

# Google Gemini API
GEMINI_API_KEY="..."

# Redis
REDIS_URL="redis://localhost:6379/0"

# Trading Configurations
SYMBOL="BTCUSD" # Use AAPL for stocks on Alpaca
TESTNET=true
LOG_LEVEL="INFO"
```

---

## 🏃 3. Operation

### Start Redis Server

Ensure a Redis instance is running locally:

```bash
docker run -d -p 6379:6379 redis:latest
```

### Run the System

The easiest way to orchestrate the entire backend (Fast API, Fast Engine, Slow Graph) is to start the API Server:

```bash
poetry run uvicorn src.app.api.server:app --host 0.0.0.0 --port 8000 --reload
```
*(Alternatively, you can run `python -m app.main` if running the legacy monolithic agent).*

### Start the Frontend Dashboard

In a new terminal:

```bash
cd frontend
npm run dev
```

Navigate to `http://localhost:5173` to view the comprehensive trading dashboard.

---

## 🛡️ 4. Safety & Risk Management

- **Health Checks**: Run `poetry run python -m app.healthcheck` to ensure API and LLM dependencies are available.
- **Limits**: Control risk with `MAX_POSITION_SIZE`, `MAX_DRAWDOWN_PERCENT`, and `MAX_DAILY_LOSS` in `.env`.
- **Paper Trading First**: We strongly advise starting with Alpaca Paper Trading (`TRADING_PROVIDER="alpaca"`).

---

## 📊 5. Backtesting & Analysis

Validate your strategies using historical data and event-driven LOB simulation:

```bash
# Basic Momentum Backtest (Last 7 Days)
poetry run python scripts/run_backtest.py --days 7 --strategy momentum --visual

# Run Mean Reversion Test
poetry run python scripts/run_backtest.py --days 30 --strategy mean_reversion --visual
```

To run unit tests:

```bash
poetry run pytest -v
```

---

## 🔧 6. Tech Stack

- **Backend**: Python 3.11+, FastAPI, LangGraph, LangChain, Pydantic, Redis.
- **Frontend**: React, Vite, TypeScript, Vanilla CSS.
- **ML/AI**: Google Gemini (LLM), Gymnasium (RL Trading Env), PPO (Beta).

## 📄 License

MIT License - see LICENSE file for details.
