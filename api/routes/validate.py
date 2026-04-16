"""Validation API routes for WHEN/THEN hypothesis testing."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.deps import get_db_path, get_data_dir
from core.validation.engine import validate_hypothesis


router = APIRouter(prefix="/api", tags=["validation"])


class ConditionInput(BaseModel):
    subject: str
    action: str
    target: str = ""
    window: Optional[int] = None
    logic: str = "AND"
    timeframe: Optional[str] = None


class ValidateRequest(BaseModel):
    pair: str
    timeframe: str
    start: str
    end: str
    when: List[ConditionInput]
    then: List[ConditionInput]
    indicator_params: Optional[Dict[str, Any]] = None
    base_timeframe: Optional[str] = None


class TriggerRecordResponse(BaseModel):
    id: int
    time: str
    trigger_price: float
    change_pct: float
    matched: bool
    indicator_values: Dict[str, float] = {}


class ValidateResponse(BaseModel):
    match_rate: float
    total_count: int
    match_count: int
    mismatch_count: int
    triggers: List[TriggerRecordResponse] = []
    distribution: List[Dict[str, Any]] = []
    percentiles: Dict[str, float] = {}
    concentration: Dict[str, Any] = {}
    signal_frequency: Dict[str, float] = {}
    extremes: List[Dict[str, Any]] = []
    warnings: List[str] = []


@router.post("/validate", response_model=ValidateResponse)
def run_validation(
    payload: ValidateRequest,
    data_dir: Path = Depends(get_data_dir),
) -> ValidateResponse:
    """Validate a WHEN->THEN hypothesis against historical data."""
    result = validate_hypothesis(
        pair=payload.pair,
        timeframe=payload.timeframe,
        start=payload.start,
        end=payload.end,
        when_conditions=[c.model_dump() for c in payload.when],
        then_conditions=[c.model_dump() for c in payload.then],
        indicator_params=payload.indicator_params,
        data_dir=str(data_dir),
        base_timeframe=payload.base_timeframe,
    )

    return ValidateResponse(
        match_rate=result.match_rate,
        total_count=result.total_count,
        match_count=result.match_count,
        mismatch_count=result.mismatch_count,
        triggers=[
            TriggerRecordResponse(
                id=t.id,
                time=t.time,
                trigger_price=t.trigger_price,
                change_pct=t.change_pct,
                matched=t.matched,
                indicator_values=t.indicator_values,
            )
            for t in result.triggers
        ],
        distribution=[
            {
                "range": [b.range_start, b.range_end],
                "match_count": b.match_count,
                "mismatch_count": b.mismatch_count,
                "total_count": b.total_count,
            }
            for b in result.distribution
        ],
        percentiles=result.percentiles,
        concentration=result.concentration,
        signal_frequency=result.signal_frequency,
        extremes=result.extremes,
        warnings=result.warnings,
    )


@router.get("/validate/{task_id}/triggers")
def get_validation_triggers(
    task_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort: str = Query("time", pattern="^(time|trigger_price|change_pct)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
) -> Dict[str, Any]:
    """Get trigger records for a validation task (placeholder for future caching)."""
    return {"total": 0, "page": page, "per_page": per_page, "records": []}
