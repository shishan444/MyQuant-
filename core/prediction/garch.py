"""GarchState -- GARCH(1,1) online recursion state.

Only 2 state values: sigma_sq (current variance) and epsilon (last shock).
"""

from __future__ import annotations

import math

import pandas as pd


class GarchState:
    """GARCH(1,1) online recursion state."""

    __slots__ = ("sigma_sq", "epsilon")

    def __init__(self, sigma_sq: float = 0.0, epsilon: float = 0.0):
        self.sigma_sq = sigma_sq
        self.epsilon = epsilon

    def update(self, actual_range: float, omega: float, alpha: float, beta: float) -> float:
        """Update state with actual bar range, return new sigma."""
        self.epsilon = actual_range - math.sqrt(self.sigma_sq) if self.sigma_sq > 0 else actual_range
        self.sigma_sq = omega + alpha * (self.epsilon ** 2) + beta * self.sigma_sq
        self.sigma_sq = max(self.sigma_sq, 1e-10)
        return math.sqrt(self.sigma_sq)

    @classmethod
    def init_from_history(cls, ranges: pd.Series, omega: float, alpha: float, beta: float) -> GarchState:
        """Initialize GARCH state from historical range series."""
        state = cls()
        for r in ranges:
            state.update(float(r), omega, alpha, beta)
        return state
