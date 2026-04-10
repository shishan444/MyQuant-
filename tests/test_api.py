"""Tests for FastAPI API layer (v0.9).

Covers:
- Strategy CRUD endpoints (create, list, get, update, delete)
- Strategy backtest endpoint
- Strategy compare endpoint
- Evolution task endpoints (create, list, get, history, pause, stop)
- Data management endpoints (datasets list, get, import, delete, preview, ohlcv)
- WebSocket connection for evolution progress
- CORS configuration
- Error handling (404, validation errors)
"""
from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from MyQuant.api.app import create_app


# ── Fixtures ──


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Return a temporary database path."""
    return tmp_path / "test_api.db"


@pytest.fixture
def client(db_path: Path, tmp_data_dir: Path):
    """Create a TestClient with test configuration.

    Yields the client within a lifespan context so startup/shutdown events fire.
    """
    app = create_app(db_path=db_path, data_dir=tmp_data_dir)
    with TestClient(app) as c:
        yield c


def _sample_dna_dict() -> Dict[str, Any]:
    """Build a minimal valid StrategyDNA dict."""
    return {
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
    }


def _sample_strategy_create() -> Dict[str, Any]:
    """Build a payload for POST /api/strategies."""
    return {
        "name": "RSI Reversal",
        "dna": _sample_dna_dict(),
        "symbol": "BTCUSDT",
        "timeframe": "4h",
        "source": "manual",
        "tags": "reversal,rsi",
        "notes": "Test strategy",
    }


def _sample_evolution_create() -> Dict[str, Any]:
    """Build a payload for POST /api/evolution/tasks."""
    return {
        "initial_dna": _sample_dna_dict(),
        "symbol": "BTCUSDT",
        "timeframe": "4h",
        "target_score": 80.0,
        "score_template": "profit_first",
        "population_size": 15,
        "max_generations": 200,
    }


# ── Test: CORS ──


class TestCORS:
    def test_cors_allows_localhost_5173(self, client: TestClient) -> None:
        """CORS should allow requests from localhost:5173."""
        response = client.options(
            "/api/strategies",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code in (200, 204)
        assert "access-control-allow-origin" in response.headers


# ── Test: Strategy CRUD ──


class TestStrategyCreate:
    def test_create_strategy(self, client: TestClient) -> None:
        """POST /api/strategies should create a strategy and return 201."""
        payload = _sample_strategy_create()
        response = client.post("/api/strategies", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "RSI Reversal"
        assert data["symbol"] == "BTCUSDT"
        assert data["timeframe"] == "4h"
        assert data["source"] == "manual"
        assert data["strategy_id"] is not None
        assert data["created_at"] is not None

    def test_create_strategy_minimal(self, client: TestClient) -> None:
        """Creating a strategy with minimal fields should succeed."""
        payload = {
            "dna": _sample_dna_dict(),
            "symbol": "ETHUSDT",
            "timeframe": "1h",
        }
        response = client.post("/api/strategies", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["symbol"] == "ETHUSDT"

    def test_create_strategy_invalid_missing_required(self, client: TestClient) -> None:
        """POST with missing required fields should return 422."""
        response = client.post("/api/strategies", json={})
        assert response.status_code == 422


class TestStrategyList:
    def test_list_strategies_empty(self, client: TestClient) -> None:
        """GET /api/strategies should return empty list when no strategies."""
        response = client.get("/api/strategies")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_strategies_after_create(self, client: TestClient) -> None:
        """GET /api/strategies should return created strategies."""
        client.post("/api/strategies", json=_sample_strategy_create())
        response = client.get("/api/strategies")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "RSI Reversal"

    def test_list_strategies_filter_by_symbol(self, client: TestClient) -> None:
        """GET /api/strategies?symbol=BTCUSDT should filter."""
        payload_btc = _sample_strategy_create()
        payload_eth = {**_sample_strategy_create(), "symbol": "ETHUSDT"}
        client.post("/api/strategies", json=payload_btc)
        client.post("/api/strategies", json=payload_eth)
        response = client.get("/api/strategies", params={"symbol": "BTCUSDT"})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["symbol"] == "BTCUSDT"

    def test_list_strategies_filter_by_source(self, client: TestClient) -> None:
        """GET /api/strategies?source=manual should filter."""
        client.post("/api/strategies", json=_sample_strategy_create())
        response = client.get("/api/strategies", params={"source": "manual"})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    def test_list_strategies_sort_by_score(self, client: TestClient) -> None:
        """GET /api/strategies?sort_by=best_score should sort."""
        for i in range(3):
            payload = {**_sample_strategy_create(), "name": f"Strat {i}"}
            client.post("/api/strategies", json=payload)
        response = client.get("/api/strategies", params={"sort_by": "created_at", "sort_order": "asc"})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3

    def test_list_strategies_with_limit(self, client: TestClient) -> None:
        """GET /api/strategies?limit=2 should limit results."""
        for i in range(5):
            payload = {**_sample_strategy_create(), "name": f"Strat {i}"}
            client.post("/api/strategies", json=payload)
        response = client.get("/api/strategies", params={"limit": 2})
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5


class TestStrategyGet:
    def test_get_strategy(self, client: TestClient) -> None:
        """GET /api/strategies/{id} should return strategy details."""
        create_resp = client.post("/api/strategies", json=_sample_strategy_create())
        strategy_id = create_resp.json()["strategy_id"]
        response = client.get(f"/api/strategies/{strategy_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["strategy_id"] == strategy_id
        assert data["name"] == "RSI Reversal"

    def test_get_strategy_not_found(self, client: TestClient) -> None:
        """GET /api/strategies/{id} with nonexistent ID should return 404."""
        response = client.get("/api/strategies/nonexistent-id")
        assert response.status_code == 404


class TestStrategyUpdate:
    def test_update_strategy(self, client: TestClient) -> None:
        """PUT /api/strategies/{id} should update strategy."""
        create_resp = client.post("/api/strategies", json=_sample_strategy_create())
        strategy_id = create_resp.json()["strategy_id"]
        response = client.put(
            f"/api/strategies/{strategy_id}",
            json={"name": "Updated Name", "notes": "Updated notes"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["notes"] == "Updated notes"

    def test_update_strategy_not_found(self, client: TestClient) -> None:
        """PUT /api/strategies/{id} with nonexistent ID should return 404."""
        response = client.put(
            "/api/strategies/nonexistent-id",
            json={"name": "New Name"},
        )
        assert response.status_code == 404


class TestStrategyDelete:
    def test_delete_strategy(self, client: TestClient) -> None:
        """DELETE /api/strategies/{id} should delete strategy."""
        create_resp = client.post("/api/strategies", json=_sample_strategy_create())
        strategy_id = create_resp.json()["strategy_id"]
        response = client.delete(f"/api/strategies/{strategy_id}")
        assert response.status_code == 204
        # Verify it is gone
        get_resp = client.get(f"/api/strategies/{strategy_id}")
        assert get_resp.status_code == 404

    def test_delete_strategy_not_found(self, client: TestClient) -> None:
        """DELETE /api/strategies/{id} with nonexistent ID should return 404."""
        response = client.delete("/api/strategies/nonexistent-id")
        assert response.status_code == 404


# ── Test: Strategy Backtest ──


class TestStrategyBacktest:
    @patch("MyQuant.api.routes.strategies._bt_engine_mod")
    @patch("MyQuant.api.routes.strategies.score_strategy")
    def test_backtest_strategy(
        self,
        mock_score: MagicMock,
        mock_bt_mod: MagicMock,
        client: TestClient,
    ) -> None:
        """POST /api/strategies/backtest should run backtest and return results."""
        import pandas as pd

        # Create a strategy first
        create_resp = client.post("/api/strategies", json=_sample_strategy_create())
        strategy_id = create_resp.json()["strategy_id"]

        # Create a dummy parquet file so the exists check passes
        data_dir = client.app.state.data_dir
        dummy_df = pd.DataFrame(
            {"open": [60000], "high": [61000], "low": [59000],
             "close": [60500], "volume": [100]},
            index=pd.DatetimeIndex(["2024-01-01"], name="timestamp"),
        )
        dummy_df.to_parquet(data_dir / "BTCUSDT_4h.parquet")

        # Mock backtest result
        mock_result = MagicMock()
        mock_result.total_return = 0.25
        mock_result.sharpe_ratio = 1.8
        mock_result.max_drawdown = -0.12
        mock_result.win_rate = 0.62
        mock_result.total_trades = 150
        mock_result.equity_curve = MagicMock()
        mock_result.trades_df = None
        mock_bt_mod.BacktestEngine.return_value.run.return_value = mock_result

        mock_score.return_value = {
            "total_score": 82.1,
            "dimension_scores": {"return": 90, "risk": 80},
            "template_name": "profit_first",
            "threshold": 75.0,
        }

        response = client.post(
            "/api/strategies/backtest",
            json={
                "strategy_id": strategy_id,
                "dataset_id": "BTCUSDT_4h",
                "init_cash": 100000,
                "fee": 0.001,
                "slippage": 0.0005,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["strategy_id"] == strategy_id
        assert data["total_return"] == 0.25
        assert data["sharpe_ratio"] == 1.8
        assert data["result_id"] is not None

    def test_backtest_strategy_not_found(self, client: TestClient) -> None:
        """POST /api/strategies/backtest with invalid strategy should return 404."""
        response = client.post(
            "/api/strategies/backtest",
            json={
                "strategy_id": "nonexistent",
                "dataset_id": "BTCUSDT_4h",
            },
        )
        assert response.status_code == 404


# ── Test: Strategy Compare ──


class TestStrategyCompare:
    @patch("MyQuant.api.routes.strategies._bt_engine_mod")
    @patch("MyQuant.api.routes.strategies.score_strategy")
    def test_compare_strategies(
        self,
        mock_score: MagicMock,
        mock_bt_mod: MagicMock,
        client: TestClient,
    ) -> None:
        """POST /api/strategies/compare should compare multiple strategies."""
        import pandas as pd

        # Create two strategies
        ids = []
        for i in range(2):
            payload = {**_sample_strategy_create(), "name": f"Strat {i}"}
            resp = client.post("/api/strategies", json=payload)
            ids.append(resp.json()["strategy_id"])

        # Create a dummy parquet file
        data_dir = client.app.state.data_dir
        dummy_df = pd.DataFrame(
            {"open": [60000], "high": [61000], "low": [59000],
             "close": [60500], "volume": [100]},
            index=pd.DatetimeIndex(["2024-01-01"], name="timestamp"),
        )
        dummy_df.to_parquet(data_dir / "BTCUSDT_4h.parquet")

        mock_result = MagicMock()
        mock_result.total_return = 0.15
        mock_result.sharpe_ratio = 1.2
        mock_result.max_drawdown = -0.10
        mock_result.win_rate = 0.55
        mock_result.total_trades = 80
        mock_result.equity_curve = MagicMock()
        mock_result.trades_df = None
        mock_bt_mod.BacktestEngine.return_value.run.return_value = mock_result

        mock_score.return_value = {
            "total_score": 70.0,
            "dimension_scores": {"return": 75, "risk": 65},
            "template_name": "profit_first",
            "threshold": 75.0,
        }

        response = client.post(
            "/api/strategies/compare",
            json={
                "strategy_ids": ids,
                "dataset_id": "BTCUSDT_4h",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 2
        assert data["results"][0]["strategy_id"] in ids


# ── Test: Evolution Tasks ──


class TestEvolutionTaskCreate:
    def test_create_evolution_task(self, client: TestClient) -> None:
        """POST /api/evolution/tasks should create an evolution task."""
        payload = _sample_evolution_create()
        response = client.post("/api/evolution/tasks", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["task_id"] is not None
        assert data["status"] == "pending"
        assert data["symbol"] == "BTCUSDT"
        assert data["timeframe"] == "4h"
        assert data["target_score"] == 80.0

    def test_create_evolution_task_missing_fields(self, client: TestClient) -> None:
        """POST /api/evolution/tasks with missing fields should return 422."""
        response = client.post("/api/evolution/tasks", json={})
        assert response.status_code == 422


class TestEvolutionTaskList:
    def test_list_tasks_empty(self, client: TestClient) -> None:
        """GET /api/evolution/tasks should return empty list."""
        response = client.get("/api/evolution/tasks")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_tasks_after_create(self, client: TestClient) -> None:
        """GET /api/evolution/tasks should list created tasks."""
        client.post("/api/evolution/tasks", json=_sample_evolution_create())
        response = client.get("/api/evolution/tasks")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    def test_list_tasks_filter_by_status(self, client: TestClient) -> None:
        """GET /api/evolution/tasks?status=pending should filter."""
        client.post("/api/evolution/tasks", json=_sample_evolution_create())
        response = client.get("/api/evolution/tasks", params={"status": "pending"})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1


class TestEvolutionTaskGet:
    def test_get_task(self, client: TestClient) -> None:
        """GET /api/evolution/tasks/{id} should return task details."""
        create_resp = client.post("/api/evolution/tasks", json=_sample_evolution_create())
        task_id = create_resp.json()["task_id"]
        response = client.get(f"/api/evolution/tasks/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["symbol"] == "BTCUSDT"

    def test_get_task_not_found(self, client: TestClient) -> None:
        """GET /api/evolution/tasks/{id} with nonexistent ID should return 404."""
        response = client.get("/api/evolution/tasks/nonexistent-id")
        assert response.status_code == 404


class TestEvolutionTaskHistory:
    def test_get_task_history_empty(self, client: TestClient) -> None:
        """GET /api/evolution/tasks/{id}/history should return empty list."""
        create_resp = client.post("/api/evolution/tasks", json=_sample_evolution_create())
        task_id = create_resp.json()["task_id"]
        response = client.get(f"/api/evolution/tasks/{task_id}/history")
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["generations"] == []

    def test_get_task_history_with_data(self, client: TestClient) -> None:
        """GET /api/evolution/tasks/{id}/history should return generation history."""
        create_resp = client.post("/api/evolution/tasks", json=_sample_evolution_create())
        task_id = create_resp.json()["task_id"]
        # Add history via the DB layer
        from MyQuant.core.persistence.db import save_history
        from MyQuant.api.deps import get_db_path

        # We need to use the test db_path - use the app state
        db_path = client.app.state.db_path
        save_history(db_path, task_id, 1, 75.0, 60.0, "summary1")
        save_history(db_path, task_id, 2, 80.0, 65.0, "summary2")

        response = client.get(f"/api/evolution/tasks/{task_id}/history")
        assert response.status_code == 200
        data = response.json()
        assert len(data["generations"]) == 2
        assert data["generations"][0]["generation"] == 1
        assert data["generations"][0]["best_score"] == 75.0


class TestEvolutionTaskPause:
    def test_pause_task(self, client: TestClient) -> None:
        """POST /api/evolution/tasks/{id}/pause should pause task."""
        create_resp = client.post("/api/evolution/tasks", json=_sample_evolution_create())
        task_id = create_resp.json()["task_id"]
        response = client.post(f"/api/evolution/tasks/{task_id}/pause")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "paused"

    def test_pause_task_not_found(self, client: TestClient) -> None:
        """POST /api/evolution/tasks/{id}/pause with nonexistent ID should return 404."""
        response = client.post("/api/evolution/tasks/nonexistent-id/pause")
        assert response.status_code == 404


class TestEvolutionTaskStop:
    def test_stop_task(self, client: TestClient) -> None:
        """POST /api/evolution/tasks/{id}/stop should stop task."""
        create_resp = client.post("/api/evolution/tasks", json=_sample_evolution_create())
        task_id = create_resp.json()["task_id"]
        response = client.post(f"/api/evolution/tasks/{task_id}/stop")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "stopped"

    def test_stop_task_not_found(self, client: TestClient) -> None:
        """POST /api/evolution/tasks/{id}/stop with nonexistent ID should return 404."""
        response = client.post("/api/evolution/tasks/nonexistent-id/stop")
        assert response.status_code == 404


# ── Test: Data Management ──


class TestDatasetList:
    def test_list_datasets_empty(self, client: TestClient) -> None:
        """GET /api/data/datasets should return empty list."""
        response = client.get("/api/data/datasets")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_datasets_with_data(self, client: TestClient) -> None:
        """GET /api/data/datasets should list datasets."""
        from MyQuant.api.db_ext import save_dataset_meta

        db_path = client.app.state.db_path
        save_dataset_meta(
            db_path,
            dataset_id="ds-001",
            symbol="BTCUSDT",
            interval="4h",
            parquet_path="/data/btc.parquet",
        )
        response = client.get("/api/data/datasets")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["dataset_id"] == "ds-001"

    def test_list_datasets_filter_by_symbol(self, client: TestClient) -> None:
        """GET /api/data/datasets?symbol=BTCUSDT should filter."""
        from MyQuant.api.db_ext import save_dataset_meta

        db_path = client.app.state.db_path
        save_dataset_meta(
            db_path,
            dataset_id="ds-btc",
            symbol="BTCUSDT",
            interval="4h",
            parquet_path="/data/btc.parquet",
        )
        save_dataset_meta(
            db_path,
            dataset_id="ds-eth",
            symbol="ETHUSDT",
            interval="4h",
            parquet_path="/data/eth.parquet",
        )
        response = client.get("/api/data/datasets", params={"symbol": "BTCUSDT"})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1


class TestDatasetGet:
    def test_get_dataset(self, client: TestClient) -> None:
        """GET /api/data/datasets/{id} should return dataset details."""
        from MyQuant.api.db_ext import save_dataset_meta

        db_path = client.app.state.db_path
        save_dataset_meta(
            db_path,
            dataset_id="ds-001",
            symbol="BTCUSDT",
            interval="4h",
            parquet_path="/data/btc.parquet",
            row_count=10000,
        )
        response = client.get("/api/data/datasets/ds-001")
        assert response.status_code == 200
        data = response.json()
        assert data["dataset_id"] == "ds-001"
        assert data["symbol"] == "BTCUSDT"
        assert data["row_count"] == 10000

    def test_get_dataset_not_found(self, client: TestClient) -> None:
        """GET /api/data/datasets/{id} with nonexistent ID should return 404."""
        response = client.get("/api/data/datasets/nonexistent")
        assert response.status_code == 404


class TestDatasetDelete:
    def test_delete_dataset(self, client: TestClient) -> None:
        """DELETE /api/data/datasets/{id} should delete dataset."""
        from MyQuant.api.db_ext import save_dataset_meta

        db_path = client.app.state.db_path
        save_dataset_meta(
            db_path,
            dataset_id="ds-001",
            symbol="BTCUSDT",
            interval="4h",
            parquet_path="/data/btc.parquet",
        )
        response = client.delete("/api/data/datasets/ds-001")
        assert response.status_code == 204

    def test_delete_dataset_not_found(self, client: TestClient) -> None:
        """DELETE /api/data/datasets/{id} with nonexistent ID should return 404."""
        response = client.delete("/api/data/datasets/nonexistent")
        assert response.status_code == 404


class TestDataImport:
    def test_import_csv_no_file(self, client: TestClient) -> None:
        """POST /api/data/import without file should return 422."""
        response = client.post("/api/data/import")
        assert response.status_code == 422

    @patch("MyQuant.api.routes.data.import_csv")
    def test_import_csv_success(
        self, mock_import: MagicMock, client: TestClient, tmp_data_dir: Path
    ) -> None:
        """POST /api/data/import with valid CSV should import data."""
        from MyQuant.core.data.csv_importer import CsvImportResult, ImportFormat, TimestampPrecision

        mock_import.return_value = CsvImportResult(
            dataset_id="BTCUSDT_4h",
            symbol="BTCUSDT",
            interval="4h",
            rows_imported=1000,
            format_detected=ImportFormat.BINANCE_OFFICIAL,
            timestamp_precision=TimestampPrecision.MILLISECOND,
            time_range=("2024-01-01", "2024-06-01"),
        )

        csv_content = b"1714521600000,60000,61000,59000,60500,100,1714525199999,6050000,500,50250,5025000,0\n"
        response = client.post(
            "/api/data/import",
            files={"file": ("BTCUSDT-4h-2024-01.csv", csv_content, "text/csv")},
            data={"symbol": "BTCUSDT", "interval": "4h"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["dataset_id"] == "BTCUSDT_4h"
        assert data["rows_imported"] == 1000


class TestDatasetPreview:
    def test_preview_not_found(self, client: TestClient) -> None:
        """GET /api/data/datasets/{id}/preview with nonexistent ID should return 404."""
        response = client.get("/api/data/datasets/nonexistent/preview")
        assert response.status_code == 404

    def test_preview_dataset(self, client: TestClient) -> None:
        """GET /api/data/datasets/{id}/preview should return first N rows."""
        import pandas as pd

        from MyQuant.api.db_ext import save_dataset_meta

        db_path = client.app.state.db_path
        data_dir = client.app.state.data_dir

        # Create actual parquet file
        df = pd.DataFrame(
            {"open": [60000, 61000], "high": [61000, 62000],
             "low": [59000, 60000], "close": [60500, 61500],
             "volume": [100, 200]},
            index=pd.DatetimeIndex(["2024-01-01", "2024-01-02"], name="timestamp"),
        )
        parquet_path = data_dir / "ds-001.parquet"
        df.to_parquet(parquet_path)

        save_dataset_meta(
            db_path,
            dataset_id="ds-001",
            symbol="BTCUSDT",
            interval="4h",
            parquet_path=str(parquet_path),
            row_count=2,
        )

        response = client.get("/api/data/datasets/ds-001/preview")
        assert response.status_code == 200
        data = response.json()
        assert "rows" in data
        assert data["total_rows"] == 2


class TestDatasetOhlcv:
    def test_ohlcv_not_found(self, client: TestClient) -> None:
        """GET /api/data/datasets/{id}/ohlcv with nonexistent ID should return 404."""
        response = client.get("/api/data/datasets/nonexistent/ohlcv")
        assert response.status_code == 404

    def test_ohlcv_dataset(self, client: TestClient) -> None:
        """GET /api/data/datasets/{id}/ohlcv should return OHLCV data."""
        import pandas as pd

        from MyQuant.api.db_ext import save_dataset_meta

        db_path = client.app.state.db_path
        data_dir = client.app.state.data_dir

        df = pd.DataFrame(
            {"open": [60000], "high": [61000], "low": [59000],
             "close": [60500], "volume": [100]},
            index=pd.DatetimeIndex(["2024-01-01"], name="timestamp"),
        )
        parquet_path = data_dir / "ds-001.parquet"
        df.to_parquet(parquet_path)

        save_dataset_meta(
            db_path,
            dataset_id="ds-001",
            symbol="BTCUSDT",
            interval="4h",
            parquet_path=str(parquet_path),
            row_count=1,
        )

        response = client.get(
            "/api/data/datasets/ds-001/ohlcv",
            params={"start": "2024-01-01", "end": "2024-01-02"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data


# ── Test: WebSocket ──


class TestWebSocket:
    def test_websocket_connect_and_disconnect(self, client: TestClient) -> None:
        """WebSocket should connect and disconnect cleanly."""
        with client.websocket_connect("/ws/evolution/test-task-id") as websocket:
            # Just test connection succeeds
            pass  # clean disconnect

    def test_websocket_receives_messages(self, client: TestClient) -> None:
        """WebSocket should be able to send/receive messages."""
        with client.websocket_connect("/ws/evolution/test-task-id") as websocket:
            # Send a ping
            websocket.send_json({"type": "ping"})
            # Receive a pong
            data = websocket.receive_json()
            assert data["type"] == "pong"


# ── Test: Health Check ──


class TestHealthCheck:
    def test_health_check(self, client: TestClient) -> None:
        """GET /api/health should return OK status."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
