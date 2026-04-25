"""Divergence detection: price vs RSI/MACD direction mismatch.

Detects bullish and bearish divergences where price makes new extremes
but the indicator does not confirm, signaling potential reversal.
"""

from __future__ import annotations

import pandas as pd

from core.features.patterns.candlestick import (
    detect_bearish_engulfing,
    detect_evening_star,
    detect_three_black_crows,
    detect_shooting_star,
    detect_three_white_soldiers,
    detect_morning_star,
    detect_bullish_reversal,
    detect_bearish_reversal,
)


def detect_bullish_divergence(df: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
    """Bullish divergence: price makes lower low but RSI makes higher low.

    Uses a rolling window to compare local minima of price and RSI.
    """
    result = df.copy()

    rsi_col = None
    for col in df.columns:
        if col.startswith("rsi_"):
            rsi_col = col
            break

    if rsi_col is None:
        result["pattern_bullish_divergence"] = 0
        return result

    price_low = df["low"].rolling(window=lookback, min_periods=lookback).min()
    rsi_val = df[rsi_col]

    price_lower = df["low"] < df["low"].shift(lookback)
    rsi_higher = rsi_val > rsi_val.shift(lookback)
    rsi_oversold = rsi_val < 40

    result["pattern_bullish_divergence"] = (
        price_lower & rsi_higher & rsi_oversold
    ).fillna(0).astype(int)
    return result


def detect_bearish_divergence(df: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
    """Bearish divergence: price makes higher high but RSI makes lower high.

    Uses a rolling window to compare local maxima of price and RSI.
    """
    result = df.copy()

    rsi_col = None
    for col in df.columns:
        if col.startswith("rsi_"):
            rsi_col = col
            break

    if rsi_col is None:
        result["pattern_bearish_divergence"] = 0
        return result

    rsi_val = df[rsi_col]

    price_higher = df["high"] > df["high"].shift(lookback)
    rsi_lower = rsi_val < rsi_val.shift(lookback)
    rsi_overbought = rsi_val > 60

    result["pattern_bearish_divergence"] = (
        price_higher & rsi_lower & rsi_overbought
    ).fillna(0).astype(int)
    return result


# Pattern name to function mapping for easy dispatch
PATTERN_FUNCTIONS = {
    "pattern_bearish_engulfing": detect_bearish_engulfing,
    "pattern_evening_star": detect_evening_star,
    "pattern_3blackcrows": detect_three_black_crows,
    "pattern_shooting_star": detect_shooting_star,
    "pattern_3whitesoldiers": detect_three_white_soldiers,
    "pattern_morning_star": detect_morning_star,
    "pattern_bullish_reversal": detect_bullish_reversal,
    "pattern_bearish_reversal": detect_bearish_reversal,
    "pattern_bullish_divergence": detect_bullish_divergence,
    "pattern_bearish_divergence": detect_bearish_divergence,
}
