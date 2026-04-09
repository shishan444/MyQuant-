"""Parquet storage for K-line data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def save_parquet(df: pd.DataFrame, path: Path) -> None:
    """Save DataFrame to Parquet file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, engine="pyarrow")


def load_parquet(path: Path) -> pd.DataFrame:
    """Load DataFrame from Parquet file."""
    return pd.read_parquet(path, engine="pyarrow")


def get_latest_timestamp(path: Path) -> pd.Timestamp | None:
    """Get the latest timestamp from a Parquet file, or None if not exists."""
    if not path.exists():
        return None
    df = load_parquet(path)
    if df.empty:
        return None
    return df.index.max()
