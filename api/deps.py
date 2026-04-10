"""Dependency injection for FastAPI routes."""
from __future__ import annotations

from pathlib import Path

from fastapi import Request


def get_db_path(request: Request) -> Path:
    """Get the SQLite database path from app state."""
    return request.app.state.db_path


def get_data_dir(request: Request) -> Path:
    """Get the data directory path from app state."""
    return request.app.state.data_dir
