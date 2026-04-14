"""Checkpoint resume logic for interrupted evolution."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.strategy.dna import StrategyDNA
from core.persistence.db import (
    get_task, get_latest_snapshot, get_running_task,
)


def save_generation(
    db_path: Path,
    task_id: str,
    generation: int,
    best_score: float,
    avg_score: float,
    best_dna: StrategyDNA,
    population: List[StrategyDNA],
    mutation_log: Optional[str] = None,
    wf_months: Optional[str] = None,
) -> None:
    """Save a complete generation state for checkpoint resume.

    Writes to both generation_snapshot and evolution_history.
    """
    from core.persistence.db import save_snapshot, save_history

    save_snapshot(
        db_path=db_path,
        task_id=task_id,
        generation=generation,
        best_score=best_score,
        avg_score=avg_score,
        best_dna=best_dna,
        population=population,
        mutation_log=mutation_log,
        wf_months=wf_months,
    )

    top3 = json.dumps([{"rank": 1, "score": best_score}])
    save_history(
        db_path=db_path,
        task_id=task_id,
        generation=generation,
        best_score=best_score,
        avg_score=avg_score,
        top3_summary=top3,
    )


def resume_evolution(
    db_path: Path,
    task_id: str,
) -> Optional[Dict[str, Any]]:
    """Resume an evolution from the latest checkpoint.

    Args:
        db_path: Path to SQLite database.
        task_id: Task to resume.

    Returns:
        Dict with generation, population, best_score, avg_score, or None.
    """
    task = get_task(db_path, task_id)
    if task is None or task["status"] != "running":
        return None

    snapshot = get_latest_snapshot(db_path, task_id)
    if snapshot is None:
        return None

    # Deserialize population
    pop_data = json.loads(snapshot["population_json"])
    population = [StrategyDNA.from_dict(d) for d in pop_data]

    # Deserialize best DNA
    best_dna = StrategyDNA.from_json(snapshot["best_dna"])

    return {
        "generation": snapshot["generation"],
        "population": population,
        "best_dna": best_dna,
        "best_score": snapshot["best_score"],
        "avg_score": snapshot["avg_score"],
        "task": task,
    }
