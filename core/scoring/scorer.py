"""Composite scorer: normalize metrics + apply template weights."""
from __future__ import annotations

import math
from typing import Dict

from core.scoring.metrics import compute_metrics
from core.scoring.normalizer import normalize
from core.scoring.templates import get_template, ScoringTemplate


def _compute_trade_factor(metrics: dict) -> float:
    """Sigmoid-based trade count penalty factor (0-1).

    Returns a multiplier close to 1.0 when trade count is sufficient,
    dropping sigmoidally when trades are too few.
    """
    total_bars = metrics.get("total_bars", 0)
    min_trades = max(10, total_bars // 500) if total_bars > 0 else 35
    trade_count = metrics.get("total_trades", 0)
    if trade_count < min_trades:
        midpoint = min_trades - 5
        return 1.0 / (1.0 + math.exp(-0.2 * (trade_count - midpoint)))
    return 1.0


def score_strategy(
    metrics: dict,
    template_name: str = "explorer",
    template: ScoringTemplate | None = None,
    liquidated: bool = False,
    max_drawdown_limit: float | None = None,
    min_annual_return_limit: float | None = None,
) -> Dict:
    """Compute composite score from raw metrics using a scoring template.

    Args:
        metrics: Dict from compute_metrics().
        template_name: Name of scoring template to use.
        template: Override template (takes precedence over name).
        liquidated: Whether the strategy was force-liquidated.
        max_drawdown_limit: Soft constraint on max drawdown (e.g. 0.20 = 20%).
            If actual drawdown exceeds this, score is penalized proportionally.
            None = no soft constraint.
        min_annual_return_limit: Soft constraint on min annual return (e.g. 6.0 = 600%).
            If actual return is below this, score is penalized proportionally.
            None = no soft constraint.

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
            if dim == "trade_count_penalty":
                dimension_scores[dim] = _compute_trade_factor(metrics) * 100
            else:
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

    # Template-level hard constraints: if any dimension fails, score = 0
    if template.hard_constraints:
        for dim, threshold in template.hard_constraints.items():
            raw_val = metrics.get(dim, 0.0)
            if dim == "max_drawdown":
                # For drawdown: raw is negative, threshold is negative
                # Fail if drawdown is worse (more negative) than threshold
                if raw_val < threshold:
                    return {
                        "total_score": 0.0,
                        "dimension_scores": {},
                        "template_name": template.name,
                        "threshold": template.threshold,
                        "raw_metrics": metrics,
                        "liquidated": False,
                        "hard_constraint_failed": dim,
                    }
            else:
                # For other metrics: fail if value is below threshold
                if raw_val < threshold:
                    return {
                        "total_score": 0.0,
                        "dimension_scores": {},
                        "template_name": template.name,
                        "threshold": template.threshold,
                        "raw_metrics": metrics,
                        "liquidated": False,
                        "hard_constraint_failed": dim,
                    }

    # Normalize each dimension
    dimension_scores = {}
    for dim, weight in template.weights.items():
        if dim == "trade_count_penalty":
            # trade_count_penalty is a special dimension: 0-100 score
            # from the sigmoid trade factor
            dimension_scores[dim] = _compute_trade_factor(metrics) * 100
        else:
            raw_val = metrics.get(dim, 0.0)
            dimension_scores[dim] = normalize(dim, raw_val)

    # Weighted sum
    total = sum(
        dimension_scores.get(dim, 0.0) * weight
        for dim, weight in template.weights.items()
    )

    # Soft constraint: drawdown penalty
    if max_drawdown_limit is not None:
        actual_dd = abs(metrics.get("max_drawdown", 0))
        if actual_dd > max_drawdown_limit:
            penalty = max(0.2, max_drawdown_limit / actual_dd)
            total = total * penalty

    # Soft constraint: annual return penalty
    if min_annual_return_limit is not None:
        actual_return = metrics.get("annual_return", 0)
        if actual_return < min_annual_return_limit:
            penalty = max(0.2, actual_return / min_annual_return_limit)
            total = total * penalty

    return {
        "total_score": round(total, 2),
        "dimension_scores": dimension_scores,
        "template_name": template.name,
        "threshold": template.threshold,
        "raw_metrics": metrics,
        "liquidated": False,
    }
