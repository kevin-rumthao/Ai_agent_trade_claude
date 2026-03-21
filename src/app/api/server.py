from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
from datetime import datetime
import logging
from typing import Set

from app.config import settings
from app.langgraph_graphs.slow_macro_graph import create_slow_macro_graph
from app.trading_engine.fast_trading_engine import run_fast_execution_cycle
from app.langgraph_graphs.full_mvp_graph import FullMVPState
from app.tools.trading_provider import trading_provider
from app.schemas.models import RiskLimits
from app.healthcheck import run_all_checks, HealthCheckError

logger = logging.getLogger(__name__)

from fastapi import Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os

app = FastAPI(title="AI Trading Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, this should be restricted
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ensure directories exist
os.makedirs(os.path.join(BASE_DIR, "static", "js"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "templates"), exist_ok=True)

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@app.get("/dashboard")
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "symbol": settings.symbol,
        "provider": settings.trading_provider
    })

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: str):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error sending message to {connection}: {e}")
                self.disconnect(connection)

manager = ConnectionManager()

# Global state to track the bot's execution status
bot_state = {
    "is_running": False,
    "fast_iterations": 0,
    "slow_iterations": 0,
    "last_error": None
}
fast_bot_task = None
slow_bot_task = None

def serialize_state(state: FullMVPState) -> str:
    """Helper to serialize FullMVPState to JSON for WebSockets."""
    # Simplify state for frontend to prevent dumping too much data
    try:
        data = {
            "timestamp": state["timestamp"].isoformat() if state.get("timestamp") else datetime.now().isoformat(),
            "symbol": state.get("symbol"),
            "iteration": bot_state["fast_iterations"],
            "slow_iterations": bot_state["slow_iterations"],
            "features": None,
            "regime": None,
            "selected_strategy": state.get("selected_strategy"),
            "signals": [],
            "approved_orders": [],
            "execution_results": []
        }
        
        if state.get("features"):
            f = state["features"]
            data["features"] = {
                "price": float(f.price),
                "ema_9": float(f.ema_9) if getattr(f, 'ema_9', None) is not None else None,
                "ema_50": float(f.ema_50) if getattr(f, 'ema_50', None) is not None else None,
                "atr": float(f.atr) if getattr(f, 'atr', None) is not None else None,
                "volatility": float(f.realized_volatility) if getattr(f, 'realized_volatility', None) is not None else None,
                "adx": float(f.adx) if getattr(f, 'adx', None) is not None else None
            }
            
        if state.get("regime"):
            r = state["regime"]
            data["regime"] = {
                "regime": r.regime.value if hasattr(r.regime, 'value') else str(r.regime),
                "confidence": float(r.confidence)
            }
            
        if state.get("signals"):
            data["signals"] = [
                {
                    "strategy": s.strategy,
                    "direction": s.direction.value if hasattr(s.direction, 'value') else str(s.direction),
                    "strength": float(s.strength),
                    "confidence": float(s.confidence),
                    "reasoning": s.reasoning
                } for s in state["signals"]
            ]
            
        if state.get("approved_orders"):
            data["approved_orders"] = [
                {
                    "symbol": o.symbol,
                    "side": o.side.value if hasattr(o.side, 'value') else str(o.side),
                    "quantity": float(o.quantity),
                    "order_type": o.order_type.value if hasattr(o.order_type, 'value') else str(o.order_type)
                } for o in state["approved_orders"]
            ]
            
        if state.get("execution_results"):
            data["execution_results"] = [
                {
                    "order_id": e.order_id,
                    "success": e.success,
                    "error_message": e.error_message
                } for e in state["execution_results"]
            ]
            
        return json.dumps(data)
    except Exception as e:
        logger.error(f"Error serializing state: {e}")
        return json.dumps({"error": str(e), "type": "serialization_error"})

async def run_slow_macro_loop():
    """Background task for the slow, LangGraph-based macro analysis."""
    logger.info("Initializing Slow Macro Loop...")
    graph = create_slow_macro_graph()
    
    initial_state = {
        "trades": [], "orderbook": None, "klines": [], "features": None,
        "market_latent_state": None, "sentiment_fear_greed": None, "sentiment_funding_rate": None,
        "regime": None, "selected_strategy": None, "signals": [], "portfolio": None,
        "approved_orders": [], "execution_results": [],
        "symbol": settings.symbol, "timestamp": datetime.now()
    }

    try:
        while bot_state["is_running"]:
            bot_state["slow_iterations"] += 1
            state = {**initial_state, "timestamp": datetime.now()}
            
            try:
                # Runs the LLM/Sentiment graph and writes to Redis at the end
                await graph.ainvoke(state)
                await manager.broadcast(json.dumps({
                    "type": "system_event",
                    "message": f"Slow Macro Loop completed cycle {bot_state['slow_iterations']} and persisted state to Redis."
                }))
            except Exception as e:
                logger.error(f"Error in macro graph execution: {e}", exc_info=True)
                
            if bot_state["is_running"]:
                await asyncio.sleep(settings.slow_loop_interval_seconds)
                
    except asyncio.CancelledError:
        logger.info("Slow Macro Loop cancelled.")
    except Exception as e:
        logger.error(f"Fatal error in Slow Macro Loop: {e}", exc_info=True)


async def run_fast_execution_loop():
    """Background task that wraps the incredibly fast RL trading engine."""
    bot_state["last_error"] = None
    bot_state["fast_iterations"] = 0
    
    logger.info("Initializing Fast Execution Engine...")

    try:
        health = await run_all_checks()
        await manager.broadcast(json.dumps({"type": "system_event", "message": f"External health checks passed"}))
    except HealthCheckError as exc:
        bot_state["last_error"] = str(exc)
        bot_state["is_running"] = False
        await manager.broadcast(json.dumps({"type": "system_error", "message": f"Health checks failed: {exc}"}))
        return

    try:
        await trading_provider.initialize()
        await manager.broadcast(json.dumps({"type": "system_event", "message": f"Fast Execution loop started for {settings.symbol}"}))

        while bot_state["is_running"]:
            bot_state["fast_iterations"] += 1
            
            # Broadcast start of iteration
            await manager.broadcast(json.dumps({
                "type": "iteration_start",
                "iteration": bot_state["fast_iterations"],
                "timestamp": datetime.now().isoformat()
            }))
            
            try:
                # Cycle runs sequentially: fetch -> strategy modules -> RL Agent -> execute
                state = await run_fast_execution_cycle(bot_state["fast_iterations"])
                
                # Broadcast result securely
                await manager.broadcast(json.dumps({
                    "type": "state_update",
                    "data": json.loads(serialize_state(state))
                }))
            except Exception as e:
                logger.error(f"Error in fast execution cycle: {e}", exc_info=True)
                await manager.broadcast(json.dumps({"type": "system_error", "message": f"Execution error: {e}"}))

            if bot_state["is_running"]:
                await asyncio.sleep(settings.fast_loop_interval_seconds)

    except asyncio.CancelledError:
        logger.info("Fast execution loop cancelled via API.")
    except Exception as e:
        bot_state["last_error"] = str(e)
        logger.error(f"Fatal error in fast execution loop: {e}", exc_info=True)
    finally:
        bot_state["is_running"] = False
        await trading_provider.close()
        await manager.broadcast(json.dumps({"type": "system_event", "message": "Trading loop stopped cleanly"}))

@app.on_event("startup")
async def startup_event():
    logger.info("FastAPI Application starting...")

@app.on_event("shutdown")
async def shutdown_event():
    global bot_state, fast_bot_task, slow_bot_task
    bot_state["is_running"] = False
    if fast_bot_task and not fast_bot_task.done():
        fast_bot_task.cancel()
    if slow_bot_task and not slow_bot_task.done():
        slow_bot_task.cancel()

@app.get("/api/status")
async def get_status():
    return {
        "is_running": bot_state["is_running"],
        "fast_iterations": bot_state["fast_iterations"],
        "slow_iterations": bot_state["slow_iterations"],
        "last_error": bot_state["last_error"],
        "symbol": settings.symbol,
        "provider": settings.trading_provider
    }

@app.post("/api/start")
async def start_bot(background_tasks: BackgroundTasks):
    global fast_bot_task, slow_bot_task
    if bot_state["is_running"]:
        return {"status": "already running"}
    
    bot_state["is_running"] = True
    fast_bot_task = asyncio.create_task(run_fast_execution_loop())
    slow_bot_task = asyncio.create_task(run_slow_macro_loop())
    return {"status": "started both loops"}

@app.post("/api/stop")
async def stop_bot():
    global fast_bot_task, slow_bot_task
    if not bot_state["is_running"]:
        return {"status": "not running"}
    
    bot_state["is_running"] = False
    if fast_bot_task:
        fast_bot_task.cancel()
    if slow_bot_task:
        slow_bot_task.cancel()
    return {"status": "stopping"}

@app.get("/api/config")
async def get_config():
    # Only return safe configuration
    return {
        "trading_provider": settings.trading_provider,
        "symbol": settings.symbol,
        "testnet": settings.testnet,
        "max_position_size": settings.max_position_size,
        "max_drawdown_percent": settings.max_drawdown_percent,
        "fast_loop_interval_seconds": settings.fast_loop_interval_seconds,
        "slow_loop_interval_seconds": settings.slow_loop_interval_seconds,
        "llm_model": settings.llm_model
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send initial status
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "message": "Connected to AI Trading Agent WebSocket"
        }))
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
