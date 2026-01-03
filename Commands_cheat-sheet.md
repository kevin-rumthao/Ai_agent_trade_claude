# ⌨️ CLI Commands Cheat Sheet & Reference

This document provides a comprehensive reference for all the terminal commands available in the **Ai_agent_trade_claude** system.

## 🚀 Setup & Verification

Commands to initialize the environment and verify that all components are working correctly.

| Command | Description |
| :--- | :--- |
| `poetry install` | Installs project dependencies. |
| `poetry shell` | Activates the virtual environment. |
| `poetry run python scripts/quickstart.py` | **Start Here.** Interactive wizard to configure `.env` and set up the project. |
| `poetry run python -m app.healthcheck` | Comprehensive system check (API keys, DB, External Services). |
| `poetry run python scripts/verify_alpaca_connection.py` | Specifically tests the connection to Alpaca (Paper Trading). |
| `poetry run python scripts/verify_gemini_connection.py` | Specifically tests the connection to Google Gemini (LLM). |
| `poetry run python scripts/verify_graphs.py` | Validates the integrity of the LangGraph workflow definitions. |
| `bash scripts/verify_setup.sh` | Shell script that checks environment variables and dependencies. |

## 🤖 Core Trading Agents

Commands to run the main trading bots in different modes.

| Command | Description |
| :--- | :--- |
| `poetry run python -m app.main` | **Main Agent Loop.** Runs the full LangGraph agent. Recommended for production-like execution. |
| `poetry run python scripts/run_paper_trade.py` | **Paper Trading Bot.** Runs the 15-minute strategy loop optimization. **Best for testing.** |

## 🧪 Backtesting & Simulation

Tools to test strategies against historical data.

| Command | Description |
| :--- | :--- |
| `poetry run python scripts/run_backtest.py` | **Main Backtester.** Runs strategy backtests. <br> **Options:** <br> `--days <N>`: Number of days. <br> `--strategy <name>`: `momentum` or `mean_reversion`. <br> `--visual`: Show charts. |
| `poetry run python scripts/quick_vectorized_test.py` | Fast, vectorized backtest for rapid strategy iteration (skips full graph simulation). |

## 📊 Data Management

Scripts to download, convert, and process market data.

| Command | Description |
| :--- | :--- |
| `poetry run python scripts/fetch_data.py` | General purpose tool to fetch historical candles. |
| `poetry run python scripts/download_trades.py` | Downloads raw trade history (tick data). |
| `poetry run python scripts/download_depth_data.py` | Downloads order book depth data. |
| `poetry run python scripts/process_trades.py` | Cleans and processes raw trade data. |
| `poetry run python scripts/reconstruct_orderbook.py` | Reconstructs Limit Order Books (LOB) from diffs/snapshots. |
| `poetry run python scripts/convert_btc_data.py` | Helper format converter for BTC datasets. |
| `poetry run python scripts/convert_nifty_data.py` | Helper format converter for Nifty (Indian Market) datasets. |
| `poetry run python scripts/merge_datasets.py` | Utilities to merge scattered CSV data files. |
| `poetry run python scripts/fetch_gap_data.py` | Fetches data for gap analysis strategies. |
| `poetry run python scripts/check_url.py` | Utility to verify data source URLs. |

## 📈 Analysis & Visualization

Tools for analyzing data quality and visualizing results.

| Command | Description |
| :--- | :--- |
| `poetry run python scripts/plot_btc_data.py` | Visualizes Bitcoin price data and indicators. |
| `poetry run python scripts/analyze_data_noise.py` | Analyzes market noise levels to tune filter parameters. |

---

## 🧐 Understanding CLI Syntax

### 1. `python -m <module>`

* **Usage:** `poetry run python -m app.main`
* **Why:** Runs a Python **module** from the package. Required for `app.*` scripts to handle relative imports correctly.

### 2. File Paths

* **Usage:** `poetry run python scripts/run_backtest.py`
* **Why:** Runs symbols as standalone scripts. Used for files in `scripts/`.

### 3. `--` Flags

* **Usage:** `... --days 7 --visual`
* **Why:** Parameters passed to the script to modify behavior.

### 4. ` -- ` Separator

* **Usage:** `poetry run -- python script.py`
* **Why:** Tells Poetry to stop parsing flags, passing everything after `--` directly to the python script.
