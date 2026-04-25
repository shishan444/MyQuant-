"""Candlestick pattern detection functions.

Each function takes a DataFrame with OHLCV columns and returns the same
DataFrame with a new boolean column (0/1) indicating pattern presence.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def detect_bearish_engulfing(df: pd.DataFrame) -> pd.DataFrame:
    """Bearish engulfing: prior bullish candle fully engulfed by bearish candle."""
    result = df.copy()
    prev_close = df["close"].shift(1)
    prev_open = df["open"].shift(1)
    prev_bullish = prev_close > prev_open
    curr_bearish = df["close"] < df["open"]
    engulfing = (df["open"] >= prev_close) & (df["close"] <= prev_open)
    result["pattern_bearish_engulfing"] = (prev_bullish & curr_bearish & engulfing).astype(int)
    return result


def detect_evening_star(df: pd.DataFrame) -> pd.DataFrame:
    """Evening star: bullish candle + small body + bearish candle."""
    result = df.copy()
    prev_body = (df["close"].shift(2) - df["open"].shift(2)).abs()
    prev_bullish = df["close"].shift(2) > df["open"].shift(2)
    mid_body = (df["close"].shift(1) - df["open"].shift(1)).abs()
    curr_bearish = df["close"] < df["open"]
    curr_body = (df["close"] - df["open"]).abs()
    result["pattern_evening_star"] = (
        prev_bullish
        & (mid_body < prev_body * 0.5)
        & curr_bearish
        & (curr_body > mid_body)
        & (df["close"] < (df["close"].shift(2) + df["open"].shift(2)) / 2)
    ).fillna(0).astype(int)
    return result


def detect_three_black_crows(df: pd.DataFrame) -> pd.DataFrame:
    """Three black crows: three consecutive bearish candles, each closing lower."""
    result = df.copy()
    bearish = df["close"] < df["open"]
    lower_close = df["close"] < df["close"].shift(1)
    open_within_body = df["open"] < df["open"].shift(1)
    result["pattern_3blackcrows"] = (
        bearish & bearish.shift(1) & bearish.shift(2)
        & lower_close & lower_close.shift(1)
        & open_within_body & open_within_body.shift(1)
    ).fillna(0).astype(int)
    return result


def detect_shooting_star(df: pd.DataFrame) -> pd.DataFrame:
    """Shooting star: small body at bottom, long upper shadow, after uptrend."""
    result = df.copy()
    body = (df["close"] - df["open"]).abs()
    upper_shadow = df["high"] - df[["close", "open"]].max(axis=1)
    lower_shadow = df[["close", "open"]].min(axis=1) - df["low"]
    uptrend = df["close"].shift(1) > df["close"].shift(4)
    result["pattern_shooting_star"] = (
        (upper_shadow > body * 2)
        & (lower_shadow < body * 0.5)
        & (body > 0)
        & uptrend
    ).fillna(0).astype(int)
    return result


def detect_three_white_soldiers(df: pd.DataFrame) -> pd.DataFrame:
    """Three white soldiers: three consecutive bullish candles, each closing higher."""
    result = df.copy()
    bullish = df["close"] > df["open"]
    higher_close = df["close"] > df["close"].shift(1)
    open_within_body = df["open"] > df["open"].shift(1)
    result["pattern_3whitesoldiers"] = (
        bullish & bullish.shift(1) & bullish.shift(2)
        & higher_close & higher_close.shift(1)
        & open_within_body & open_within_body.shift(1)
    ).fillna(0).astype(int)
    return result


def detect_morning_star(df: pd.DataFrame) -> pd.DataFrame:
    """Morning star: bearish candle + small body + bullish candle."""
    result = df.copy()
    prev_body = (df["close"].shift(2) - df["open"].shift(2)).abs()
    prev_bearish = df["close"].shift(2) < df["open"].shift(2)
    mid_body = (df["close"].shift(1) - df["open"].shift(1)).abs()
    curr_bullish = df["close"] > df["open"]
    curr_body = (df["close"] - df["open"]).abs()
    result["pattern_morning_star"] = (
        prev_bearish
        & (mid_body < prev_body * 0.5)
        & curr_bullish
        & (curr_body > mid_body)
        & (df["close"] > (df["close"].shift(2) + df["open"].shift(2)) / 2)
    ).fillna(0).astype(int)
    return result


def detect_bullish_reversal(df: pd.DataFrame) -> pd.DataFrame:
    """Bullish reversal (yang reversal): bearish candle followed by bullish engulfing."""
    result = df.copy()
    prev_bearish = df["close"].shift(1) < df["open"].shift(1)
    curr_bullish = df["close"] > df["open"]
    lower_low = df["low"] < df["low"].shift(1)
    strong_body = (df["close"] - df["open"]) > (df["open"].shift(1) - df["close"].shift(1)).abs()
    result["pattern_bullish_reversal"] = (
        prev_bearish & curr_bullish & lower_low & strong_body
    ).fillna(0).astype(int)
    return result


def detect_bearish_reversal(df: pd.DataFrame) -> pd.DataFrame:
    """Bearish reversal (yin reversal): bullish candle followed by bearish engulfing."""
    result = df.copy()
    prev_bullish = df["close"].shift(1) > df["open"].shift(1)
    curr_bearish = df["close"] < df["open"]
    higher_high = df["high"] > df["high"].shift(1)
    strong_body = (df["open"] - df["close"]) > (df["close"].shift(1) - df["open"].shift(1)).abs()
    result["pattern_bearish_reversal"] = (
        prev_bullish & curr_bearish & higher_high & strong_body
    ).fillna(0).astype(int)
    return result
