"""Strategy CRUD + backtest + compare routes."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from api.db_ext import (
    delete_strategy,
    get_strategy,
    list_strategies,
    save_backtest_result,
    save_strategy,
    update_strategy,
)
from api.deps import get_data_dir, get_db_path
from api.schemas import (
    BacktestRequest,
    BacktestResponse,
    CompareRequest,
    CompareResponse,
    CompareResultItem,
    DNAModel,
    StrategyCreate,
    StrategyListResponse,
    StrategyResponse,
    StrategyUpdate,
)
from core.backtest import engine as _bt_engine_mod
from core.scoring.scorer import score_strategy
from core.scoring.metrics import compute_metrics
from core.strategy.dna import StrategyDNA

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


def _dna_model_to_dna(dna_model: DNAModel) -> StrategyDNA:
    """Convert a Pydantic DNAModel to a core StrategyDNA."""
    data = dna_model.model_dump()
    return StrategyDNA.from_dict(data)


def _strategy_row_to_response(row: Dict[str, Any]) -> StrategyResponse:
    """Convert a DB row dict to StrategyResponse."""
    dna = None
    if row.get("dna_json"):
        try:
            dna_dict = json.loads(row["dna_json"])
            dna = DNAModel.model_validate(dna_dict)
        except (json.JSONDecodeError, Exception):
            dna = None

    return StrategyResponse(
        strategy_id=row["strategy_id"],
        name=row.get("name"),
        dna=dna,
        symbol=row["symbol"],
        timeframe=row["timeframe"],
        source=row.get("source", "manual"),
        source_task_id=row.get("source_task_id"),
        best_score=row.get("best_score"),
        generation=row.get("generation", 0),
        parent_ids=row.get("parent_ids"),
        tags=row.get("tags"),
        notes=row.get("notes"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.post("", status_code=201)
def create_strategy(
    payload: StrategyCreate,
    db_path: Path = Depends(get_db_path),
) -> StrategyResponse:
    """Create a new strategy."""
    strategy_id = str(uuid.uuid4())
    dna = _dna_model_to_dna(payload.dna)

    save_strategy(
        db_path,
        strategy_id=strategy_id,
        name=payload.name,
        dna_json=dna.to_json(),
        symbol=payload.symbol,
        timeframe=payload.timeframe,
        source=payload.source,
        source_task_id=payload.source_task_id,
        tags=payload.tags,
        notes=payload.notes,
    )

    row = get_strategy(db_path, strategy_id)
    if row is None:
        raise HTTPException(status_code=500, detail="Failed to create strategy")
    return _strategy_row_to_response(row)


@router.get("")
def list_strategies_endpoint(
    symbol: Optional[str] = None,
    source: Optional[str] = None,
    tags: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    limit: int = 100,
    db_path: Path = Depends(get_db_path),
) -> StrategyListResponse:
    """List strategies with filtering, sorting, and pagination."""
    # Count total (no limit)
    all_rows = list_strategies(
        db_path,
        symbol=symbol,
        source=source,
        tags=tags,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=10000,
    )
    total = len(all_rows)

    # Apply limit to results
    limited_rows = all_rows[:limit]
    items = [_strategy_row_to_response(r) for r in limited_rows]
    return StrategyListResponse(items=items, total=total)


@router.get("/{strategy_id}")
def get_strategy_endpoint(
    strategy_id: str,
    db_path: Path = Depends(get_db_path),
) -> StrategyResponse:
    """Get strategy details by ID."""
    row = get_strategy(db_path, strategy_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return _strategy_row_to_response(row)


@router.put("/{strategy_id}")
def update_strategy_endpoint(
    strategy_id: str,
    payload: StrategyUpdate,
    db_path: Path = Depends(get_db_path),
) -> StrategyResponse:
    """Update an existing strategy."""
    existing = get_strategy(db_path, strategy_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Strategy not found")

    fields: Dict[str, Any] = {}
    if payload.name is not None:
        fields["name"] = payload.name
    if payload.tags is not None:
        fields["tags"] = payload.tags
    if payload.notes is not None:
        fields["notes"] = payload.notes
    if payload.best_score is not None:
        fields["best_score"] = payload.best_score
    if payload.dna is not None:
        dna = _dna_model_to_dna(payload.dna)
        fields["dna_json"] = dna.to_json()

    if fields:
        update_strategy(db_path, strategy_id=strategy_id, **fields)

    row = get_strategy(db_path, strategy_id)
    return _strategy_row_to_response(row)


@router.delete("/{strategy_id}", status_code=204)
def delete_strategy_endpoint(
    strategy_id: str,
    db_path: Path = Depends(get_db_path),
) -> None:
    """Delete a strategy by ID."""
    existing = get_strategy(db_path, strategy_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    delete_strategy(db_path, strategy_id)


@router.post("/backtest")
def backtest_strategy(
    payload: BacktestRequest,
    db_path: Path = Depends(get_db_path),
    data_dir: Path = Depends(get_data_dir),
) -> BacktestResponse:
    """Run a backtest for a strategy.

    Supports two modes:
    - strategy_id: Load DNA from saved strategy
    - dna + symbol + timeframe: Use DNA directly (for Lab page)
    """
    # Resolve DNA and metadata
    if payload.strategy_id:
        row = get_strategy(db_path, payload.strategy_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Strategy not found")
        dna = StrategyDNA.from_json(row["dna_json"])
        symbol = row["symbol"]
        timeframe = row["timeframe"]
        strategy_id = payload.strategy_id
    elif payload.dna:
        dna = StrategyDNA.from_json(payload.dna.model_dump_json())
        symbol = payload.symbol or "UNKNOWN"
        timeframe = payload.timeframe or "1d"
        strategy_id = "inline"
    else:
        raise HTTPException(
            status_code=400,
            detail="Must provide either strategy_id or dna",
        )

    # Try to load the dataset
    parquet_path = data_dir / f"{payload.dataset_id}.parquet"
    if not parquet_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Dataset {payload.dataset_id} not found",
        )

    from core.data.storage import load_parquet

    engine = _bt_engine_mod.BacktestEngine(
        init_cash=payload.init_cash,
        fee=payload.fee,
        slippage=payload.slippage,
    )

    df = load_parquet(parquet_path)

    # Compute indicators needed by DNA signal genes
    from core.features.indicators import _compute_indicator
    for gene in dna.signal_genes:
        try:
            indicator_name = gene.indicator
            params = {k: v for k, v in gene.params.items()}
            indicator_df = _compute_indicator(df, indicator_name, params)
            for col in indicator_df.columns:
                if col not in df.columns:
                    df[col] = indicator_df[col]
        except Exception:
            continue

    result = engine.run(dna, df)

    # Compute score
    metrics = compute_metrics(result.equity_curve, total_trades=result.total_trades)
    score_result = score_strategy(metrics, template_name=payload.score_template)

    # Save result
    result_id = str(uuid.uuid4())
    if payload.strategy_id:
        save_backtest_result(
            db_path,
            result_id=result_id,
            strategy_id=strategy_id,
            symbol=symbol,
            timeframe=timeframe,
            data_start=str(df.index.min()) if len(df) > 0 else "",
            data_end=str(df.index.max()) if len(df) > 0 else "",
            init_cash=payload.init_cash,
            fee=payload.fee,
            slippage=payload.slippage,
            total_return=result.total_return,
            sharpe_ratio=result.sharpe_ratio,
            max_drawdown=result.max_drawdown,
            win_rate=result.win_rate,
            total_trades=result.total_trades,
            total_score=score_result["total_score"],
            template_name=payload.score_template,
            dimension_scores=json.dumps(score_result.get("dimension_scores", {})),
            run_source="lab",
        )

    # Build equity curve
    equity_data = None
    if result.equity_curve is not None and len(result.equity_curve) > 0:
        eq = result.equity_curve
        equity_data = [
            {"timestamp": str(idx), "value": float(val)}
            for idx, val in eq.items()
        ]

    # Build signals from trades
    signals_data = None
    if result.trades_df is not None and len(result.trades_df) > 0:
        signals_data = []
        for _, trade_row in result.trades_df.iterrows():
            entry_side = "buy"
            signals_data.append({
                "type": entry_side,
                "timestamp": str(trade_row.get("Entry Timestamp", "")),
                "price": float(trade_row.get("Avg Entry Price", 0)),
                "confidence": 0.8,
                "reason": f"Entry @ {float(trade_row.get('Avg Entry Price', 0)):.2f}",
            })
            signals_data.append({
                "type": "sell",
                "timestamp": str(trade_row.get("Exit Timestamp", "")),
                "price": float(trade_row.get("Avg Exit Price", 0)),
                "confidence": 0.8,
                "reason": f"Exit @ {float(trade_row.get('Avg Exit Price', 0)):.2f}",
            })

    return BacktestResponse(
        result_id=result_id,
        strategy_id=strategy_id,
        symbol=symbol,
        timeframe=timeframe,
        data_start=str(df.index.min()) if len(df) > 0 else None,
        data_end=str(df.index.max()) if len(df) > 0 else None,
        init_cash=payload.init_cash,
        fee=payload.fee,
        slippage=payload.slippage,
        total_return=result.total_return,
        sharpe_ratio=result.sharpe_ratio,
        max_drawdown=result.max_drawdown,
        win_rate=result.win_rate,
        total_trades=result.total_trades,
        total_score=score_result["total_score"],
        template_name=payload.score_template,
        dimension_scores=score_result.get("dimension_scores"),
        run_source="lab",
        equity_curve=equity_data,
        signals=signals_data,
    )


@router.post("/compare")
def compare_strategies(
    payload: CompareRequest,
    db_path: Path = Depends(get_db_path),
    data_dir: Path = Depends(get_data_dir),
) -> CompareResponse:
    """Compare multiple strategies by running backtests."""
    parquet_path = data_dir / f"{payload.dataset_id}.parquet"
    if not parquet_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Dataset {payload.dataset_id} not found",
        )

    from core.data.storage import load_parquet

    engine = _bt_engine_mod.BacktestEngine(
        init_cash=payload.init_cash,
        fee=payload.fee,
        slippage=payload.slippage,
    )

    df = load_parquet(parquet_path)
    results: List[CompareResultItem] = []

    for sid in payload.strategy_ids:
        row = get_strategy(db_path, sid)
        if row is None:
            results.append(CompareResultItem(
                strategy_id=sid,
                error="Strategy not found",
            ))
            continue

        try:
            dna = StrategyDNA.from_json(row["dna_json"])
            bt_result = engine.run(dna, df)
            metrics = compute_metrics(
                bt_result.equity_curve,
                total_trades=bt_result.total_trades,
            )
            score_result = score_strategy(
                metrics, template_name=payload.score_template,
            )

            result_id = str(uuid.uuid4())
            save_backtest_result(
                db_path,
                result_id=result_id,
                strategy_id=sid,
                symbol=row["symbol"],
                timeframe=row["timeframe"],
                data_start=str(df.index.min()) if len(df) > 0 else "",
                data_end=str(df.index.max()) if len(df) > 0 else "",
                init_cash=payload.init_cash,
                fee=payload.fee,
                slippage=payload.slippage,
                total_return=bt_result.total_return,
                sharpe_ratio=bt_result.sharpe_ratio,
                max_drawdown=bt_result.max_drawdown,
                win_rate=bt_result.win_rate,
                total_trades=bt_result.total_trades,
                total_score=score_result["total_score"],
                template_name=payload.score_template,
                dimension_scores=json.dumps(
                    score_result.get("dimension_scores", {})
                ),
                run_source="lab",
            )

            results.append(CompareResultItem(
                strategy_id=sid,
                result_id=result_id,
                total_return=bt_result.total_return,
                sharpe_ratio=bt_result.sharpe_ratio,
                max_drawdown=bt_result.max_drawdown,
                win_rate=bt_result.win_rate,
                total_trades=bt_result.total_trades,
                total_score=score_result["total_score"],
                dimension_scores=score_result.get("dimension_scores"),
            ))
        except Exception as exc:
            results.append(CompareResultItem(
                strategy_id=sid,
                error=str(exc),
            ))

    return CompareResponse(results=results)
