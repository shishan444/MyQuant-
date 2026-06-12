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

from core.persistence.db import _connect, init_db

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


_MTF_COLUMNS = [
    ("indicator_pool", "TEXT"),
    ("timeframe_pool", "TEXT"),
    ("mode", "TEXT"),
]

_STRATEGY_EXT_COLUMNS = [
    ("metrics_json", "TEXT"),  # JSON: {annual_return, sharpe_ratio, max_drawdown, win_rate, ...}
]

_CONSTRAINT_COLUMNS = [
    ("leverage", "INTEGER DEFAULT 1"),
    ("direction", "TEXT DEFAULT 'long'"),
    ("data_start", "TEXT"),
    ("data_end", "TEXT"),
    ("data_time_start", "TEXT"),
    ("data_time_end", "TEXT"),
    ("data_row_count", "INTEGER DEFAULT 0"),
    ("best_score", "REAL"),
    ("indicator_pool", "TEXT"),
    ("timeframe_pool", "TEXT"),
    ("mode", "TEXT"),
    ("champion_metrics", "TEXT"),
    ("champion_dimension_scores", "TEXT"),
    ("walk_forward_enabled", "INTEGER DEFAULT 0"),
    ("continuous", "INTEGER DEFAULT 1"),
]

_PROGRESS_COLUMNS = [
    ("current_phase", "TEXT DEFAULT 'idle'"),
    ("progress_json", "TEXT"),
    ("heartbeat_at", "TEXT"),
]

_SCORING_CONSTRAINT_COLUMNS = [
    ("min_annual_return", "REAL DEFAULT 0.10"),
    ("max_drawdown_limit", "REAL DEFAULT 0.10"),
]

# -- Fitness scoring columns (migration 021) --

_FITNESS_EVOLUTION_TASK_COLUMNS = [
    ("best_fitness",          "REAL"),
    ("champion_satisfaction",  "TEXT"),
    ("requirements_json",      "TEXT"),
    ("qualified_count",        "INTEGER DEFAULT 0"),
    ("target_fitness",         "REAL DEFAULT 1.0"),
]

_FITNESS_STRATEGY_COLUMNS = [
    ("best_fitness", "REAL"),
    ("qualified",    "INTEGER DEFAULT NULL"),
]

_FITNESS_BACKTEST_RESULT_COLUMNS = [
    ("fitness",          "REAL DEFAULT 0.0"),
    ("qualified",        "INTEGER DEFAULT 0"),
    ("satisfaction_json", "TEXT"),
]

_OOS_VALIDATION_COLUMNS = [
    ("oos_fitness",   "REAL"),
    ("oos_qualified", "INTEGER DEFAULT 0"),
    ("oos_metrics",   "TEXT"),
]

_VERIFY_STRATEGY_COLUMNS = [
    ("verify_count",      "INTEGER DEFAULT 0"),
    ("verify_avg_score",  "REAL"),
    ("verify_best_score", "REAL"),
    ("last_verified_at",  "TEXT"),
    ("verify_star",       "INTEGER DEFAULT NULL"),
]


def _apply_constraint_columns(conn: sqlite3.Connection) -> None:
    """Add leverage/direction and data range columns to evolution_task (idempotent)."""
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("PRAGMA table_info(evolution_task)")
    existing = {row[1] for row in cursor.fetchall()}
    conn.row_factory = None

    for col_name, col_def in _CONSTRAINT_COLUMNS:
        if col_name not in existing:
            conn.execute(
                f"ALTER TABLE evolution_task ADD COLUMN {col_name} {col_def}"
            )


def _apply_mtf_columns(conn: sqlite3.Connection) -> None:
    """Add MTF-related columns to evolution_task (idempotent)."""
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("PRAGMA table_info(evolution_task)")
    existing = {row[1] for row in cursor.fetchall()}
    conn.row_factory = None

    for col_name, col_def in _MTF_COLUMNS:
        if col_name not in existing:
            conn.execute(
                f"ALTER TABLE evolution_task ADD COLUMN {col_name} {col_def}"
            )


def _apply_progress_columns(conn: sqlite3.Connection) -> None:
    """Add progress tracking columns to evolution_task (idempotent)."""
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("PRAGMA table_info(evolution_task)")
    existing = {row[1] for row in cursor.fetchall()}
    conn.row_factory = None

    for col_name, col_def in _PROGRESS_COLUMNS:
        if col_name not in existing:
            conn.execute(
                f"ALTER TABLE evolution_task ADD COLUMN {col_name} {col_def}"
            )


def _apply_scoring_constraint_columns(conn: sqlite3.Connection) -> None:
    """Add min_annual_return and max_drawdown_limit to evolution_task (idempotent)."""
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("PRAGMA table_info(evolution_task)")
    existing = {row[1] for row in cursor.fetchall()}
    conn.row_factory = None

    for col_name, col_def in _SCORING_CONSTRAINT_COLUMNS:
        if col_name not in existing:
            conn.execute(
                f"ALTER TABLE evolution_task ADD COLUMN {col_name} {col_def}"
            )


def _apply_strategy_ext_columns(conn: sqlite3.Connection) -> None:
    """Add metrics_json column to strategy table (idempotent)."""
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("PRAGMA table_info(strategy)")
    existing = {row[1] for row in cursor.fetchall()}
    conn.row_factory = None

    for col_name, col_def in _STRATEGY_EXT_COLUMNS:
        if col_name not in existing:
            conn.execute(
                f"ALTER TABLE strategy ADD COLUMN {col_name} {col_def}"
            )


def _apply_fitness_columns(conn: sqlite3.Connection) -> None:
    """Add fitness scoring columns to evolution_task, strategy, and backtest_result (idempotent).

    Migration 021: new fitness-based scoring replaces score_strategy (0-100 weighted sum)
    with compute_fitness (satisfaction ratio product + qualified boolean gate).
    Old columns are kept for backward compatibility.
    """
    tables_columns = [
        ("evolution_task", _FITNESS_EVOLUTION_TASK_COLUMNS),
        ("strategy", _FITNESS_STRATEGY_COLUMNS),
        ("backtest_result", _FITNESS_BACKTEST_RESULT_COLUMNS),
    ]
    for table_name, columns in tables_columns:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        existing = {row[1] for row in cursor.fetchall()}
        conn.row_factory = None
        for col_name, col_def in columns:
            if col_name not in existing:
                conn.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}"
                )


def _apply_oos_validation_columns(conn: sqlite3.Connection) -> None:
    """Add OOS validation columns to evolution_task (idempotent).

    Migration 022: out-of-sample validation columns for champion strategies.
    """
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("PRAGMA table_info(evolution_task)")
    existing = {row[1] for row in cursor.fetchall()}
    conn.row_factory = None
    for col_name, col_def in _OOS_VALIDATION_COLUMNS:
        if col_name not in existing:
            conn.execute(
                f"ALTER TABLE evolution_task ADD COLUMN {col_name} {col_def}"
            )


# -- Verify session columns (migration 023) --

_VERIFY_SESSION_BT_COLUMNS = [
    ("session_id", "TEXT"),
]


def _create_verify_session_table(conn: sqlite3.Connection) -> None:
    """Create verify_session table (idempotent)."""
    conn.execute("""CREATE TABLE IF NOT EXISTS verify_session (
        session_id       TEXT PRIMARY KEY,
        status           TEXT NOT NULL DEFAULT 'running',
        strategy_ids     TEXT NOT NULL,
        data_ranges      TEXT NOT NULL,
        init_cash        REAL NOT NULL DEFAULT 100000,
        fee              REAL NOT NULL DEFAULT 0.001,
        slippage         REAL NOT NULL DEFAULT 0.0005,
        summary_json     TEXT,
        total_results    INTEGER DEFAULT 0,
        total_strategies INTEGER DEFAULT 0,
        error_message    TEXT,
        created_at       TEXT NOT NULL,
        completed_at     TEXT
    )""")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_verify_session_created "
        "ON verify_session(created_at DESC)"
    )


def _apply_verify_session_columns(conn: sqlite3.Connection) -> None:
    """Add session_id column to backtest_result (idempotent)."""
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("PRAGMA table_info(backtest_result)")
    existing = {row[1] for row in cursor.fetchall()}
    conn.row_factory = None
    for col_name, col_def in _VERIFY_SESSION_BT_COLUMNS:
        if col_name not in existing:
            conn.execute(
                f"ALTER TABLE backtest_result ADD COLUMN {col_name} {col_def}"
            )


def _apply_verify_strategy_columns(conn: sqlite3.Connection) -> None:
    """Add verification summary columns to strategy (idempotent).

    Migration 024: track how many times a strategy has been verified,
    its average and best comprehensive scores, and last verification time.
    """
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("PRAGMA table_info(strategy)")
    existing = {row[1] for row in cursor.fetchall()}
    conn.row_factory = None
    for col_name, col_def in _VERIFY_STRATEGY_COLUMNS:
        if col_name not in existing:
            conn.execute(
                f"ALTER TABLE strategy ADD COLUMN {col_name} {col_def}"
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
                # Skip migration 005/006 — handled separately via ALTER
                if version in (5, 6):
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

        # 5. ALTER TABLE for MTF support (migration 006)
        _apply_mtf_columns(conn)
        if 6 not in applied:
            _record_version(conn, 6)

        # 6. ALTER TABLE for task-level constraints (migration 007)
        _apply_constraint_columns(conn)
        if 7 not in applied:
            _record_version(conn, 7)

        # 7. ALTER TABLE for strategy metrics column
        _apply_strategy_ext_columns(conn)
        if 8 not in applied:
            _record_version(conn, 8)

        # 8. ALTER TABLE for progress tracking columns (migration 009)
        _apply_progress_columns(conn)
        if 9 not in applied:
            _record_version(conn, 9)

        # 9. Paper trading tables (migration 010)
        _create_paper_trading_tables(conn)
        if 10 not in applied:
            _record_version(conn, 10)

        # 10. Paper equity snapshot table (migration 011)
        _create_equity_snapshot_table(conn)
        if 11 not in applied:
            _record_version(conn, 11)

        # 11. Scoring constraint columns (migration 012)
        _apply_scoring_constraint_columns(conn)
        if 12 not in applied:
            _record_version(conn, 12)

        # 12. Execution model column (migration 013)
        _apply_execution_model_column(conn)
        if 13 not in applied:
            _record_version(conn, 13)

        # 13. Bars held column (migration 014)
        _apply_bars_held_column(conn)
        if 14 not in applied:
            _record_version(conn, 14)

        # 14. Position open cost column (migration 015)
        _apply_position_open_cost_column(conn)
        if 15 not in applied:
            _record_version(conn, 15)

        # 15. Pending decision column (migration 016)
        _apply_pending_decision_column(conn)
        if 16 not in applied:
            _record_version(conn, 16)

        # 16. Confidence sizing column (migration 017)
        _apply_confidence_sizing_column(conn)
        if 17 not in applied:
            _record_version(conn, 17)

        # 17. Prediction DNA column (migration 018)
        _apply_prediction_dna_column(conn)
        if 18 not in applied:
            _record_version(conn, 18)

        # 18. Deduplicate strategies (migration 019)
        _dedup_strategies(conn)
        if 19 not in applied:
            _record_version(conn, 19)

        # 19. Recompute strategy names to include MTF layers (migration 020)
        _recompute_strategy_names(conn)
        if 20 not in applied:
            _record_version(conn, 20)

        # 20. Fitness scoring columns (migration 021)
        _apply_fitness_columns(conn)
        if 21 not in applied:
            _record_version(conn, 21)

        # 21. OOS validation columns (migration 022)
        _apply_oos_validation_columns(conn)
        if 22 not in applied:
            _record_version(conn, 22)

        # 22. Verify session table + session_id column (migration 023)
        _create_verify_session_table(conn)
        _apply_verify_session_columns(conn)
        if 23 not in applied:
            _record_version(conn, 23)

        # 23. Strategy verification summary columns (migration 024)
        _apply_verify_strategy_columns(conn)
        if 24 not in applied:
            _record_version(conn, 24)

        # 24. Strategy verification star column (migration 025)
        _apply_verify_strategy_columns(conn)
        if 25 not in applied:
            _record_version(conn, 25)

        conn.commit()
    finally:
        conn.close()


# ===================================================================
# Strategy dedup cleanup (migration 019)
# ===================================================================

def _dedup_strategies(conn: sqlite3.Connection) -> None:
    """Remove duplicate strategies, keeping the one with the highest best_score per gene_signature."""
    try:
        # Find duplicates: gene_signature appears more than once
        dup_sigs = conn.execute(
            """SELECT gene_signature FROM strategy
               WHERE gene_signature IS NOT NULL
               GROUP BY gene_signature
               HAVING COUNT(*) > 1"""
        ).fetchall()
        if not dup_sigs:
            return

        for (sig,) in dup_sigs:
            # Get all rows with this signature, ordered by best_score DESC (NULLs last)
            rows = conn.execute(
                """SELECT strategy_id, best_score FROM strategy
                   WHERE gene_signature = ?
                   ORDER BY CASE WHEN best_score IS NULL THEN 1 ELSE 0 END, best_score DESC""",
                (sig,),
            ).fetchall()
            # Keep the first (highest score), delete the rest
            keep_id = rows[0][0]
            delete_ids = [r[0] for r in rows[1:]]
            if delete_ids:
                placeholders = ",".join("?" * len(delete_ids))
                conn.execute(
                    f"DELETE FROM strategy WHERE strategy_id IN ({placeholders})",
                    delete_ids,
                )
        logger.info("Deduped %d strategy signatures", len(dup_sigs))
    except Exception:
        logger.warning("Strategy dedup failed", exc_info=True)


def _recompute_strategy_names(conn: sqlite3.Connection) -> None:
    """Recompute all strategy names to include MTF layer data in the hash."""
    try:
        from core.strategy.dna import StrategyDNA, generate_strategy_name

        rows = conn.execute(
            "SELECT strategy_id, dna_json FROM strategy WHERE dna_json IS NOT NULL"
        ).fetchall()
        updated = 0
        for strategy_id, dna_json in rows:
            try:
                dna = StrategyDNA.from_json(dna_json)
                new_name = generate_strategy_name(dna)
                conn.execute(
                    "UPDATE strategy SET name = ? WHERE strategy_id = ?",
                    (new_name, strategy_id),
                )
                updated += 1
            except Exception:
                continue
        if updated:
            logger.info("Recomputed %d strategy names", updated)
    except Exception:
        logger.warning("Strategy name recomputation failed", exc_info=True)
# ===================================================================

def _create_paper_trading_tables(conn: sqlite3.Connection) -> None:
    """Create paper_trading_task and paper_trade tables (idempotent)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS paper_trading_task (
            task_id          TEXT PRIMARY KEY,
            status           TEXT NOT NULL DEFAULT 'pending',
            strategy_name    TEXT,
            symbol           TEXT NOT NULL DEFAULT 'BTCUSDT',
            timeframe        TEXT NOT NULL DEFAULT '4h',
            initial_cash     REAL NOT NULL DEFAULT 100000,
            fee              REAL NOT NULL DEFAULT 0.001,
            leverage         INTEGER NOT NULL DEFAULT 1,
            direction        TEXT NOT NULL DEFAULT 'long',
            dna_json         TEXT NOT NULL,
            score_template   TEXT DEFAULT 'explorer',
            created_at       TEXT NOT NULL,
            updated_at       TEXT NOT NULL,
            started_at       TEXT,
            stopped_at       TEXT,
            stop_reason      TEXT,
            -- Position state (for recovery)
            position_side     TEXT,
            position_entry    REAL,
            position_quantity REAL,
            position_margin   REAL,
            position_funding  REAL DEFAULT 0,
            -- Account state
            balance          REAL,
            unrealized_pnl   REAL DEFAULT 0,
            -- Stats
            total_trades     INTEGER DEFAULT 0,
            total_pnl        REAL DEFAULT 0,
            win_count        INTEGER DEFAULT 0,
            loss_count       INTEGER DEFAULT 0,
            -- Last processed bar
            last_bar_time    TEXT,
            last_bar_close   REAL,
            -- Heartbeat
            heartbeat_at     TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS paper_trade (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id     TEXT NOT NULL,
            bar_time    TEXT NOT NULL,
            side        TEXT NOT NULL,
            action      TEXT NOT NULL,
            price       REAL NOT NULL,
            quantity    REAL NOT NULL,
            pnl         REAL,
            fee_paid    REAL DEFAULT 0,
            reason      TEXT,
            FOREIGN KEY (task_id) REFERENCES paper_trading_task(task_id)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_paper_trade_task
        ON paper_trade(task_id, bar_time)
    """)


def _apply_execution_model_column(conn: sqlite3.Connection) -> None:
    """Add execution_model column to paper_trading_task (idempotent)."""
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("PRAGMA table_info(paper_trading_task)")
    existing = {row[1] for row in cursor.fetchall()}
    conn.row_factory = None
    if "execution_model" not in existing:
        conn.execute(
            "ALTER TABLE paper_trading_task ADD COLUMN execution_model TEXT DEFAULT 'v1'"
        )


def _apply_bars_held_column(conn: sqlite3.Connection) -> None:
    """Add bars_held column to paper_trading_task (idempotent)."""
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("PRAGMA table_info(paper_trading_task)")
    existing = {row[1] for row in cursor.fetchall()}
    conn.row_factory = None
    if "bars_held" not in existing:
        conn.execute(
            "ALTER TABLE paper_trading_task ADD COLUMN bars_held INTEGER DEFAULT 0"
        )


def _apply_position_open_cost_column(conn: sqlite3.Connection) -> None:
    """Add position_open_cost column to paper_trading_task (idempotent)."""
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("PRAGMA table_info(paper_trading_task)")
    existing = {row[1] for row in cursor.fetchall()}
    conn.row_factory = None
    if "position_open_cost" not in existing:
        conn.execute(
            "ALTER TABLE paper_trading_task ADD COLUMN position_open_cost REAL DEFAULT 0"
        )


def _apply_pending_decision_column(conn: sqlite3.Connection) -> None:
    """Add pending_decision_json column to paper_trading_task (idempotent)."""
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("PRAGMA table_info(paper_trading_task)")
    existing = {row[1] for row in cursor.fetchall()}
    conn.row_factory = None
    if "pending_decision_json" not in existing:
        conn.execute(
            "ALTER TABLE paper_trading_task ADD COLUMN pending_decision_json TEXT"
        )


def _apply_confidence_sizing_column(conn: sqlite3.Connection) -> None:
    """Add confidence_sizing_enabled column to paper_trading_task (idempotent)."""
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("PRAGMA table_info(paper_trading_task)")
    existing = {row[1] for row in cursor.fetchall()}
    conn.row_factory = None
    if "confidence_sizing_enabled" not in existing:
        conn.execute(
            "ALTER TABLE paper_trading_task ADD COLUMN confidence_sizing_enabled INTEGER DEFAULT 0"
        )


def _apply_prediction_dna_column(conn: sqlite3.Connection) -> None:
    """Add prediction_dna_json column to paper_trading_task (idempotent)."""
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("PRAGMA table_info(paper_trading_task)")
    existing = {row[1] for row in cursor.fetchall()}
    conn.row_factory = None
    if "prediction_dna_json" not in existing:
        conn.execute(
            "ALTER TABLE paper_trading_task ADD COLUMN prediction_dna_json TEXT"
        )


def _create_equity_snapshot_table(conn: sqlite3.Connection) -> None:
    """Create paper_equity_snapshot table (idempotent)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS paper_equity_snapshot (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id         TEXT NOT NULL,
            timestamp       TEXT NOT NULL,
            equity          REAL NOT NULL,
            balance         REAL NOT NULL,
            unrealized_pnl  REAL DEFAULT 0,
            position_side   TEXT DEFAULT 'flat'
        )
    """)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_equity_task_time
        ON paper_equity_snapshot(task_id, timestamp)
    """)


# -- Paper Trading Task CRUD --

def save_paper_trading_task(
    db_path: Path,
    *,
    task_id: str,
    dna_json: str,
    symbol: str = "BTCUSDT",
    timeframe: str = "4h",
    initial_cash: float = 100_000,
    fee: float = 0.001,
    leverage: int = 1,
    direction: str = "long",
    score_template: str = "explorer",
    strategy_name: Optional[str] = None,
    confidence_sizing_enabled: bool = False,
    prediction_dna_json: Optional[str] = None,
) -> None:
    now = _now()
    with _connect(db_path) as conn:
        conn.execute(
            """INSERT INTO paper_trading_task
               (task_id, status, strategy_name, symbol, timeframe,
                initial_cash, fee, leverage, direction, dna_json,
                score_template, created_at, updated_at, balance,
                execution_model, confidence_sizing_enabled, prediction_dna_json)
               VALUES (?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'v2', ?, ?)""",
            (task_id, strategy_name, symbol, timeframe,
             initial_cash, fee, leverage, direction, dna_json,
             score_template, now, now, initial_cash,
             int(confidence_sizing_enabled), prediction_dna_json),
        )
        conn.commit()


def get_paper_trading_task(db_path: Path, task_id: str) -> Optional[Dict[str, Any]]:
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM paper_trading_task WHERE task_id = ?", (task_id,)
        ).fetchone()
        return dict(row) if row else None


_ALLOWED_COLUMNS = frozenset({
    "status", "started_at", "stopped_at", "stop_reason", "heartbeat_at",
    "position_side", "position_entry", "position_quantity", "position_margin",
    "position_funding", "position_open_cost", "balance", "unrealized_pnl",
    "total_trades", "total_pnl", "win_count", "loss_count", "bars_held",
    "last_bar_time", "last_bar_close", "execution_model", "pending_decision_json",
    "prediction_dna_json", "updated_at",
})


def update_paper_trading_task(db_path: Path, task_id: str, **kwargs) -> None:
    if not kwargs:
        return
    # Filter to allowed columns only
    filtered = {k: v for k, v in kwargs.items() if k in _ALLOWED_COLUMNS}
    if not filtered:
        return
    filtered["updated_at"] = _now()
    sets = ", ".join(f"{k} = ?" for k in filtered)
    vals = list(filtered.values()) + [task_id]
    with _connect(db_path) as conn:
        conn.execute(
            f"UPDATE paper_trading_task SET {sets} WHERE task_id = ?", vals
        )
        conn.commit()


def list_paper_trading_tasks(
    db_path: Path, status: Optional[str] = None, limit: int = 50, offset: int = 0,
) -> List[Dict[str, Any]]:
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if status:
            rows = conn.execute(
                "SELECT * FROM paper_trading_task WHERE status = ? "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (status, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM paper_trading_task ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(r) for r in rows]


def count_paper_trading_tasks(
    db_path: Path, status: Optional[str] = None,
) -> int:
    """Return total count of paper trading tasks, optionally filtered by status."""
    with _connect(db_path) as conn:
        if status:
            row = conn.execute(
                "SELECT COUNT(*) FROM paper_trading_task WHERE status = ?",
                (status,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) FROM paper_trading_task"
            ).fetchone()
        return row[0]


def save_paper_trade(
    db_path: Path,
    *,
    task_id: str,
    bar_time: str,
    side: str,
    action: str,
    price: float,
    quantity: float,
    pnl: Optional[float] = None,
    fee_paid: float = 0.0,
    reason: Optional[str] = None,
) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """INSERT INTO paper_trade
               (task_id, bar_time, side, action, price, quantity, pnl, fee_paid, reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (task_id, bar_time, side, action, price, quantity, pnl, fee_paid, reason),
        )
        conn.commit()


def list_paper_trades(
    db_path: Path, task_id: str, limit: int = 100,
) -> List[Dict[str, Any]]:
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM paper_trade WHERE task_id = ? "
            "ORDER BY bar_time DESC LIMIT ?",
            (task_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def count_paper_trades(db_path: Path, task_id: str) -> int:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM paper_trade WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        return row[0]


# -- Paper Equity Snapshot CRUD --

def save_equity_snapshots(
    db_path: Path, task_id: str, snapshots: list[dict],
) -> None:
    """Batch insert equity snapshots for a task."""
    if not snapshots:
        return
    with _connect(db_path) as conn:
        conn.executemany(
            """INSERT OR IGNORE INTO paper_equity_snapshot
               (task_id, timestamp, equity, balance, unrealized_pnl, position_side)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                (task_id, s["timestamp"], s["equity"], s["balance"],
                 s.get("unrealized_pnl", 0.0), s.get("position_side", "flat"))
                for s in snapshots
            ],
        )
        conn.commit()


def list_equity_snapshots(
    db_path: Path, task_id: str,
) -> List[Dict[str, Any]]:
    """Return all equity snapshots for a task in chronological order."""
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM paper_equity_snapshot WHERE task_id = ? "
            "ORDER BY timestamp ASC",
            (task_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_paper_trading_task(db_path: Path, task_id: str) -> bool:
    """Delete a paper trading task and all associated data."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT task_id FROM paper_trading_task WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        if row is None:
            return False
        conn.execute("DELETE FROM paper_equity_snapshot WHERE task_id = ?", (task_id,))
        conn.execute("DELETE FROM paper_trade WHERE task_id = ?", (task_id,))
        conn.execute("DELETE FROM paper_trading_task WHERE task_id = ?", (task_id,))
        conn.commit()
        return True


def _compute_equity(task: dict, balance: float) -> float:
    """Compute equity from balance + position_margin + unrealized_pnl."""
    if not task.get("position_side"):
        return balance
    margin = task.get("position_margin") or 0.0
    pnl = task.get("unrealized_pnl") or 0.0
    return balance + margin + pnl


def compute_trading_metrics(db_path: Path, task_id: str) -> Optional[Dict[str, Any]]:
    """Compute performance metrics for a paper trading task."""
    task = get_paper_trading_task(db_path, task_id)
    if task is None:
        return None

    initial_cash = task["initial_cash"]
    balance = task.get("balance") if task.get("balance") is not None else initial_cash
    total_trades = task.get("total_trades", 0)
    win_count = task.get("win_count", 0)
    loss_count = task.get("loss_count", 0)

    # Use equity for total_pnl to include all costs (open/close fees + slippage)
    equity = _compute_equity(task, balance)
    total_pnl = equity - initial_cash

    # Win rate
    win_rate = win_count / max(total_trades, 1)

    # Compute gross profit / gross loss from trades
    gross_profit = 0.0
    gross_loss = 0.0
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT pnl FROM paper_trade WHERE task_id = ? AND pnl IS NOT NULL AND action = 'close'",
            (task_id,),
        ).fetchall()
        for r in rows:
            if r[0] > 0:
                gross_profit += r[0]
            else:
                gross_loss += r[0]

    profit_factor = gross_profit / max(abs(gross_loss), 1e-8) if gross_loss != 0 else float("inf")

    # Max drawdown from equity snapshots
    max_drawdown = 0.0
    max_drawdown_pct = 0.0
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT equity FROM paper_equity_snapshot WHERE task_id = ? ORDER BY timestamp ASC",
            (task_id,),
        ).fetchall()
        if rows:
            peak = rows[0][0]
            for r in rows:
                eq = r[0]
                if eq > peak:
                    peak = eq
                dd = peak - eq
                if dd > max_drawdown:
                    max_drawdown = dd
                    max_drawdown_pct = dd / peak if peak > 0 else 0.0

    # Use equity (balance + margin + unrealized_pnl) for return calculation
    # balance alone excludes locked margin, giving misleading -100% when in position
    equity = _compute_equity(task, balance)
    total_return = equity / initial_cash - 1 if initial_cash > 0 else 0.0
    avg_trade_pnl = total_pnl / max(total_trades, 1)

    unrealized_pnl = task.get("unrealized_pnl", 0.0) or 0.0

    return {
        "task_id": task_id,
        "total_return": round(total_return, 6),
        "total_return_pct": round(total_return * 100, 2),
        "win_rate": round(win_rate, 4),
        "profit_factor": round(profit_factor, 4) if profit_factor != float("inf") else None,
        "max_drawdown": round(max_drawdown, 2),
        "max_drawdown_pct": round(max_drawdown_pct * 100, 2),
        "avg_trade_pnl": round(avg_trade_pnl, 2),
        "total_trades": total_trades,
        "total_pnl": round(total_pnl, 2),
        "realized_pnl": round(task.get("total_pnl", 0.0) or 0.0, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "win_count": win_count,
        "loss_count": loss_count,
    }


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
    metrics_json: Optional[str] = None,
    gene_signature: Optional[str] = None,
) -> None:
    """Insert a new strategy record. Deduplicates by gene_signature.

    If a strategy with the same gene_signature already exists, keeps the one
    with the higher best_score.
    """
    # Compute gene_signature from DNA if not provided
    if gene_signature is None:
        try:
            from core.strategy.dna import StrategyDNA
            from core.evolution.diversity import _gene_signature
            dna = StrategyDNA.from_json(dna_json)
            gene_signature = _gene_signature(dna)
        except Exception:
            gene_signature = None

    now = _now()
    conn = _connect(db_path)

    # Dedup by gene_signature: keep the higher-scoring version.
    if gene_signature:
        existing = conn.execute(
            "SELECT strategy_id, best_score FROM strategy WHERE gene_signature = ? LIMIT 1",
            (gene_signature,),
        ).fetchone()
        if existing:
            existing_id, existing_score = existing[0], existing[1]
            new_is_better = (
                best_score is not None
                and (existing_score is None or best_score > existing_score)
            )
            if new_is_better:
                # New strategy is better: replace the old one
                conn.execute(
                    """UPDATE strategy SET
                       strategy_id=?, name=?, dna_json=?, source=?, source_task_id=?,
                       symbol=?, timeframe=?, best_score=?, generation=?, parent_ids=?,
                       tags=?, notes=?, metrics_json=?, gene_signature=?, updated_at=?
                       WHERE strategy_id=?""",
                    (strategy_id, name, dna_json, source, source_task_id, symbol, timeframe,
                     best_score, generation, parent_ids, tags, notes, metrics_json,
                     gene_signature, now, existing_id),
                )
                conn.commit()
            conn.close()
            return

    conn.execute(
        """INSERT INTO strategy
           (strategy_id, name, dna_json, source, source_task_id, symbol, timeframe,
            best_score, generation, parent_ids, tags, notes, metrics_json,
            gene_signature, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (strategy_id, name, dna_json, source, source_task_id, symbol, timeframe,
         best_score, generation, parent_ids, tags, notes, metrics_json,
         gene_signature, now, now),
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


def count_strategies_by_tasks(
    db_path: Path,
    task_ids: List[str],
    min_score: float = 0,
) -> Dict[str, int]:
    """Batch count strategies per task_id.

    Returns {task_id: count} for strategies with best_score >= min_score.
    """
    if not task_ids:
        return {}
    conn = _connect(db_path)
    placeholders = ",".join("?" for _ in task_ids)
    rows = conn.execute(
        f"""SELECT source_task_id, COUNT(*) as cnt
           FROM strategy
           WHERE source_task_id IN ({placeholders})
             AND source = 'evolution'
             AND best_score >= ?
           GROUP BY source_task_id""",
        (*task_ids, min_score),
    ).fetchall()
    conn.close()
    result: Dict[str, int] = {tid: 0 for tid in task_ids}
    for r in rows:
        result[r["source_task_id"]] = r["cnt"]
    return result


_SORT_ALLOWED_COLUMNS = {
    "created_at", "updated_at", "best_score", "best_fitness",
    "name", "symbol", "timeframe", "source", "generation",
}
_SORT_ALLOWED_ORDERS = {"asc", "desc"}


def _build_strategy_where(
    *,
    symbol: Optional[str] = None,
    source: Optional[str] = None,
    source_task_id: Optional[str] = None,
    tags: Optional[str] = None,
    qualified: Optional[bool] = None,
) -> tuple[str, list[Any]]:
    conditions: list[str] = []
    params: list[Any] = []

    if symbol is not None:
        conditions.append("symbol = ?")
        params.append(symbol)
    if source is not None:
        conditions.append("source = ?")
        params.append(source)
    if source_task_id is not None:
        conditions.append("source_task_id = ?")
        params.append(source_task_id)
    if tags is not None:
        conditions.append("tags LIKE ?")
        params.append(f"%{tags}%")
    if qualified is not None:
        conditions.append("qualified = ?")
        params.append(1 if qualified else 0)

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    return where, params


def count_strategies(
    db_path: Path,
    *,
    symbol: Optional[str] = None,
    source: Optional[str] = None,
    source_task_id: Optional[str] = None,
    tags: Optional[str] = None,
    qualified: Optional[bool] = None,
) -> int:
    where, params = _build_strategy_where(
        symbol=symbol, source=source, source_task_id=source_task_id,
        tags=tags, qualified=qualified,
    )
    conn = _connect(db_path)
    row = conn.execute(f"SELECT COUNT(*) FROM strategy{where}", params).fetchone()
    conn.close()
    return row[0]


def list_strategies(
    db_path: Path,
    *,
    symbol: Optional[str] = None,
    source: Optional[str] = None,
    source_task_id: Optional[str] = None,
    tags: Optional[str] = None,
    qualified: Optional[bool] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """List strategies with optional filtering, sorting, and pagination."""
    if sort_by not in _SORT_ALLOWED_COLUMNS:
        raise ValueError(f"Invalid sort_by: {sort_by!r}. Allowed: {sorted(_SORT_ALLOWED_COLUMNS)}")
    if sort_order.lower() not in _SORT_ALLOWED_ORDERS:
        raise ValueError(f"Invalid sort_order: {sort_order!r}. Allowed: asc, desc")

    where, params = _build_strategy_where(
        symbol=symbol, source=source, source_task_id=source_task_id,
        tags=tags, qualified=qualified,
    )
    order = f" ORDER BY {sort_by} {sort_order.upper()}"
    query = f"SELECT * FROM strategy{where}{order} LIMIT ? OFFSET ?"
    params.extend([limit, offset])

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
        "best_score", "generation", "parent_ids", "tags", "notes", "metrics_json",
        "verify_count", "verify_avg_score", "verify_best_score", "last_verified_at", "verify_star",
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
    template_name: str = "explorer",
    dimension_scores: Optional[str] = None,
    equity_curve: Optional[str] = None,
    trades_json: Optional[str] = None,
    run_source: str = "lab",
    fitness: float = 0.0,
    qualified: int = 0,
    satisfaction_json: Optional[str] = None,
    session_id: Optional[str] = None,
) -> None:
    """Insert a backtest result record."""
    now = _now()
    conn = _connect(db_path)
    conn.execute(
        """INSERT INTO backtest_result
           (result_id, strategy_id, symbol, timeframe, data_start, data_end,
            init_cash, fee, slippage, total_return, sharpe_ratio, max_drawdown,
            win_rate, total_trades, total_score, template_name, dimension_scores,
            equity_curve, trades_json, run_source, created_at,
            fitness, qualified, satisfaction_json, session_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                   ?, ?, ?, ?)""",
        (result_id, strategy_id, symbol, timeframe, data_start, data_end,
         init_cash, fee, slippage, total_return, sharpe_ratio, max_drawdown,
         win_rate, total_trades, total_score, template_name, dimension_scores,
         equity_curve, trades_json, run_source, now,
         fitness, qualified, satisfaction_json, session_id),
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
# Verify Session CRUD
# ===================================================================

def save_verify_session(
    db_path: Path,
    *,
    session_id: str,
    strategy_ids: str,
    data_ranges: str,
    init_cash: float = 100000.0,
    fee: float = 0.001,
    slippage: float = 0.0005,
    status: str = "running",
) -> None:
    conn = _connect(db_path)
    conn.execute(
        """INSERT INTO verify_session
           (session_id, status, strategy_ids, data_ranges,
            init_cash, fee, slippage, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (session_id, status, strategy_ids, data_ranges,
         init_cash, fee, slippage, _now()),
    )
    conn.commit()
    conn.close()


def get_verify_session(db_path: Path, session_id: str) -> Optional[Dict[str, Any]]:
    conn = _connect(db_path)
    row = conn.execute(
        "SELECT * FROM verify_session WHERE session_id = ?", (session_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_verify_session(
    db_path: Path,
    session_id: str,
    *,
    status: Optional[str] = None,
    summary_json: Optional[str] = None,
    total_results: Optional[int] = None,
    total_strategies: Optional[int] = None,
    error_message: Optional[str] = None,
    completed_at: Optional[str] = None,
) -> None:
    fields: Dict[str, Any] = {}
    if status is not None:
        fields["status"] = status
    if summary_json is not None:
        fields["summary_json"] = summary_json
    if total_results is not None:
        fields["total_results"] = total_results
    if total_strategies is not None:
        fields["total_strategies"] = total_strategies
    if error_message is not None:
        fields["error_message"] = error_message
    if completed_at is not None:
        fields["completed_at"] = completed_at
    if not fields:
        return
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn = _connect(db_path)
    conn.execute(
        f"UPDATE verify_session SET {sets} WHERE session_id = ?",
        (*fields.values(), session_id),
    )
    conn.commit()
    conn.close()


def list_verify_sessions(
    db_path: Path,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    conn = _connect(db_path)
    rows = conn.execute(
        "SELECT * FROM verify_session ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
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
