"""Trading performance metrics."""
from typing import Any
import math


def calculate_sharpe_ratio(returns: list[float], risk_free_rate: float = 0.0) -> float:
    """
    Calculate Sharpe ratio.

    Args:
        returns: List of period returns
        risk_free_rate: Risk-free rate (annualized)

    Returns:
        Sharpe ratio
    """
    if not returns or len(returns) < 2:
        return 0.0

    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
    std_dev = math.sqrt(variance)

    if std_dev == 0:
        return 0.0

    # Annualize assuming daily returns
    sharpe = ((mean_return - risk_free_rate) / std_dev) * math.sqrt(252)
    return sharpe


def calculate_sortino_ratio(
    returns: list[float],
    risk_free_rate: float = 0.0,
    target_return: float = 0.0
) -> float:
    """
    Calculate Sortino ratio (like Sharpe but only penalizes downside volatility).

    Args:
        returns: List of period returns
        risk_free_rate: Risk-free rate
        target_return: Target/minimum acceptable return

    Returns:
        Sortino ratio
    """
    if not returns or len(returns) < 2:
        return 0.0

    mean_return = sum(returns) / len(returns)

    # Calculate downside deviation
    downside_returns = [r - target_return for r in returns if r < target_return]

    if not downside_returns:
        return float('inf') if mean_return > target_return else 0.0

    downside_variance = sum(r ** 2 for r in downside_returns) / len(downside_returns)
    downside_std = math.sqrt(downside_variance)

    if downside_std == 0:
        return 0.0

    sortino = ((mean_return - risk_free_rate) / downside_std) * math.sqrt(252)
    return sortino


def calculate_max_drawdown(equity_curve: list[float]) -> float:
    """
    Calculate maximum drawdown percentage.

    Args:
        equity_curve: List of equity values over time

    Returns:
        Maximum drawdown as percentage
    """
    if not equity_curve:
        return 0.0

    peak = equity_curve[0]
    max_dd = 0.0

    for equity in equity_curve:
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak * 100 if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    return max_dd


def calculate_calmar_ratio(
    total_return: float,
    max_drawdown: float,
    years: float = 1.0
) -> float:
    """
    Calculate Calmar ratio (annualized return / max drawdown).

    Args:
        total_return: Total return percentage
        max_drawdown: Maximum drawdown percentage
        years: Number of years in period

    Returns:
        Calmar ratio
    """
    if max_drawdown == 0:
        return 0.0

    annualized_return = ((1 + total_return / 100) ** (1 / years) - 1) * 100
    return annualized_return / max_drawdown


def calculate_win_rate(trades: list[dict[str, Any]]) -> float:
    """
    Calculate win rate from trade history.

    Args:
        trades: List of trade dictionaries with 'pnl' key

    Returns:
        Win rate percentage
    """
    if not trades:
        return 0.0

    winning_trades = sum(1 for trade in trades if trade.get('pnl', 0) > 0)
    return winning_trades / len(trades) * 100


def calculate_profit_factor(trades: list[dict[str, Any]]) -> float:
    """
    Calculate profit factor (gross profit / gross loss).

    Args:
        trades: List of trade dictionaries with 'pnl' key

    Returns:
        Profit factor
    """
    if not trades:
        return 0.0

    gross_profit = sum(trade.get('pnl', 0) for trade in trades if trade.get('pnl', 0) > 0)
    gross_loss = abs(sum(trade.get('pnl', 0) for trade in trades if trade.get('pnl', 0) < 0))

    if gross_loss == 0:
        return float('inf') if gross_profit > 0 else 0.0

    return gross_profit / gross_loss


def calculate_average_win_loss_ratio(trades: list[dict[str, Any]]) -> float:
    """
    Calculate average win / average loss ratio.

    Args:
        trades: List of trade dictionaries with 'pnl' key

    Returns:
        Win/Loss ratio
    """
    if not trades:
        return 0.0

    winning_trades = [trade.get('pnl', 0) for trade in trades if trade.get('pnl', 0) > 0]
    losing_trades = [abs(trade.get('pnl', 0)) for trade in trades if trade.get('pnl', 0) < 0]

    if not winning_trades or not losing_trades:
        return 0.0

    avg_win = sum(winning_trades) / len(winning_trades)
    avg_loss = sum(losing_trades) / len(losing_trades)

    if avg_loss == 0:
        return float('inf')

    return avg_win / avg_loss


def generate_performance_report(
    equity_curve: list[float],
    trades: list[dict[str, Any]],
    initial_balance: float,
    years: float = 1.0
) -> dict[str, float]:
    """
    Generate comprehensive performance report.

    Args:
        equity_curve: List of equity values
        trades: List of trade dictionaries
        initial_balance: Starting balance
        years: Period length in years

    Returns:
        Dictionary of performance metrics
    """
    if not equity_curve:
        return {}

    final_equity = equity_curve[-1]
    total_return = (final_equity - initial_balance) / initial_balance * 100

    # Calculate returns
    returns = []
    for i in range(1, len(equity_curve)):
        ret = (equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1]
        returns.append(ret)

    max_dd = calculate_max_drawdown(equity_curve)

    return {
        "total_return_pct": total_return,
        "final_equity": final_equity,
        "max_drawdown_pct": max_dd,
        "sharpe_ratio": calculate_sharpe_ratio(returns),
        "sortino_ratio": calculate_sortino_ratio(returns),
        "calmar_ratio": calculate_calmar_ratio(total_return, max_dd, years),
        "total_trades": len(trades),
        "win_rate_pct": calculate_win_rate(trades),
        "profit_factor": calculate_profit_factor(trades),
        "avg_win_loss_ratio": calculate_average_win_loss_ratio(trades)
    }

