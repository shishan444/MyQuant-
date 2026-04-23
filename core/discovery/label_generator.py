"""Label generator: creates target labels from future price movements.

Generates classification labels (UP/DOWN/FLAT) and regression targets
(future return percentages) for supervised learning.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def generate_labels(
    df: pd.DataFrame,
    horizon: int = 12,
    up_threshold: float = 0.01,
    down_threshold: float = -0.01,
) -> pd.DataFrame:
    """Generate target labels from future price movements.

    Args:
        df: OHLCV DataFrame with DatetimeIndex.
        horizon: Number of bars to look ahead.
        up_threshold: Minimum return to label as UP.
        down_threshold: Maximum return to label as DOWN.

    Returns:
        DataFrame with label columns: direction, future_close_pct,
        future_high_pct, future_low_pct.
    """
    close = df["close"]
    high = df["high"]
    low = df["low"]

    # Future close return
    future_close = close.shift(-horizon)
    future_close_pct = (future_close - close) / close

    # Future max high and min low within horizon
    future_high_pct = pd.Series(np.nan, index=df.index)
    future_low_pct = pd.Series(np.nan, index=df.index)

    for i in range(len(df) - horizon):
        window_high = high.iloc[i + 1: i + 1 + horizon].max()
        window_low = low.iloc[i + 1: i + 1 + horizon].min()
        future_high_pct.iloc[i] = (window_high - close.iloc[i]) / close.iloc[i]
        future_low_pct.iloc[i] = (window_low - close.iloc[i]) / close.iloc[i]

    # Direction classification
    direction = pd.Series("FLAT", index=df.index)
    direction[future_close_pct > up_threshold] = "UP"
    direction[future_close_pct < down_threshold] = "DOWN"

    result = pd.DataFrame({
        "direction": direction,
        "future_close_pct": future_close_pct,
        "future_high_pct": future_high_pct,
        "future_low_pct": future_low_pct,
    }, index=df.index)

    return result
