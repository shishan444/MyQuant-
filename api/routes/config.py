"""Config CRUD routes - GET/PUT /api/config."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends

from api.deps import get_db_path

router = APIRouter(prefix="/api/config", tags=["config"])

_DEFAULT_CONFIG: Dict[str, Any] = {
    "language": "zh-CN",
    "timezone": "UTC+8",
    "notify_evolution": True,
    "notify_signal": True,
    "binance_api_key": "",
    "binance_secret_key": "",
    "binance_connected": False,
    "init_cash": 100000,
    "maker_fee": 0.1,
    "taker_fee": 0.1,
    "max_positions": 1,
}


def _config_path(db_path: Path) -> Path:
    return db_path.parent / "config.json"


def _read_config(db_path: Path) -> Dict[str, Any]:
    path = _config_path(db_path)
    if path.exists():
        try:
            with open(path) as f:
                saved = json.load(f)
            return {**_DEFAULT_CONFIG, **saved}
        except (json.JSONDecodeError, OSError):
            pass
    return {**_DEFAULT_CONFIG}


def _write_config(db_path: Path, config: Dict[str, Any]) -> None:
    path = _config_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


@router.get("")
def get_config(db_path: Path = Depends(get_db_path)) -> Dict[str, Any]:
    return _read_config(db_path)


@router.put("")
def update_config(
    payload: Dict[str, Any],
    db_path: Path = Depends(get_db_path),
) -> Dict[str, Any]:
    current = _read_config(db_path)
    for key, value in payload.items():
        if key in _DEFAULT_CONFIG:
            current[key] = value
    _write_config(db_path, current)
    return current
