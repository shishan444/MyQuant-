"""PredictionDNA -- price range prediction formula gene.

Evolved offline by PredictionEvolver, then fixed for online use.
GARCH(1,1) params + factor weights + window params.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class PredictionDNA:
    """Prediction formula gene. Evolved offline, then serialized to JSON."""

    # GARCH(1,1) params
    omega: float = 1e-5       # long-term variance baseline
    alpha: float = 0.10       # shock sensitivity
    beta: float = 0.80        # variance persistence

    # Width multiplier
    k_base: float = 0.6       # base multiplier
    k_min: float = 0.3        # safety floor

    # Factor weights (8 factors; weight=0 means unused)
    factor_weights: Dict[str, float] = field(default_factory=dict)

    # Multi-scale tension windows
    short_window: int = 15
    mid_window: int = 60
    long_window: int = 200

    # Metadata
    prediction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    generation: int = 0
    fitness_score: float = 0.0

    # ------------------------------------------------------------------
    # GARCH stationarity
    # ------------------------------------------------------------------

    @property
    def is_stationary(self) -> bool:
        """GARCH(1,1) requires alpha + beta < 1 for stationarity."""
        return (self.alpha + self.beta) < 1.0

    def clamp_params(self) -> None:
        """Force alpha + beta < 0.95, preserving their ratio."""
        ceiling = 0.95
        if self.alpha + self.beta >= ceiling:
            scale = ceiling / (self.alpha + self.beta) * 0.9999
            self.alpha *= scale
            self.beta *= scale

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "omega": self.omega,
            "alpha": self.alpha,
            "beta": self.beta,
            "k_base": self.k_base,
            "k_min": self.k_min,
            "factor_weights": dict(self.factor_weights),
            "short_window": self.short_window,
            "mid_window": self.mid_window,
            "long_window": self.long_window,
            "prediction_id": self.prediction_id,
            "generation": self.generation,
            "fitness_score": self.fitness_score,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PredictionDNA:
        return cls(
            omega=data.get("omega", 1e-5),
            alpha=data.get("alpha", 0.10),
            beta=data.get("beta", 0.80),
            k_base=data.get("k_base", 0.6),
            k_min=data.get("k_min", 0.3),
            factor_weights=data.get("factor_weights", {}),
            short_window=data.get("short_window", 15),
            mid_window=data.get("mid_window", 60),
            long_window=data.get("long_window", 200),
            prediction_id=data.get("prediction_id", str(uuid.uuid4())),
            generation=data.get("generation", 0),
            fitness_score=data.get("fitness_score", 0.0),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> PredictionDNA:
        return cls.from_dict(json.loads(json_str))
