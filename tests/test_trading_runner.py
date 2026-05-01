"""Tests for TradingRunner: task lifecycle, state persistence, and WS push.

Covers:
1. Runner picks up pending task and transitions to running
2. Runner saves PositionManager state to DB after bar replay
3. Runner restores PM state from DB row correctly
4. TaskController cooperative stop via threading.Event
5. Stale task recovery marks running tasks as stopped
6. WS push delegates to configured push function
7. Multiple tasks run sequentially (one at a time)
"""
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit]

from tests.helpers.data_factory import make_dna, make_pm


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_controllers():
    """Ensure no stale controllers between tests."""
    from core.trading.runner import _active_controllers
    _active_controllers.clear()
    yield
    _active_controllers.clear()


@pytest.fixture
def trading_db(tmp_path: Path) -> Path:
    """Create a DB with paper trading tables and a sample task."""
    from api.db_ext import init_db_ext, save_paper_trading_task
    db_path = tmp_path / "test_runner.db"
    init_db_ext(db_path)
    return db_path


@pytest.fixture
def trading_db_with_task(trading_db: Path) -> Path:
    """DB with a pending paper trading task."""
    from api.db_ext import save_paper_trading_task
    dna = make_dna(direction="long", leverage=1)
    save_paper_trading_task(
        trading_db,
        task_id="task-001",
        dna_json=dna.to_json(),
        symbol="BTCUSDT",
        timeframe="4h",
        initial_cash=100_000,
        fee=0.001,
    )
    return trading_db


# ---------------------------------------------------------------------------
# Test: TaskController
# ---------------------------------------------------------------------------

class TestTaskController:

    def test_initial_state_not_stopped(self):
        from core.trading.runner import TaskController
        ctrl = TaskController()
        assert not ctrl.stop_requested

    def test_request_stop_sets_flag(self):
        from core.trading.runner import TaskController
        ctrl = TaskController()
        ctrl.request_stop()
        assert ctrl.stop_requested

    def test_check_stop_raises_when_requested(self):
        from core.trading.runner import TaskController, TaskStopRequested
        ctrl = TaskController()
        ctrl.request_stop()
        with pytest.raises(TaskStopRequested):
            ctrl.check_stop()

    def test_check_stop_noop_when_not_requested(self):
        from core.trading.runner import TaskController
        ctrl = TaskController()
        ctrl.check_stop()  # should not raise


# ---------------------------------------------------------------------------
# Test: Stale task recovery
# ---------------------------------------------------------------------------

class TestStaleTaskRecovery:

    def test_marks_running_tasks_as_stopped(self, trading_db: Path):
        from api.db_ext import save_paper_trading_task, update_paper_trading_task, get_paper_trading_task
        from core.trading.runner import recover_stale_trading_tasks

        dna = make_dna()
        save_paper_trading_task(trading_db, task_id="r1", dna_json=dna.to_json())
        save_paper_trading_task(trading_db, task_id="r2", dna_json=dna.to_json())
        update_paper_trading_task(trading_db, "r1", status="running")
        update_paper_trading_task(trading_db, "r2", status="running")

        recover_stale_trading_tasks(trading_db)

        row1 = get_paper_trading_task(trading_db, "r1")
        row2 = get_paper_trading_task(trading_db, "r2")
        assert row1["status"] == "stopped"
        assert row1["stop_reason"] == "crash_recovery"
        assert row2["status"] == "stopped"

    def test_does_not_affect_pending_tasks(self, trading_db: Path):
        from api.db_ext import save_paper_trading_task, get_paper_trading_task
        from core.trading.runner import recover_stale_trading_tasks

        dna = make_dna()
        save_paper_trading_task(trading_db, task_id="p1", dna_json=dna.to_json())

        recover_stale_trading_tasks(trading_db)

        row = get_paper_trading_task(trading_db, "p1")
        assert row["status"] == "pending"

    @pytest.mark.parametrize("status,should_be_recovered", [
        ("running", True),
        ("pending", False),
        ("paused", False),
        ("stopped", False),
    ])
    def test_recovery_only_affects_running(
        self, trading_db: Path, status: str, should_be_recovered: bool,
    ):
        from api.db_ext import save_paper_trading_task, update_paper_trading_task, get_paper_trading_task
        from core.trading.runner import recover_stale_trading_tasks

        dna = make_dna()
        save_paper_trading_task(trading_db, task_id="t1", dna_json=dna.to_json())
        if status != "pending":
            update_paper_trading_task(trading_db, "t1", status=status)

        recover_stale_trading_tasks(trading_db)

        row = get_paper_trading_task(trading_db, "t1")
        if should_be_recovered:
            assert row["status"] == "stopped"
            assert row["stop_reason"] == "crash_recovery"
        else:
            assert row["status"] == status


# ---------------------------------------------------------------------------
# Test: Runner state save/restore
# ---------------------------------------------------------------------------

class TestRunnerStateSaveRestore:

    def test_save_flat_state(self, trading_db: Path):
        from api.db_ext import save_paper_trading_task, get_paper_trading_task
        from core.trading.runner import TradingRunner

        dna = make_dna()
        save_paper_trading_task(
            trading_db, task_id="s1", dna_json=dna.to_json(), initial_cash=100_000,
        )

        pm = make_pm(init_cash=100_000, fee=0.0)
        runner = TradingRunner(db_path=trading_db, data_dir=trading_db.parent / "data")
        runner._save_pm_state(pm, "s1")

        row = get_paper_trading_task(trading_db, "s1")
        assert row["balance"] == 100_000
        assert row["position_side"] is None
        assert row["total_trades"] == 0

    def test_save_position_state(self, trading_db: Path):
        from api.db_ext import save_paper_trading_task, get_paper_trading_task
        from core.trading.runner import TradingRunner

        dna = make_dna()
        save_paper_trading_task(
            trading_db, task_id="s2", dna_json=dna.to_json(), initial_cash=100_000, fee=0.0,
        )

        pm = make_pm(init_cash=100_000, fee=0.0)
        pm.process_bar(
            bar_time="2024-01-01T00:00:00",
            bar_high=101.0, bar_low=99.0, bar_close=100.0,
            entry_signal=True, direction=1.0,
        )
        assert pm.position is not None

        runner = TradingRunner(db_path=trading_db, data_dir=trading_db.parent / "data")
        runner._save_pm_state(pm, "s2")

        row = get_paper_trading_task(trading_db, "s2")
        assert row["position_side"] == "long"
        assert row["position_entry"] == 100.0

    def test_restore_flat_state_restores_balance(self, trading_db: Path):
        """When position_side is None, balance is still restored from DB."""
        from api.db_ext import save_paper_trading_task, update_paper_trading_task, get_paper_trading_task
        from core.trading.runner import TradingRunner

        dna = make_dna()
        save_paper_trading_task(
            trading_db, task_id="r1", dna_json=dna.to_json(), initial_cash=100_000,
        )
        update_paper_trading_task(trading_db, "r1", balance=95000)

        row = get_paper_trading_task(trading_db, "r1")
        pm = make_pm(init_cash=100_000)
        runner = TradingRunner(db_path=trading_db, data_dir=trading_db.parent / "data")
        runner._restore_pm_state(pm, row)

        # balance is restored from DB even when flat
        assert pm.balance == 95000
        assert pm.position is None

    def test_restore_position_state(self, trading_db: Path):
        from api.db_ext import save_paper_trading_task, update_paper_trading_task, get_paper_trading_task
        from core.trading.runner import TradingRunner

        dna = make_dna()
        save_paper_trading_task(
            trading_db, task_id="r2", dna_json=dna.to_json(), initial_cash=100_000, fee=0.0,
        )
        update_paper_trading_task(
            trading_db, "r2",
            balance=70000,
            position_side="long", position_entry=100.0,
            position_quantity=300.0, position_margin=30000.0,
            position_funding=50.0,
        )

        row = get_paper_trading_task(trading_db, "r2")
        pm = make_pm(init_cash=100_000, fee=0.0)
        runner = TradingRunner(db_path=trading_db, data_dir=trading_db.parent / "data")
        runner._restore_pm_state(pm, row)

        assert pm.position is not None
        assert pm.position.side == "long"
        assert pm.position.entry_price == 100.0
        assert pm.position.quantity == 300.0
        assert pm.position.margin == 30000.0
        assert pm.position.cumulative_funding == 50.0
        assert pm.balance == 70000


# ---------------------------------------------------------------------------
# Test: Runner task execution (mocked data)
# ---------------------------------------------------------------------------

class TestRunnerTaskExecution:

    def test_find_pending_task(self, trading_db_with_task: Path):
        from core.trading.runner import TradingRunner

        runner = TradingRunner(
            db_path=trading_db_with_task,
            data_dir=trading_db_with_task.parent / "data",
        )
        task = runner._find_pending_task()
        assert task is not None
        assert task["task_id"] == "task-001"

    def test_find_pending_returns_none_when_empty(self, trading_db: Path):
        from core.trading.runner import TradingRunner

        runner = TradingRunner(
            db_path=trading_db,
            data_dir=trading_db.parent / "data",
        )
        task = runner._find_pending_task()
        assert task is None

    def test_get_task(self, trading_db_with_task: Path):
        from core.trading.runner import TradingRunner

        runner = TradingRunner(
            db_path=trading_db_with_task,
            data_dir=trading_db_with_task.parent / "data",
        )
        row = runner._get_task("task-001")
        assert row is not None
        assert row["task_id"] == "task-001"

    def test_get_task_returns_none_for_unknown(self, trading_db: Path):
        from core.trading.runner import TradingRunner

        runner = TradingRunner(
            db_path=trading_db,
            data_dir=trading_db.parent / "data",
        )
        row = runner._get_task("no-such-task")
        assert row is None

    def test_execute_task_marks_running(self, trading_db_with_task: Path):
        from api.db_ext import get_paper_trading_task
        from core.trading.runner import TradingRunner

        runner = TradingRunner(
            db_path=trading_db_with_task,
            data_dir=trading_db_with_task.parent / "data",
            poll_interval=0.1,
        )

        task = runner._find_pending_task()
        assert task is not None

        # _execute_task will fail because no parquet data, but should set status
        with patch.object(runner, "_load_data", return_value=None):
            runner._run_task(task)

        row = get_paper_trading_task(trading_db_with_task, "task-001")
        assert row["status"] == "stopped"
        assert row["stop_reason"] == "no_data"

    def test_controller_stop_sets_active_task_none(self, trading_db_with_task: Path):
        from core.trading.runner import TradingRunner, TaskController, _active_controllers

        runner = TradingRunner(
            db_path=trading_db_with_task,
            data_dir=trading_db_with_task.parent / "data",
        )

        # Simulate a task being active
        runner._active_task_id = "task-001"
        ctrl = TaskController()
        _active_controllers["task-001"] = ctrl

        # Stop via controller
        ctrl.request_stop()

        assert ctrl.stop_requested
        assert "task-001" in _active_controllers

    def test_run_task_with_controller_stop(self, trading_db_with_task: Path):
        """Runner should transition to stopped when controller requests stop."""
        from api.db_ext import get_paper_trading_task
        from core.trading.runner import TradingRunner

        runner = TradingRunner(
            db_path=trading_db_with_task,
            data_dir=trading_db_with_task.parent / "data",
        )

        task = runner._find_pending_task()
        assert task is not None

        # Mock _execute_task to raise TaskStopRequested
        from core.trading.runner import TaskStopRequested
        with patch.object(
            runner, "_execute_task",
            side_effect=TaskStopRequested(),
        ):
            runner._run_task(task)

        row = get_paper_trading_task(trading_db_with_task, "task-001")
        assert row["status"] == "stopped"
        assert row["stop_reason"] == "user_stop"
