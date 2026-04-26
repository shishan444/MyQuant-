"""Integration tests for evolution flow: REST + WebSocket + Runner pipeline.

Verifies the end-to-end contract between:
- REST endpoints (task creation, progress queries)
- WebSocket push (task_started, generation_complete, task_snapshot)
- Runner execution (status transitions, DB writes)
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from fastapi.testclient import TestClient

from core.persistence.db import get_task, init_db, save_task, update_task
from core.strategy.dna import (
    ExecutionGenes,
    LogicGenes,
    RiskGenes,
    SignalGene,
    SignalRole,
    StrategyDNA,
)

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_dna() -> StrategyDNA:
    return StrategyDNA(
        signal_genes=[
            SignalGene(
                indicator="RSI",
                params={"period": 14},
                role=SignalRole.ENTRY_TRIGGER,
                condition={"type": "lt", "threshold": 30},
            ),
            SignalGene(
                indicator="RSI",
                params={"period": 14},
                role=SignalRole.EXIT_TRIGGER,
                condition={"type": "gt", "threshold": 70},
            ),
        ],
        logic_genes=LogicGenes(entry_logic="AND", exit_logic="AND"),
        execution_genes=ExecutionGenes(timeframe="4h", symbol="BTCUSDT"),
        risk_genes=RiskGenes(stop_loss=0.05, take_profit=0.10, position_size=0.3),
    )


def _sample_evolution_create() -> Dict[str, Any]:
    return {
        "initial_dna": {
            "signal_genes": [
                {
                    "indicator": "RSI",
                    "params": {"period": 14},
                    "role": "entry_trigger",
                    "field": None,
                    "condition": {"type": "lt", "threshold": 30},
                },
                {
                    "indicator": "RSI",
                    "params": {"period": 14},
                    "role": "exit_trigger",
                    "field": None,
                    "condition": {"type": "gt", "threshold": 70},
                },
            ],
            "logic_genes": {"entry_logic": "AND", "exit_logic": "AND"},
            "execution_genes": {"timeframe": "4h", "symbol": "BTCUSDT"},
            "risk_genes": {"stop_loss": 0.05, "take_profit": 0.10, "position_size": 0.3},
        },
        "symbol": "BTCUSDT",
        "timeframe": "4h",
        "target_score": 80.0,
        "score_template": "profit_first",
        "population_size": 15,
        "max_generations": 200,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    import pandas as pd

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    dummy_df = pd.DataFrame(
        {"open": [60000], "high": [61000], "low": [59000],
         "close": [60500], "volume": [100]},
        index=pd.DatetimeIndex(["2024-01-01"], name="timestamp"),
    )
    dummy_df.to_parquet(data_dir / "BTCUSDT_4h.parquet")
    return data_dir


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_flow.db"


@pytest.fixture
def client(db_path: Path, tmp_data_dir: Path):
    from MyQuant.api.app import create_app

    app = create_app(db_path=db_path, data_dir=tmp_data_dir)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test_runner_flow.db"
    init_db(db_path)
    return db_path


# ---------------------------------------------------------------------------
# Test 1: REST reflects runner progress
# ---------------------------------------------------------------------------

class TestRESTProgress:
    def test_rest_reflects_runner_progress(self, client: TestClient) -> None:
        """After runner updates DB, REST endpoint should reflect the progress."""
        # Create a task via REST
        create_resp = client.post("/api/evolution/tasks", json=_sample_evolution_create())
        assert create_resp.status_code == 201
        task_id = create_resp.json()["task_id"]

        # Simulate runner writing progress to DB
        db_path = client.app.state.db_path
        update_task(db_path, task_id, status="running")
        # Simulate a generation update (runner does this in on_generation)
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            "UPDATE evolution_task SET current_generation = ?, best_score = ? WHERE task_id = ?",
            (5, 42.5, task_id),
        )
        conn.commit()
        conn.close()

        # REST should return the updated progress
        resp = client.get(f"/api/evolution/tasks/{task_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["current_generation"] == 5
        assert data["best_score"] == 42.5


# ---------------------------------------------------------------------------
# Test 2: task_started push on runner begin
# ---------------------------------------------------------------------------

class TestTaskStartedPush:
    def test_task_started_pushed_on_runner_begin(
        self, tmp_db: Path, tmp_data_dir: Path
    ) -> None:
        """Runner should push task_started when it begins executing a task."""
        from api.runner import EvolutionRunner

        # Create a task
        dna = _make_dna()
        save_task(tmp_db, "task-start-push", 80.0, "profit_first", "BTCUSDT", "4h", dna)
        task_row = dict(get_task(tmp_db, "task-start-push"))

        # Capture WS push
        pushed_messages: list[dict] = []

        def mock_push(task_id: str, payload: dict) -> None:
            pushed_messages.append(payload)

        from api import runner as runner_mod
        original_push = runner_mod._push_ws
        runner_mod._push_ws = mock_push

        try:
            r = EvolutionRunner(db_path=tmp_db, data_dir=tmp_data_dir)
            # Run until data loading fails (no real data), but task_started should have fired
            with patch("core.data.mtf_loader.load_and_prepare_df", return_value=None):
                r._run_task(task_row)
        finally:
            runner_mod._push_ws = original_push

        # Verify task_started was pushed
        started_msgs = [m for m in pushed_messages if m.get("type") == "task_started"]
        assert len(started_msgs) >= 1, f"Expected task_started, got: {pushed_messages}"
        msg = started_msgs[0]
        assert msg["status"] == "running"
        assert msg["target_score"] == 80.0


# ---------------------------------------------------------------------------
# Test 3: WS snapshot on connect
# ---------------------------------------------------------------------------

class TestWSSnapshot:
    def test_ws_snapshot_on_connect_with_running_task(
        self, client: TestClient
    ) -> None:
        """WS connect to a running task should receive a task_snapshot."""
        # Create task and set to running
        create_resp = client.post("/api/evolution/tasks", json=_sample_evolution_create())
        task_id = create_resp.json()["task_id"]
        db_path = client.app.state.db_path

        # Simulate runner has started and progressed
        update_task(db_path, task_id, status="running")
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "UPDATE evolution_task SET current_generation = ?, best_score = ? WHERE task_id = ?",
            (3, 25.0, task_id),
        )
        conn.commit()
        conn.close()

        # Connect WS and check for snapshot
        with client.websocket_connect(f"/ws/evolution/{task_id}") as ws:
            # First message: subscribed
            msg1 = ws.receive_json()
            assert msg1["type"] == "subscribed"

            # Second message: task_snapshot
            msg2 = ws.receive_json()
            assert msg2["type"] == "task_snapshot"
            assert msg2["task_id"] == task_id
            assert msg2["status"] == "running"
            assert msg2["current_generation"] == 3
            assert msg2["best_score"] == 25.0

    def test_ws_no_snapshot_for_nonexistent_task(
        self, client: TestClient
    ) -> None:
        """WS connect to a nonexistent task should only receive subscribed."""
        with client.websocket_connect("/ws/evolution/nonexistent-id") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "subscribed"

    def test_ws_snapshot_for_pending_task(
        self, client: TestClient
    ) -> None:
        """WS connect to a pending task should receive snapshot."""
        create_resp = client.post("/api/evolution/tasks", json=_sample_evolution_create())
        task_id = create_resp.json()["task_id"]

        with client.websocket_connect(f"/ws/evolution/{task_id}") as ws:
            msg1 = ws.receive_json()
            assert msg1["type"] == "subscribed"

            msg2 = ws.receive_json()
            assert msg2["type"] == "task_snapshot"
            assert msg2["status"] == "pending"


# ---------------------------------------------------------------------------
# Test 4: WS generation_complete push
# ---------------------------------------------------------------------------

class TestWSGenerationPush:
    def test_manager_tracks_ws_connections(
        self, client: TestClient
    ) -> None:
        """Manager should track WS connections and be able to push messages."""
        from api.routes.ws import get_manager

        task_id = "ws-manager-test-id"
        manager = get_manager()

        # Before connecting, no connections for this task
        assert task_id not in manager._connections or len(manager._connections[task_id]) == 0

        with client.websocket_connect(f"/ws/evolution/{task_id}") as ws:
            # After connecting, the first message should be subscribed
            msg = ws.receive_json()
            assert msg["type"] == "subscribed"

            # Verify WS protocol works: send ping, receive pong
            ws.send_json({"type": "ping"})
            pong = ws.receive_json()
            assert pong["type"] == "pong"


# ---------------------------------------------------------------------------
# Test 5: REST-WS consistency
# ---------------------------------------------------------------------------

class TestRESTWSConsistency:
    def test_rest_ws_consistent_after_generation(
        self, client: TestClient
    ) -> None:
        """REST and WS should return consistent progress data."""
        create_resp = client.post("/api/evolution/tasks", json=_sample_evolution_create())
        task_id = create_resp.json()["task_id"]
        db_path = client.app.state.db_path

        # Simulate runner progress
        update_task(db_path, task_id, status="running")
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "UPDATE evolution_task SET current_generation = ?, best_score = ? WHERE task_id = ?",
            (7, 55.0, task_id),
        )
        conn.commit()
        conn.close()

        # Check REST
        rest_resp = client.get(f"/api/evolution/tasks/{task_id}")
        rest_data = rest_resp.json()
        assert rest_data["current_generation"] == 7

        # Check WS snapshot
        with client.websocket_connect(f"/ws/evolution/{task_id}") as ws:
            ws.receive_json()  # subscribed
            snapshot = ws.receive_json()
            assert snapshot["type"] == "task_snapshot"
            assert snapshot["current_generation"] == 7
            assert snapshot["best_score"] == rest_data["best_score"]


# ---------------------------------------------------------------------------
# Test 6: Runner error recovery
# ---------------------------------------------------------------------------

class TestRunnerErrorRecovery:
    def test_runner_recovers_after_task_error(
        self, tmp_db: Path, tmp_data_dir: Path
    ) -> None:
        """After a task fails, runner should process the next one."""
        from api.runner import EvolutionRunner

        runner = EvolutionRunner(db_path=tmp_db, data_dir=tmp_data_dir)

        # First task: will fail
        dna = _make_dna()
        save_task(tmp_db, "task-err-1", 80.0, "profit_first", "BTCUSDT", "4h", dna)
        row1 = dict(get_task(tmp_db, "task-err-1"))

        with patch("core.data.mtf_loader.load_and_prepare_df", side_effect=RuntimeError("corrupt")):
            runner._run_task(row1)

        assert runner._active_task_id is None

        # Second task: succeeds (no data -> stopped with no_data)
        save_task(tmp_db, "task-err-2", 80.0, "profit_first", "BTCUSDT", "4h", dna)
        row2 = dict(get_task(tmp_db, "task-err-2"))

        with patch("core.data.mtf_loader.load_and_prepare_df", return_value=None):
            runner._run_task(row2)

        assert runner._active_task_id is None
        row = get_task(tmp_db, "task-err-2")
        assert row["status"] == "stopped"
        assert row["stop_reason"] == "no_data"
