"""Champion tracker: atomic score + metrics updates (Hall-of-Fame pattern)."""
from __future__ import annotations

import copy
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ChampionRecord:
    """Immutable snapshot of the best individual at a point in time."""
    score: float
    metrics: Dict[str, Any] = field(default_factory=dict)
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    generation: int = 0
    timestamp: float = 0.0


class ChampionTracker:
    """Tracks the all-time best individual across generations.

    Score and metrics are always updated as a single atomic unit,
    eliminating the desynchronization bug where best_score could come
    from a different individual than champion_metrics.
    """

    def __init__(self) -> None:
        self._champion: Optional[ChampionRecord] = None
        self._lock = threading.Lock()

    def update(
        self,
        score: float,
        metrics: Optional[Dict[str, Any]] = None,
        dimension_scores: Optional[Dict[str, float]] = None,
        generation: int = 0,
    ) -> bool:
        """Atomically update champion if candidate is strictly better.

        Returns True if champion was updated, False otherwise.
        """
        if score <= 0:
            return False

        record = ChampionRecord(
            score=score,
            metrics=copy.deepcopy(metrics) if metrics else {},
            dimension_scores=copy.deepcopy(dimension_scores) if dimension_scores else {},
            generation=generation,
            timestamp=time.time(),
        )

        with self._lock:
            if self._champion is None or score > self._champion.score:
                self._champion = record
                return True
            return False

    def get_champion(self) -> Optional[ChampionRecord]:
        """Return current champion snapshot (thread-safe copy)."""
        with self._lock:
            if self._champion is None:
                return None
            return copy.deepcopy(self._champion)

    @property
    def best_score(self) -> float:
        """Return current best score, or -1.0 if no champion."""
        with self._lock:
            return self._champion.score if self._champion else -1.0
