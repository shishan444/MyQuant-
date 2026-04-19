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
        self._population_count: int = 0  # Track continuous population count

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
        leverage = task_row.get("leverage", 1)
        direction = task_row.get("direction", "long")

        # Parse timeframe_pool from task config
        tf_pool_raw = task_row.get("timeframe_pool")
        tf_pool = None
        if tf_pool_raw:
            try:
                tf_pool = json.loads(tf_pool_raw) if isinstance(tf_pool_raw, str) else tf_pool_raw
            except (json.JSONDecodeError, Exception):
                tf_pool = None

        engine = EvolutionEngine(
            target_score=target_score,
            template_name=template,
            population_size=pop_size,
            max_generations=max_gens,
            leverage=leverage,
            direction=direction,
            timeframe_pool=tf_pool,
        )

        # Build a simple evaluate_fn that scores a DNA
        def evaluate_fn(individual: StrategyDNA) -> float:
            result = self._evaluate_dna(individual, task_row, leverage, direction)
            if isinstance(result, dict):
                individual._eval_diagnostics = result
                return result["score"]
            return result

        # Track mutations for logging
        last_mutations: List[str] = []
        gen_diagnostics: List[dict] = []

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

            # Compute generation-level diagnostics
            gen_diag = {}
            if gen_diagnostics:
                fallback_count = sum(1 for d in gen_diagnostics if d.get("fallback"))
                zero_trade_count = sum(1 for d in gen_diagnostics if d.get("total_trades", 0) == 0 and not d.get("fallback"))
                avg_trades = sum(d.get("total_trades", 0) for d in gen_diagnostics) / len(gen_diagnostics)
                gen_diag = {
                    "fallback_pct": round(fallback_count / len(gen_diagnostics) * 100, 1),
                    "zero_trade_pct": round(zero_trade_count / len(gen_diagnostics) * 100, 1),
                    "avg_trades": round(avg_trades, 1),
                }
            gen_diagnostics.clear()

            # Save history record with diagnostics
            top3_summary = f"best={best_score:.1f}"
            if gen_diag:
                top3_summary += f"|diag={json.dumps(gen_diag)}"
            save_history(self.db_path, task_id, gen, best_score, avg_score, top3_summary)

            # Save snapshot for each generation
            if hasattr(engine, '_population') and engine._population:
                try:
                    # Find best individual from current population
                    best_ind = engine._population[0]
                    save_snapshot(
                        self.db_path, task_id, gen,
                        best_score=best_score,
                        avg_score=avg_score,
                        best_dna=best_ind,
                        population=engine._population,
                        mutation_log=json.dumps(gen_diag) if gen_diag else None,
                    )
                except Exception:
                    pass

            # Update best_score in DB
            if best_score > 0:
                import sqlite3
                conn2 = sqlite3.connect(str(self.db_path))
                conn2.execute("PRAGMA journal_mode=WAL")
                conn2.execute(
                    "UPDATE evolution_task SET best_score = ? WHERE task_id = ? AND (best_score IS NULL OR best_score < ?)",
                    (best_score, task_id, best_score),
                )

                # Persist champion real metrics from best individual
                best_ind_diagnostics = None
                if hasattr(engine, '_population') and engine._population:
                    best_ind = engine._population[0]
                    best_ind_diagnostics = getattr(best_ind, '_eval_diagnostics', None)

                if best_ind_diagnostics and "raw_metrics" in best_ind_diagnostics:
                    metrics_json = json.dumps(best_ind_diagnostics["raw_metrics"])
                    dim_json = json.dumps(best_ind_diagnostics.get("dimension_scores", {}))
                    conn2.execute(
                        "UPDATE evolution_task SET champion_metrics = ?, champion_dimension_scores = ? WHERE task_id = ?",
                        (metrics_json, dim_json, task_id),
                    )

                conn2.commit()
                conn2.close()

            # Push WS update with champion DNA
            ws_payload = {
                "type": "generation_complete",
                "task_id": task_id,
                "generation": gen,
                "best_score": best_score,
                "avg_score": avg_score,
                "target_score": target_score,
                "max_generations": max_gens,
            }
            if hasattr(engine, '_population') and engine._population:
                best_ind = engine._population[0]
                if hasattr(best_ind, 'to_dict'):
                    ws_payload["champion_dna"] = best_ind.to_dict()
            _push_ws(task_id, ws_payload)

        try:
            result = engine.evolve(
                ancestor=dna,
                evaluate_fn=evaluate_fn,
                on_generation=on_generation,
            )

            champion = result["champion"]
            stop_reason = result["stop_reason"]

            # Continuous evolution loop: keep starting new populations
            # until user manually stops or an error occurs
            continuous = bool(task_row.get("continuous", 1))

            while continuous and stop_reason not in ("error",):
                from core.persistence.db import get_task
                t = get_task(self.db_path, task_id)
                if not t or t["status"] not in ("running", "pending"):
                    break

                self._population_count += 1
                logger.info(
                    "Task %s: starting population #%d (stop_reason=%s)",
                    task_id, self._population_count + 1, stop_reason,
                )

                # Reset for new population with champion as ancestor
                # Pass top-3 individuals as extra ancestors for multi-start
                extra_ancestors = []
                if champion is not None:
                    dna = champion
                    dna.mutation_ops = []
                    # Collect top-3 from previous population
                    if hasattr(engine, '_population') and engine._population:
                        seen_ids = {dna.strategy_id}
                        for ind in engine._population[:5]:
                            if ind.strategy_id not in seen_ids:
                                ind.mutation_ops = []
                                extra_ancestors.append(ind)
                                seen_ids.add(ind.strategy_id)
                                if len(extra_ancestors) >= 2:
                                    break
                engine._population = None

                result = engine.evolve(
                    ancestor=dna,
                    evaluate_fn=evaluate_fn,
                    on_generation=on_generation,
                    extra_ancestors=extra_ancestors if extra_ancestors else None,
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

                # Save final champion real metrics
                champion_diag = getattr(champion, '_eval_diagnostics', None)
                if champion_diag and "raw_metrics" in champion_diag:
                    import sqlite3
                    conn = sqlite3.connect(str(self.db_path))
                    conn.execute(
                        "UPDATE evolution_task SET champion_metrics = ?, champion_dimension_scores = ? WHERE task_id = ?",
                        (json.dumps(champion_diag["raw_metrics"]),
                         json.dumps(champion_diag.get("dimension_scores", {})),
                         task_id),
                    )
                    conn.commit()
                    conn.close()
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

    def _evaluate_dna(self, individual: StrategyDNA, task_row: Dict[str, Any],
                       leverage: int = 1, direction: str = "long") -> dict:
        """Score a DNA using backtesting against the dataset.

        Returns a dict with score and diagnostics.
        Falls back to random scoring if backtesting data is unavailable.
        """
        # Force override task-level constraints before backtesting
        individual.risk_genes.leverage = leverage
        # mixed mode: allow evolution to explore both directions
        if direction != "mixed":
            individual.risk_genes.direction = direction

        diagnostics = {
            "used_real_data": False,
            "data_bars": 0,
            "total_trades": 0,
            "fallback": True,
            "liquidated": False,
        }

        try:
            from core.backtest.engine import BacktestEngine
            from core.data.mtf_loader import load_and_prepare_df, load_mtf_data
            from core.strategy.executor import dna_to_signals
            from core.scoring.scorer import score_strategy

            symbol = task_row["symbol"]
            timeframe = task_row["execution_timeframe"] if "execution_timeframe" in task_row else task_row["timeframe"]

            # Load market data for the execution timeframe
            data_start = task_row.get("data_start")
            data_end = task_row.get("data_end")
            enhanced_df = load_and_prepare_df(
                self.data_dir, symbol, timeframe, data_start, data_end,
            )

            if enhanced_df is None:
                diagnostics["score"] = random.uniform(10, 50)
                return diagnostics

            diagnostics["used_real_data"] = True
            diagnostics["data_bars"] = len(enhanced_df)

            # Load multi-timeframe data if task has timeframe_pool
            dfs_by_timeframe = None
            tf_pool_raw = task_row.get("timeframe_pool")
            tf_pool = None
            if tf_pool_raw:
                try:
                    tf_pool = json.loads(tf_pool_raw) if isinstance(tf_pool_raw, str) else tf_pool_raw
                except (json.JSONDecodeError, Exception):
                    tf_pool = None

            if tf_pool and len(tf_pool) > 1:
                dfs_by_timeframe = load_mtf_data(
                    self.data_dir, symbol, timeframe, enhanced_df,
                    set(tf_pool), data_start, data_end,
                )

            entries, exits = dna_to_signals(individual, enhanced_df,
                                            dfs_by_timeframe=dfs_by_timeframe)

            if entries.sum() == 0:
                diagnostics["score"] = 5.0
                diagnostics["fallback"] = False
                return diagnostics

            bt = BacktestEngine()
            bt_result = bt.run(individual, enhanced_df,
                               dfs_by_timeframe=dfs_by_timeframe)

            from core.scoring.metrics import compute_metrics

            # Reuse trade-level data and bars_per_year from BacktestEngine
            metrics = compute_metrics(
                bt_result.equity_curve, total_trades=bt_result.total_trades,
                bars_per_year=bt_result.bars_per_year,
                trade_win_rate=bt_result.trade_win_rate,
                trade_returns=bt_result.trade_returns,
            )
            template_name = task_row.get("score_template", "profit_first")
            score_result = score_strategy(metrics, template_name)

            diagnostics["score"] = score_result["total_score"]
            diagnostics["total_trades"] = bt_result.total_trades
            diagnostics["fallback"] = False
            diagnostics["liquidated"] = bt_result.liquidated
            diagnostics["data_bars"] = bt_result.data_bars
            diagnostics["raw_metrics"] = score_result["raw_metrics"]
            diagnostics["dimension_scores"] = score_result["dimension_scores"]

            # Walk-Forward validation (only for high-score individuals)
            if task_row.get("walk_forward_enabled") and score_result["total_score"] > 40:
                try:
                    from core.backtest.walk_forward import WalkForwardValidator
                    wf = WalkForwardValidator(template_name=template_name)
                    wf_result = wf.validate(individual, enhanced_df)
                    if wf_result["wf_score"] > 0:
                        diagnostics["wf_score"] = wf_result["wf_score"]
                        diagnostics["wf_rounds"] = wf_result["n_rounds"]
                        if wf_result["rounds"]:
                            diagnostics["wf_train_score"] = wf_result["rounds"][0]["train_score"]
                            diagnostics["wf_val_score"] = wf_result["rounds"][0]["val_score"]
                except Exception:
                    pass  # WF failure should not block scoring

            return diagnostics

        except Exception:
            # Fallback: random score to keep evolution moving
            diagnostics["score"] = random.uniform(10, 40)
            return diagnostics


    def _find_parquet(self, safe_symbol: str, timeframe: str):
        """Find parquet file for a symbol+timeframe, trying aliases."""
        from core.data.mtf_loader import find_parquet
        return find_parquet(self.data_dir, safe_symbol, timeframe)


class _StopEvolution(Exception):
    """Signal to break out of the evolution loop."""
    pass
