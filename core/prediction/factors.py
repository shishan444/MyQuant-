"""Factor computation for price range prediction.

Pure function: compute_factors(df, idx, dna) -> Dict[str, float].
Input df must contain compute_all_indicators() output columns.
"""

from __future__ import annotations

from typing import Dict

import pandas as pd

from core.prediction.genes import PredictionDNA

FACTOR_POOL = {
    "vol_regime": "ATR / SMA(ATR, 50), volatility regime",
    "bb_squeeze": "1 - BB_width percentile rank, squeeze degree",
    "rvol": "Volume / SMA(Volume, 20), relative volume",
    "tension_short": "abs(z-score, short_window), short-term tension",
    "tension_mid": "abs(z-score, mid_window), mid-term tension",
    "tension_long": "abs(z-score, long_window), long-term tension",
    "tension_divergence": "abs(tau_short) - abs(tau_long), divergence",
    "adx_strength": "ADX / 100, trend strength",
}


def compute_factors(df: pd.DataFrame, idx: int, dna: PredictionDNA) -> Dict[str, float]:
    """Compute all factors for bar at index idx."""
    close = float(df["close"].iloc[idx])
    factors: Dict[str, float] = {}

    # vol_regime: ATR relative to its SMA
    if "atr_14" in df.columns:
        atr = float(df["atr_14"].iloc[idx])
        atr_sma = df["atr_14"].rolling(50, min_periods=10).mean()
        atr_sma_val = float(atr_sma.iloc[idx])
        factors["vol_regime"] = atr / max(atr_sma_val, 1e-8)
    else:
        factors["vol_regime"] = 1.0

    # bb_squeeze: BB width percentile rank (inverted)
    if "bb_upper_20_2" in df.columns and "bb_lower_20_2" in df.columns:
        bb_width = df["bb_upper_20_2"] - df["bb_lower_20_2"]
        bb_pct = bb_width.rolling(100, min_periods=20).rank(pct=True)
        val = float(bb_pct.iloc[idx])
        factors["bb_squeeze"] = 1.0 - val if pd.notna(val) else 0.5
    else:
        factors["bb_squeeze"] = 0.5

    # rvol: relative volume
    vol = float(df["volume"].iloc[idx])
    vol_sma = df["volume"].rolling(20, min_periods=5).mean()
    vol_sma_val = float(vol_sma.iloc[idx])
    factors["rvol"] = vol / max(vol_sma_val, 1.0)

    # Multi-scale tension (z-score)
    for scale_name, window in [
        ("short", dna.short_window),
        ("mid", dna.mid_window),
        ("long", dna.long_window),
    ]:
        min_p = max(window // 2, 5)
        ma = df["close"].rolling(window, min_periods=min_p).mean()
        std = df["close"].rolling(window, min_periods=min_p).std()
        ma_val = float(ma.iloc[idx])
        std_val = float(std.iloc[idx])
        if pd.notna(ma_val) and pd.notna(std_val) and std_val > 0:
            tau = (close - ma_val) / std_val
            factors[f"tension_{scale_name}"] = abs(tau)
        else:
            factors[f"tension_{scale_name}"] = 0.5

    # tension_divergence
    factors["tension_divergence"] = factors["tension_short"] - factors["tension_long"]

    # adx_strength
    if "adx_14" in df.columns:
        adx_val = float(df["adx_14"].iloc[idx])
        factors["adx_strength"] = min(max(adx_val / 100.0, 0.0), 1.0)
    else:
        factors["adx_strength"] = 0.5

    return factors
