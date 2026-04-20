"""Evolution task management routes."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_db_path, get_data_dir
from api.schemas import (
    DNAModel,
    EvolutionHistoryRecord,
    EvolutionHistoryResponse,
    EvolutionTaskCreate,
    EvolutionTaskListResponse,
    EvolutionTaskResponse,
)
from core.persistence.db import (
    count_all_tasks,
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


def _parse_json_list(raw: Optional[str]) -> Optional[List[str]]:
    """Parse a JSON-encoded list from a DB text column."""
    if not raw:
        return None
    try:
        val = json.loads(raw)
        return val if isinstance(val, list) else None
    except (json.JSONDecodeError, Exception):
        return None


def _parse_json_dict(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    """Parse a JSON-encoded dict from a DB text column."""
    if not raw:
        return None
    try:
        val = json.loads(raw)
        return val if isinstance(val, dict) else None
    except (json.JSONDecodeError, Exception):
        return None


def _task_row_to_response(
    row: Dict[str, Any],
    strategy_count: int = 0,
) -> EvolutionTaskResponse:
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
        best_score=row.get("best_score"),
        leverage=row.get("leverage", 1),
        direction=row.get("direction", "long"),
        data_start=row.get("data_start"),
        data_end=row.get("data_end"),
        data_time_start=row.get("data_time_start"),
        data_time_end=row.get("data_time_end"),
        data_row_count=row.get("data_row_count", 0),
        indicator_pool=_parse_json_list(row.get("indicator_pool")),
        timeframe_pool=_parse_json_list(row.get("timeframe_pool")),
        mode=row.get("mode"),
        champion_metrics=_parse_json_dict(row.get("champion_metrics")),
        champion_dimension_scores=_parse_json_dict(row.get("champion_dimension_scores")),
        walk_forward_enabled=bool(row.get("walk_forward_enabled", 0)),
        continuous=bool(row.get("continuous", 1)),
        strategy_threshold=row.get("strategy_threshold", 80.0),
        strategy_count=strategy_count,
        exploration_efficiency=round(
            strategy_count / max(row.get("current_generation", 0), 1), 4
        ),
    )


@router.post("/tasks", status_code=201)
def create_task(
    payload: EvolutionTaskCreate,
    db_path: Path = Depends(get_db_path),
    data_dir: Path = Depends(get_data_dir),
) -> EvolutionTaskResponse:
    """Create a new evolution task."""
    task_id = str(uuid.uuid4())

    # --- Auto-derive execution timeframe from timeframe_pool ---
    # Sort pool by duration (longest first), execution TF = shortest
    tf_pool = payload.timeframe_pool
    if tf_pool and len(tf_pool) > 1:
        tf_pool = sort_timeframes(tf_pool)
        # Override timeframe with the shortest in pool
        payload.timeframe = tf_pool[-1]

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
            risk_genes=RiskGenes(stop_loss=0.03, take_profit=0.06, position_size=1.0,
                                 leverage=payload.leverage, direction=payload.direction),
        )

    # Force override leverage/direction on seed DNA with task-level constraints
    dna.risk_genes.leverage = payload.leverage
    # mixed mode: don't override direction, allow evolution to explore both
    if payload.direction != "mixed":
        dna.risk_genes.direction = payload.direction

    # Validate data availability
    import re
    safe_symbol = re.sub(r'[^A-Za-z0-9]', '', payload.symbol)
    timeframe = payload.timeframe

    parquet_path = data_dir / f"{safe_symbol}_{timeframe}.parquet"
    # Try aliases
    if not parquet_path.exists():
        aliases = {"1h": ["1h", "60m"], "4h": ["4h"], "1d": ["1d", "1D"]}
        for alias in aliases.get(timeframe, [timeframe]):
            alt_path = data_dir / f"{safe_symbol}_{alias}.parquet"
            if alt_path.exists():
                parquet_path = alt_path
                break

    data_time_start = None
    data_time_end = None
    data_row_count = 0

    if not parquet_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"无 {payload.symbol}/{payload.timeframe} 的K线数据"
        )

    # Read parquet time range
    try:
        import pandas as pd
        df = pd.read_parquet(parquet_path)
        data_row_count = len(df)
        if data_row_count > 0:
            if isinstance(df.index, pd.DatetimeIndex):
                data_time_start = str(df.index.min())
                data_time_end = str(df.index.max())
            elif "timestamp" in df.columns or "date" in df.columns:
                ts_col = "timestamp" if "timestamp" in df.columns else "date"
                data_time_start = str(df[ts_col].min())
                data_time_end = str(df[ts_col].max())
    except Exception:
        pass

    save_task(
        db_path,
        task_id=task_id,
        target_score=payload.target_score,
        template=payload.score_template,
        symbol=payload.symbol,
        timeframe=payload.timeframe,
        initial_dna=dna,
    )

    # Update extended columns (including leverage/direction constraints and data info)
    conn = _get_connection(db_path)
    conn.execute(
        """UPDATE evolution_task
           SET population_size = ?, max_generations = ?,
               elite_ratio = ?, n_workers = ?, status = 'pending',
               leverage = ?, direction = ?,
               data_start = ?, data_end = ?,
               data_time_start = ?, data_time_end = ?, data_row_count = ?,
               indicator_pool = ?, timeframe_pool = ?, mode = ?,
               walk_forward_enabled = ?, continuous = ?,
               strategy_threshold = ?
           WHERE task_id = ?""",
        (payload.population_size, payload.max_generations,
         payload.elite_ratio, payload.n_workers,
         payload.leverage, payload.direction,
         payload.data_start, payload.data_end,
         data_time_start, data_time_end, data_row_count,
         json.dumps(payload.indicator_pool) if payload.indicator_pool else None,
         json.dumps(payload.timeframe_pool) if payload.timeframe_pool else None,
         payload.mode,
         1 if payload.walk_forward_enabled else 0,
         1 if payload.continuous else 0,
         payload.strategy_threshold,
         task_id),
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
    page: int = 1,
    page_size: int = 20,
    db_path: Path = Depends(get_db_path),
) -> EvolutionTaskListResponse:
    """List evolution tasks with optional status filter and pagination."""
    offset = (page - 1) * page_size
    total = count_all_tasks(db_path, status=status)
    rows = list_all_tasks(db_path, status=status, limit=page_size, offset=offset)

    # Batch query strategy counts for all tasks on this page
    from api.db_ext import count_strategies_by_tasks
    task_ids = [r["task_id"] for r in rows]
    strategy_counts = count_strategies_by_tasks(db_path, task_ids) if task_ids else {}

    items = [
        _task_row_to_response(r, strategy_count=strategy_counts.get(r["task_id"], 0))
        for r in rows
    ]
    return EvolutionTaskListResponse(items=items, total=total, page=page, page_size=page_size)


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


@router.get("/tasks/{task_id}/discovered-strategies")
def get_discovered_strategies(
    task_id: str,
    min_score: Optional[float] = None,
    db_path: Path = Depends(get_db_path),
) -> List[Dict[str, Any]]:
    """Get auto-extracted strategies for a task from the strategy table."""
    from api.db_ext import list_strategies
    strategies = list_strategies(
        db_path,
        source="evolution",
        limit=100,
    )
    # Filter by source_task_id and optional min_score
    result = []
    for s in strategies:
        if s.get("source_task_id") != task_id:
            continue
        if min_score is not None and (s.get("best_score") or 0) < min_score:
            continue
        result.append({
            "strategy_id": s["strategy_id"],
            "name": s.get("name"),
            "dna": json.loads(s["dna_json"]) if s.get("dna_json") else None,
            "source": "evolution",
            "source_task_id": s.get("source_task_id"),
            "score": s.get("best_score"),
            "generation": s.get("generation", 0),
            "created_at": s.get("created_at"),
        })
    # Sort by score desc
    result.sort(key=lambda x: x.get("score", 0) or 0, reverse=True)
    return result


def _get_connection(db_path: Path):
    """Get a raw SQLite connection for extended column updates."""
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


# ── Timeframe utilities ──

_TF_DURATION_MINUTES = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "2h": 120, "4h": 240, "6h": 360, "8h": 480,
    "12h": 720, "1d": 1440, "3d": 4320, "1w": 10080,
}


def sort_timeframes(tfs: List[str]) -> List[str]:
    """Sort timeframes by duration, longest first."""
    def _key(tf: str) -> int:
        return _TF_DURATION_MINUTES.get(tf, 0)
    return sorted(tfs, key=_key, reverse=True)
