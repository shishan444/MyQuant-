"""PriceRangePredictor -- system-level price range predictor.

Core predict/observe cycle with GARCH state recursion and factor-weighted K.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd

from core.prediction.garch import GarchState
from core.prediction.genes import PredictionDNA
from core.prediction.factors import compute_factors


@dataclass
class PredictionResult:
    """Output of a price range prediction."""
    low: float       # predicted lower bound
    high: float      # predicted upper bound
    width: float     # single-side half-width = sigma * K
    k_actual: float  # actual dynamic K value used


class PriceRangePredictor:
    """System-level shared price range predictor."""

    def __init__(self, dna: PredictionDNA):
        self._dna = dna
        self._garch = GarchState()
        self._initialized = False
        self._hit_count = 0
        self._total_count = 0
        self._miss_streak = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def warmup(self, df: pd.DataFrame, n_bars: int = 100):
        """Warm up GARCH state with historical data."""
        ranges = df["high"] - df["low"]
        start = max(0, len(ranges) - n_bars)
        self._garch = GarchState.init_from_history(
            ranges.iloc[start:],
            self._dna.omega, self._dna.alpha, self._dna.beta,
        )
        self._initialized = True

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def predict(self, df: pd.DataFrame, idx: int) -> PredictionResult:
        """Predict price range for next bar based on data up to idx."""
        if not self._initialized:
            raise RuntimeError("Predictor not warmed up. Call warmup() first.")

        close = float(df["close"].iloc[idx])
        sigma = math.sqrt(self._garch.sigma_sq)

        # Compute factors
        factors = compute_factors(df, idx, self._dna)

        # Compute dynamic K
        k = self._dna.k_base
        for factor_name, weight in self._dna.factor_weights.items():
            if factor_name in factors:
                k += weight * factors[factor_name]

        # Emergency: inflate k_min when consecutive misses
        effective_k_min = self._dna.k_min
        if self._miss_streak >= 5:
            effective_k_min *= 2.0
        elif self._miss_streak >= 3:
            effective_k_min *= 1.5

        k = max(k, effective_k_min)

        # Final width
        width = sigma * k

        return PredictionResult(
            low=close - width,
            high=close + width,
            width=width,
            k_actual=k,
        )

    def observe(self, actual_high: float, actual_low: float,
                predicted: PredictionResult) -> None:
        """Observe actual result, update GARCH state and hit tracking."""
        actual_range = actual_high - actual_low
        self._garch.update(actual_range, self._dna.omega, self._dna.alpha, self._dna.beta)

        self._total_count += 1
        if actual_low >= predicted.low and actual_high <= predicted.high:
            self._hit_count += 1
            self._miss_streak = 0
        else:
            self._miss_streak += 1

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def state_dict(self) -> dict:
        """Export runtime state for optional persistence."""
        return {
            "sigma_sq": self._garch.sigma_sq,
            "epsilon": self._garch.epsilon,
            "hit_count": self._hit_count,
            "total_count": self._total_count,
            "miss_streak": self._miss_streak,
            "initialized": self._initialized,
        }

    def restore_state(self, state: dict) -> None:
        """Restore runtime state from dict."""
        self._garch = GarchState(
            sigma_sq=state["sigma_sq"],
            epsilon=state["epsilon"],
        )
        self._hit_count = state["hit_count"]
        self._total_count = state["total_count"]
        self._miss_streak = state["miss_streak"]
        self._initialized = state.get("initialized", True)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def hit_rate(self) -> float:
        return self._hit_count / max(self._total_count, 1)

    def needs_retrain(self) -> bool:
        return self._total_count >= 50 and self.hit_rate < 0.45
