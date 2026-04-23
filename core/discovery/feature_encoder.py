"""Feature encoder: transforms indicator values into ML-ready feature vectors.

Encodes current indicator state into ~16-dimensional feature vectors for
use by decision tree and KNN engines.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler


class FeatureEncoder:
    """Encode indicator columns into normalized feature vectors."""

    def __init__(self):
        self.scaler: Optional[MinMaxScaler] = None
        self.feature_columns: List[str] = []

    def fit(self, df: pd.DataFrame) -> "FeatureEncoder":
        """Identify and fit scaler on available indicator columns."""
        self.feature_columns = self._select_features(df)

        if self.feature_columns:
            values = df[self.feature_columns].fillna(0).values
            self.scaler = MinMaxScaler()
            self.scaler.fit(values)

        return self

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        """Transform DataFrame into normalized feature matrix."""
        if not self.feature_columns or self.scaler is None:
            return np.zeros((len(df), 1))

        values = df[self.feature_columns].fillna(0).values
        return self.scaler.transform(values)

    def fit_transform(self, df: pd.DataFrame) -> np.ndarray:
        """Fit and transform in one step."""
        self.fit(df)
        return self.transform(df)

    def _select_features(self, df: pd.DataFrame) -> List[str]:
        """Select ~16 representative indicator columns."""
        features = []

        # Momentum: RSI
        rsi_cols = [c for c in df.columns if c.startswith("rsi_")]
        if rsi_cols:
            features.append(rsi_cols[0])

        # Trend: EMA relationship (close vs EMA)
        ema_cols = [c for c in df.columns if c.startswith("ema_")]
        for col in ema_cols[:3]:
            features.append(col)

        # MACD histogram
        macd_cols = [c for c in df.columns if "macd_histogram" in c]
        if macd_cols:
            features.append(macd_cols[0])

        # Volatility: BB position
        bb_percent_cols = [c for c in df.columns if "bb_percent" in c]
        if bb_percent_cols:
            features.append(bb_percent_cols[0])
        bb_bw_cols = [c for c in df.columns if "bb_bandwidth" in c]
        if bb_bw_cols:
            features.append(bb_bw_cols[0])

        # ATR (normalized)
        atr_cols = [c for c in df.columns if c.startswith("atr_")]
        if atr_cols:
            features.append(atr_cols[0])

        # Volume: RVOL
        rvol_cols = [c for c in df.columns if c.startswith("rvol_")]
        if rvol_cols:
            features.append(rvol_cols[0])

        # ADX
        adx_cols = [c for c in df.columns if c.startswith("adx_")]
        if adx_cols:
            features.append(adx_cols[0])

        # Stochastic
        stoch_cols = [c for c in df.columns if c.startswith("stoch_k_")]
        if stoch_cols:
            features.append(stoch_cols[0])

        # CCI
        cci_cols = [c for c in df.columns if c.startswith("cci_")]
        if cci_cols:
            features.append(cci_cols[0])

        # MFI
        mfi_cols = [c for c in df.columns if c.startswith("mfi_")]
        if mfi_cols:
            features.append(mfi_cols[0])

        # Pattern columns (binary 0/1)
        pattern_cols = [c for c in df.columns if c.startswith("pattern_")]
        for col in pattern_cols[:4]:
            features.append(col)

        return features[:20]  # Cap at 20 features
