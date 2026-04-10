"""Extended database operations for v0.8 schema.

Adds 3 new tables (strategy, backtest_result, dataset_meta),
extends evolution_task with 6 columns, and provides a
version-managed migration runner on top of core.persistence.db.

Public API:
    init_db_ext           -- run migrations to create/upgrade schema
    save_strategy / get_strategy / list_strategies / update_strategy / delete_strategy
    save_backtest_result / list_backtest_results / get_backtest_result
    save_dataset_meta / list_datasets / get_dataset / update_dataset_stats / delete_dataset
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from MyQuant.core.persistence.db import _connect, init_db

logger = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

# ---------------------------------------------------------------------------

# -- helpers --

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# -- migration runner --

def _get_applied_versions(conn: sqlite3.Connection) -> set[int]:
    """Return the set of already-applied migration version numbers."""
    try:
        rows = conn.execute(
            "SELECT version FROM schema_version"
        ).fetchall()
        return {r[0] for r in rows}
    except sqlite3.OperationalError:
        # table does not exist yet -- first run
        return set()


def _ensure_schema_version_table(conn: sqlite3.Connection) -> None:
    """Create the schema_version table if absent."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version     INTEGER PRIMARY KEY,
            applied_at  TEXT NOT NULL
        )
    """)


_ALTER_COLUMNS = [
    ("champion_strategy_id", "TEXT"),
    ("population_size",      "INTEGER DEFAULT 15"),
    ("max_generations",      "INTEGER DEFAULT 200"),
    ("elite_ratio",          "REAL DEFAULT 0.5"),
    ("n_workers",            "INTEGER DEFAULT 6"),
    ("current_generation",   "INTEGER DEFAULT 0"),
]


def _apply_alter_evolution_task(conn: sqlite3.Connection) -> None:
    """Add extended columns to evolution_task (idempotent)."""
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("PRAGMA table_info(evolution_task)")
    existing = {row[1] for row in cursor.fetchall()}
    conn.row_factory = None

    for col_name, col_def in _ALTER_COLUMNS:
        if col_name not in existing:
            conn.execute(
                f"ALTER TABLE evolution_task ADD COLUMN {col_name} {col_def}"
            )


def _record_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (?, ?)",
        (version, _now()),
    )


# -- public init --

def init_db_ext(db_path: Path) -> None:
    """Initialize the extended schema.

    Calls core ``init_db`` first, then runs any pending SQL migrations
    from the *migrations/* directory, plus the ALTER TABLE for extended
    evolution_task columns.

    Safe to call multiple times (idempotent).
    """
    # 1. Ensure core tables exist
    init_db(db_path)

    conn = _connect(db_path)
    try:
        _ensure_schema_version_table(conn)
        applied = _get_applied_versions(conn)

        # 2. Run numbered SQL migrations
        if _MIGRATIONS_DIR.is_dir():
            sql_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
            for sql_file in sql_files:
                # extract leading digits as version number
                version_str = ""
                for ch in sql_file.name:
                    if ch.isdigit():
                        version_str += ch
                    else:
                        break
                if not version_str:
                    continue
                version = int(version_str)
                if version in applied:
                    continue
                sql_text = sql_file.read_text(encoding="utf-8")
                # Skip migration 005 — handled separately via ALTER
                if version == 5:
                    continue
                conn.executescript(sql_text)
                _record_version(conn, version)
                logger.info("Applied migration %s", sql_file.name)

        # 3. Always ensure schema_version table is recorded
        if 1 not in applied:
            _record_version(conn, 1)

        # 4. ALTER TABLE for evolution_task extensions (migration 005)
        _apply_alter_evolution_task(conn)
        if 5 not in applied:
            _record_version(conn, 5)

        conn.commit()
    finally:
        conn.close()


# ===================================================================
# Strategy CRUD
# ===================================================================

def save_strategy(
    db_path: Path,
    *,
    strategy_id: str,
    dna_json: str,
    symbol: str,
    timeframe: str,
    name: Optional[str] = None,
    source: str = "manual",
    source_task_id: Optional[str] = None,
    best_score: Optional[float] = None,
    generation: int = 0,
    parent_ids: Optional[str] = None,
    tags: Optional[str] = None,
    notes: Optional[str] = None,
) -> None:
    """Insert a new strategy record."""
    now = _now()
    conn = _connect(db_path)
    conn.execute(
        """INSERT INTO strategy
           (strategy_id, name, dna_json, source, source_task_id, symbol, timeframe,
            best_score, generation, parent_ids, tags, notes, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (strategy_id, name, dna_json, source, source_task_id, symbol, timeframe,
         best_score, generation, parent_ids, tags, notes, now, now),
    )
    conn.commit()
    conn.close()


def get_strategy(db_path: Path, strategy_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a single strategy by ID, or None if not found."""
    conn = _connect(db_path)
    row = conn.execute(
        "SELECT * FROM strategy WHERE strategy_id = ?", (strategy_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def list_strategies(
    db_path: Path,
    *,
    symbol: Optional[str] = None,
    source: Optional[str] = None,
    tags: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """List strategies with optional filtering and sorting.

    Args:
        symbol: filter by trading pair (e.g. 'BTCUSDT').
        source: filter by origin (e.g. 'manual', 'evolution').
        tags: substring match against the tags column.
        sort_by: column name to sort by.
        sort_order: 'asc' or 'desc'.
        limit: maximum rows to return.
    """
    conditions: list[str] = []
    params: list[Any] = []

    if symbol is not None:
        conditions.append("symbol = ?")
        params.append(symbol)
    if source is not None:
        conditions.append("source = ?")
        params.append(source)
    if tags is not None:
        conditions.append("tags LIKE ?")
        params.append(f"%{tags}%")

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    order = f" ORDER BY {sort_by} {sort_order.upper()}"
    query = f"SELECT * FROM strategy{where}{order} LIMIT ?"
    params.append(limit)

    conn = _connect(db_path)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_strategy(
    db_path: Path,
    *,
    strategy_id: str,
    **fields: Any,
) -> None:
    """Update one or more fields on an existing strategy.

    Automatically refreshes ``updated_at``.
    """
    allowed = {
        "name", "dna_json", "source", "source_task_id", "symbol", "timeframe",
        "best_score", "generation", "parent_ids", "tags", "notes",
    }
    updates: list[str] = []
    params: list[Any] = []

    for key, value in fields.items():
        if key in allowed:
            updates.append(f"{key} = ?")
            params.append(value)

    if not updates:
        return

    updates.append("updated_at = ?")
    params.append(_now())
    params.append(strategy_id)

    conn = _connect(db_path)
    conn.execute(
        f"UPDATE strategy SET {', '.join(updates)} WHERE strategy_id = ?",
        params,
    )
    conn.commit()
    conn.close()


def delete_strategy(db_path: Path, strategy_id: str) -> None:
    """Delete a strategy by ID. No error if not found."""
    conn = _connect(db_path)
    conn.execute("DELETE FROM strategy WHERE strategy_id = ?", (strategy_id,))
    conn.commit()
    conn.close()


# ===================================================================
# Backtest Result
# ===================================================================

def save_backtest_result(
    db_path: Path,
    *,
    result_id: str,
    strategy_id: str,
    symbol: str,
    timeframe: str,
    data_start: str,
    data_end: str,
    init_cash: float = 100000.0,
    fee: float = 0.001,
    slippage: float = 0.0005,
    total_return: float = 0.0,
    sharpe_ratio: float = 0.0,
    max_drawdown: float = 0.0,
    win_rate: float = 0.0,
    total_trades: int = 0,
    total_score: float = 0.0,
    template_name: str = "profit_first",
    dimension_scores: Optional[str] = None,
    wf_score: Optional[float] = None,
    wf_rounds: int = 0,
    equity_curve: Optional[str] = None,
    trades_json: Optional[str] = None,
    run_source: str = "lab",
) -> None:
    """Insert a backtest result record."""
    now = _now()
    conn = _connect(db_path)
    conn.execute(
        """INSERT INTO backtest_result
           (result_id, strategy_id, symbol, timeframe, data_start, data_end,
            init_cash, fee, slippage, total_return, sharpe_ratio, max_drawdown,
            win_rate, total_trades, total_score, template_name, dimension_scores,
            wf_score, wf_rounds, equity_curve, trades_json, run_source, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (result_id, strategy_id, symbol, timeframe, data_start, data_end,
         init_cash, fee, slippage, total_return, sharpe_ratio, max_drawdown,
         win_rate, total_trades, total_score, template_name, dimension_scores,
         wf_score, wf_rounds, equity_curve, trades_json, run_source, now),
    )
    conn.commit()
    conn.close()


def get_backtest_result(db_path: Path, result_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a single backtest result by ID, or None if not found."""
    conn = _connect(db_path)
    row = conn.execute(
        "SELECT * FROM backtest_result WHERE result_id = ?", (result_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def list_backtest_results(
    db_path: Path,
    *,
    strategy_id: Optional[str] = None,
    symbol: Optional[str] = None,
    run_source: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """List backtest results with optional filtering and sorting."""
    conditions: list[str] = []
    params: list[Any] = []

    if strategy_id is not None:
        conditions.append("strategy_id = ?")
        params.append(strategy_id)
    if symbol is not None:
        conditions.append("symbol = ?")
        params.append(symbol)
    if run_source is not None:
        conditions.append("run_source = ?")
        params.append(run_source)

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    order = f" ORDER BY {sort_by} {sort_order.upper()}"
    query = f"SELECT * FROM backtest_result{where}{order} LIMIT ?"
    params.append(limit)

    conn = _connect(db_path)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ===================================================================
# Dataset Metadata CRUD
# ===================================================================

def save_dataset_meta(
    db_path: Path,
    *,
    dataset_id: str,
    symbol: str,
    interval: str,
    parquet_path: str,
    row_count: int = 0,
    time_start: Optional[str] = None,
    time_end: Optional[str] = None,
    file_size_bytes: int = 0,
    source: str = "csv_import",
    format_detected: Optional[str] = None,
    timestamp_precision: Optional[str] = None,
    ohlcv_stats: Optional[str] = None,
    gap_count: int = 0,
    quality_status: str = "unknown",
    quality_notes: Optional[str] = None,
    import_batch_id: Optional[str] = None,
) -> None:
    """Insert a dataset metadata record."""
    now = _now()
    conn = _connect(db_path)
    conn.execute(
        """INSERT INTO dataset_meta
           (dataset_id, symbol, interval, parquet_path, row_count, time_start,
            time_end, file_size_bytes, source, format_detected, timestamp_precision,
            ohlcv_stats, gap_count, quality_status, quality_notes, import_batch_id,
            last_import_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (dataset_id, symbol, interval, parquet_path, row_count, time_start,
         time_end, file_size_bytes, source, format_detected, timestamp_precision,
         ohlcv_stats, gap_count, quality_status, quality_notes, import_batch_id,
         now, now, now),
    )
    conn.commit()
    conn.close()


def get_dataset(db_path: Path, dataset_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a single dataset by ID, or None if not found."""
    conn = _connect(db_path)
    row = conn.execute(
        "SELECT * FROM dataset_meta WHERE dataset_id = ?", (dataset_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def list_datasets(
    db_path: Path,
    *,
    symbol: Optional[str] = None,
    interval: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """List datasets with optional filtering."""
    conditions: list[str] = []
    params: list[Any] = []

    if symbol is not None:
        conditions.append("symbol = ?")
        params.append(symbol)
    if interval is not None:
        conditions.append("interval = ?")
        params.append(interval)

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"SELECT * FROM dataset_meta{where} ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    conn = _connect(db_path)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_dataset_stats(
    db_path: Path,
    *,
    dataset_id: str,
    **fields: Any,
) -> None:
    """Update fields on a dataset record. Refreshes ``updated_at``."""
    allowed = {
        "row_count", "time_start", "time_end", "file_size_bytes",
        "format_detected", "timestamp_precision", "ohlcv_stats",
        "gap_count", "quality_status", "quality_notes", "import_batch_id",
        "last_import_at", "parquet_path",
    }
    updates: list[str] = []
    params: list[Any] = []

    for key, value in fields.items():
        if key in allowed:
            updates.append(f"{key} = ?")
            params.append(value)

    if not updates:
        return

    updates.append("updated_at = ?")
    params.append(_now())
    params.append(dataset_id)

    conn = _connect(db_path)
    conn.execute(
        f"UPDATE dataset_meta SET {', '.join(updates)} WHERE dataset_id = ?",
        params,
    )
    conn.commit()
    conn.close()


def delete_dataset(db_path: Path, dataset_id: str) -> None:
    """Delete a dataset by ID. No error if not found."""
    conn = _connect(db_path)
    conn.execute("DELETE FROM dataset_meta WHERE dataset_id = ?", (dataset_id,))
    conn.commit()
    conn.close()
