"""Pattern detection algorithms for validation engine."""
from __future__ import annotations

import numpy as np
import pandas as pd


def detect_divergence_top(
    df: pd.DataFrame,
    subject_col: str,
    price_col: str = "close",
    lookback: int = 20,
) -> pd.Series:
    """Detect bearish (top) divergence.

    Price creates a new high but the indicator does not.
    Compares the two most recent local extrema within *lookback* bars.
    """
    if subject_col not in df.columns or price_col not in df.columns:
        return pd.Series(False, index=df.index)

    result = pd.Series(False, index=df.index)
    price = df[price_col].values
    subject = df[subject_col].values

    for i in range(lookback, len(df)):
        window_price = price[i - lookback : i + 1]
        window_subject = subject[i - lookback : i + 1]

        # Find local maxima positions
        peaks_price = _find_local_maxima(window_price)
        if len(peaks_price) < 2:
            continue

        # Take the two most recent peaks
        p1, p2 = peaks_price[-2], peaks_price[-1]
        # Price made higher high, subject made lower high
        if window_price[p2] > window_price[p1] and window_subject[p2] < window_subject[p1]:
            result.iloc[i] = True

    return result


def detect_divergence_bottom(
    df: pd.DataFrame,
    subject_col: str,
    price_col: str = "close",
    lookback: int = 20,
) -> pd.Series:
    """Detect bullish (bottom) divergence.

    Price creates a new low but the indicator does not.
    """
    if subject_col not in df.columns or price_col not in df.columns:
        return pd.Series(False, index=df.index)

    result = pd.Series(False, index=df.index)
    price = df[price_col].values
    subject = df[subject_col].values

    for i in range(lookback, len(df)):
        window_price = price[i - lookback : i + 1]
        window_subject = subject[i - lookback : i + 1]

        # Find local minima positions
        troughs_price = _find_local_minima(window_price)
        if len(troughs_price) < 2:
            continue

        t1, t2 = troughs_price[-2], troughs_price[-1]
        # Price made lower low, subject made higher low
        if window_price[t2] < window_price[t1] and window_subject[t2] > window_subject[t1]:
            result.iloc[i] = True

    return result


def detect_consecutive_up(
    df: pd.DataFrame,
    subject_col: str,
    count: int = 3,
) -> pd.Series:
    """Detect consecutive rising bars in subject column."""
    if subject_col not in df.columns:
        return pd.Series(False, index=df.index)

    series = df[subject_col]
    result = pd.Series(False, index=df.index)

    # Check if each of the last `count` values is strictly increasing
    for i in range(count, len(df)):
        window = series.iloc[i - count : i + 1].values
        if _is_strictly_increasing(window):
            result.iloc[i] = True

    return result


def detect_consecutive_down(
    df: pd.DataFrame,
    subject_col: str,
    count: int = 3,
) -> pd.Series:
    """Detect consecutive falling bars in subject column."""
    if subject_col not in df.columns:
        return pd.Series(False, index=df.index)

    series = df[subject_col]
    result = pd.Series(False, index=df.index)

    for i in range(count, len(df)):
        window = series.iloc[i - count : i + 1].values
        if _is_strictly_decreasing(window):
            result.iloc[i] = True

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_local_maxima(arr: np.ndarray) -> list:
    """Find indices of local maxima in an array."""
    peaks = []
    for i in range(1, len(arr) - 1):
        if arr[i] > arr[i - 1] and arr[i] > arr[i + 1]:
            peaks.append(i)
    # Include endpoints if they are higher than neighbors
    if len(arr) > 1 and arr[0] > arr[1]:
        peaks.insert(0, 0)
    if len(arr) > 1 and arr[-1] > arr[-2]:
        peaks.append(len(arr) - 1)
    return peaks


def _find_local_minima(arr: np.ndarray) -> list:
    """Find indices of local minima in an array."""
    troughs = []
    for i in range(1, len(arr) - 1):
        if arr[i] < arr[i - 1] and arr[i] < arr[i + 1]:
            troughs.append(i)
    if len(arr) > 1 and arr[0] < arr[1]:
        troughs.insert(0, 0)
    if len(arr) > 1 and arr[-1] < arr[-2]:
        troughs.append(len(arr) - 1)
    return troughs


def _is_strictly_increasing(arr: np.ndarray) -> bool:
    """Check if array values are strictly increasing."""
    for i in range(1, len(arr)):
        if np.isnan(arr[i]) or np.isnan(arr[i - 1]):
            return False
        if arr[i] <= arr[i - 1]:
            return False
    return True


def _is_strictly_decreasing(arr: np.ndarray) -> bool:
    """Check if array values are strictly decreasing."""
    for i in range(1, len(arr)):
        if np.isnan(arr[i]) or np.isnan(arr[i - 1]):
            return False
        if arr[i] >= arr[i - 1]:
            return False
    return True
