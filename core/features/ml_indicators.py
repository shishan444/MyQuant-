"""ML-based indicators: FractalEntropy and MultifactorOsc.

Lazy-computed indicators using statistical learning techniques.
These require more computation than standard indicators and are
only calculated when explicitly requested (skip_lazy=False).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def compute_fractal_entropy(
    close: pd.Series,
    bins: int = 10,
    lookback: int = 100,
) -> pd.Series:
    """Compute normalized Shannon entropy of discretized returns.

    Rolling window entropy measures market complexity/randomness.
    Low entropy indicates a trending regime; high entropy indicates random walk.

    Args:
        close: Close price series.
        bins: Number of bins for return distribution discretization.
        lookback: Rolling window size.

    Returns:
        Series with values in [0, 1], NaN during warmup period.
    """
    returns = close.pct_change()
    values = returns.values
    n = len(close)
    result = np.full(n, np.nan)
    max_entropy = np.log2(bins) if bins > 1 else 1.0

    for i in range(lookback - 1, n):
        window = values[i - lookback + 1: i + 1]
        window = window[~np.isnan(window)]
        if len(window) < 10:
            continue
        hist, _ = np.histogram(window, bins=bins)
        prob = hist / hist.sum()
        prob = prob[prob > 0]
        entropy = -np.sum(prob * np.log2(prob))
        result[i] = entropy / max_entropy

    return pd.Series(result, index=close.index)


def compute_multifactor_osc(
    df: pd.DataFrame,
    lookback: int = 20,
) -> pd.Series:
    """Compute adaptive multi-factor oscillator.

    Combines normalized RSI, CCI, MFI, and Stochastic K with rolling
    prediction accuracy weighting. Indicators with better recent
    directional accuracy receive higher weights.

    Args:
        df: OHLCV DataFrame with pre-computed indicator columns.
        lookback: Rolling window for accuracy estimation.

    Returns:
        Series with values in [-1, 1], NaN if insufficient sub-indicators.
    """
    # Sub-indicator column -> (type, center_value for normalization)
    sub_indicators = {
        "rsi_14": ("bounded", 50, 50),
        "cci_20": ("cci", 0, 200),
        "mfi_14": ("bounded", 50, 50),
        "stoch_k_14_3": ("bounded", 50, 50),
    }

    available = {
        col: info for col, info in sub_indicators.items()
        if col in df.columns
    }
    if len(available) < 2:
        return pd.Series(np.nan, index=df.index)

    # Normalize each sub-indicator to [-1, 1]
    normalized = {}
    for col, (itype, center, scale) in available.items():
        if itype == "cci":
            normalized[col] = df[col].clip(-scale, scale) / scale
        else:
            normalized[col] = (df[col] - center) / scale

    # Compute rolling prediction accuracy (no lookahead)
    actual_dir = np.sign(df["close"].pct_change())

    weighted_sum = pd.Series(0.0, index=df.index)
    total_weight = pd.Series(0.0, index=df.index)

    for col in available:
        signal_dir = np.sign(normalized[col].shift(1))
        correct = (signal_dir == actual_dir).astype(float)
        accuracy = correct.rolling(lookback, min_periods=5).mean().fillna(0)
        weighted_sum += normalized[col].fillna(0) * accuracy
        total_weight += accuracy

    osc = weighted_sum / total_weight.replace(0, 1)

    return pd.Series(osc.clip(-1, 1).values, index=df.index)
