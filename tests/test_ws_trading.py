"""Tests for WebSocket trading endpoint: connection, messages, and push delegation.

Covers:
1. WS connection accepts and sends subscribed message
2. Ping/pong protocol
3. WS push via runner delegates correctly
4. WS push swallows exceptions
"""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

pytestmark = [pytest.mark.integration]

from tests.helpers.data_factory import make_dna


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def trading_app(tmp_path: Path):
    """Create FastAPI app with initialized DB."""
    from api.app import create_app
    from api.db_ext import init_db_ext

    db_path = tmp_path / "test.db"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    init_db_ext(db_path)
    app = create_app(db_path=db_path, data_dir=data_dir)
    return app, db_path


# ---------------------------------------------------------------------------
# Test: WS connection and subscription
# ---------------------------------------------------------------------------

class TestTradingWSConnection:

    def test_ws_subscribes_and_receives_subscribed_msg(self, trading_app):
        from fastapi.testclient import TestClient
        app, db_path = trading_app
        with TestClient(app) as client:
            with client.websocket_connect("/ws/trading/task-001") as ws:
                msg = ws.receive_json()
                assert msg["type"] == "subscribed"
                assert msg["task_id"] == "task-001"

    def test_ws_ping_pong(self, trading_app):
        from fastapi.testclient import TestClient
        app, db_path = trading_app
        with TestClient(app) as client:
            with client.websocket_connect("/ws/trading/ping-test") as ws:
                msg1 = ws.receive_json()
                assert msg1["type"] == "subscribed"
                ws.send_json({"type": "ping"})
                msg2 = ws.receive_json()
                assert msg2["type"] == "pong"


# ---------------------------------------------------------------------------
# Test: Snapshot helper
# ---------------------------------------------------------------------------

class TestTradingSnapshotHelper:

    def test_snapshot_returns_data_for_running_task(self, trading_app):
        """_get_trading_snapshot returns snapshot dict for active tasks."""
        app, db_path = trading_app
        from api.db_ext import save_paper_trading_task, update_paper_trading_task

        dna = make_dna()
        save_paper_trading_task(
            db_path, task_id="snap-1", dna_json=dna.to_json(),
            symbol="BTCUSDT", timeframe="4h", initial_cash=100_000,
        )
        update_paper_trading_task(
            db_path, "snap-1", status="running",
            position_side="long", balance=80000.0,
            total_trades=3, total_pnl=500.0,
        )

        from api.routes.ws import _get_trading_snapshot
        from unittest.mock import MagicMock
        mock_ws = MagicMock()
        mock_ws.app.state.db_path = db_path

        result = _get_trading_snapshot(mock_ws, "snap-1")
        assert result is not None
        assert result["type"] == "task_snapshot"
        assert result["task_id"] == "snap-1"
        assert result["status"] == "running"
        assert result["position_side"] == "long"
        assert result["balance"] == 80000.0

    def test_snapshot_returns_none_for_stopped_task(self, trading_app):
        """_get_trading_snapshot returns None for stopped tasks."""
        app, db_path = trading_app
        from api.db_ext import save_paper_trading_task, update_paper_trading_task

        dna = make_dna()
        save_paper_trading_task(
            db_path, task_id="snap-stopped", dna_json=dna.to_json(),
        )
        update_paper_trading_task(db_path, "snap-stopped", status="stopped")

        from api.routes.ws import _get_trading_snapshot
        from unittest.mock import MagicMock
        mock_ws = MagicMock()
        mock_ws.app.state.db_path = db_path

        result = _get_trading_snapshot(mock_ws, "snap-stopped")
        assert result is None

    def test_snapshot_returns_none_for_nonexistent_task(self, trading_app):
        """_get_trading_snapshot returns None for unknown task IDs."""
        app, db_path = trading_app

        from api.routes.ws import _get_trading_snapshot
        from unittest.mock import MagicMock
        mock_ws = MagicMock()
        mock_ws.app.state.db_path = db_path

        result = _get_trading_snapshot(mock_ws, "no-exist")
        assert result is None


# ---------------------------------------------------------------------------
# Test: WS push delegation
# ---------------------------------------------------------------------------

class TestTradingWSPush:

    def test_push_ws_calls_configured_fn(self):
        """Verify _push_ws delegates to the configured push function."""
        from core.trading.runner import _push_ws
        import core.trading.runner as runner_mod

        mock_fn = MagicMock()
        original = runner_mod._ws_push_fn
        runner_mod._ws_push_fn = mock_fn
        try:
            _push_ws("task-1", {"type": "position_update"})
            mock_fn.assert_called_once_with("task-1", {"type": "position_update"})
        finally:
            runner_mod._ws_push_fn = original

    def test_push_ws_noop_when_no_fn(self):
        """Verify _push_ws is a no-op when no push function is set."""
        from core.trading.runner import _push_ws
        import core.trading.runner as runner_mod

        original = runner_mod._ws_push_fn
        runner_mod._ws_push_fn = None
        try:
            _push_ws("task-1", {"type": "position_update"})  # should not raise
        finally:
            runner_mod._ws_push_fn = original

    def test_push_ws_swallows_exception(self):
        """Verify _push_ws does not propagate exceptions."""
        from core.trading.runner import _push_ws
        import core.trading.runner as runner_mod

        mock_fn = MagicMock(side_effect=RuntimeError("WS error"))
        original = runner_mod._ws_push_fn
        runner_mod._ws_push_fn = mock_fn
        try:
            _push_ws("task-1", {"type": "position_update"})  # should not raise
        finally:
            runner_mod._ws_push_fn = original
