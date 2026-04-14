"""Data management routes: datasets CRUD, CSV import, preview, OHLCV."""
from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from api.db_ext import (
    delete_dataset as db_delete_dataset,
    get_dataset,
    list_datasets,
    save_dataset_meta,
)
from api.deps import get_data_dir, get_db_path
from api.schemas import (
    DataImportResponse,
    DatasetListResponse,
    DatasetPreviewResponse,
    DatasetResponse,
    OhlcvResponse,
)
from core.data.csv_importer import import_csv, import_csv_batch, parse_filename, ImportMode
from core.data.storage import load_parquet

router = APIRouter(prefix="/api/data", tags=["data"])


@router.get("/datasets")
def list_datasets_endpoint(
    symbol: Optional[str] = None,
    interval: Optional[str] = None,
    limit: int = 100,
    db_path: Path = Depends(get_db_path),
) -> DatasetListResponse:
    """List datasets with optional filtering."""
    rows = list_datasets(db_path, symbol=symbol, interval=interval, limit=limit)
    items = [
        DatasetResponse(
            dataset_id=r["dataset_id"],
            symbol=r["symbol"],
            interval=r["interval"],
            parquet_path=r["parquet_path"],
            row_count=r.get("row_count", 0),
            time_start=r.get("time_start"),
            time_end=r.get("time_end"),
            file_size_bytes=r.get("file_size_bytes", 0),
            source=r.get("source", "csv_import"),
            format_detected=r.get("format_detected"),
            timestamp_precision=r.get("timestamp_precision"),
            quality_status=r.get("quality_status", "unknown"),
            quality_notes=r.get("quality_notes"),
            gap_count=r.get("gap_count", 0),
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
        for r in rows
    ]
    return DatasetListResponse(items=items, total=len(items))


@router.get("/datasets/{dataset_id}")
def get_dataset_endpoint(
    dataset_id: str,
    db_path: Path = Depends(get_db_path),
) -> DatasetResponse:
    """Get dataset details by ID."""
    row = get_dataset(db_path, dataset_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return DatasetResponse(
        dataset_id=row["dataset_id"],
        symbol=row["symbol"],
        interval=row["interval"],
        parquet_path=row["parquet_path"],
        row_count=row.get("row_count", 0),
        time_start=row.get("time_start"),
        time_end=row.get("time_end"),
        file_size_bytes=row.get("file_size_bytes", 0),
        source=row.get("source", "csv_import"),
        format_detected=row.get("format_detected"),
        timestamp_precision=row.get("timestamp_precision"),
        quality_status=row.get("quality_status", "unknown"),
        quality_notes=row.get("quality_notes"),
        gap_count=row.get("gap_count", 0),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.post("/import")
def import_csv_endpoint(
    file: UploadFile = File(...),
    symbol: Optional[str] = Form(None),
    interval: Optional[str] = Form(None),
    mode: str = Form("merge"),
    db_path: Path = Depends(get_db_path),
    data_dir: Path = Depends(get_data_dir),
) -> DataImportResponse:
    """Import a CSV file into Parquet storage."""
    # Save uploaded file to a temp location
    data_dir.mkdir(parents=True, exist_ok=True)

    original_stem = Path(file.filename).stem if file.filename else None
    prefix = original_stem + "-" if original_stem else None
    with tempfile.NamedTemporaryFile(
        suffix=".csv", prefix=prefix, delete=False, dir=data_dir
    ) as tmp:
        content = file.file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        import_mode = ImportMode(mode)
    except ValueError:
        import_mode = ImportMode.MERGE

    try:
        result = import_csv(
            path=tmp_path,
            data_dir=data_dir,
            symbol=symbol,
            interval=interval,
            mode=import_mode,
        )

        # Save dataset metadata
        parquet_path = data_dir / f"{result.dataset_id}.parquet"
        row_count = result.rows_imported
        file_size = parquet_path.stat().st_size if parquet_path.exists() else 0

        # Upsert dataset metadata
        existing = get_dataset(db_path, result.dataset_id)
        if existing is None:
            save_dataset_meta(
                db_path,
                dataset_id=result.dataset_id,
                symbol=result.symbol,
                interval=result.interval,
                parquet_path=str(parquet_path),
                row_count=row_count,
                time_start=result.time_range[0] if result.time_range else None,
                time_end=result.time_range[1] if result.time_range else None,
                file_size_bytes=file_size,
                source="csv_import",
                format_detected=result.format_detected.value,
                timestamp_precision=result.timestamp_precision.value,
            )
        else:
            from api.db_ext import update_dataset_stats
            update_dataset_stats(
                db_path,
                dataset_id=result.dataset_id,
                row_count=row_count,
                time_start=result.time_range[0] if result.time_range else None,
                time_end=result.time_range[1] if result.time_range else None,
                file_size_bytes=file_size,
                format_detected=result.format_detected.value,
                timestamp_precision=result.timestamp_precision.value,
            )

        return DataImportResponse(
            dataset_id=result.dataset_id,
            symbol=result.symbol,
            interval=result.interval,
            rows_imported=result.rows_imported,
            format_detected=result.format_detected.value,
            timestamp_precision=result.timestamp_precision.value,
            files_processed=result.files_processed,
            time_range=list(result.time_range) if result.time_range else None,
        )
    finally:
        # Clean up temp file
        tmp_path.unlink(missing_ok=True)


@router.post("/import-batch")
def import_csv_batch_endpoint(
    files: List[UploadFile] = File(...),
    symbol: Optional[str] = Form(None),
    interval: Optional[str] = Form(None),
    mode: str = Form("merge"),
    db_path: Path = Depends(get_db_path),
    data_dir: Path = Depends(get_data_dir),
) -> DataImportResponse:
    """Import multiple CSV files into a single Parquet dataset."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    data_dir.mkdir(parents=True, exist_ok=True)

    tmp_paths: list[Path] = []
    for f in files:
        # Use original filename stem as prefix so parse_filename can detect symbol/interval
        original_stem = Path(f.filename).stem if f.filename else None
        prefix = original_stem + "-" if original_stem else None
        tmp = tempfile.NamedTemporaryFile(
            suffix=".csv", prefix=prefix, delete=False, dir=data_dir
        )
        tmp.write(f.file.read())
        tmp.close()
        tmp_paths.append(Path(tmp.name))

    try:
        import_mode = ImportMode(mode)
    except ValueError:
        import_mode = ImportMode.MERGE

    try:
        result = import_csv_batch(
            paths=tmp_paths,
            data_dir=data_dir,
            symbol=symbol,
            interval=interval,
            mode=import_mode,
        )

        parquet_path = data_dir / f"{result.dataset_id}.parquet"
        row_count = result.rows_imported
        file_size = parquet_path.stat().st_size if parquet_path.exists() else 0

        existing = get_dataset(db_path, result.dataset_id)
        if existing is None:
            save_dataset_meta(
                db_path,
                dataset_id=result.dataset_id,
                symbol=result.symbol,
                interval=result.interval,
                parquet_path=str(parquet_path),
                row_count=row_count,
                time_start=result.time_range[0] if result.time_range else None,
                time_end=result.time_range[1] if result.time_range else None,
                file_size_bytes=file_size,
                source="csv_import",
                format_detected=result.format_detected.value,
                timestamp_precision=result.timestamp_precision.value,
            )
        else:
            from api.db_ext import update_dataset_stats
            update_dataset_stats(
                db_path,
                dataset_id=result.dataset_id,
                row_count=row_count,
                time_start=result.time_range[0] if result.time_range else None,
                time_end=result.time_range[1] if result.time_range else None,
                file_size_bytes=file_size,
                format_detected=result.format_detected.value,
                timestamp_precision=result.timestamp_precision.value,
            )

        return DataImportResponse(
            dataset_id=result.dataset_id,
            symbol=result.symbol,
            interval=result.interval,
            rows_imported=result.rows_imported,
            format_detected=result.format_detected.value,
            timestamp_precision=result.timestamp_precision.value,
            files_processed=result.files_processed,
            time_range=list(result.time_range) if result.time_range else None,
        )
    finally:
        for p in tmp_paths:
            p.unlink(missing_ok=True)


@router.delete("/datasets/{dataset_id}", status_code=204)
def delete_dataset_endpoint(
    dataset_id: str,
    db_path: Path = Depends(get_db_path),
) -> None:
    """Delete a dataset by ID."""
    row = get_dataset(db_path, dataset_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    db_delete_dataset(db_path, dataset_id)


@router.get("/datasets/{dataset_id}/preview")
def preview_dataset(
    dataset_id: str,
    limit: int = 20,
    db_path: Path = Depends(get_db_path),
    data_dir: Path = Depends(get_data_dir),
) -> DatasetPreviewResponse:
    """Preview the first N rows of a dataset."""
    row = get_dataset(db_path, dataset_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    parquet_path = Path(row["parquet_path"])
    if not parquet_path.exists():
        # Try data_dir fallback
        parquet_path = data_dir / f"{dataset_id}.parquet"

    if not parquet_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Parquet file not found on disk",
        )

    df = load_parquet(parquet_path)
    preview_df = df.head(limit)

    rows = []
    for idx, row_data in preview_df.iterrows():
        row_dict = {"timestamp": str(idx)}
        for col in row_data.index:
            val = row_data[col]
            # Convert numpy types to native Python types
            if hasattr(val, "item"):
                val = val.item()
            row_dict[col] = val
        rows.append(row_dict)

    return DatasetPreviewResponse(
        dataset_id=dataset_id,
        total_rows=len(df),
        rows=rows,
    )


@router.get("/datasets/{dataset_id}/ohlcv")
def get_ohlcv(
    dataset_id: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = 1000,
    db_path: Path = Depends(get_db_path),
    data_dir: Path = Depends(get_data_dir),
) -> OhlcvResponse:
    """Get OHLCV data for a dataset with optional time range filter."""
    row = get_dataset(db_path, dataset_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    parquet_path = Path(row["parquet_path"])
    if not parquet_path.exists():
        parquet_path = data_dir / f"{dataset_id}.parquet"

    if not parquet_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Parquet file not found on disk",
        )

    df = load_parquet(parquet_path)

    # Apply time range filter
    if start is not None:
        import pandas as pd
        start_ts = pd.Timestamp(start)
        df = df[df.index >= start_ts]
    if end is not None:
        import pandas as pd
        end_ts = pd.Timestamp(end)
        df = df[df.index <= end_ts]

    # Apply limit
    df = df.head(limit)

    ohlcv_data = []
    for idx, row_data in df.iterrows():
        ohlcv_data.append({
            "timestamp": str(idx),
            "open": float(row_data.get("open", 0)),
            "high": float(row_data.get("high", 0)),
            "low": float(row_data.get("low", 0)),
            "close": float(row_data.get("close", 0)),
            "volume": float(row_data.get("volume", 0)),
        })

    return OhlcvResponse(
        dataset_id=dataset_id,
        data=ohlcv_data,
    )
