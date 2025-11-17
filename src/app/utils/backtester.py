"""Backtesting utilities."""
from datetime import datetime, timedelta
from typing import Any
import pandas as pd

from app.schemas.models import ExecutionResult, PortfolioState, Position, Signal
from app.schemas.events import KlineEvent


class Backtester:
    """Simple backtesting engine for strategy evaluation."""

    def __init__(self, initial_balance: float = 10000.0) -> None:
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.positions: list[Position] = []
        self.trades: list[dict[str, Any]] = []
        self.equity_curve: list[tuple[datetime, float]] = []

    def process_signal(
        self,
        signal: Signal,
        current_price: float,
        timestamp: datetime
    ) -> ExecutionResult:
        """
        Process a trading signal in backtest mode.

        Args:
            signal: Trading signal to process
            current_price: Current market price
            timestamp: Current timestamp

        Returns:
            ExecutionResult with simulated execution
        """
        # Close existing position if signal is opposite or neutral
        if self.positions:
            position = self.positions[0]

            should_close = False
            if signal.direction == "NEUTRAL":
                should_close = True
            elif signal.direction == "LONG" and position.side == "SHORT":
                should_close = True
            elif signal.direction == "SHORT" and position.side == "LONG":
                should_close = True

            if should_close:
                pnl = self._close_position(position, current_price, timestamp)
                self.balance += pnl

        # Open new position if signal is not neutral
        if signal.direction in ["LONG", "SHORT"] and not self.positions:
            self._open_position(signal, current_price, timestamp)

        # Record equity
        equity = self._calculate_equity(current_price)
        self.equity_curve.append((timestamp, equity))

        return ExecutionResult(
            success=True,
            order_id=f"backtest_{timestamp.timestamp()}",
            filled_quantity=0.01,  # Fixed size for simplicity
            filled_price=current_price,
            status="FILLED",
            timestamp=timestamp
        )

    def _open_position(
        self,
        signal: Signal,
        price: float,
        timestamp: datetime
    ) -> None:
        """Open a new position."""
        quantity = 0.01  # Fixed size for simplicity

        position = Position(
            symbol=signal.symbol,
            side=signal.direction,  # type: ignore
            quantity=quantity,
            entry_price=price,
            current_price=price,
            unrealized_pnl=0.0,
            timestamp=timestamp
        )

        self.positions.append(position)

        self.trades.append({
            "timestamp": timestamp,
            "type": "OPEN",
            "side": signal.direction,
            "price": price,
            "quantity": quantity,
            "signal_confidence": signal.confidence
        })

    def _close_position(
        self,
        position: Position,
        price: float,
        timestamp: datetime
    ) -> float:
        """Close a position and return PnL."""
        if position.side == "LONG":
            pnl = (price - position.entry_price) * position.quantity
        else:
            pnl = (position.entry_price - price) * position.quantity

        self.trades.append({
            "timestamp": timestamp,
            "type": "CLOSE",
            "side": position.side,
            "price": price,
            "quantity": position.quantity,
            "pnl": pnl,
            "entry_price": position.entry_price
        })

        self.positions.remove(position)
        return pnl

    def _calculate_equity(self, current_price: float) -> float:
        """Calculate current equity (balance + unrealized PnL)."""
        unrealized_pnl = 0.0

        for position in self.positions:
            if position.side == "LONG":
                unrealized_pnl += (current_price - position.entry_price) * position.quantity
            else:
                unrealized_pnl += (position.entry_price - current_price) * position.quantity

        return self.balance + unrealized_pnl

    def get_results(self) -> dict[str, Any]:
        """Get backtesting results and metrics."""
        if not self.equity_curve:
            return {
                "total_return": 0.0,
                "total_trades": 0,
                "win_rate": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0
            }

        final_equity = self.equity_curve[-1][1]
        total_return = (final_equity - self.initial_balance) / self.initial_balance * 100

        # Calculate win rate
        closed_trades = [t for t in self.trades if t["type"] == "CLOSE"]
        winning_trades = [t for t in closed_trades if t["pnl"] > 0]
        win_rate = len(winning_trades) / len(closed_trades) * 100 if closed_trades else 0.0

        # Calculate max drawdown
        max_drawdown = self._calculate_max_drawdown()

        # Calculate Sharpe ratio (simplified)
        sharpe_ratio = self._calculate_sharpe_ratio()

        return {
            "total_return": total_return,
            "final_equity": final_equity,
            "total_trades": len(closed_trades),
            "win_rate": win_rate,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "trades": self.trades
        }

    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown percentage."""
        if not self.equity_curve:
            return 0.0

        equities = [e for _, e in self.equity_curve]
        peak = equities[0]
        max_dd = 0.0

        for equity in equities:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100
            if dd > max_dd:
                max_dd = dd

        return max_dd

    def _calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio (simplified, assuming daily data)."""
        if len(self.equity_curve) < 2:
            return 0.0

        returns = []
        for i in range(1, len(self.equity_curve)):
            prev_equity = self.equity_curve[i-1][1]
            curr_equity = self.equity_curve[i][1]
            ret = (curr_equity - prev_equity) / prev_equity
            returns.append(ret)

        if not returns:
            return 0.0

        mean_return = sum(returns) / len(returns)

        if len(returns) < 2:
            return 0.0

        variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = variance ** 0.5

        if std_dev == 0:
            return 0.0

        # Annualize (assuming daily data)
        sharpe = (mean_return / std_dev) * (252 ** 0.5)
        return sharpe

