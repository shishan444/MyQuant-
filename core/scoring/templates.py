"""Scoring template definitions.

Templates use 11 dimensions for comprehensive strategy evaluation:
- Core: annual_return, sharpe_ratio, max_drawdown, win_rate, calmar_ratio
- Extended: sortino_ratio, profit_factor, max_consecutive_losses, monthly_consistency, r_squared
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class ScoringTemplate:
    """A scoring template with dimension weights and threshold."""
    name: str
    weights: Dict[str, float]
    threshold: float


SCORING_TEMPLATES: Dict[str, ScoringTemplate] = {
    "balanced": ScoringTemplate(
        name="balanced",
        weights={
            "annual_return": 0.15,
            "sharpe_ratio": 0.15,
            "max_drawdown": 0.15,
            "win_rate": 0.10,
            "calmar_ratio": 0.10,
            "sortino_ratio": 0.10,
            "profit_factor": 0.10,
            "max_consecutive_losses": 0.05,
            "monthly_consistency": 0.05,
            "r_squared": 0.05,
        },
        threshold=65.0,
    ),
    "aggressive": ScoringTemplate(
        name="aggressive",
        weights={
            "annual_return": 0.30,
            "sharpe_ratio": 0.20,
            "max_drawdown": 0.10,
            "win_rate": 0.10,
            "calmar_ratio": 0.10,
            "sortino_ratio": 0.05,
            "profit_factor": 0.10,
            "max_consecutive_losses": 0.05,
            "r_squared": 0.00,
        },
        threshold=55.0,
    ),
    "conservative": ScoringTemplate(
        name="conservative",
        weights={
            "annual_return": 0.05,
            "sharpe_ratio": 0.15,
            "max_drawdown": 0.25,
            "win_rate": 0.10,
            "calmar_ratio": 0.15,
            "sortino_ratio": 0.10,
            "profit_factor": 0.05,
            "max_consecutive_losses": 0.10,
            "monthly_consistency": 0.03,
            "r_squared": 0.02,
        },
        threshold=75.0,
    ),
    # Legacy aliases (mapped to new templates)
    "profit_first": ScoringTemplate(
        name="profit_first",
        weights={
            "annual_return": 0.30,
            "sharpe_ratio": 0.20,
            "max_drawdown": 0.10,
            "win_rate": 0.10,
            "calmar_ratio": 0.10,
            "sortino_ratio": 0.05,
            "profit_factor": 0.10,
            "max_consecutive_losses": 0.05,
            "r_squared": 0.00,
        },
        threshold=55.0,
    ),
    "steady": ScoringTemplate(
        name="steady",
        weights={
            "annual_return": 0.15,
            "sharpe_ratio": 0.15,
            "max_drawdown": 0.15,
            "win_rate": 0.10,
            "calmar_ratio": 0.10,
            "sortino_ratio": 0.10,
            "profit_factor": 0.10,
            "max_consecutive_losses": 0.05,
            "monthly_consistency": 0.05,
            "r_squared": 0.05,
        },
        threshold=65.0,
    ),
    "risk_first": ScoringTemplate(
        name="risk_first",
        weights={
            "annual_return": 0.05,
            "sharpe_ratio": 0.15,
            "max_drawdown": 0.25,
            "win_rate": 0.10,
            "calmar_ratio": 0.15,
            "sortino_ratio": 0.10,
            "profit_factor": 0.05,
            "max_consecutive_losses": 0.10,
            "monthly_consistency": 0.03,
            "r_squared": 0.02,
        },
        threshold=75.0,
    ),
    "custom": ScoringTemplate(
        name="custom",
        weights={
            "annual_return": 0.12,
            "sharpe_ratio": 0.12,
            "max_drawdown": 0.12,
            "win_rate": 0.12,
            "calmar_ratio": 0.12,
            "sortino_ratio": 0.10,
            "profit_factor": 0.10,
            "max_consecutive_losses": 0.10,
            "monthly_consistency": 0.05,
            "r_squared": 0.05,
        },
        threshold=70.0,
    ),
}


def get_template(name: str) -> ScoringTemplate:
    """Get a scoring template by name."""
    if name not in SCORING_TEMPLATES:
        raise ValueError(f"Unknown template: {name}. Available: {list(SCORING_TEMPLATES.keys())}")
    return SCORING_TEMPLATES[name]
