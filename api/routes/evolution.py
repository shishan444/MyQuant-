"""Evolution task management routes."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_db_path
from api.schemas import (
    DNAModel,
    EvolutionHistoryRecord,
    EvolutionHistoryResponse,
    EvolutionTaskCreate,
    EvolutionTaskListResponse,
    EvolutionTaskResponse,
)
from core.persistence.db import (
    get_history,
    get_task,
    list_all_tasks,
    save_task,
    update_task,
)
from core.strategy.dna import StrategyDNA

router = APIRouter(prefix="/api/evolution", tags=["evolution"])


def _dna_model_to_dna(dna_model: DNAModel) -> StrategyDNA:
    """Convert a Pydantic DNAModel to a core StrategyDNA."""
    data = dna_model.model_dump()
    return StrategyDNA.from_dict(data)


def _task_row_to_response(row: Dict[str, Any]) -> EvolutionTaskResponse:
    """Convert a DB row dict to EvolutionTaskResponse."""
    initial_dna = None
    if row.get("initial_dna"):
        try:
            dna_dict = json.loads(row["initial_dna"])
            initial_dna = DNAModel.model_validate(dna_dict)
        except (json.JSONDecodeError, Exception):
            initial_dna = None

    champion_dna = None
    if row.get("champion_dna"):
        try:
            dna_dict = json.loads(row["champion_dna"])
            champion_dna = DNAModel.model_validate(dna_dict)
        except (json.JSONDecodeError, Exception):
            champion_dna = None

    return EvolutionTaskResponse(
        task_id=row["task_id"],
        status=row["status"],
        target_score=row["target_score"],
        score_template=row["score_template"],
        symbol=row["symbol"],
        timeframe=row["timeframe"],
        initial_dna=initial_dna,
        champion_dna=champion_dna,
        population_size=row.get("population_size", 15),
        max_generations=row.get("max_generations", 200),
        elite_ratio=row.get("elite_ratio", 0.5),
        n_workers=row.get("n_workers", 6),
        current_generation=row.get("current_generation", 0),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        stop_reason=row.get("stop_reason"),
    )


@router.post("/tasks", status_code=201)
def create_task(
    payload: EvolutionTaskCreate,
    db_path: Path = Depends(get_db_path),
) -> EvolutionTaskResponse:
    """Create a new evolution task."""
    task_id = str(uuid.uuid4())

    # Build initial DNA: use provided or generate a default
    if payload.initial_dna:
        dna = _dna_model_to_dna(payload.initial_dna)
    else:
        from core.strategy.dna import StrategyDNA, SignalGene, SignalRole, LogicGenes, ExecutionGenes, RiskGenes
        dna = StrategyDNA(
            signal_genes=[
                SignalGene(indicator="EMA", params={"period": 20}, role=SignalRole.ENTRY_TRIGGER, condition={"type": "price_above"}),
                SignalGene(indicator="EMA", params={"period": 20}, role=SignalRole.EXIT_TRIGGER, condition={"type": "price_below"}),
            ],
            logic_genes=LogicGenes(entry_logic="AND", exit_logic="AND"),
            execution_genes=ExecutionGenes(timeframe=payload.timeframe, symbol=payload.symbol),
            risk_genes=RiskGenes(stop_loss=0.03, take_profit=0.06, position_size=1.0),
        )

    save_task(
        db_path,
        task_id=task_id,
        target_score=payload.target_score,
        template=payload.score_template,
        symbol=payload.symbol,
        timeframe=payload.timeframe,
        initial_dna=dna,
    )

    # Update extended columns
    conn = _get_connection(db_path)
    conn.execute(
        """UPDATE evolution_task
           SET population_size = ?, max_generations = ?,
               elite_ratio = ?, n_workers = ?, status = 'pending'
           WHERE task_id = ?""",
        (payload.population_size, payload.max_generations,
         payload.elite_ratio, payload.n_workers, task_id),
    )
    conn.commit()
    conn.close()

    row = get_task(db_path, task_id)
    if row is None:
        raise HTTPException(status_code=500, detail="Failed to create task")
    return _task_row_to_response(row)


@router.get("/tasks")
def list_tasks(
    status: Optional[str] = None,
    limit: int = 50,
    db_path: Path = Depends(get_db_path),
) -> EvolutionTaskListResponse:
    """List evolution tasks with optional status filter."""
    rows = list_all_tasks(db_path, status=status, limit=limit)
    items = [_task_row_to_response(r) for r in rows]
    return EvolutionTaskListResponse(items=items, total=len(items))


@router.get("/tasks/{task_id}")
def get_task_endpoint(
    task_id: str,
    db_path: Path = Depends(get_db_path),
) -> EvolutionTaskResponse:
    """Get evolution task details."""
    row = get_task(db_path, task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return _task_row_to_response(row)


@router.get("/tasks/{task_id}/history")
def get_task_history(
    task_id: str,
    db_path: Path = Depends(get_db_path),
) -> EvolutionHistoryResponse:
    """Get generation history for an evolution task."""
    row = get_task(db_path, task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")

    history = get_history(db_path, task_id)
    generations = [
        EvolutionHistoryRecord(
            generation=h["generation"],
            best_score=h["best_score"],
            avg_score=h["avg_score"],
            top3_summary=h.get("top3_summary"),
            created_at=h["created_at"],
        )
        for h in history
    ]

    return EvolutionHistoryResponse(
        task_id=task_id,
        generations=generations,
    )


@router.post("/tasks/{task_id}/pause")
def pause_task(
    task_id: str,
    db_path: Path = Depends(get_db_path),
) -> EvolutionTaskResponse:
    """Pause an evolution task."""
    row = get_task(db_path, task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")

    update_task(db_path, task_id, status="paused")
    row = get_task(db_path, task_id)
    return _task_row_to_response(row)


@router.post("/tasks/{task_id}/stop")
def stop_task(
    task_id: str,
    db_path: Path = Depends(get_db_path),
) -> EvolutionTaskResponse:
    """Stop an evolution task."""
    row = get_task(db_path, task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")

    update_task(db_path, task_id, status="stopped", stop_reason="user_stop")
    row = get_task(db_path, task_id)
    return _task_row_to_response(row)


@router.post("/tasks/{task_id}/resume")
def resume_task(
    task_id: str,
    db_path: Path = Depends(get_db_path),
) -> EvolutionTaskResponse:
    """Resume a paused evolution task."""
    row = get_task(db_path, task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if row["status"] != "paused":
        raise HTTPException(status_code=400, detail="Task is not paused")

    update_task(db_path, task_id, status="pending")
    row = get_task(db_path, task_id)
    return _task_row_to_response(row)


@router.get("/tasks/{task_id}/strategies")
def get_task_strategies(
    task_id: str,
    db_path: Path = Depends(get_db_path),
) -> dict:
    """Return effective strategies discovered by this evolution task.

    Returns champion and any snapshot strategies with score > 0.
    """
    row = get_task(db_path, task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")

    strategies = []

    # Champion strategy
    if row.get("champion_dna"):
        try:
            champion = json.loads(row["champion_dna"])
            strategies.append({
                "strategy_id": champion.get("strategy_id", ""),
                "dna": champion,
                "source": "champion",
                "score": row.get("champion_score", 0),
            })
        except (json.JSONDecodeError, Exception):
            pass

    # Snapshot-based strategies
    from core.persistence.db import _connect
    conn = _connect(db_path)
    snapshots = conn.execute(
        """SELECT generation, best_score, best_dna FROM generation_snapshot
           WHERE task_id = ? ORDER BY best_score DESC LIMIT 10""",
        (task_id,),
    ).fetchall()
    conn.close()

    for snap in snapshots:
        try:
            snap_dna = json.loads(snap["best_dna"])
            sid = snap_dna.get("strategy_id", "")
            # Skip if already included as champion
            if any(s["strategy_id"] == sid for s in strategies):
                continue
            strategies.append({
                "strategy_id": sid,
                "dna": snap_dna,
                "source": "snapshot",
                "generation": snap["generation"],
                "score": snap["best_score"],
            })
        except (json.JSONDecodeError, Exception):
            continue

    return {"task_id": task_id, "strategies": strategies}


def _get_connection(db_path: Path):
    """Get a raw SQLite connection for extended column updates."""
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn
