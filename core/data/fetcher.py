"""Binance K-line data fetcher."""

from __future__ import annotations

import pandas as pd
from binance.client import Client


def fetch_klines(
    symbol: str = "BTCUSDT",
    interval: str = "4h",
    start_str: str = "2 year ago UTC",
    end_str: str | None = None,
    api_key: str = "",
    api_secret: str = "",
) -> pd.DataFrame:
    """Fetch historical K-line data from Binance.

    Args:
        symbol: Trading pair (e.g. "BTCUSDT").
        interval: K-line interval ("1h", "4h", "1d").
        start_str: Start time string.
        end_str: End time string (None = now).
        api_key: Binance API key (public endpoints work without it).
        api_secret: Binance API secret.

    Returns:
        DataFrame with columns: open, high, low, close, volume.
        DatetimeIndex in UTC.
    """
    client = Client(api_key, api_secret)

    kwargs = {
        "symbol": symbol,
        "interval": interval,
        "start_str": start_str,
    }
    if end_str:
        kwargs["end_str"] = end_str

    klines = client.get_historical_klines(**kwargs)

    df = pd.DataFrame(klines, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore",
    ])

    # Keep only needed columns
    df = df[["timestamp", "open", "high", "low", "close", "volume", "trades"]]

    # Convert types
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df["trades"] = df["trades"].astype(int)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp")

    # Remove duplicates
    df = df[~df.index.duplicated(keep="first")]

    return df
