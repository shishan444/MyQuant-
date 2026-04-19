"""Normalize raw metrics to 0-100 scores."""
from __future__ import annotations


def normalize(metric_name: str, value: float) -> float:
    """Map a raw metric value to a 0-100 score.

    Normalization rules:
    - annual_return: linear map [-100%, +100%] -> [0, 100]
    - sharpe_ratio: linear map [0, 3.0] -> [0, 100], >= 3.0 = 100
    - max_drawdown: 0% drawdown = 100, >= 50% drawdown = 0
    - win_rate: linear map [40%, 70%] -> [0, 100]
    - calmar_ratio: linear map [0, 5.0] -> [0, 100], >= 5.0 = 100
    """
    if metric_name == "annual_return":
        # Map [-1.0, 1.0] to [0, 100]
        score = (value + 1.0) / 2.0 * 100
    elif metric_name == "sharpe_ratio":
        # Map [0, 3.0] to [0, 100]
        score = min(value / 3.0, 1.0) * 100
        if value < 0:
            score = max(0, 50 + value * 10)
    elif metric_name == "max_drawdown":
        # 0% drawdown = 100, >= 50% = 0
        # value is negative (e.g. -0.60 means 60% drawdown)
        # Linear: 0% dd → 100, 50% dd → 0
        score = (1.0 + value) * 100  # -0.60 → 40, but we want < 10 for -0.60
        score = max(0, min(100, score))
        # Use squared penalty for large drawdowns
        if value < -0.20:
            score = score * (1.0 + value)  # Extra penalty for large dd
    elif metric_name == "win_rate":
        # Map [0.4, 0.7] to [0, 100]
        score = (value - 0.4) / 0.3 * 100
    elif metric_name == "calmar_ratio":
        # Map [0, 5.0] to [0, 100]
        score = min(value / 5.0, 1.0) * 100
    elif metric_name == "sortino_ratio":
        # Map [0, 4.0] to [0, 100]
        score = min(value / 4.0, 1.0) * 100
        if value < 0:
            score = max(0, 50 + value * 10)
    elif metric_name == "profit_factor":
        # Map [0, 3.0] to [0, 100]
        if value <= 0:
            score = 0.0
        elif value < 1.0:
            score = value * 30  # PF < 1 is poor
        else:
            score = min(30 + (value - 1.0) / 2.0 * 70, 100.0)
    elif metric_name == "max_consecutive_losses":
        # 0 losses = 100, >= 10 losses = 0
        score = max(0, 100 - value * 10)
    elif metric_name == "monthly_consistency":
        # Already 0-1, scale to 0-100
        score = value * 100
    elif metric_name == "r_squared":
        # Already 0-1, scale to 0-100
        score = max(0.0, value) * 100
    else:
        score = 50.0

    return max(0.0, min(100.0, score))
