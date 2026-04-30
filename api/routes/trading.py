"""REST API routes for paper trading tasks."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from api.db_ext import (
    save_paper_trading_task,
    get_paper_trading_task,
    update_paper_trading_task,
    list_paper_trading_tasks,
    list_paper_trades,
)
from api.deps import get_db_path
from api.schemas import (
    PaperTradingTaskCreate,
    PaperTradingTaskResponse,
    PaperTradingTaskListResponse,
    PaperTradeListResponse,
    PaperTradeResponse,
)

router = APIRouter(prefix="/api/trading", tags=["trading"])


def _task_to_response(row: dict) -> PaperTradingTaskResponse:
    return PaperTradingTaskResponse(
        task_id=row["task_id"],
        status=row["status"],
        strategy_name=row.get("strategy_name"),
        symbol=row["symbol"],
        timeframe=row["timeframe"],
        initial_cash=row["initial_cash"],
        fee=row["fee"],
        leverage=row["leverage"],
        direction=row["direction"],
        score_template=row.get("score_template", "explorer"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        started_at=row.get("started_at"),
        stopped_at=row.get("stopped_at"),
        stop_reason=row.get("stop_reason"),
        position_side=row.get("position_side"),
        position_entry=row.get("position_entry"),
        position_quantity=row.get("position_quantity"),
        position_margin=row.get("position_margin"),
        position_funding=row.get("position_funding"),
        balance=row.get("balance"),
        unrealized_pnl=row.get("unrealized_pnl", 0.0),
        total_trades=row.get("total_trades", 0),
        total_pnl=row.get("total_pnl", 0.0),
        win_count=row.get("win_count", 0),
        loss_count=row.get("loss_count", 0),
        last_bar_time=row.get("last_bar_time"),
        last_bar_close=row.get("last_bar_close"),
    )


@router.post("/tasks", response_model=PaperTradingTaskResponse, status_code=201)
def create_task(
    body: PaperTradingTaskCreate,
    db_path: Path = Depends(get_db_path),
) -> PaperTradingTaskResponse:
    task_id = uuid.uuid4().hex[:12]
    save_paper_trading_task(
        db_path,
        task_id=task_id,
        dna_json=body.dna_json,
        symbol=body.symbol,
        timeframe=body.timeframe,
        initial_cash=body.initial_cash,
        fee=body.fee,
        leverage=body.leverage,
        direction=body.direction,
        score_template=body.score_template,
        strategy_name=body.strategy_name,
    )
    row = get_paper_trading_task(db_path, task_id)
    return _task_to_response(row)


@router.get("/tasks", response_model=PaperTradingTaskListResponse)
def list_tasks(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db_path: Path = Depends(get_db_path),
) -> PaperTradingTaskListResponse:
    tasks = list_paper_trading_tasks(db_path, status=status, limit=limit, offset=offset)
    return PaperTradingTaskListResponse(
        tasks=[_task_to_response(t) for t in tasks],
        total=len(tasks),
    )


@router.get("/tasks/{task_id}", response_model=PaperTradingTaskResponse)
def get_task(
    task_id: str,
    db_path: Path = Depends(get_db_path),
) -> PaperTradingTaskResponse:
    row = get_paper_trading_task(db_path, task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return _task_to_response(row)


@router.post("/tasks/{task_id}/stop", response_model=PaperTradingTaskResponse)
def stop_task(
    task_id: str,
    db_path: Path = Depends(get_db_path),
) -> PaperTradingTaskResponse:
    row = get_paper_trading_task(db_path, task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if row["status"] not in ("running", "pending"):
        raise HTTPException(status_code=400, detail=f"Cannot stop task in status '{row['status']}'")

    # Signal via controller (immediate)
    from core.trading.runner import get_trading_controllers
    controller = get_trading_controllers().get(task_id)
    if controller:
        controller.request_stop()

    # Also set DB status (belt-and-suspenders)
    update_paper_trading_task(db_path, task_id, status="stopped", stop_reason="user_stop")
    row = get_paper_trading_task(db_path, task_id)
    return _task_to_response(row)


@router.post("/tasks/{task_id}/pause", response_model=PaperTradingTaskResponse)
def pause_task(
    task_id: str,
    db_path: Path = Depends(get_db_path),
) -> PaperTradingTaskResponse:
    row = get_paper_trading_task(db_path, task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if row["status"] != "running":
        raise HTTPException(status_code=400, detail="Can only pause running tasks")

    from core.trading.runner import get_trading_controllers
    controller = get_trading_controllers().get(task_id)
    if controller:
        controller.request_stop()

    update_paper_trading_task(db_path, task_id, status="paused")
    row = get_paper_trading_task(db_path, task_id)
    return _task_to_response(row)


@router.post("/tasks/{task_id}/resume", response_model=PaperTradingTaskResponse)
def resume_task(
    task_id: str,
    db_path: Path = Depends(get_db_path),
) -> PaperTradingTaskResponse:
    row = get_paper_trading_task(db_path, task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if row["status"] != "paused":
        raise HTTPException(status_code=400, detail="Can only resume paused tasks")
    update_paper_trading_task(db_path, task_id, status="pending")
    row = get_paper_trading_task(db_path, task_id)
    return _task_to_response(row)


@router.get("/tasks/{task_id}/trades", response_model=PaperTradeListResponse)
def get_trades(
    task_id: str,
    limit: int = 100,
    db_path: Path = Depends(get_db_path),
) -> PaperTradeListResponse:
    row = get_paper_trading_task(db_path, task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    trades = list_paper_trades(db_path, task_id, limit=limit)
    return PaperTradeListResponse(
        trades=[PaperTradeResponse(**t) for t in trades],
        total=len(trades),
    )


@router.get("/runner-status")
def runner_status(db_path: Path = Depends(get_db_path)) -> dict:
    from api.app import app
    runner = getattr(app.state, "trading_runner", None)
    if runner:
        return runner.get_status()
    return {"is_alive": False, "active_task_id": None}
