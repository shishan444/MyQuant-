"""Binance K-line data fetcher.

Uses Binance public data API (data-api.binance.vision) which is accessible
from restricted regions via proxy, unlike the standard API endpoints.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pandas as pd
import requests

# Default proxy for Binance API access (override via BINANCE_PROXY env var)
_DEFAULT_PROXY = os.environ.get("BINANCE_PROXY", "http://172.20.112.1:10809")

# Public data API - accessible from all regions
_BASE_URL = os.environ.get("BINANCE_DATA_API_URL", "https://data-api.binance.vision")

# Maximum rows per request (Binance limit)
_PAGE_LIMIT = 1000


def _parse_start_ts(start_str: str) -> int:
    """Convert a human-readable start string to milliseconds timestamp."""
    mapping = {
        "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
        "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600,
        "8h": 28800, "12h": 43200, "1d": 86400, "3d": 259200, "1w": 604800,
    }
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    # Handle "N year(s) ago UTC" pattern
    lower = start_str.lower().strip()
    for unit, label in [("year", "year"), ("years", "year")]:
        if f"{unit} ago" in lower:
            parts = lower.split()
            n = int(parts[0])
            dt = datetime.now(timezone.utc)
            dt = dt.replace(year=dt.year - n)
            return int(dt.timestamp() * 1000)

    # Handle "N day(s) ago" pattern
    for unit in ["day", "days"]:
        if f"{unit} ago" in lower:
            parts = lower.split()
            n = int(parts[0])
            return now_ms - n * 86400 * 1000

    # Try ISO format
    try:
        dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except (ValueError, AttributeError):
        pass

    # Try direct millisecond timestamp
    try:
        return int(start_str)
    except (ValueError, TypeError):
        pass

    # Fallback: 2 years ago
    dt = datetime.now(timezone.utc)
    dt = dt.replace(year=dt.year - 2)
    return int(dt.timestamp() * 1000)


def _build_session() -> requests.Session:
    """Create a requests session with proxy configured."""
    session = requests.Session()
    if _DEFAULT_PROXY:
        session.proxies = {
            "http": _DEFAULT_PROXY,
            "https": _DEFAULT_PROXY,
        }
    return session


def fetch_klines(
    symbol: str = "BTCUSDT",
    interval: str = "4h",
    start_str: str = "2 year ago UTC",
    end_str: str | None = None,
    api_key: str = "",
    api_secret: str = "",
) -> pd.DataFrame:
    """Fetch historical K-line data from Binance public data API.

    Args:
        symbol: Trading pair (e.g. "BTCUSDT").
        interval: K-line interval ("1m", "5m", "15m", "1h", "4h", "1d").
        start_str: Start time string.
        end_str: End time string (None = now).
        api_key: Unused, kept for API compatibility.
        api_secret: Unused, kept for API compatibility.

    Returns:
        DataFrame with columns: open, high, low, close, volume, trades.
        DatetimeIndex in UTC.
    """
    start_ms = _parse_start_ts(start_str)
    end_ms = (
        int(datetime.now(timezone.utc).timestamp() * 1000)
        if end_str is None
        else _parse_start_ts(end_str)
    )

    session = _build_session()
    all_klines: list[list] = []

    # Paginate through the data
    current_start = start_ms
    while current_start < end_ms:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current_start,
            "endTime": end_ms,
            "limit": _PAGE_LIMIT,
        }
        resp = session.get(f"{_BASE_URL}/api/v3/klines", params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if not data:
            break

        all_klines.extend(data)

        # Move start to after the last candle
        last_open_time = data[-1][0]
        if last_open_time <= current_start:
            break
        current_start = last_open_time + 1

        # If we got fewer than limit, we've reached the end
        if len(data) < _PAGE_LIMIT:
            break

    if not all_klines:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume", "trades"])

    df = pd.DataFrame(all_klines, columns=[
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
