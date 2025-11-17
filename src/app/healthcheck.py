"""Health checks for external dependencies (Binance/Alpaca, Gemini LLM).

Run this module as a script to verify that external services are reachable and
credentials are configured correctly before starting the full trading system.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from app.config import settings
from app.schemas.events import KlineEvent
from app.schemas.models import MarketFeatures, MarketRegime


class HealthCheckError(RuntimeError):
    """Raised when a health check fails."""


async def check_trading_provider(symbol: str | None = None) -> dict[str, Any]:
    """Check connectivity to configured trading provider (Binance or Alpaca).

    Returns a dict with status information. Raises HealthCheckError if a
    critical check fails.
    """
    from app.tools.trading_provider import trading_provider

    sym = symbol or settings.symbol
    result: dict[str, Any] = {
        "provider": settings.trading_provider,
        "symbol": sym,
        "ok": False
    }

    try:
        await trading_provider.initialize()

        # Fetch a tiny snapshot of each type of data to validate credentials and
        # basic connectivity without doing anything stateful.
        orderbook = await trading_provider.get_orderbook(sym, limit=5)

        # Try to fetch trades and klines, but don't fail if they're empty
        try:
            trades = await trading_provider.get_recent_trades(sym, limit=5)
        except Exception:
            trades = []  # Trades might not be available for all symbols/times

        try:
            klines = await trading_provider.get_klines(sym, interval="1m", limit=5)
        except Exception:
            klines = []  # Klines might not be available for all symbols/times

        # Try to fetch portfolio state (this validates write permissions)
        try:
            if settings.trading_provider == "binance":
                portfolio = await trading_provider.get_portfolio_state(sym)  # type: ignore
            else:
                portfolio = await trading_provider.get_portfolio_state()  # type: ignore
            result["portfolio_balance"] = portfolio.balance
            result["portfolio_equity"] = portfolio.equity
        except Exception as e:
            result["portfolio_error"] = str(e)
            # Don't fail the entire check if portfolio fetch fails
            # (might be permission issue)

        result.update(
            {
                "orderbook_levels": len(orderbook.bids) + len(orderbook.asks),
                "recent_trades": len(trades),
                "klines": len(klines),
                "ok": True,
            }
        )
        return result
    except Exception as exc:  # pragma: no cover - network dependent
        raise HealthCheckError(
            f"{settings.trading_provider.upper()} health check failed: {exc}"
        ) from exc
    finally:
        try:
            await trading_provider.close()
        except Exception:
            # Best-effort cleanup; not critical for health check
            pass


async def check_llm() -> dict[str, Any]:
    """Check that the Gemini LLM can be called and responds in the expected format.

    This uses a tiny dummy feature set and verifies that we can parse a
    MarketRegime out of the response.
    """
    from app.tools.llm_tool import llm_tool

    if not settings.gemini_api_key:
        raise HealthCheckError("GEMINI_API_KEY is not set in the environment")

    # Minimal synthetic features
    features = MarketFeatures(
        timestamp=datetime.now(),
        symbol=settings.symbol,
        price=50000.0,
        ema_9=50100.0,
        ema_50=49500.0,
    )

    try:
        regime: MarketRegime = await llm_tool.classify_regime_with_llm(
            features=features, ambiguity_score=0.5
        )
    except Exception as exc:  # pragma: no cover - network dependent
        raise HealthCheckError(f"LLM health check failed: {exc}") from exc

    if regime.regime not in {"TRENDING", "RANGING", "HIGH_VOLATILITY", "LOW_VOLATILITY", "UNKNOWN"}:
        raise HealthCheckError(f"Unexpected regime from LLM: {regime.regime}")

    return {
        "model": settings.llm_model,
        "regime": regime.regime,
        "confidence": regime.confidence,
        "ok": True,
    }


async def run_all_checks() -> dict[str, Any]:
    """Run all external health checks and aggregate results."""

    results: dict[str, Any] = {}

    # Run trading provider and LLM checks sequentially; in practice these could be
    # parallelised but sequential keeps logs simpler.
    trading_result = await check_trading_provider()
    results["trading_provider"] = trading_result

    llm_result = await check_llm()
    results["llm"] = llm_result

    results["ok"] = bool(trading_result.get("ok") and llm_result.get("ok"))
    return results


def main() -> None:
    """CLI entrypoint for running health checks.

    Usage:
        python -m app.healthcheck
    """

    print(f"Running external health checks ({settings.trading_provider.upper()}, Gemini)...")
    try:
        results = asyncio.run(run_all_checks())
    except HealthCheckError as exc:
        print(f"❌ Health check failed: {exc}")
        raise SystemExit(1) from exc

    print("✅ All health checks passed")
    print(results)


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()

