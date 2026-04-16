"""Integration tests for validate API and chart_config API."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from api.app import create_app


# ── Fixtures ──


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def client(db_path: Path, tmp_data_dir: Path):
    app = create_app(db_path=db_path, data_dir=tmp_data_dir)
    with TestClient(app) as c:
        yield c


# ── Validate API ──


class TestValidateAPI:
    """Tests for POST /api/validate endpoint."""

    def test_validate_with_no_data(self, client):
        """Should return empty result when no data files exist."""
        resp = client.post("/api/validate", json={
            "pair": "BTCUSDT",
            "timeframe": "4h",
            "start": "2024-01-01",
            "end": "2024-06-01",
            "when": [{"subject": "rsi_14", "action": "cross_above", "target": "70", "logic": "AND"}],
            "then": [{"subject": "close", "action": "drops_pct", "target": "2", "logic": "AND"}],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "match_rate" in data
        assert "total_count" in data
        assert data["total_count"] == 0

    def test_validate_accepts_base_timeframe(self, client):
        """Should accept base_timeframe field without error."""
        resp = client.post("/api/validate", json={
            "pair": "BTCUSDT",
            "timeframe": "15m",
            "base_timeframe": "15m",
            "start": "2024-01-01",
            "end": "2024-06-01",
            "when": [{"subject": "close", "action": "rises_pct", "target": "1", "logic": "AND"}],
            "then": [{"subject": "close", "action": "drops_pct", "target": "1", "logic": "AND"}],
        })
        assert resp.status_code == 200

    def test_validate_condition_with_timeframe(self, client):
        """Should accept timeframe field in conditions without error."""
        resp = client.post("/api/validate", json={
            "pair": "BTCUSDT",
            "timeframe": "15m",
            "base_timeframe": "15m",
            "start": "2024-01-01",
            "end": "2024-06-01",
            "when": [{"subject": "close", "action": "rises_pct", "target": "1", "logic": "AND", "timeframe": "4h"}],
            "then": [{"subject": "close", "action": "drops_pct", "target": "1", "logic": "AND"}],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "warnings" in data

    def test_validate_missing_required_fields(self, client):
        """Should return 422 for missing required fields."""
        resp = client.post("/api/validate", json={
            "pair": "BTCUSDT",
            # missing timeframe, start, end, when, then
        })
        assert resp.status_code == 422

    def test_validate_triggers_endpoint(self, client):
        """GET /api/validate/{task_id}/triggers should return paginated structure."""
        resp = client.get("/api/validate/test-task/triggers", params={"page": 1, "per_page": 10})
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "records" in data


# ── Chart Config API ──


class TestChartConfigAPI:
    """Tests for GET/PUT /api/config/chart_indicators."""

    def test_get_default_config(self, client):
        """Should return default config when no saved config exists."""
        resp = client.get("/api/config/chart_indicators")
        assert resp.status_code == 200
        data = resp.json()
        assert "ema_periods" in data
        assert data["ema_periods"] == [10, 20, 50]
        assert "boll" in data
        assert data["boll"]["enabled"] is True
        assert "rsi" in data
        assert "vol" in data

    def test_update_ema_periods(self, client):
        """Should persist updated EMA periods."""
        resp = client.put("/api/config/chart_indicators", json={
            "ema_periods": [7, 14, 21, 50],
            "ema_colors": ["#FF0000", "#00FF00", "#0000FF", "#FFFF00"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ema_periods"] == [7, 14, 21, 50]

        # Verify persistence via GET
        resp2 = client.get("/api/config/chart_indicators")
        assert resp2.json()["ema_periods"] == [7, 14, 21, 50]

    def test_update_boll_config(self, client):
        resp = client.put("/api/config/chart_indicators", json={
            "boll": {"enabled": False, "period": 30, "std": 2.5, "color": "#FFFFFF"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["boll"]["enabled"] is False
        assert data["boll"]["period"] == 30

    def test_partial_update_preserves_others(self, client):
        """Updating one field should not reset others."""
        # Set initial config
        client.put("/api/config/chart_indicators", json={
            "ema_periods": [5, 10, 20],
        })
        # Update only boll
        client.put("/api/config/chart_indicators", json={
            "boll": {"enabled": True, "period": 25, "std": 2.0, "color": "#FF0000"},
        })
        # ema_periods should still be [5, 10, 20]
        resp = client.get("/api/config/chart_indicators")
        data = resp.json()
        assert data["ema_periods"] == [5, 10, 20]
        assert data["boll"]["period"] == 25
