"""Phase J: load_mtf_data single-timeframe fallback fix.

Verifies that load_mtf_data returns a valid dict (not None) when only
the execution timeframe data is available, enabling graceful degradation.
"""
import numpy as np
import pandas as pd
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from core.data.mtf_loader import load_mtf_data


def _make_df(n=200):
    """Create a minimal DataFrame with OHLCV columns."""
    dates = pd.date_range('2024-01-01', periods=n, freq='4h', tz='UTC')
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    df = pd.DataFrame({
        'open': close * 0.999, 'high': close * 1.005,
        'low': close * 0.995, 'close': close, 'volume': 1000.0,
    }, index=dates)
    df.index.name = 'timestamp'
    return df


def test_single_timeframe_returns_valid_dict():
    """When only exec_timeframe data exists, return {exec_timeframe: df} not None.

    Before fix: returned None because len(dfs_by_timeframe) == 1.
    After fix: returns the valid dict with exec_timeframe.
    """
    enhanced_df = _make_df()
    result = load_mtf_data(
        data_dir=Path("/tmp/fake_data"),
        symbol="BTCUSDT",
        exec_timeframe="4h",
        enhanced_df=enhanced_df,
        needed_tfs={"1d", "1h"},
    )

    # No additional TF data available, but should still return exec_timeframe
    assert result is not None
    assert isinstance(result, dict)
    assert "4h" in result
    assert len(result["4h"]) == 200


def test_multi_timeframe_returns_all():
    """When additional TF data is available, return all timeframes."""
    enhanced_df = _make_df()

    # Mock find_parquet to return a path for "1d" but not "1h"
    def mock_find_parquet(data_dir, safe_symbol, tf):
        if tf == "1d":
            return Path("/tmp/fake_data/BTCUSDT_1d.parquet")
        return None

    mock_df = _make_df(300)

    with patch('core.data.mtf_loader.find_parquet', side_effect=mock_find_parquet):
        with patch('core.data.storage.load_parquet', return_value=mock_df):
            with patch('core.features.indicators.compute_all_indicators', side_effect=lambda x: x):
                result = load_mtf_data(
                    data_dir=Path("/tmp/fake_data"),
                    symbol="BTCUSDT",
                    exec_timeframe="4h",
                    enhanced_df=enhanced_df,
                    needed_tfs={"1d", "1h"},
                )

    assert result is not None
    assert "4h" in result
    assert "1d" in result
    assert len(result) == 2


def test_no_needed_tfs_returns_exec_only():
    """When needed_tfs is empty, return just the exec_timeframe dict."""
    enhanced_df = _make_df()
    result = load_mtf_data(
        data_dir=Path("/tmp/fake_data"),
        symbol="BTCUSDT",
        exec_timeframe="4h",
        enhanced_df=enhanced_df,
        needed_tfs=set(),
    )

    assert result is not None
    assert "4h" in result
