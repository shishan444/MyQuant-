"""Chart indicator configuration routes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends

from api.deps import get_db_path

router = APIRouter(prefix="/api/config", tags=["chart_config"])

CHART_INDICATOR_DEFAULTS: Dict[str, Any] = {
    "ema_periods": [10, 20, 50],
    "ema_colors": ["#3B82F6", "#10B981", "#F59E0B"],
    "boll": {"enabled": True, "period": 20, "std": 2.0, "color": "#F59E0B"},
    "rsi": {"enabled": True, "period": 14, "overbought": 70, "oversold": 30},
    "vol": {"enabled": True, "position": "overlay"},
}


def _chart_config_path(db_path: Path) -> Path:
    return db_path.parent / "chart_indicators.json"


def _read_chart_config(db_path: Path) -> Dict[str, Any]:
    path = _chart_config_path(db_path)
    if path.exists():
        try:
            with open(path) as f:
                saved = json.load(f)
            return {**CHART_INDICATOR_DEFAULTS, **saved}
        except (json.JSONDecodeError, OSError):
            pass
    return {**CHART_INDICATOR_DEFAULTS}


def _write_chart_config(db_path: Path, config: Dict[str, Any]) -> None:
    path = _chart_config_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


@router.get("/chart_indicators")
def get_chart_indicators(db_path: Path = Depends(get_db_path)) -> Dict[str, Any]:
    return _read_chart_config(db_path)


@router.put("/chart_indicators")
def update_chart_indicators(
    payload: Dict[str, Any],
    db_path: Path = Depends(get_db_path),
) -> Dict[str, Any]:
    current = _read_chart_config(db_path)
    for key in ("ema_periods", "ema_colors", "boll", "rsi", "vol"):
        if key in payload:
            current[key] = payload[key]
    _write_chart_config(db_path, current)
    return current
