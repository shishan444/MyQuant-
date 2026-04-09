"""Raw metrics extraction from equity curve."""
from __future__ import annotations

import numpy as np
import pandas as pd


def compute_metrics(
    equity_curve: pd.Series,
    total_trades: int = 0,
    bars_per_year: int = 365 * 6,  # 4h bars per year
) -> dict:
    """Compute raw performance metrics from an equity curve.

    Args:
        equity_curve: Series of portfolio values over time.
        total_trades: Number of closed trades.
        bars_per_year: Number of bars in one year (default: 6 * 365 for 4h).

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

    # Returns
    returns = equity_curve.pct_change().dropna()
    if len(returns) == 0:
        return {
            "annual_return": 0.0, "sharpe_ratio": 0.0,
            "max_drawdown": 0.0, "win_rate": 0.0,
            "calmar_ratio": 0.0, "total_trades": total_trades,
        }

    # Annual return
    total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1
    n_bars = len(equity_curve)
    years = n_bars / bars_per_year
    annual_return = (1 + total_return) ** (1 / max(years, 0.01)) - 1 if years > 0 else 0.0

    # Sharpe ratio (annualized)
    mean_return = returns.mean()
    std_return = returns.std()
    if std_return == 0 or np.isnan(std_return):
        sharpe_ratio = 0.0
    else:
        sharpe_ratio = (mean_return / std_return) * np.sqrt(bars_per_year)

    # Max drawdown
    cummax = equity_curve.cummax()
    drawdown = (equity_curve - cummax) / cummax
    max_drawdown = float(drawdown.min())
    if np.isnan(max_drawdown):
        max_drawdown = 0.0

    # Win rate (from returns)
    positive_returns = (returns > 0).sum()
    win_rate = positive_returns / len(returns)

    # Calmar ratio (annual_return / abs(max_drawdown))
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
