"""Composite scorer: normalize metrics + apply template weights."""
from __future__ import annotations

import math
from typing import Dict

from core.scoring.metrics import compute_metrics
from core.scoring.normalizer import normalize
from core.scoring.templates import get_template, ScoringTemplate

# Drawdown penalty thresholds
_DRAWDOWN_PENALTY_THRESHOLD = 0.50
_DRAWDOWN_FATAL = 0.90


def score_strategy(
    metrics: dict,
    template_name: str = "profit_first",
    template: ScoringTemplate | None = None,
    liquidated: bool = False,
) -> Dict:
    """Compute composite score from raw metrics using a scoring template.

    Args:
        metrics: Dict from compute_metrics().
        template_name: Name of scoring template to use.
        template: Override template (takes precedence over name).
        liquidated: Whether the strategy was force-liquidated.

    Returns:
        Dict with total_score (0-100), dimension_scores, template_name, threshold.
    """
    if template is None:
        template = get_template(template_name)

    # Zero trades = zero score
    if metrics.get("total_trades", 0) == 0:
        return {
            "total_score": 0.0,
            "dimension_scores": {},
            "template_name": template.name,
            "threshold": template.threshold,
            "raw_metrics": metrics,
            "liquidated": liquidated,
        }

    # Hard constraint: liquidated strategies get zero score
    if liquidated:
        dimension_scores = {}
        for dim in template.weights:
            raw_val = metrics.get(dim, 0.0)
            dimension_scores[dim] = normalize(dim, raw_val)
        return {
            "total_score": 0.0,
            "dimension_scores": dimension_scores,
            "template_name": template.name,
            "threshold": template.threshold,
            "raw_metrics": metrics,
            "liquidated": True,
        }

    # Normalize each dimension
    dimension_scores = {}
    for dim, weight in template.weights.items():
        raw_val = metrics.get(dim, 0.0)
        dimension_scores[dim] = normalize(dim, raw_val)

    # Weighted sum
    total = sum(
        dimension_scores.get(dim, 0.0) * weight
        for dim, weight in template.weights.items()
    )

    # Near-liquidation gradient penalty: heavy drawdown reduces score
    max_dd = abs(metrics.get("max_drawdown", 0.0))
    if max_dd >= _DRAWDOWN_FATAL:
        total *= 0.05
    elif max_dd >= _DRAWDOWN_PENALTY_THRESHOLD:
        penalty_ratio = (max_dd - _DRAWDOWN_PENALTY_THRESHOLD) / (_DRAWDOWN_FATAL - _DRAWDOWN_PENALTY_THRESHOLD)
        total *= (1.0 - 0.95 * penalty_ratio)

    # Trade count penalty: Sigmoid-based penalty for low trade count
    MIN_TRADES_THRESHOLD = 35
    trade_count = metrics.get("total_trades", 0)
    if trade_count < MIN_TRADES_THRESHOLD:
        trade_factor = 1.0 / (1.0 + math.exp(-0.2 * (trade_count - 30)))
    else:
        trade_factor = 1.0
    total *= trade_factor

    return {
        "total_score": round(total, 2),
        "dimension_scores": dimension_scores,
        "template_name": template.name,
        "threshold": template.threshold,
        "raw_metrics": metrics,
        "liquidated": False,
    }
