"""Paper Trading Runner: background thread that executes paper trading tasks.

Polls SQLite for pending tasks, loads strategy DNA, processes real-time
bars through PositionManager, and pushes updates via WebSocket.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logging import get_logger
from core.strategy.dna import StrategyDNA
from core.strategy.executor import dna_to_signal_set
from core.data.mtf_loader import load_and_prepare_df
from core.data.updater import update_market_data
from core.trading.position import PositionManager, Position

logger = get_logger("TRADING_RUNNER")

# Borrowed from runner.py for WS push
_ws_push_fn = None
_active_controllers: Dict[str, "TaskController"] = {}


def set_trading_ws_push_fn(fn) -> None:
    global _ws_push_fn
    _ws_push_fn = fn


def get_trading_controllers() -> Dict[str, "TaskController"]:
    return _active_controllers


class TaskStopRequested(Exception):
    pass


class TaskController:
    def __init__(self) -> None:
        self._stop_event = threading.Event()

    def request_stop(self) -> None:
        self._stop_event.set()

    @property
    def stop_requested(self) -> bool:
        return self._stop_event.is_set()

    def check_stop(self) -> None:
        if self._stop_event.is_set():
            raise TaskStopRequested()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _push_ws(task_id: str, payload: dict) -> None:
    if _ws_push_fn is not None:
        try:
            _ws_push_fn(task_id, payload)
        except Exception:
            logger.warning("WS push failed for trading task %s", task_id, exc_info=True)


def recover_stale_trading_tasks(db_path: Path) -> None:
    """Mark running paper trading tasks as stopped (crash recovery)."""
    from core.persistence.db import _connect
    with _connect(db_path) as conn:
        result = conn.execute(
            "UPDATE paper_trading_task SET status = 'stopped', "
            "stop_reason = 'crash_recovery', updated_at = ? "
            "WHERE status = 'running'",
            (_now_iso(),),
        )
        conn.commit()
        if result.rowcount > 0:
            logger.info("Recovered %d stale trading tasks", result.rowcount)


# Seconds between polls for new data per timeframe
_BAR_SECONDS = {
    "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400, "1d": 86400,
}


class TradingRunner(threading.Thread):
    """Daemon thread that picks up pending paper trading tasks and runs them."""

    def __init__(
        self,
        db_path: Path,
        data_dir: Path,
        poll_interval: float = 2.0,
    ) -> None:
        super().__init__(daemon=True, name="trading-runner")
        self.db_path = db_path
        self.data_dir = data_dir
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._active_task_id: Optional[str] = None

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        logger.info("TradingRunner started (db=%s)", self.db_path)
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception:
                logger.error("tick error", exc_info=True)
            self._stop_event.wait(self.poll_interval)
        logger.info("TradingRunner stopped")

    def get_status(self) -> dict:
        return {
            "is_alive": self.is_alive(),
            "active_task_id": self._active_task_id,
        }

    def _tick(self) -> None:
        if self._active_task_id:
            # Check if active task was stopped/paused externally
            row = self._get_task(self._active_task_id)
            if row is None or row["status"] not in ("running", "pending"):
                self._active_task_id = None
            return

        task = self._find_pending_task()
        if task:
            self._run_task(task)

    def _find_pending_task(self) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM paper_trading_task "
            "WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def _get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM paper_trading_task WHERE task_id = ?", (task_id,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def _run_task(self, task_row: Dict[str, Any]) -> None:
        task_id = task_row["task_id"]
        self._active_task_id = task_id
        controller = TaskController()
        _active_controllers[task_id] = controller

        try:
            self._execute_task(task_row, task_id, controller)
        except TaskStopRequested:
            logger.info("Trading task %s stopped via controller", task_id)
            self._update_status(task_id, "stopped", "user_stop")
        except Exception:
            logger.error("Trading task %s failed", task_id, exc_info=True)
            self._update_status(task_id, "stopped", "error")
        finally:
            self._active_task_id = None
            _active_controllers.pop(task_id, None)

    def _update_status(self, task_id: str, status: str, reason: str = None) -> None:
        from api.db_ext import update_paper_trading_task
        kwargs = {"status": status}
        if reason:
            kwargs["stop_reason"] = reason
        if status == "stopped":
            kwargs["stopped_at"] = _now_iso()
        update_paper_trading_task(self.db_path, task_id, **kwargs)

    def _execute_task(
        self,
        task_row: Dict[str, Any],
        task_id: str,
        controller: TaskController,
    ) -> None:
        from api.db_ext import (
            update_paper_trading_task, save_paper_trade, list_paper_trades,
        )

        # Mark running
        update_paper_trading_task(
            self.db_path, task_id, status="running", started_at=_now_iso(),
        )
        _push_ws(task_id, {
            "type": "task_started",
            "task_id": task_id,
        })

        # Parse DNA
        dna = StrategyDNA.from_json(task_row["dna_json"])
        symbol = task_row["symbol"]
        timeframe = task_row["timeframe"]
        init_cash = task_row["initial_cash"]
        fee = task_row["fee"]

        # Create PositionManager
        pm = PositionManager(dna, init_cash=init_cash, fee=fee, slippage=0.0005)

        # Restore position state if resuming
        self._restore_pm_state(pm, task_row)

        # Load historical data and compute signals
        controller.check_stop()
        df = self._load_data(symbol, timeframe)
        if df is None or df.empty:
            self._update_status(task_id, "stopped", "no_data")
            return

        from core.features.indicators import compute_all_indicators
        df = compute_all_indicators(df)
        sig_set = dna_to_signal_set(dna, df)

        # Replay through PM up to last_bar_time
        last_bar_time = task_row.get("last_bar_time")
        start_idx = self._find_replay_start(df, last_bar_time)

        # Apply shift(1) to replay signals to prevent look-ahead bias
        # (mirrors backtest engine behavior)
        replay_entries = sig_set.entries.shift(1).fillna(False)
        replay_exits = sig_set.exits.shift(1).fillna(False)
        replay_adds = sig_set.adds.shift(1).fillna(False)
        replay_reduces = sig_set.reduces.shift(1).fillna(False)
        replay_direction = (
            sig_set.entry_direction.shift(1).fillna(1.0)
            if sig_set.entry_direction is not None else None
        )

        for i in range(start_idx, len(df)):
            controller.check_stop()
            row = df.iloc[i]
            ts = df.index[i]
            direction_val = 1.0
            if replay_direction is not None:
                direction_val = float(replay_direction.iloc[i])
            events = pm.process_bar(
                bar_time=ts.isoformat(),
                bar_high=float(row["high"]),
                bar_low=float(row["low"]),
                bar_close=float(row["close"]),
                entry_signal=bool(replay_entries.iloc[i]),
                exit_signal=bool(replay_exits.iloc[i]),
                add_signal=bool(replay_adds.iloc[i]),
                reduce_signal=bool(replay_reduces.iloc[i]),
                direction=direction_val,
            )
            self._log_events(
                save_paper_trade, task_id, ts.isoformat(), events,
            )

            # Checkpoint every 500 bars
            if (i - start_idx + 1) % 500 == 0:
                self._save_pm_state(pm, task_id, df)
                self._push_position_update(pm, task_id)
                logger.info(
                    "Replay checkpoint at bar %d/%d for task %s",
                    i + 1, len(df), task_id,
                )

        # Save state after replay
        self._save_pm_state(pm, task_id, df)
        self._push_position_update(pm, task_id)

        # Main loop: fetch new bars and process
        bar_interval = _BAR_SECONDS.get(timeframe, 14400)
        poll_wait = min(bar_interval, 60)  # check at least every 60s

        while not controller.stop_requested:
            controller.check_stop()
            try:
                new_df = self._fetch_and_update(symbol, timeframe)
                if new_df is not None and len(new_df) > len(df):
                    df_new = compute_all_indicators(new_df)
                    sig_new = dna_to_signal_set(dna, df_new)

                    for i in range(len(df), len(df_new)):
                        row = df_new.iloc[i]
                        ts = df_new.index[i]
                        direction_val = 1.0
                        if sig_new.entry_direction is not None:
                            direction_val = float(sig_new.entry_direction.iloc[i])
                        events = pm.process_bar(
                            bar_time=ts.isoformat(),
                            bar_high=float(row["high"]),
                            bar_low=float(row["low"]),
                            bar_close=float(row["close"]),
                            entry_signal=bool(sig_new.entries.iloc[i]),
                            exit_signal=bool(sig_new.exits.iloc[i]),
                            add_signal=bool(sig_new.adds.iloc[i]),
                            reduce_signal=bool(sig_new.reduces.iloc[i]),
                            direction=direction_val,
                        )
                        self._log_events(
                            save_paper_trade, task_id, ts.isoformat(), events,
                        )

                    df = df_new
            except Exception:
                logger.warning("Data fetch failed for %s", task_id, exc_info=True)

            # Save state and push update
            self._save_pm_state(pm, task_id, df)
            self._push_position_update(pm, task_id)
            update_paper_trading_task(
                self.db_path, task_id, heartbeat_at=_now_iso(),
            )

            controller._stop_event.wait(poll_wait)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_data(self, symbol: str, timeframe: str):
        """Load historical data from parquet."""
        from core.data.storage import load_parquet
        path = self.data_dir / f"{symbol}_{timeframe}.parquet"
        if not path.exists():
            return None
        return load_parquet(path)

    def _fetch_and_update(self, symbol: str, timeframe: str):
        """Fetch latest data and update local parquet."""
        try:
            return update_market_data(
                symbol=symbol, interval=timeframe, data_dir=self.data_dir,
            )
        except Exception:
            return None

    def _find_replay_start(self, df, last_bar_time: Optional[str]) -> int:
        """Find the index to start replaying from."""
        if last_bar_time is None:
            return 0
        ts = last_bar_time
        for i in range(len(df) - 1, -1, -1):
            if df.index[i].isoformat() <= ts:
                return i + 1
        return 0

    def _restore_pm_state(self, pm: PositionManager, task: dict) -> None:
        """Restore PositionManager state from DB row."""
        # Restore cumulative stats
        pm._prior_trades = task.get("total_trades", 0)
        pm._prior_pnl = task.get("total_pnl", 0.0)
        pm._prior_wins = task.get("win_count", 0)
        pm._prior_losses = task.get("loss_count", 0)

        if task.get("position_side") is None:
            return
        pm.balance = task.get("balance", pm._init_cash)
        pm.position = Position(
            side=task["position_side"],
            entry_price=task["position_entry"],
            quantity=task["position_quantity"],
            margin=task["position_margin"],
            cumulative_funding=task.get("position_funding", 0.0),
        )

    def _save_pm_state(self, pm: PositionManager, task_id: str, df=None) -> None:
        """Persist PositionManager state to DB."""
        from api.db_ext import update_paper_trading_task
        kwargs = {"balance": pm.balance}

        # Get actual last close price from df
        last_close = 0.0
        if df is not None and len(df) > 0:
            last_close = float(df.iloc[-1]["close"])

        if pm.position is not None:
            pos = pm.position
            kwargs.update({
                "position_side": pos.side,
                "position_entry": pos.entry_price,
                "position_quantity": pos.quantity,
                "position_margin": pos.margin,
                "position_funding": pos.cumulative_funding,
                "unrealized_pnl": pm._unrealized_pnl(last_close),
            })
        else:
            kwargs.update({
                "position_side": None,
                "position_entry": None,
                "position_quantity": None,
                "position_margin": None,
                "position_funding": 0.0,
                "unrealized_pnl": 0.0,
            })

        if pm.equity_snapshots:
            snap = pm.equity_snapshots[-1]
            kwargs["last_bar_time"] = snap.timestamp
            kwargs["last_bar_close"] = last_close

        # Stats (use PM cumulative properties)
        kwargs.update({
            "total_trades": pm.total_trades,
            "total_pnl": pm.total_pnl,
            "win_count": pm.win_count,
            "loss_count": pm.loss_count,
        })

        update_paper_trading_task(self.db_path, task_id, **kwargs)

    def _log_events(self, save_trade_fn, task_id: str, bar_time: str,
                    events: List[dict]) -> None:
        """Save trade events to DB."""
        for ev in events:
            action = ev["type"]
            if action == "position_opened":
                save_trade_fn(
                    self.db_path,
                    task_id=task_id, bar_time=bar_time,
                    side=ev["side"], action="open",
                    price=ev["entry_price"], quantity=ev.get("quantity", 0),
                )
            elif action == "position_closed":
                save_trade_fn(
                    self.db_path,
                    task_id=task_id, bar_time=bar_time,
                    side=ev["side"], action="close",
                    price=ev["exit_price"], quantity=0,
                    pnl=ev["pnl"], reason=ev["exit_reason"],
                )
            elif action == "position_added":
                save_trade_fn(
                    self.db_path,
                    task_id=task_id, bar_time=bar_time,
                    side="", action="add",
                    price=ev.get("new_entry_price", 0),
                    quantity=ev.get("quantity_added", 0),
                )
            elif action == "position_reduced":
                save_trade_fn(
                    self.db_path,
                    task_id=task_id, bar_time=bar_time,
                    side="", action="reduce",
                    price=0, quantity=ev.get("quantity_reduced", 0),
                    pnl=ev.get("pnl"),
                )

    def _push_position_update(self, pm: PositionManager, task_id: str) -> None:
        """Push current position state via WS."""
        pos_data = None
        if pm.position is not None:
            pos = pm.position
            price = 0.0
            if pm.equity_snapshots:
                # Estimate current price from last snapshot
                price = pos.entry_price  # fallback
            pos_data = {
                "side": pos.side,
                "entry_price": pos.entry_price,
                "quantity": pos.quantity,
                "margin": pos.margin,
                "cumulative_funding": pos.cumulative_funding,
            }

        equity = pm._init_cash
        unrealized = 0.0
        if pm.equity_snapshots:
            snap = pm.equity_snapshots[-1]
            equity = snap.equity
            unrealized = snap.unrealized_pnl

        _push_ws(task_id, {
            "type": "position_update",
            "task_id": task_id,
            "position": pos_data,
            "balance": pm.balance,
            "equity": equity,
            "unrealized_pnl": unrealized,
            "total_trades": pm.total_trades,
            "total_pnl": pm.total_pnl,
        })
