"""Main application entrypoint."""
import asyncio
import logging
from datetime import datetime

from app.config import settings
from app.langgraph_graphs.full_mvp_graph import create_full_mvp_graph, FullMVPState
from app.tools.trading_provider import trading_provider
from app.schemas.models import RiskLimits
from app.healthcheck import run_all_checks, HealthCheckError


# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_trading_loop() -> None:
    """
    Run the main trading loop.

    This executes the full MVP graph continuously, processing market data
    and executing trades based on the strategy pipeline.
    """
    logger.info("Initializing trading system...")

    # Run external health checks first so we fail fast if configuration is wrong.
    try:
        health = await run_all_checks()
        logger.info("External health checks passed: %s", health)
    except HealthCheckError as exc:
        logger.error("Health checks failed: %s", exc)
        return

    # Initialize trading provider connection
    await trading_provider.initialize()
    provider_name = settings.trading_provider.upper()
    mode = "PAPER TRADING" if settings.trading_provider == "alpaca" else ("TESTNET" if settings.testnet else "MAINNET")
    logger.info(f"Connected to {provider_name} ({mode})")

    # Create the full MVP graph
    graph = create_full_mvp_graph()
    logger.info("Trading graph compiled successfully")

    # Initialize state
    initial_state: FullMVPState = {
        "trades": [],
        "orderbook": None,
        "klines": [],
        "features": None,
        "regime": None,
        "selected_strategy": None,
        "signal": None,
        "portfolio": None,
        "approved_orders": [],
        "risk_limits": RiskLimits(
            max_position_size=settings.max_position_size,
            max_drawdown_percent=settings.max_drawdown_percent,
            max_daily_loss=settings.max_daily_loss
        ),
        "execution_results": [],
        "symbol": settings.symbol,
        "timestamp": datetime.now()
    }

    logger.info(f"Starting trading loop for {settings.symbol}")
    logger.info(
        "Loop interval set to %s seconds (configure via LOOP_INTERVAL_SECONDS)",
        settings.loop_interval_seconds,
    )

    # Check for iteration/time limits
    if settings.max_iterations > 0:
        logger.info(f"Max iterations limit: {settings.max_iterations}")
    if settings.time_limit_hours > 0:
        logger.info(f"Time limit: {settings.time_limit_hours} hours")

    if settings.max_iterations == 0 and settings.time_limit_hours == 0:
        logger.info("Running indefinitely - press Ctrl+C to stop")

    try:
        iteration = 0
        start_time = datetime.now()

        while True:
            iteration += 1

            # Check iteration limit
            if settings.max_iterations > 0 and iteration > settings.max_iterations:
                logger.info(f"Reached max iterations ({settings.max_iterations}). Stopping...")
                break

            # Check time limit
            if settings.time_limit_hours > 0:
                elapsed_hours = (datetime.now() - start_time).total_seconds() / 3600
                if elapsed_hours >= settings.time_limit_hours:
                    logger.info(f"Reached time limit ({settings.time_limit_hours} hours). Stopping...")
                    break

            logger.info(f"\n{'='*60}")
            logger.info(f"Trading Loop Iteration {iteration}")
            logger.info(f"{'='*60}")

            # Reset state for new iteration
            state = {
                **initial_state,
                "timestamp": datetime.now()
            }

            # Execute the graph
            try:
                iter_start = datetime.now()
                result = await graph.ainvoke(state)
                iter_duration = (datetime.now() - iter_start).total_seconds()

                # Log results
                logger.info(f"\nIteration {iteration} Results:")
                logger.info(f"Symbol: {result.get('symbol')}")

                if result.get('features'):
                    features = result['features']
                    logger.info(f"Price: {features.price:.2f}")
                    ema9 = f"{features.ema_9:.2f}" if getattr(features, 'ema_9', None) is not None else "N/A"
                    ema50 = f"{features.ema_50:.2f}" if getattr(features, 'ema_50', None) is not None else "N/A"
                    atr = f"{features.atr:.4f}" if getattr(features, 'atr', None) is not None else "N/A"
                    logger.info(f"EMA(9): {ema9}")
                    logger.info(f"EMA(50): {ema50}")
                    logger.info(f"ATR: {atr}")

                if result.get('regime'):
                    regime = result['regime']
                    logger.info(f"Regime: {regime.regime} (confidence: {regime.confidence:.2f})")

                if result.get('selected_strategy'):
                    logger.info(f"Selected Strategy: {result['selected_strategy']}")

                if result.get('signal'):
                    signal = result['signal']
                    logger.info(f"Signal: {signal.direction} (strength: {signal.strength:.2f}, confidence: {signal.confidence:.2f})")
                    logger.info(f"Reasoning: {signal.reasoning}")

                if result.get('approved_orders'):
                    logger.info(f"Approved Orders: {len(result['approved_orders'])}")
                    for order in result['approved_orders']:
                        logger.info(f"  - {order.side} {order.quantity} {order.symbol} @ {order.order_type}")

                if result.get('execution_results'):
                    logger.info(f"Execution Results: {len(result['execution_results'])}")
                    for exec_result in result['execution_results']:
                        status = "SUCCESS" if exec_result.success else "FAILED"
                        logger.info(f"  - {status}: {exec_result.order_id}")
                        if exec_result.error_message:
                            logger.error(f"    Error: {exec_result.error_message}")

            except Exception as e:
                logger.error(f"Error executing trading graph: {e}", exc_info=True)

            logger.info("Iteration %s completed in %.3fs", iteration, iter_duration)

            # Wait before next iteration based on configured interval
            await asyncio.sleep(settings.loop_interval_seconds)

    except KeyboardInterrupt:
        logger.info("\nShutting down trading system (Ctrl+C pressed)...")
    finally:
        await trading_provider.close()
        logger.info("Trading system stopped cleanly")
        logger.info(f"Total iterations completed: {iteration}")


async def run_single_iteration() -> None:
    """
    Run a single iteration of the trading pipeline (for testing).
    """
    logger.info("Running single iteration...")

    # Initialize via provider abstraction to match runtime selection (Alpaca/Binance)
    await trading_provider.initialize()

    graph = create_full_mvp_graph()

    state: FullMVPState = {
        "trades": [],
        "orderbook": None,
        "klines": [],
        "features": None,
        "regime": None,
        "selected_strategy": None,
        "signal": None,
        "portfolio": None,
        "approved_orders": [],
        "risk_limits": RiskLimits(
            max_position_size=settings.max_position_size,
            max_drawdown_percent=settings.max_drawdown_percent,
            max_daily_loss=settings.max_daily_loss
        ),
        "execution_results": [],
        "symbol": settings.symbol,
        "timestamp": datetime.now()
    }

    result = await graph.ainvoke(state)

    logger.info("Results:")
    logger.info(f"Features: {result.get('features')}")
    logger.info(f"Regime: {result.get('regime')}")
    logger.info(f"Signal: {result.get('signal')}")
    logger.info(f"Approved Orders: {result.get('approved_orders')}")
    logger.info(f"Execution Results: {result.get('execution_results')}")

    await trading_provider.close()


def main() -> None:
    """Main entrypoint."""
    logger.info("LangGraph Trading Agent Starting...")
    logger.info(f"Python 3.11 | LangGraph | Binance {'Testnet' if settings.testnet else 'Mainnet'}")
    logger.info(f"Symbol: {settings.symbol}")

    # Run the trading loop
    asyncio.run(run_trading_loop())


if __name__ == "__main__":
    main()
