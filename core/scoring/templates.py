"""Scoring template definitions."""
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
    "profit_first": ScoringTemplate(
        name="profit_first",
        weights={
            "annual_return": 0.35,
            "sharpe_ratio": 0.25,
            "max_drawdown": 0.25,
            "win_rate": 0.15,
        },
        threshold=75.0,
    ),
    "steady": ScoringTemplate(
        name="steady",
        weights={
            "annual_return": 0.20,
            "sharpe_ratio": 0.35,
            "max_drawdown": 0.35,
            "calmar_ratio": 0.10,
        },
        threshold=80.0,
    ),
    "risk_first": ScoringTemplate(
        name="risk_first",
        weights={
            "annual_return": 0.10,
            "sharpe_ratio": 0.30,
            "max_drawdown": 0.40,
            "calmar_ratio": 0.20,
        },
        threshold=82.0,
    ),
    "custom": ScoringTemplate(
        name="custom",
        weights={
            "annual_return": 0.20,
            "sharpe_ratio": 0.20,
            "max_drawdown": 0.20,
            "win_rate": 0.20,
            "calmar_ratio": 0.20,
        },
        threshold=80.0,
    ),
}


def get_template(name: str) -> ScoringTemplate:
    """Get a scoring template by name."""
    if name not in SCORING_TEMPLATES:
        raise ValueError(f"Unknown template: {name}. Available: {list(SCORING_TEMPLATES.keys())}")
    return SCORING_TEMPLATES[name]
