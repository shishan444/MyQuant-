"""Composite scorer: normalize metrics + apply template weights."""
from __future__ import annotations

from typing import Dict

from core.scoring.metrics import compute_metrics
from core.scoring.normalizer import normalize
from core.scoring.templates import get_template, ScoringTemplate


def score_strategy(
    metrics: dict,
    template_name: str = "profit_first",
    template: ScoringTemplate | None = None,
) -> Dict:
    """Compute composite score from raw metrics using a scoring template.

    Args:
        metrics: Dict from compute_metrics().
        template_name: Name of scoring template to use.
        template: Override template (takes precedence over name).

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

    # Trade count penalty: Sigmoid-based penalty for low trade count
    # Smooth transition instead of harsh linear cutoff
    MIN_TRADES_THRESHOLD = 10
    trade_count = metrics.get("total_trades", 0)
    if trade_count < MIN_TRADES_THRESHOLD:
        # Sigmoid: k=0.5 controls steepness, x0=5 is midpoint
        # At 0 trades: ~0.07, at 5 trades: ~0.50, at 10 trades: ~0.93
        import math
        trade_factor = 1.0 / (1.0 + math.exp(-0.5 * (trade_count - 5)))
    else:
        trade_factor = 1.0
    total *= trade_factor

    return {
        "total_score": round(total, 2),
        "dimension_scores": dimension_scores,
        "template_name": template.name,
        "threshold": template.threshold,
        "raw_metrics": metrics,
    }
