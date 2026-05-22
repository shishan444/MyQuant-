"""Order generator: combines trading signals with price predictions to produce orders.

Pure function module: (BarSignals, PredictionResult, AccountState, JudgmentConfig) -> Order | None.
No side effects, no state.
"""
from __future__ import annotations

import uuid

from scipy.stats import norm

from core.trading.types import (
    AccountState,
    BarSignals,
    JudgmentConfig,
    Order,
)


def compute_order_price(
    prediction_low: float,
    prediction_high: float,
    prediction_width: float,
    direction: float,
    confidence: float,
    config: JudgmentConfig,
) -> tuple[float, float]:
    """Compute optimal limit order price within predicted range.

    Uses a parametric offset from mid-price based on confidence:
      alpha_factor = base + range * confidence
      long:  price = mid - alpha * sigma  (clamp to [low, mid])
      short: price = mid + alpha * sigma  (clamp to [mid, high])

    Returns (order_price, fill_probability).
    """
    mu = (prediction_low + prediction_high) / 2
    sigma = prediction_width

    if sigma <= 0:
        return mu, 0.5

    alpha = config.pricing_alpha_base + config.pricing_alpha_range * confidence

    if direction > 0:  # long
        price = mu - alpha * sigma
        price = max(prediction_low, min(price, mu))
    else:  # short
        price = mu + alpha * sigma
        price = min(prediction_high, max(price, mu))

    # Fill probability estimate using normal CDF
    z = (price - mu) / sigma
    if direction > 0:
        p_fill = norm.cdf(z)
    else:
        p_fill = 1 - norm.cdf(z)

    return price, p_fill


def generate_order(
    signals: BarSignals,
    prediction: object | None,
    state: AccountState,
    config: JudgmentConfig,
    bar_idx: int = 0,
    source: str = "entry",
) -> Order | None:
    """Generate a limit order from signal + prediction.

    Rules:
      - signals.entry must be True
      - direction must be determinable (+1 or -1)
      - direction must match allowed_direction
      - if prediction available: compute limit price with fill probability check
      - if prediction unavailable: fallback to market order
      - size scaled by confidence if confidence_sizing_enabled
    """
    if not signals.entry:
        return None

    direction = "long" if signals.direction > 0 else "short" if signals.direction < 0 else None
    if direction is None:
        return None

    # Direction filter
    if state.allowed_direction != "mixed" and direction != state.allowed_direction:
        return None

    # Position size
    target_pct = state.target_position_pct if state.target_position_pct > 0 else 0.30
    entry_pct = target_pct * config.initial_entry_pct
    if config.confidence_sizing_enabled:
        entry_pct *= max(signals.confidence, 0.1)

    # Price calculation
    if prediction is not None and hasattr(prediction, "low") and prediction.width > 0:
        price, p_fill = compute_order_price(
            prediction_low=prediction.low,
            prediction_high=prediction.high,
            prediction_width=prediction.width,
            direction=signals.direction,
            confidence=signals.confidence,
            config=config,
        )

        if p_fill < config.pricing_min_fill_prob:
            # Fill probability too low -- fallback to market
            price = 0.0
            p_fill = 1.0
            order_type = "market"
        else:
            order_type = "limit"
    else:
        price = 0.0
        p_fill = 1.0
        order_type = "market"

    predicted_range = (
        (prediction.low, prediction.high)
        if prediction is not None and hasattr(prediction, "low")
        else (0.0, 0.0)
    )

    return Order(
        order_id=uuid.uuid4().hex[:12],
        created_at_bar=bar_idx,
        side=direction,
        price=price,
        size_pct=entry_pct,
        source=source,
        order_type=order_type,
        predicted_range=predicted_range,
        fill_probability=p_fill,
    )
