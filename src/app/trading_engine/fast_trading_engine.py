import asyncio
from typing import Dict, Any, List
from datetime import datetime
import logging

from app.config import settings
from app.langgraph_graphs.full_mvp_graph import FullMVPState
from app.schemas.models import RiskLimits
from app.utils.redis_client import redis_manager

# Nodes to run in sequence
from app.nodes.market_ingest import ingest_market_data_node
from app.nodes.feature_engineering import compute_features_node
from app.nodes.momentum_policy import momentum_strategy_node
from app.nodes.mean_reversion_policy import mean_reversion_strategy_node
from app.nodes.rl_agent_node import rl_agent_node
from app.nodes.hedge_agent import hedge_agent_node
from app.nodes.risk_manager import risk_management_node
from app.nodes.execution_agent import execution_agent_node

logger = logging.getLogger(__name__)

async def run_fast_execution_cycle(iteration: int) -> FullMVPState:
    """
    Executes one cycle of the fast trading engine.
    This skips LLM/sentiment logic entirely and relies on Redis for macro-state constraints.
    """
    logger.debug(f"[Fast Engine] Starting iteration {iteration}")

    # 1. Initialize State
    state: FullMVPState = {
        "trades": [], "orderbook": None, "klines": [], "features": None,
        "market_latent_state": None, "sentiment_fear_greed": None, "sentiment_funding_rate": None,
        "regime": None, "selected_strategy": None, "signals": [], "portfolio": None,
        "approved_orders": [], "execution_results": [],
        "risk_limits": RiskLimits(
            max_position_size=settings.max_position_size,
            max_drawdown_percent=settings.max_drawdown_percent,
            max_daily_loss=settings.max_daily_loss
        ),
        "symbol": settings.symbol, "timestamp": datetime.now()
    }

    try:
        # 2. Ingest Fast Data & Compute Features
        state = await ingest_market_data_node(state)
        state = await compute_features_node(state)

        # 3. Read Macro State from Redis (The Bridge)
        macro_state = await redis_manager.get_macro_state()
        if macro_state:
            # Inject slow-loop data into fast-loop state
            if "market_latent_state" in macro_state:
                state["market_latent_state"] = macro_state["market_latent_state"]
            
            # Since regime is a Pydantic model (MarketRegime) in full state but dict in Redis,
            # we need to reconstruct it if we use it strictly, or just pass dict. 
            # Risk limits could be dynamically adjusted here based on regime.
            # Example: Decrease position sizing in High Volatility regime.
            if macro_state.get("regime", {}).get("regime") in ["HIGH_VOLATILITY", "BEAR_MARKET"]:
                 state["risk_limits"].max_position_size = settings.max_position_size / 2.0
                 logger.debug("[Fast Engine] Reduced risk limits based on Redis macro regime.")

        # 4. Run Sub-Strategies (Generate individual signals)
        # These don't overwrite each other if they append to state["signals"] 
        # But 'momentum_strategy_node' overwrites state["signals"] by doing "signals": [Signal(...)]
        # We need to preserve them.
        
        all_signals = []
        
        # Momentum
        mom_state = await momentum_strategy_node(state)
        all_signals.extend(mom_state.get("signals", []))
        
        # Mean Reversion
        mr_state = await mean_reversion_strategy_node(state)
        all_signals.extend(mr_state.get("signals", []))
        
        state["signals"] = all_signals

        # 5. Run RL Meta-Agent
        # The RL agent can look at state["signals"] if retrained. 
        # Right now, it just calculates its own signal based on state["features"].
        rl_state = await rl_agent_node(state)
        
        # Determine the final signal to act on. 
        # For this architecture, the Meta RL agent's signal takes priority, 
        # but we include all signals for transparency.
        final_signals = state["signals"] + rl_state.get("signals", [])
        state["signals"] = final_signals

        # The rest of the pipeline expects state["selected_strategy"] to match one of the signals? 
        # No, hedge/risk manager just loop over state["signals"].
        
        # 6. Hedge, Risk Manage, and Execute
        state = await hedge_agent_node(state)
        state = await risk_management_node(state)
        state = await execution_agent_node(state)

    except Exception as e:
        logger.error(f"[Fast Engine] Error in execution cycle: {e}", exc_info=True)

    return state
