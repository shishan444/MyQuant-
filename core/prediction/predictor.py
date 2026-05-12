"""PriceRangePredictor -- system-level price range predictor."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PredictionResult:
    """Output of a price range prediction."""
    low: float       # predicted lower bound
    high: float      # predicted upper bound
    width: float     # range width = high - low
    k_actual: float  # actual dynamic K value used


class PriceRangePredictor:
    """System-level shared price range predictor."""

    def __init__(self, dna):
        # Will be implemented in Phase 1
        pass
