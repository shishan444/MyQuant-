"""Scoring template definitions.

Three differentiated templates use 5 core dimensions:
- annual_return, sharpe_ratio, max_drawdown, profit_factor, monthly_consistency

Legacy template names are automatically mapped to the new templates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class ScoringTemplate:
    """A scoring template with dimension weights, threshold, and optional hard constraints."""
    name: str
    weights: Dict[str, float]
    threshold: float
    hard_constraints: Optional[Dict[str, float]] = None


SCORING_TEMPLATES: Dict[str, ScoringTemplate] = {
    # -- Core templates --
    "explorer": ScoringTemplate(
        name="explorer",
        weights={
            "annual_return": 0.25,
            "alpha": 0.15,
            "sharpe_ratio": 0.20,
            "profit_factor": 0.15,
            "max_drawdown": 0.10,
            "monthly_consistency": 0.10,
            "trade_count_penalty": 0.05,
        },
        threshold=50.0,
    ),
    "optimizer": ScoringTemplate(
        name="optimizer",
        weights={
            "sharpe_ratio": 0.25,
            "annual_return": 0.15,
            "alpha": 0.10,
            "monthly_consistency": 0.20,
            "profit_factor": 0.10,
            "max_drawdown": 0.15,
            "trade_count_penalty": 0.05,
        },
        threshold=65.0,
        hard_constraints={
            "annual_return": 0.10,   # annual return < 10% -> zero score
            "max_drawdown": -0.60,   # drawdown > 60% -> zero score
        },
    ),
    "max_return": ScoringTemplate(
        name="max_return",
        weights={
            "annual_return": 0.40,
            "alpha": 0.15,
            "profit_factor": 0.20,
            "sharpe_ratio": 0.15,
            "trade_count_penalty": 0.10,
        },
        threshold=40.0,
    ),
}

# Legacy template name -> new template name mapping
_TEMPLATE_ALIASES: Dict[str, str] = {
    "balanced": "optimizer",
    "steady": "optimizer",
    "custom": "optimizer",
    "aggressive": "explorer",
    "profit_first": "explorer",
    "conservative": "optimizer",
    "risk_first": "optimizer",
}


def get_template(name: str) -> ScoringTemplate:
    """Get a scoring template by name (supports aliases)."""
    # Resolve alias
    resolved = _TEMPLATE_ALIASES.get(name, name)
    if resolved not in SCORING_TEMPLATES:
        raise ValueError(
            f"Unknown template: {name}. Available: {list(SCORING_TEMPLATES.keys())}"
        )
    return SCORING_TEMPLATES[resolved]


def list_template_names() -> list[str]:
    """Return all valid template names (core + aliases)."""
    return list(SCORING_TEMPLATES.keys()) + list(_TEMPLATE_ALIASES.keys())
