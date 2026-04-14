"""Incremental data updater for Binance K-line data.

Checks local Parquet files for existing data. If none exists, does a full
fetch. Otherwise, only fetches data after the latest local timestamp and
appends it, removing duplicates.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.data.fetcher import fetch_klines
from core.data.storage import save_parquet, load_parquet, get_latest_timestamp


def update_market_data(
    symbol: str = "BTCUSDT",
    interval: str = "4h",
    data_dir: Path | None = None,
    history_years: int = 2,
    api_key: str = "",
    api_secret: str = "",
) -> pd.DataFrame:
    """Ensure local Parquet is up-to-date, fetching incrementally if needed.

    Args:
        symbol: Trading pair.
        interval: K-line interval.
        data_dir: Directory for Parquet files (default: data/market).
        history_years: Years of history to fetch if no local data.
        api_key: Binance API key.
        api_secret: Binance API secret.

    Returns:
        Complete DataFrame with all available data.
    """
    if data_dir is None:
        data_dir = Path("data/market")
    data_dir = Path(data_dir)

    path = data_dir / f"{symbol}_{interval}.parquet"

    latest_ts = get_latest_timestamp(path)

    if latest_ts is None:
        # Full fetch
        df = fetch_klines(
            symbol=symbol,
            interval=interval,
            start_str=f"{history_years} year ago UTC",
            api_key=api_key,
            api_secret=api_secret,
        )
        save_parquet(df, path)
        return df

    # Incremental fetch: from latest timestamp onward
    start_str = latest_ts.strftime("%Y-%m-%d %H:%M:%S")
    new_df = fetch_klines(
        symbol=symbol,
        interval=interval,
        start_str=start_str,
        api_key=api_key,
        api_secret=api_secret,
    )

    if new_df.empty:
        existing = load_parquet(path)
        return existing

    # Merge: concat, remove duplicates, sort
    existing = load_parquet(path)
    combined = pd.concat([existing, new_df])
    combined = combined[~combined.index.duplicated(keep="last")]
    combined = combined.sort_index()

    save_parquet(combined, path)
    return combined
