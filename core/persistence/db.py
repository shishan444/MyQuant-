"""SQLite database layer for evolution persistence.

3 tables:
- evolution_task: one row per evolution run
- generation_snapshot: full population per generation (for checkpoint resume)
- evolution_history: lightweight score records (for UI charts)
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.strategy.dna import StrategyDNA


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path) -> None:
    """Create tables if not exist."""
    conn = _connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS evolution_task (
            task_id         TEXT PRIMARY KEY,
            status          TEXT NOT NULL DEFAULT 'running',
            target_score    REAL NOT NULL,
            score_template  TEXT NOT NULL,
            symbol          TEXT NOT NULL,
            timeframe       TEXT NOT NULL,
            initial_dna     TEXT NOT NULL,
            champion_dna    TEXT,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL,
            stop_reason     TEXT
        );

        CREATE TABLE IF NOT EXISTS generation_snapshot (
            task_id         TEXT NOT NULL,
            generation      INTEGER NOT NULL,
            best_score      REAL NOT NULL,
            avg_score       REAL NOT NULL,
            best_dna        TEXT NOT NULL,
            population_json TEXT NOT NULL,
            mutation_log    TEXT,
            wf_months       TEXT,
            created_at      TEXT NOT NULL,
            PRIMARY KEY (task_id, generation)
        );

        CREATE TABLE IF NOT EXISTS evolution_history (
            task_id         TEXT NOT NULL,
            generation      INTEGER NOT NULL,
            best_score      REAL NOT NULL,
            avg_score       REAL NOT NULL,
            top3_summary    TEXT NOT NULL,
            created_at      TEXT NOT NULL,
            PRIMARY KEY (task_id, generation)
        );
    """)
    # Migration: add strategy_threshold column if missing
    try:
        conn.execute("ALTER TABLE evolution_task ADD COLUMN strategy_threshold REAL DEFAULT 80.0")
    except Exception:
        pass  # Column already exists
    conn.commit()
    conn.close()

def save_task(
    db_path: Path,
    task_id: str,
    target_score: float,
    template: str,
    symbol: str,
    timeframe: str,
    initial_dna: StrategyDNA,
) -> None:
    """Create a new evolution task."""
    now = _now()
    conn = _connect(db_path)
    conn.execute(
        """INSERT INTO evolution_task
           (task_id, status, target_score, score_template, symbol, timeframe,
            initial_dna, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (task_id, "running", target_score, template, symbol, timeframe,
         initial_dna.to_json(), now, now),
    )
    conn.commit()
    conn.close()


def update_task(
    db_path: Path,
    task_id: str,
    status: Optional[str] = None,
    champion_dna: Optional[StrategyDNA] = None,
    stop_reason: Optional[str] = None,
) -> None:
    """Update task status, champion, or stop reason."""
    conn = _connect(db_path)
    updates = ["updated_at = ?"]
    params: list = [_now()]

    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if champion_dna is not None:
        updates.append("champion_dna = ?")
        params.append(champion_dna.to_json())
    if stop_reason is not None:
        updates.append("stop_reason = ?")
        params.append(stop_reason)

    params.append(task_id)
    conn.execute(
        f"UPDATE evolution_task SET {', '.join(updates)} WHERE task_id = ?",
        params,
    )
    conn.commit()
    conn.close()


def get_task(db_path: Path, task_id: str) -> Optional[Dict[str, Any]]:
    """Get a task by ID."""
    conn = _connect(db_path)
    row = conn.execute(
        "SELECT * FROM evolution_task WHERE task_id = ?", (task_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def get_running_task(db_path: Path) -> Optional[Dict[str, Any]]:
    """Get the currently running task (if any)."""
    conn = _connect(db_path)
    row = conn.execute(
        "SELECT * FROM evolution_task WHERE status = 'running' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


# ── Snapshot operations ──

def save_snapshot(
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
    """Save a generation snapshot for checkpoint resume."""
    pop_json = json.dumps([ind.to_dict() for ind in population])
    now = _now()
    conn = _connect(db_path)
    conn.execute(
        """INSERT OR REPLACE INTO generation_snapshot
           (task_id, generation, best_score, avg_score, best_dna,
            population_json, mutation_log, wf_months, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (task_id, generation, best_score, avg_score, best_dna.to_json(),
         pop_json, mutation_log, wf_months, now),
    )
    conn.commit()
    conn.close()


def get_latest_snapshot(db_path: Path, task_id: str) -> Optional[Dict[str, Any]]:
    """Get the latest generation snapshot for a task."""
    conn = _connect(db_path)
    row = conn.execute(
        """SELECT * FROM generation_snapshot
           WHERE task_id = ? ORDER BY generation DESC LIMIT 1""",
        (task_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


# ── History operations ──

def save_history(
    db_path: Path,
    task_id: str,
    generation: int,
    best_score: float,
    avg_score: float,
    top3_summary: str,
) -> None:
    """Save a lightweight history record."""
    now = _now()
    conn = _connect(db_path)
    conn.execute(
        """INSERT OR REPLACE INTO evolution_history
           (task_id, generation, best_score, avg_score, top3_summary, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (task_id, generation, best_score, avg_score, top3_summary, now),
    )
    conn.commit()
    conn.close()


def get_history(db_path: Path, task_id: str) -> List[Dict[str, Any]]:
    """Get all history records for a task, ordered by generation."""
    conn = _connect(db_path)
    rows = conn.execute(
        "SELECT * FROM evolution_history WHERE task_id = ? ORDER BY generation",
        (task_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_all_tasks(
    db_path: Path,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """List tasks, optionally filtered by status, ordered by creation time desc."""
    conn = _connect(db_path)
    if status is not None:
        rows = conn.execute(
            "SELECT * FROM evolution_task WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (status, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM evolution_task ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_all_tasks(
    db_path: Path,
    status: Optional[str] = None,
) -> int:
    """Count total tasks, optionally filtered by status."""
    conn = _connect(db_path)
    if status is not None:
        row = conn.execute(
            "SELECT COUNT(*) FROM evolution_task WHERE status = ?",
            (status,),
        ).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) FROM evolution_task").fetchone()
    conn.close()
    return row[0] if row else 0
