"""Composite scorer: normalize metrics + apply template weights."""
from __future__ import annotations

from typing import Dict

from MyQuant.core.scoring.metrics import compute_metrics
from MyQuant.core.scoring.normalizer import normalize
from MyQuant.core.scoring.templates import get_template, ScoringTemplate


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

    return {
        "total_score": round(total, 2),
        "dimension_scores": dimension_scores,
        "template_name": template.name,
        "threshold": template.threshold,
        "raw_metrics": metrics,
    }
