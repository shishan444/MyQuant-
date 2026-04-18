"""Raw metrics extraction from equity curve and trade-level data."""
from __future__ import annotations

import numpy as np
import pandas as pd


def compute_metrics(
    equity_curve: pd.Series,
    total_trades: int = 0,
    bars_per_year: int = 365 * 6,  # 4h bars per year
    trade_win_rate: float | None = None,
    trade_returns: np.ndarray | None = None,
) -> dict:
    """Compute raw performance metrics.

    Uses trade-level data for Sharpe and win_rate when available,
    falls back to equity curve for annual_return, max_drawdown, calmar.

    Args:
        equity_curve: Series of portfolio values over time.
        total_trades: Number of closed trades.
        bars_per_year: Number of bars in one year (default: 6 * 365 for 4h).
        trade_win_rate: Win rate from closed trades (0-1). None if unavailable.
        trade_returns: Array of per-trade returns (PnL / init_cash). None if unavailable.

    Returns:
        Dict with annual_return, sharpe_ratio, max_drawdown, win_rate,
        calmar_ratio, total_trades.
    """
    if len(equity_curve) < 2 or total_trades == 0:
        return {
            "annual_return": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "calmar_ratio": 0.0,
            "total_trades": 0,
        }

    # Annual return (from equity curve - standard)
    total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1
    n_bars = len(equity_curve)
    years = n_bars / bars_per_year
    annual_return = (1 + total_return) ** (1 / max(years, 0.01)) - 1 if years > 0 else 0.0

    # Max drawdown (from equity curve - standard)
    cummax = equity_curve.cummax()
    drawdown = (equity_curve - cummax) / cummax
    max_drawdown = float(drawdown.min())
    if np.isnan(max_drawdown):
        max_drawdown = 0.0

    # Sharpe ratio: prefer trade-level, fallback to bar-level
    sharpe_ratio = 0.0
    if trade_returns is not None and len(trade_returns) > 1:
        trade_mean = np.mean(trade_returns)
        trade_std = np.std(trade_returns, ddof=1)
        if trade_std > 0 and not np.isnan(trade_std):
            trades_per_year = total_trades / max(years, 0.01)
            sharpe_ratio = (trade_mean / trade_std) * np.sqrt(trades_per_year)
    elif total_trades >= 5:
        # Fallback: bar-level Sharpe from equity curve (only when enough trades)
        returns = equity_curve.pct_change().dropna()
        if len(returns) > 0:
            mean_ret = returns.mean()
            std_ret = returns.std()
            if std_ret > 0 and not np.isnan(std_ret):
                sharpe_ratio = (mean_ret / std_ret) * np.sqrt(bars_per_year)

    # Win rate: prefer trade-level, fallback to bar-level
    if trade_win_rate is not None:
        win_rate = trade_win_rate
    else:
        # Fallback: bar-level (less accurate)
        returns = equity_curve.pct_change().dropna()
        if len(returns) > 0:
            win_rate = float((returns > 0).sum() / len(returns))
        else:
            win_rate = 0.0

    # Calmar ratio
    if abs(max_drawdown) > 0.001:
        calmar_ratio = abs(annual_return / max_drawdown)
    else:
        calmar_ratio = 0.0

    return {
        "annual_return": float(annual_return),
        "sharpe_ratio": float(sharpe_ratio),
        "max_drawdown": float(max_drawdown),
        "win_rate": float(win_rate),
        "calmar_ratio": float(calmar_ratio),
        "total_trades": total_trades,
    }
