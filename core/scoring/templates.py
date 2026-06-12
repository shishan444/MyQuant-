"""DEPRECATED: Scoring templates are replaced by RequirementsConfig.

This module exists solely for backward compatibility with code that imports
from core.scoring.templates. All new code should use RequirementsConfig
from core.scoring.scorer instead.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ScoringTemplate:
    """Legacy scoring template stub for backward compatibility."""
    name: str
    weights: Dict[str, float]
    threshold: float
    hard_constraints: Optional[Dict[str, float]] = None


SCORING_TEMPLATES: Dict[str, ScoringTemplate] = {
    "explorer": ScoringTemplate(
        name="explorer",
        weights={"annual_return": 0.25, "alpha": 0.15, "sharpe_ratio": 0.20,
                 "profit_factor": 0.15, "max_drawdown": 0.10,
                 "monthly_consistency": 0.10, "trade_count_penalty": 0.05},
        threshold=50.0,
    ),
    "optimizer": ScoringTemplate(
        name="optimizer",
        weights={"sharpe_ratio": 0.25, "annual_return": 0.15, "alpha": 0.10,
                 "monthly_consistency": 0.20, "profit_factor": 0.10,
                 "max_drawdown": 0.15, "trade_count_penalty": 0.05},
        threshold=65.0,
        hard_constraints={"annual_return": 0.10, "max_drawdown": -0.60},
    ),
    "max_return": ScoringTemplate(
        name="max_return",
        weights={"annual_return": 0.40, "alpha": 0.15, "profit_factor": 0.20,
                 "sharpe_ratio": 0.15, "trade_count_penalty": 0.10},
        threshold=40.0,
    ),
}

_TEMPLATE_ALIASES: Dict[str, str] = {
    "balanced": "optimizer", "steady": "optimizer", "custom": "optimizer",
    "aggressive": "explorer", "profit_first": "explorer",
    "conservative": "optimizer", "risk_first": "optimizer",
}


def get_template(name: str) -> ScoringTemplate:
    resolved = _TEMPLATE_ALIASES.get(name, name)
    if resolved not in SCORING_TEMPLATES:
        raise ValueError(f"Unknown template: {name}. Available: {list(SCORING_TEMPLATES.keys())}")
    return SCORING_TEMPLATES[resolved]


def list_template_names() -> list[str]:
    return list(SCORING_TEMPLATES.keys()) + list(_TEMPLATE_ALIASES.keys())
