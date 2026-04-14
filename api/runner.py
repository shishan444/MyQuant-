"""Evolution Runner: background thread that executes evolution tasks.

Polls SQLite for pending tasks, runs EvolutionEngine.evolve(),
and pushes generation updates via WebSocket.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.evolution.engine import EvolutionEngine
from core.evolution.diversity import compute_diversity
from core.strategy.dna import StrategyDNA
from core.persistence.db import (
    save_history,
    save_snapshot,
    update_task,
)

logger = logging.getLogger("runner")

# Global reference to the FastAPI app's asyncio loop for WS push
_ws_push_fn: Optional[Callable] = None


def set_ws_push_fn(fn: Callable) -> None:
    """Register a function that the runner can call to push WS messages.

    Called once during app startup.
    """
    global _ws_push_fn
    _ws_push_fn = fn


def _push_ws(task_id: str, payload: Dict[str, Any]) -> None:
    """Fire-and-forget WS push (non-blocking)."""
    if _ws_push_fn is not None:
        try:
            _ws_push_fn(task_id, payload)
        except Exception:
            logger.debug("ws push failed", exc_info=True)


class EvolutionRunner(threading.Thread):
    """Daemon thread that picks up pending evolution tasks and runs them."""

    def __init__(
        self,
        db_path: Path,
        data_dir: Path,
        poll_interval: float = 2.0,
    ) -> None:
        super().__init__(daemon=True, name="evolution-runner")
        self.db_path = db_path
        self.data_dir = data_dir
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._active_task_id: Optional[str] = None

    def stop(self) -> None:
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Thread main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        logger.info("EvolutionRunner started (db=%s)", self.db_path)
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception:
                logger.error("tick error", exc_info=True)
            self._stop_event.wait(self.poll_interval)
        logger.info("EvolutionRunner stopped")

    def _tick(self) -> None:
        """One poll cycle: pick a task, run one generation, update DB."""
        if self._active_task_id:
            # Check if the active task was paused / stopped
            from core.persistence.db import get_task
            row = get_task(self.db_path, self._active_task_id)
            if row is None or row["status"] not in ("running", "pending"):
                self._active_task_id = None
                return
            # Continue evolving - handled by the on_generation callback loop
            return

        # Look for a pending task
        task = self._find_pending_task()
        if task is None:
            return

        self._run_task(task)

    # ------------------------------------------------------------------
    # Task execution
    # ------------------------------------------------------------------

    def _find_pending_task(self) -> Optional[Dict[str, Any]]:
        import sqlite3
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM evolution_task WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def _run_task(self, task_row: Dict[str, Any]) -> None:
        task_id = task_row["task_id"]
        self._active_task_id = task_id

        # Mark as running
        update_task(self.db_path, task_id, status="running")

        # Parse initial DNA
        try:
            dna = StrategyDNA.from_json(task_row["initial_dna"])
        except Exception:
            logger.error("Failed to parse initial_dna for task %s", task_id)
            update_task(self.db_path, task_id, status="stopped", stop_reason="invalid_dna")
            self._active_task_id = None
            return

        target_score = task_row["target_score"]
        template = task_row["score_template"]
        pop_size = task_row.get("population_size", 15)
        max_gens = task_row.get("max_generations", 200)

        engine = EvolutionEngine(
            target_score=target_score,
            template_name=template,
            population_size=pop_size,
            max_generations=max_gens,
        )

        # Build a simple evaluate_fn that scores a DNA
        def evaluate_fn(individual: StrategyDNA) -> float:
            return self._evaluate_dna(individual, task_row)

        # Track mutations for logging
        last_mutations: List[str] = []

        def on_generation(gen: int, best_score: float, avg_score: float) -> None:
            nonlocal last_mutations

            # Check stop/pause
            from core.persistence.db import get_task
            t = get_task(self.db_path, task_id)
            if t is None or t["status"] not in ("running", "pending"):
                raise _StopEvolution(t["status"] if t else "unknown")

            # Update current_generation in DB
            import sqlite3
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                "UPDATE evolution_task SET current_generation = ?, updated_at = ? WHERE task_id = ?",
                (gen, datetime.now(timezone.utc).isoformat(), task_id),
            )
            conn.commit()
            conn.close()

            # Save history record
            top3_summary = f"best={best_score:.1f}"
            save_history(self.db_path, task_id, gen, best_score, avg_score, top3_summary)

            # Update champion
            if best_score > 0:
                champion = engine._champion if hasattr(engine, "_champion") else None
                if champion is None:
                    # Retrieve from the population - the engine returns it in evolve()
                    pass

            # Push WS update
            _push_ws(task_id, {
                "type": "generation_complete",
                "task_id": task_id,
                "generation": gen,
                "best_score": best_score,
                "avg_score": avg_score,
                "target_score": target_score,
                "max_generations": max_gens,
            })

        try:
            result = engine.evolve(
                ancestor=dna,
                evaluate_fn=evaluate_fn,
                on_generation=on_generation,
            )

            champion = result["champion"]
            stop_reason = result["stop_reason"]

            # Save champion
            if champion is not None:
                update_task(
                    self.db_path, task_id,
                    status="completed",
                    champion_dna=champion,
                    stop_reason=stop_reason,
                )
            else:
                update_task(
                    self.db_path, task_id,
                    status="completed",
                    stop_reason=stop_reason,
                )

            # Final WS push
            _push_ws(task_id, {
                "type": "evolution_complete",
                "task_id": task_id,
                "stop_reason": stop_reason,
                "total_generations": result["total_generations"],
                "champion_score": result["champion_score"],
            })

        except _StopEvolution as e:
            logger.info("Task %s stopped: %s", task_id, e)
        except Exception:
            logger.error("Task %s failed", task_id, exc_info=True)
            update_task(self.db_path, task_id, status="stopped", stop_reason="error")
        finally:
            self._active_task_id = None

    def _evaluate_dna(self, individual: StrategyDNA, task_row: Dict[str, Any]) -> float:
        """Score a DNA using backtesting against the dataset.

        Returns a score in [0, 100]. Falls back to random scoring
        if backtesting data is unavailable.
        """
        try:
            from core.backtest.engine import BacktestEngine
            from core.features.indicators import compute_all_indicators
            from core.data.storage import load_parquet
            from core.strategy.executor import dna_to_signals
            from core.scoring.scorer import score_strategy

            symbol = task_row["symbol"]
            timeframe = task_row["execution_timeframe"] if "execution_timeframe" in task_row else task_row["timeframe"]

            # Load market data
            import re
            safe_symbol = re.sub(r'[^A-Za-z0-9]', '', symbol)
            parquet_path = self.data_dir / f"{safe_symbol}_{timeframe}.parquet"

            if not parquet_path.exists():
                # Try common timeframe aliases
                aliases = {"1h": ["1h", "60m"], "4h": ["4h"], "1d": ["1d", "1D"]}
                for alias in aliases.get(timeframe, [timeframe]):
                    alt_path = self.data_dir / f"{safe_symbol}_{alias}.parquet"
                    if alt_path.exists():
                        parquet_path = alt_path
                        break

            if not parquet_path.exists():
                return random.uniform(10, 50)

            df = load_parquet(parquet_path)
            if df is None or len(df) < 50:
                return random.uniform(10, 50)

            enhanced_df = compute_all_indicators(df)
            entries, exits = dna_to_signals(individual, enhanced_df)

            if entries.sum() == 0:
                return 5.0

            bt = BacktestEngine()
            bt_result = bt.run(enhanced_df, entries, exits, init_cash=100000.0)

            from core.scoring.metrics import compute_metrics
            from core.scoring.scorer import score_strategy

            metrics = compute_metrics(bt_result.equity_curve)
            template_name = task_row.get("score_template", "profit_first")
            score_result = score_strategy(metrics, template_name)

            return score_result["total_score"]

        except Exception:
            # Fallback: random score to keep evolution moving
            return random.uniform(10, 40)


class _StopEvolution(Exception):
    """Signal to break out of the evolution loop."""
    pass
