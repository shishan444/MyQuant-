"""Pivot point detection: identify local peaks and troughs in price data."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd


@dataclass
class PivotPoint:
    """A single pivot point (local peak or trough)."""

    index: int          # bar position in DataFrame
    price: float        # high for peak, low for trough
    pivot_type: str     # "peak" or "trough"
    volume: float = 0.0 # volume at this bar


def detect_pivots(
    df: pd.DataFrame,
    bars_left: int = 6,
    bars_right: int = 6,
) -> List[PivotPoint]:
    """Detect pivot points using a rolling-window approach.

    A bar is a *peak* if its high is the maximum in the surrounding window
    [i - bars_left .. i + bars_right].  A bar is a *trough* if its low is
    the minimum in the same window.

    Args:
        df: DataFrame with at least ``high`` and ``low`` columns.
        bars_left: Number of bars to the left of the candidate.
        bars_right: Number of bars to the right of the candidate.

    Returns:
        Chronologically ordered list of PivotPoint instances.
    """
    highs = df["high"].values.astype(np.float64)
    lows = df["low"].values.astype(np.float64)
    volumes = df["volume"].values.astype(np.float64) if "volume" in df.columns else np.zeros(len(df))
    n = len(df)
    window = bars_left + bars_right + 1

    if n < window:
        return []

    pivots: List[PivotPoint] = []

    for i in range(bars_left, n - bars_right):
        left = i - bars_left
        right = i + bars_right + 1

        # Peak: center high is the window maximum
        h_window = highs[left:right]
        if highs[i] == np.max(h_window) and np.sum(h_window == highs[i]) == 1:
            pivots.append(PivotPoint(
                index=i, price=float(highs[i]),
                pivot_type="peak", volume=float(volumes[i]),
            ))

        # Trough: center low is the window minimum
        l_window = lows[left:right]
        if lows[i] == np.min(l_window) and np.sum(l_window == lows[i]) == 1:
            pivots.append(PivotPoint(
                index=i, price=float(lows[i]),
                pivot_type="trough", volume=float(volumes[i]),
            ))

    # Sort chronologically
    pivots.sort(key=lambda p: p.index)
    return pivots
