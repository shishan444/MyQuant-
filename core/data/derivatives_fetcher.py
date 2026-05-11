"""Derivatives data fetcher: Open Interest and Funding Rate from Binance Futures.

Provides fetch_open_interest() and fetch_funding_rate() that mirror the
pagination and proxy patterns in fetcher.py.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import pandas as pd
import requests

logger = logging.getLogger(__name__)

_PROXY_URL = os.environ.get("BINANCE_PROXY", "http://172.20.112.1:10809")
_FUTURES_BASE = "https://fapi.binance.com"
_PAGE_LIMIT = 1000


def _build_session() -> requests.Session:
    """Create a requests.Session with proxy configured."""
    session = requests.Session()
    session.proxies = {"http": _PROXY_URL, "https": _PROXY_URL}
    return session


def _parse_start_ts(start_str: str) -> int:
    """Parse human-readable time string to millisecond timestamp."""
    start_str = start_str.strip()
    # "N day(s) ago UTC"
    lower = start_str.lower()
    if "day" in lower and "ago" in lower:
        parts = start_str.split()
        days = int(parts[0])
        ts = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days)
        return int(ts.timestamp() * 1000)
    if "year" in lower and "ago" in lower:
        parts = start_str.split()
        years = int(parts[0])
        ts = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=years * 365)
        return int(ts.timestamp() * 1000)
    # ISO format or raw ms
    try:
        return int(float(start_str))
    except ValueError:
        ts = pd.Timestamp(start_str, tz="UTC")
        return int(ts.timestamp() * 1000)


def fetch_open_interest(
    symbol: str = "BTCUSDT",
    interval: str = "4h",
    start_str: str = "1 year ago UTC",
    end_str: str | None = None,
) -> pd.DataFrame:
    """Fetch historical open interest from Binance Futures API.

    Args:
        symbol: Trading pair symbol.
        interval: Kline interval (e.g. "4h", "1d").
        start_str: Start time (human-readable or ms timestamp).
        end_str: Optional end time.

    Returns:
        DataFrame with columns [open_interest] and DatetimeIndex.
    """
    session = _build_session()
    start_ms = _parse_start_ts(start_str)
    end_ms = (
        int(pd.Timestamp(end_str, tz="UTC").timestamp() * 1000)
        if end_str
        else int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    )

    all_data = []
    current_start = start_ms

    while current_start < end_ms:
        params = {
            "symbol": symbol,
            "period": interval,
            "startTime": current_start,
            "endTime": end_ms,
            "limit": _PAGE_LIMIT,
        }
        try:
            resp = session.get(
                f"{_FUTURES_BASE}/futures/data/openInterestHist",
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as e:
            logger.warning("OI fetch error at %s: %s", current_start, e)
            break

        if not data:
            break

        all_data.extend(data)
        last_ts = int(data[-1]["timestamp"])
        if last_ts <= current_start:
            break
        current_start = last_ts + 1

        if len(data) < _PAGE_LIMIT:
            break

    if not all_data:
        return pd.DataFrame(columns=["open_interest"])

    df = pd.DataFrame(all_data)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp")
    df = df[["sumOpenInterest"]].rename(columns={"sumOpenInterest": "open_interest"})
    df = df[~df.index.duplicated(keep="first")]
    df = df.sort_index()
    df["open_interest"] = pd.to_numeric(df["open_interest"], errors="coerce")

    return df


def fetch_funding_rate(
    symbol: str = "BTCUSDT",
    start_str: str = "1 year ago UTC",
    end_str: str | None = None,
) -> pd.DataFrame:
    """Fetch historical funding rate from Binance Futures API.

    Funding rate has a fixed 8h interval, so no interval parameter needed.

    Args:
        symbol: Trading pair symbol.
        start_str: Start time (human-readable or ms timestamp).
        end_str: Optional end time.

    Returns:
        DataFrame with columns [funding_rate] and DatetimeIndex.
    """
    session = _build_session()
    start_ms = _parse_start_ts(start_str)
    end_ms = (
        int(pd.Timestamp(end_str, tz="UTC").timestamp() * 1000)
        if end_str
        else int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    )

    all_data = []
    current_start = start_ms

    while current_start < end_ms:
        params = {
            "symbol": symbol,
            "startTime": current_start,
            "endTime": end_ms,
            "limit": _PAGE_LIMIT,
        }
        try:
            resp = session.get(
                f"{_FUTURES_BASE}/fapi/v1/fundingRate",
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as e:
            logger.warning("Funding rate fetch error at %s: %s", current_start, e)
            break

        if not data:
            break

        all_data.extend(data)
        last_ts = int(data[-1]["fundingTime"])
        if last_ts <= current_start:
            break
        current_start = last_ts + 1

        if len(data) < _PAGE_LIMIT:
            break

    if not all_data:
        return pd.DataFrame(columns=["funding_rate"])

    df = pd.DataFrame(all_data)
    df["fundingTime"] = pd.to_datetime(df["fundingTime"], unit="ms", utc=True)
    df = df.set_index("fundingTime")
    df = df[["fundingRate"]].rename(columns={"fundingRate": "funding_rate"})
    df = df[~df.index.duplicated(keep="first")]
    df = df.sort_index()
    df["funding_rate"] = pd.to_numeric(df["funding_rate"], errors="coerce")

    return df
