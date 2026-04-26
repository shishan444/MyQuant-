"""Tests for fetch_klines (core/data/fetcher.py)."""

import pytest

pytestmark = [pytest.mark.unit]

from unittest.mock import patch, MagicMock

import pandas as pd

from core.data.fetcher import fetch_klines


def _make_kline_rows(n: int = 5, base_ts: int = 1700000000000) -> list[list]:
    """Build *n* fake Binance kline rows (12-element lists).

    Each row: [timestamp_ms, open, high, low, close, volume,
               close_time, quote_volume, trades,
               taker_buy_base, taker_buy_quote, ignore]
    """
    rows = []
    for i in range(n):
        ts = base_ts + i * 3600_000  # 1 h apart
        price = 40000.0 + i * 100
        rows.append([
            ts,
            str(price),
            str(price + 50),
            str(price - 50),
            str(price + 25),
            "1234.5",
            ts + 3599_999,
            "50000.0",
            500,
            "600.0",
            "24000.0",
            "0",
        ])
    return rows


class TestFetchKlinesReturnsDataframe:
    """fetch_klines returns a properly structured DataFrame."""

    @patch("core.data.fetcher.Client")
    def test_returns_dataframe(self, mock_client_cls: MagicMock) -> None:
        mock_instance = MagicMock()
        mock_instance.get_historical_klines.return_value = _make_kline_rows(3)
        mock_client_cls.return_value = mock_instance

        df = fetch_klines(symbol="BTCUSDT", interval="4h")

        assert isinstance(df, pd.DataFrame)
        expected_cols = ["open", "high", "low", "close", "volume", "trades"]
        assert list(df.columns) == expected_cols

    @patch("core.data.fetcher.Client")
    def test_column_types(self, mock_client_cls: MagicMock) -> None:
        mock_instance = MagicMock()
        mock_instance.get_historical_klines.return_value = _make_kline_rows(2)
        mock_client_cls.return_value = mock_instance

        df = fetch_klines()

        for col in ["open", "high", "low", "close", "volume"]:
            assert df[col].dtype == float
        assert df["trades"].dtype == int

    @patch("core.data.fetcher.Client")
    def test_client_called_with_correct_args(self, mock_client_cls: MagicMock) -> None:
        mock_instance = MagicMock()
        mock_instance.get_historical_klines.return_value = _make_kline_rows(1)
        mock_client_cls.return_value = mock_instance

        fetch_klines(
            symbol="ETHUSDT",
            interval="1d",
            start_str="1 year ago UTC",
            api_key="key",
            api_secret="secret",
        )

        mock_client_cls.assert_called_once_with("key", "secret")
        mock_instance.get_historical_klines.assert_called_once_with(
            symbol="ETHUSDT",
            interval="1d",
            start_str="1 year ago UTC",
        )


class TestFetchKlinesRemovesDuplicates:
    """Duplicate timestamps are deduplicated (keep=first)."""

    @patch("core.data.fetcher.Client")
    def test_removes_duplicates(self, mock_client_cls: MagicMock) -> None:
        rows = _make_kline_rows(3)
        # Insert a duplicate of row 1 with different close price
        dup_row = rows[1].copy()
        dup_row[4] = "99999.0"  # different close
        rows_with_dup = rows[:2] + [dup_row] + rows[2:]

        mock_instance = MagicMock()
        mock_instance.get_historical_klines.return_value = rows_with_dup
        mock_client_cls.return_value = mock_instance

        df = fetch_klines()

        # 4 rows in, 3 rows out (duplicate removed)
        assert len(df) == 3
        # The kept row should be the first occurrence (original, not the dup)
        assert df.iloc[1]["close"] == float(rows[1][4])


class TestFetchKlinesDatetimeIndex:
    """The DataFrame index is a timezone-aware DatetimeIndex."""

    @patch("core.data.fetcher.Client")
    def test_creates_datetime_index(self, mock_client_cls: MagicMock) -> None:
        mock_instance = MagicMock()
        mock_instance.get_historical_klines.return_value = _make_kline_rows(2)
        mock_client_cls.return_value = mock_instance

        df = fetch_klines()

        assert isinstance(df.index, pd.DatetimeIndex)
        assert df.index.tz is not None
        assert str(df.index.tz) == "UTC"
