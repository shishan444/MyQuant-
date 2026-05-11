"""Derivatives data merger: forward-fill merge OI and Funding Rate into OHLCV.

Provides merge_derivatives_into_ohlcv() which takes optional OI and Funding
DataFrames and forward-fills them into the OHLCV DataFrame for downstream
indicator computation.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def merge_derivatives_into_ohlcv(
    ohlcv_df: pd.DataFrame,
    oi_df: pd.DataFrame | None = None,
    funding_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Merge derivatives data into OHLCV DataFrame via forward-fill.

    Args:
        ohlcv_df: OHLCV DataFrame with DatetimeIndex.
        oi_df: Optional DataFrame with 'open_interest' column and DatetimeIndex.
        funding_df: Optional DataFrame with 'funding_rate' column and DatetimeIndex.

    Returns:
        DataFrame with derivatives columns added (forward-filled).
        Returns original DataFrame if no derivatives data provided.
    """
    if oi_df is None and funding_df is None:
        return ohlcv_df

    result = ohlcv_df.copy()

    if oi_df is not None and not oi_df.empty and "open_interest" in oi_df.columns:
        oi_series = oi_df["open_interest"]
        # Reindex to OHLCV frequency and forward-fill
        oi_aligned = oi_series.reindex(result.index, method="ffill")
        result["open_interest"] = oi_aligned
        logger.debug(
            "Merged OI data: %d/%d bars filled",
            oi_aligned.notna().sum(), len(result),
        )

    if funding_df is not None and not funding_df.empty and "funding_rate" in funding_df.columns:
        fr_series = funding_df["funding_rate"]
        fr_aligned = fr_series.reindex(result.index, method="ffill")
        result["funding_rate"] = fr_aligned
        logger.debug(
            "Merged Funding Rate data: %d/%d bars filled",
            fr_aligned.notna().sum(), len(result),
        )

    return result
