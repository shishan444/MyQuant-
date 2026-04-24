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
from core.evolution.diversity import compute_diversity, compute_phenotype_diversity, _gene_signature
from core.evolution.champion import ChampionTracker
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

        # Load market data once for all evaluations (saves ~1.8s per individual)
        from core.data.mtf_loader import load_and_prepare_df, load_mtf_data

        _symbol = task_row["symbol"]
        _timeframe = task_row["execution_timeframe"] if "execution_timeframe" in task_row else task_row["timeframe"]
        _data_start = task_row.get("data_start")
        _data_end = task_row.get("data_end")

        _enhanced_df = load_and_prepare_df(
            self.data_dir, _symbol, _timeframe, _data_start, _data_end,
        )
        if _enhanced_df is None:
            update_task(self.db_path, task_id, status="stopped", stop_reason="no_data")
            self._active_task_id = None
            return

        _dfs_by_timeframe = None
        if tf_pool and len(tf_pool) > 1:
            _dfs_by_timeframe = load_mtf_data(
                self.data_dir, _symbol, _timeframe, _enhanced_df,
                set(tf_pool), _data_start, _data_end,
            )

        # Build a simple evaluate_fn that scores a DNA
        # NOTE: direction is fixed to the task's original direction (e.g. "mixed").
        # Continuous evolution direction rotation only affects seed creation, NOT evaluation.
        _eval_direction = direction

        def evaluate_fn(individual: StrategyDNA) -> float:
            result = self._evaluate_dna(
                individual, task_row, leverage, _eval_direction,
                enhanced_df=_enhanced_df, dfs_by_timeframe=_dfs_by_timeframe,
            )
            if isinstance(result, dict):
                individual._eval_diagnostics = result
                return result["score"]
            return result

        # Track mutations for logging
        last_mutations: List[str] = []
        global_gen_offset = 0  # Offset for continuous mode: avoids history overwrite
        discovered_signatures: set = set()  # Signatures of auto-extracted strategies
        strategy_threshold = task_row.get("strategy_threshold", 80.0)
        champion_tracker = ChampionTracker()

        def on_generation(gen: int, best_score: float, avg_score: float) -> None:
            nonlocal last_mutations, global_gen_offset

            # Check stop/pause
            from core.persistence.db import get_task
            t = get_task(self.db_path, task_id)
            if t is None or t["status"] not in ("running", "pending"):
                raise _StopEvolution(t["status"] if t else "unknown")

            # Update current_generation in DB (use global offset for continuous mode)
            global_gen = gen + global_gen_offset
            import sqlite3
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                "UPDATE evolution_task SET current_generation = ?, updated_at = ? WHERE task_id = ?",
                (global_gen, datetime.now(timezone.utc).isoformat(), task_id),
            )
            conn.commit()
            conn.close()

            # Compute generation-level diagnostics from population
            gen_diag = {}
            if hasattr(engine, '_population') and engine._population:
                diags = [getattr(ind, '_eval_diagnostics', None) for ind in engine._population]
                diags = [d for d in diags if d]

                if diags:
                    avg_trades = sum(d.get("total_trades", 0) for d in diags) / len(diags)
                    phenotype_div = compute_phenotype_diversity(engine._population)
                    gen_diag = {
                        "avg_trades": round(avg_trades, 1),
                        "diversity": phenotype_div,
                    }

            # Save history record with diagnostics
            top3_summary = f"best={best_score:.1f}|pop={self._population_count + 1}"
            if gen_diag:
                top3_summary += f"|diag={json.dumps(gen_diag)}"
            save_history(self.db_path, task_id, global_gen, best_score, avg_score, top3_summary)

            # Save snapshot for each generation
            if hasattr(engine, '_population') and engine._population:
                try:
                    # Find best individual from current population
                    best_ind = engine._population[0]
                    save_snapshot(
                        self.db_path, task_id, global_gen,
                        best_score=best_score,
                        avg_score=avg_score,
                        best_dna=best_ind,
                        population=engine._population,
                        mutation_log=json.dumps(gen_diag) if gen_diag else None,
                    )
                except Exception:
                    pass

            # Update champion atomically via ChampionTracker
            if best_score > 0 and hasattr(engine, '_population') and engine._population:
                best_ind = engine._population[0]
                best_ind_diagnostics = getattr(best_ind, '_eval_diagnostics', None)

                if best_ind_diagnostics and "raw_metrics" in best_ind_diagnostics:
                    updated = champion_tracker.update(
                        score=best_score,
                        metrics=best_ind_diagnostics.get("raw_metrics"),
                        dimension_scores=best_ind_diagnostics.get("dimension_scores", {}),
                        generation=global_gen,
                    )

                    if updated:
                        champion_rec = champion_tracker.get_champion()
                        import sqlite3
                        conn2 = sqlite3.connect(str(self.db_path))
                        conn2.execute("PRAGMA journal_mode=WAL")
                        conn2.execute(
                            "UPDATE evolution_task SET best_score = ?, champion_metrics = ?, champion_dimension_scores = ? WHERE task_id = ?",
                            (
                                champion_rec.score,
                                json.dumps(champion_rec.metrics),
                                json.dumps(champion_rec.dimension_scores),
                                task_id,
                            ),
                        )
                        conn2.commit()
                        conn2.close()
                elif best_score > 0:
                    # No diagnostics but score is positive - update best_score only
                    updated = champion_tracker.update(score=best_score, generation=global_gen)
                    if updated:
                        import sqlite3
                        conn2 = sqlite3.connect(str(self.db_path))
                        conn2.execute("PRAGMA journal_mode=WAL")
                        conn2.execute(
                            "UPDATE evolution_task SET best_score = ? WHERE task_id = ? AND (best_score IS NULL OR best_score < ?)",
                            (best_score, task_id, best_score),
                        )
                        conn2.commit()
                        conn2.close()

            # Auto-extract high-scoring strategies to strategy table
            if hasattr(engine, '_population') and engine._population:
                for ind in engine._population:
                    diag = getattr(ind, '_eval_diagnostics', None)
                    if not diag or diag.get("score", 0) < strategy_threshold:
                        continue
                    sig = _gene_signature(ind)
                    if sig in discovered_signatures:
                        continue
                    discovered_signatures.add(sig)
                    try:
                        from api.db_ext import save_strategy
                        from core.strategy.dna import generate_strategy_name
                        name = generate_strategy_name(ind)
                        save_strategy(
                            self.db_path,
                            strategy_id=ind.strategy_id,
                            dna_json=ind.to_json(),
                            symbol=task_row.get("symbol", "BTCUSDT"),
                            timeframe=task_row.get("timeframe", "4h"),
                            name=name,
                            source="evolution",
                            source_task_id=task_id,
                            best_score=diag["score"],
                            gene_signature=sig,
                            generation=global_gen,
                            metrics_json=json.dumps(diag.get("raw_metrics")) if diag.get("raw_metrics") else None,
                        )
                        _push_ws(task_id, {
                            "type": "strategy_discovered",
                            "task_id": task_id,
                            "strategy_id": ind.strategy_id,
                            "score": diag["score"],
                            "name": name,
                            "generation": global_gen,
                        })
                    except Exception:
                        logger.debug("strategy extract failed", exc_info=True)

            # Push WS update with champion DNA
            ws_payload = {
                "type": "generation_complete",
                "task_id": task_id,
                "generation": global_gen,
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

                # Rotate direction for diversity in continuous mode
                original_direction = task_row.get("direction", "long")
                if original_direction == "mixed":
                    directions = ["long", "short"]
                    direction = directions[self._population_count % 2]
                    logger.info(
                        "Task %s: rotating direction to '%s' for population #%d",
                        task_id, direction, self._population_count + 1,
                    )

                logger.info(
                    "Task %s: starting population #%d (stop_reason=%s)",
                    task_id, self._population_count + 1, stop_reason,
                )

                # Notify frontend that a new population has started
                _push_ws(task_id, {
                    "type": "population_started",
                    "task_id": task_id,
                    "population_count": self._population_count + 1,
                    "best_score_ever": result.get("champion_score", 0) if result else 0,
                    "total_generations_so_far": global_gen_offset,
                })

                # Reset for new population with expanded search space
                # Inject diverse strategy templates to avoid searching the same region
                extra_ancestors = []
                if champion is not None:
                    dna = champion
                    dna.mutation_ops = []

                # Inject 2 random strategy templates as seeds (trend/momentum/mean-reversion etc.)
                # This expands the search space beyond the champion's strategy region
                from core.evolution.population import STRATEGY_TEMPLATES, _dna_from_template
                _tf = task_row.get("execution_timeframe", task_row.get("timeframe", "4h"))
                _sym = task_row.get("symbol", "BTCUSDT")
                template_seeds = random.sample(
                    STRATEGY_TEMPLATES, min(2, len(STRATEGY_TEMPLATES))
                )
                for tpl in template_seeds:
                    seed = _dna_from_template(
                        tpl, _tf, _sym, leverage, direction,
                    )
                    extra_ancestors.append(seed)

                # Collect signatures from previous population for dedup
                # MUST happen before setting _population = None
                if hasattr(engine, '_population') and engine._population:
                    for ind in engine._population:
                        discovered_signatures.add(_gene_signature(ind))
                    # Preserve top elites as ancestors for next population
                    extra_ancestors.extend(engine._population[:3])

                engine._population = None

                result = engine.evolve(
                    ancestor=dna,
                    evaluate_fn=evaluate_fn,
                    on_generation=on_generation,
                    extra_ancestors=extra_ancestors if extra_ancestors else None,
                    exclude_signatures=discovered_signatures,
                )
                champion = result["champion"]
                stop_reason = result["stop_reason"]
                # Accumulate global generation offset to prevent history overwrite
                global_gen_offset += result["total_generations"]

            # Save champion
            if champion is not None:
                update_task(
                    self.db_path, task_id,
                    status="completed",
                    champion_dna=champion,
                    stop_reason=stop_reason,
                )

                # Save final champion metrics from tracker (consistent snapshot)
                champion_rec = champion_tracker.get_champion()
                if champion_rec and champion_rec.metrics:
                    import sqlite3
                    conn = sqlite3.connect(str(self.db_path))
                    conn.execute(
                        "UPDATE evolution_task SET champion_metrics = ?, champion_dimension_scores = ? WHERE task_id = ?",
                        (json.dumps(champion_rec.metrics),
                         json.dumps(champion_rec.dimension_scores),
                         task_id),
                    )
                    conn.commit()
                    conn.close()

                # Walk-Forward validation on champion only (moved from per-individual)
                if champion_rec and champion_rec.score > 20:
                    try:
                        from core.backtest.walk_forward import WalkForwardValidator
                        template_name = task_row.get("score_template", "profit_first")
                        wf = WalkForwardValidator(template_name=template_name)
                        # Pass raw OHLCV data (without indicators) so each WF window
                        # recomputes indicators independently, eliminating look-ahead bias
                        _raw_cols = ["open", "high", "low", "close", "volume"]
                        _raw_wf_df = _enhanced_df[[
                            c for c in _raw_cols if c in _enhanced_df.columns
                        ]].copy()
                        wf_result = wf.validate(
                            champion, _enhanced_df, raw_df=_raw_wf_df,
                            dfs_by_timeframe=_dfs_by_timeframe,
                        )
                        if wf_result["wf_score"] > 0:
                            _wf_metrics = (champion_rec.metrics or {}).copy()
                            _wf_metrics["wf_score"] = wf_result["wf_score"]
                            _wf_metrics["wf_rounds"] = wf_result["n_rounds"]
                            import sqlite3
                            conn = sqlite3.connect(str(self.db_path))
                            conn.execute("PRAGMA journal_mode=WAL")
                            conn.execute(
                                "UPDATE evolution_task SET champion_metrics = ? WHERE task_id = ?",
                                (json.dumps(_wf_metrics), task_id),
                            )
                            conn.commit()
                            conn.close()
                            logger.info(
                                "Task %s: champion WF score=%.1f (%d rounds)",
                                task_id, wf_result["wf_score"], wf_result["n_rounds"],
                            )
                    except Exception:
                        logger.debug("WF validation failed for champion", exc_info=True)
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
                "generation": result["total_generations"],
                "best_score": result["champion_score"],
                "target_score": target_score,
                "max_generations": max_gens,
            })

        except _StopEvolution as e:
            logger.info("Task %s stopped: %s", task_id, e)
        except Exception:
            logger.error("Task %s failed", task_id, exc_info=True)
            update_task(self.db_path, task_id, status="stopped", stop_reason="error")
        finally:
            self._active_task_id = None

    def _evaluate_dna(self, individual: StrategyDNA, task_row: Dict[str, Any],
                       leverage: int = 1, direction: str = "long",
                       enhanced_df=None, dfs_by_timeframe=None) -> dict:
        """Score a DNA using backtesting against the dataset.

        Returns a dict with score and diagnostics.
        Accepts pre-loaded data to avoid redundant I/O per individual.
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
            from core.strategy.executor import dna_to_signal_set
            from core.scoring.scorer import score_strategy

            # Load data on demand if not pre-loaded (backward compatibility)
            if enhanced_df is None:
                from core.data.mtf_loader import load_and_prepare_df, load_mtf_data

                symbol = task_row["symbol"]
                timeframe = task_row["execution_timeframe"] if "execution_timeframe" in task_row else task_row["timeframe"]
                data_start = task_row.get("data_start")
                data_end = task_row.get("data_end")
                enhanced_df = load_and_prepare_df(
                    self.data_dir, symbol, timeframe, data_start, data_end,
                )

                if enhanced_df is None:
                    diagnostics["score"] = 0.0
                    return diagnostics

                # Load multi-timeframe data if task has timeframe_pool
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

            diagnostics["used_real_data"] = True
            diagnostics["data_bars"] = len(enhanced_df)

            # Compute signals once, pass to BacktestEngine to avoid double computation
            sig_set = dna_to_signal_set(individual, enhanced_df,
                                         dfs_by_timeframe=dfs_by_timeframe)

            if sig_set.entries.sum() == 0:
                diagnostics["score"] = 5.0
                diagnostics["fallback"] = False
                return diagnostics

            bt = BacktestEngine()
            bt_result = bt.run(individual, enhanced_df,
                               dfs_by_timeframe=dfs_by_timeframe,
                               signal_set=sig_set)

            # Use pre-computed metrics from BacktestEngine (avoids double computation)
            metrics = bt_result.metrics_dict
            template_name = task_row.get("score_template", "profit_first")
            score_result = score_strategy(metrics, template_name, liquidated=bt_result.liquidated)

            diagnostics["score"] = score_result["total_score"]
            diagnostics["total_trades"] = bt_result.total_trades
            diagnostics["fallback"] = False
            diagnostics["liquidated"] = bt_result.liquidated
            diagnostics["data_bars"] = bt_result.data_bars
            diagnostics["raw_metrics"] = score_result["raw_metrics"]
            diagnostics["dimension_scores"] = score_result["dimension_scores"]

            return diagnostics

        except Exception:
            # Fallback: zero score (not random noise)
            diagnostics["score"] = 0.0
            return diagnostics


    def _find_parquet(self, safe_symbol: str, timeframe: str):
        """Find parquet file for a symbol+timeframe, trying aliases."""
        from core.data.mtf_loader import find_parquet
        return find_parquet(self.data_dir, safe_symbol, timeframe)


class _StopEvolution(Exception):
    """Signal to break out of the evolution loop."""
    pass
