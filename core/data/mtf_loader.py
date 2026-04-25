"""Multi-timeframe data loading utilities.

Stateless functions shared by the evolution runner and the backtest API.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional, Set

import pandas as pd


# Timeframe aliases for parquet file lookup
_TF_ALIASES: dict[str, list[str]] = {
    "1h": ["1h", "60m"],
    "4h": ["4h"],
    "1d": ["1d", "1D"],
    "15m": ["15m"],
    "5m": ["5m"],
    "1m": ["1m"],
    "30m": ["30m"],
    "3d": ["3d"],
}


def find_parquet(data_dir: Path, safe_symbol: str, timeframe: str) -> Optional[Path]:
    """Find parquet file for symbol+timeframe, trying known aliases."""
    primary = data_dir / f"{safe_symbol}_{timeframe}.parquet"
    if primary.exists():
        return primary

    for alias in _TF_ALIASES.get(timeframe, [timeframe]):
        alt = data_dir / f"{safe_symbol}_{alias}.parquet"
        if alt.exists():
            return alt
    return None


def load_and_prepare_df(
    data_dir: Path,
    symbol: str,
    timeframe: str,
    data_start: Optional[str] = None,
    data_end: Optional[str] = None,
    min_bars: int = 50,
) -> Optional[pd.DataFrame]:
    """Load a single-timeframe parquet, slice by date, and compute all indicators.

    Returns None if data is unavailable or insufficient.
    """
    from core.data.storage import load_parquet
    from core.features.indicators import compute_all_indicators

    safe_symbol = re.sub(r"[^A-Za-z0-9]", "", symbol)
    parquet_path = find_parquet(data_dir, safe_symbol, timeframe)
    if parquet_path is None:
        return None

    df = load_parquet(parquet_path)
    if df is None or len(df) < min_bars:
        return None

    if data_start:
        df = df[df.index >= data_start]
    if data_end:
        df = df[df.index <= data_end]
    if len(df) < min_bars:
        return None

    return compute_all_indicators(df)


def load_mtf_data(
    data_dir: Path,
    symbol: str,
    exec_timeframe: str,
    enhanced_df: pd.DataFrame,
    needed_tfs: Set[str],
    data_start: Optional[str] = None,
    data_end: Optional[str] = None,
) -> Optional[Dict[str, pd.DataFrame]]:
    """Load DataFrames for additional timeframes and compute indicators.

    Returns a dict mapping timeframe -> DataFrame (including exec_timeframe).
    Returns None if no additional timeframes could be loaded.
    """
    from core.data.storage import load_parquet
    from core.features.indicators import compute_all_indicators

    safe_symbol = re.sub(r"[^A-Za-z0-9]", "", symbol)
    dfs_by_timeframe: Dict[str, pd.DataFrame] = {exec_timeframe: enhanced_df}

    for tf in needed_tfs:
        if tf == exec_timeframe:
            continue
        path = find_parquet(data_dir, safe_symbol, tf)
        if path is None:
            continue
        try:
            tf_df = load_parquet(path)
            if tf_df is None or len(tf_df) < 50:
                continue
            if data_start:
                tf_df = tf_df[tf_df.index >= data_start]
            if data_end:
                tf_df = tf_df[tf_df.index <= data_end]
            if len(tf_df) < 50:
                continue
            dfs_by_timeframe[tf] = compute_all_indicators(tf_df)
        except Exception:
            continue

    return dfs_by_timeframe
