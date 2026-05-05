"""Paper Trading Runner: background thread that executes paper trading tasks.

V2 architecture: signal -> judgment -> pending_decision -> bar_open execution.
Uses VirtualAccount instead of PositionManager.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from core.logging import get_logger
from core.strategy.dna import StrategyDNA
from core.strategy.executor import dna_to_signal_set
from core.data.updater import update_market_data
from core.trading.account import VirtualAccount
from core.trading.position import Position
from core.trading.types import BarSignals, Decision, JudgmentConfig
from core.trading.judgment import evaluate

logger = get_logger("TRADING_RUNNER")

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
            row = self._get_task(self._active_task_id)
            if row is None or row["status"] not in ("running", "pending"):
                self._active_task_id = None
            return

        task = self._find_pending_task()
        if task:
            self._run_task(task)

    def _find_pending_task(self) -> Optional[Dict[str, Any]]:
        from core.persistence.db import _connect
        with _connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM paper_trading_task "
                "WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None

    def _get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        from core.persistence.db import _connect
        with _connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM paper_trading_task WHERE task_id = ?", (task_id,)
            ).fetchone()
            return dict(row) if row else None

    def _run_task(self, task_row: Dict[str, Any]) -> None:
        task_id = task_row["task_id"]
        self._active_task_id = task_id
        controller = TaskController()
        _active_controllers[task_id] = controller

        try:
            self._execute_task(task_row, task_id, controller)
        except TaskStopRequested:
            row = self._get_task(task_id)
            if row and row["status"] == "paused":
                logger.info("Trading task %s paused via controller", task_id)
            else:
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
            update_paper_trading_task, save_paper_trade,
        )

        # Mark running
        update_paper_trading_task(
            self.db_path, task_id, status="running", started_at=_now_iso(),
        )
        _push_ws(task_id, {"type": "task_started", "task_id": task_id})

        # Parse DNA
        dna = StrategyDNA.from_json(task_row["dna_json"])
        symbol = task_row["symbol"]
        timeframe = task_row["timeframe"]
        init_cash = task_row["initial_cash"]
        fee = task_row["fee"]

        # Create VirtualAccount
        account = VirtualAccount(dna, init_cash=init_cash, fee=fee, slippage=0.0005)

        # Restore state if resuming
        self._restore_account_state(account, task_row)

        # Load data
        controller.check_stop()
        df = self._load_data(symbol, timeframe)
        if df is None or df.empty:
            self._update_status(task_id, "stopped", "no_data")
            return

        from core.features.indicators import compute_all_indicators
        df = compute_all_indicators(df)

        # Trim warmup rows where indicators produced NaN
        df = self._trim_nan_rows(df)

        # Filter forming bar
        df = self._filter_forming_bar(df, timeframe)

        # Resume: minimal replay from last_bar_time
        pending_decision: Optional[Decision] = None
        last_bar_time = task_row.get("last_bar_time")
        if last_bar_time:
            sig_set = dna_to_signal_set(dna, df)
            start_idx = self._find_replay_start(df, last_bar_time)
            pending_decision = self._min_replay(
                account, sig_set, df, start_idx, task_id, controller,
                save_paper_trade, timeframe,
            )

        # Save state after replay
        self._save_account_state(account, task_id, df)
        self._push_position_update(account, task_id)

        # Main loop
        bar_interval = _BAR_SECONDS.get(timeframe, 14400)
        poll_wait = min(bar_interval, 60)
        config = JudgmentConfig()

        while not controller.stop_requested:
            controller.check_stop()
            try:
                new_df = self._fetch_and_update(symbol, timeframe)
                if new_df is not None and len(new_df) > len(df):
                    new_df = compute_all_indicators(new_df)
                    new_df = self._filter_forming_bar(new_df, timeframe)
                    sig_set = dna_to_signal_set(dna, new_df)

                    for i in range(len(df), len(new_df)):
                        controller.check_stop()
                        row = new_df.iloc[i]
                        ts = new_df.index[i]

                        # Execute pending decision at bar open
                        events = account.process_bar_v2(
                            bar_high=float(row["high"]),
                            bar_low=float(row["low"]),
                            bar_open=float(row["open"]),
                            bar_close=float(row["close"]),
                            bar_time=ts.isoformat(),
                            pending_decision=pending_decision,
                        )
                        self._log_events(
                            save_paper_trade, task_id, ts.isoformat(), events,
                        )
                        pending_decision = None

                        # Evaluate signals for next bar
                        signals = BarSignals.from_signal_set(sig_set, i)
                        state = account.get_state(float(row["close"]))
                        decision = evaluate(signals, state, config)
                        if decision.action != "hold":
                            pending_decision = decision

                    df = new_df
            except Exception:
                logger.warning("Data fetch failed for %s", task_id, exc_info=True)

            self._save_account_state(account, task_id, df)
            self._push_position_update(account, task_id)
            update_paper_trading_task(
                self.db_path, task_id, heartbeat_at=_now_iso(),
            )
            controller._stop_event.wait(poll_wait)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _filter_forming_bar(self, df, timeframe: str):
        """Exclude incomplete (forming) bar."""
        if df.empty:
            return df
        interval_seconds = _BAR_SECONDS.get(timeframe, 14400)
        now = pd.Timestamp.now(tz="UTC")
        last_bar_time = df.index[-1]
        if last_bar_time.tz is None:
            last_bar_time = last_bar_time.tz_localize("UTC")
        if last_bar_time + pd.Timedelta(seconds=interval_seconds) > now:
            return df.iloc[:-1]
        return df

    def _trim_nan_rows(self, df):
        """Drop leading rows where indicator columns are all NaN (warmup period)."""
        if df.empty:
            return df
        ohlcv_cols = {"open", "high", "low", "close", "volume"}
        ind_cols = [c for c in df.columns if c not in ohlcv_cols]
        if not ind_cols:
            return df
        valid_mask = df[ind_cols].notna().any(axis=1)
        first_valid = valid_mask.idxmax()
        if not valid_mask.loc[first_valid]:
            return df.iloc[0:0]  # all NaN
        first_idx = df.index.get_loc(first_valid)
        if first_idx == 0:
            return df
        logger.info("Trimmed %d warmup rows with NaN indicators", first_idx)
        return df.iloc[first_idx:]

    def _min_replay(
        self, account, sig_set, df, start_idx, task_id,
        controller, save_trade_fn, timeframe,
    ) -> Optional[Decision]:
        """Replay bars from start_idx, return last pending decision."""
        config = JudgmentConfig()
        pending: Optional[Decision] = None

        for i in range(start_idx, len(df)):
            controller.check_stop()
            row = df.iloc[i]
            ts = df.index[i]

            events = account.process_bar_v2(
                bar_high=float(row["high"]),
                bar_low=float(row["low"]),
                bar_open=float(row["open"]),
                bar_close=float(row["close"]),
                bar_time=ts.isoformat(),
                pending_decision=pending,
            )
            self._log_events(save_trade_fn, task_id, ts.isoformat(), events)
            pending = None

            # Evaluate for next bar
            signals = BarSignals.from_signal_set(sig_set, i)
            state = account.get_state(float(row["close"]))
            decision = evaluate(signals, state, config)
            if decision.action != "hold":
                pending = decision

        return pending

    def _load_data(self, symbol: str, timeframe: str):
        from core.data.storage import load_parquet
        path = self.data_dir / f"{symbol}_{timeframe}.parquet"
        if not path.exists():
            return None
        return load_parquet(path)

    def _fetch_and_update(self, symbol: str, timeframe: str):
        try:
            return update_market_data(
                symbol=symbol, interval=timeframe, data_dir=self.data_dir,
            )
        except Exception:
            return None

    def _find_replay_start(self, df, last_bar_time: Optional[str]) -> int:
        if last_bar_time is None:
            return 0
        ts = last_bar_time
        for i in range(len(df) - 1, -1, -1):
            if df.index[i].isoformat() <= ts:
                return i + 1
        return 0

    def _restore_account_state(self, account: VirtualAccount, task: dict) -> None:
        """Restore VirtualAccount state from DB row."""
        account._prior_trades = task.get("total_trades", 0)
        account._prior_pnl = task.get("total_pnl", 0.0)
        account._prior_wins = task.get("win_count", 0)
        account._prior_losses = task.get("loss_count", 0)

        if task.get("balance") is not None:
            account.balance = task["balance"]

        if task.get("position_side") is None:
            return
        account._bars_held_count = task.get("bars_held", 0)
        account.position = Position(
            side=task["position_side"],
            entry_price=task["position_entry"],
            quantity=task["position_quantity"],
            margin=task["position_margin"],
            cumulative_funding=task.get("position_funding", 0.0),
            open_cost=task.get("position_open_cost", 0.0),
        )

    def _save_account_state(self, account: VirtualAccount, task_id: str,
                            df=None) -> None:
        """Persist VirtualAccount state to DB."""
        from api.db_ext import update_paper_trading_task
        kwargs = {"balance": account.balance}

        last_close = 0.0
        if df is not None and len(df) > 0:
            last_close = float(df.iloc[-1]["close"])

        if account.position is not None:
            pos = account.position
            kwargs.update({
                "position_side": pos.side,
                "position_entry": pos.entry_price,
                "position_quantity": pos.quantity,
                "position_margin": pos.margin,
                "position_funding": pos.cumulative_funding,
                "position_open_cost": pos.open_cost,
                "unrealized_pnl": account._unrealized_pnl(last_close),
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

        if account.equity_snapshots:
            snap = account.equity_snapshots[-1]
            kwargs["last_bar_time"] = snap.timestamp
            kwargs["last_bar_close"] = last_close

        kwargs.update({
            "total_trades": account.total_trades,
            "total_pnl": account.total_pnl,
            "win_count": account.win_count,
            "loss_count": account.loss_count,
            "bars_held": account._bars_held() if account.position else 0,
        })

        update_paper_trading_task(self.db_path, task_id, **kwargs)

        if len(account.equity_snapshots) > 1:
            from api.db_ext import save_equity_snapshots
            snap_dicts = [
                {
                    "timestamp": s.timestamp,
                    "equity": s.equity,
                    "balance": s.balance,
                    "unrealized_pnl": s.unrealized_pnl,
                    "position_side": s.position_side,
                }
                for s in account.equity_snapshots[:-1]
            ]
            save_equity_snapshots(self.db_path, task_id, snap_dicts)
            account.equity_snapshots = account.equity_snapshots[-1:]

    def _log_events(self, save_trade_fn, task_id: str, bar_time: str,
                    events: List[dict]) -> None:
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
                    price=ev["exit_price"], quantity=ev.get("quantity", 0),
                    pnl=ev["pnl"], reason=ev["exit_reason"],
                )
            elif action == "position_added":
                save_trade_fn(
                    self.db_path,
                    task_id=task_id, bar_time=bar_time,
                    side=ev.get("side", ""), action="add",
                    price=ev.get("price", 0),
                    quantity=ev.get("quantity_added", 0),
                )
            elif action == "position_reduced":
                save_trade_fn(
                    self.db_path,
                    task_id=task_id, bar_time=bar_time,
                    side=ev.get("side", ""), action="reduce",
                    price=ev.get("price", 0),
                    quantity=ev.get("quantity_reduced", 0),
                    pnl=ev.get("pnl"),
                )

    def _push_position_update(self, account: VirtualAccount, task_id: str) -> None:
        pos_data = None
        if account.position is not None:
            pos = account.position
            pos_data = {
                "side": pos.side,
                "entry_price": pos.entry_price,
                "quantity": pos.quantity,
                "margin": pos.margin,
                "cumulative_funding": pos.cumulative_funding,
            }

        equity = account._init_cash
        unrealized = 0.0
        if account.equity_snapshots:
            snap = account.equity_snapshots[-1]
            equity = snap.equity
            unrealized = snap.unrealized_pnl

        _push_ws(task_id, {
            "type": "position_update",
            "task_id": task_id,
            "position": pos_data,
            "balance": account.balance,
            "equity": equity,
            "unrealized_pnl": unrealized,
            "total_trades": account.total_trades,
            "total_pnl": account.total_pnl,
        })
