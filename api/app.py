"""FastAPI application entry point with CORS, lifecycle, and route mounting."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from MyQuant.api.db_ext import init_db_ext
from MyQuant.api.routes import data, evolution, strategies, ws
from MyQuant.api.schemas import HealthResponse


def create_app(
    db_path: Path | None = None,
    data_dir: Path | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        db_path: Path to the SQLite database file.
                 Defaults to ``data/quant.db`` relative to project root.
        data_dir: Path to the data directory for Parquet files.
                  Defaults to ``data/market`` relative to project root.
    """
    if db_path is None:
        project_root = Path(__file__).resolve().parent.parent
        db_path = project_root / "data" / "quant.db"
    if data_dir is None:
        project_root = Path(__file__).resolve().parent.parent
        data_dir = project_root / "data" / "market"

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Startup: initialize database
        db_path.parent.mkdir(parents=True, exist_ok=True)
        data_dir.mkdir(parents=True, exist_ok=True)
        init_db_ext(db_path)

        # Store paths on app state for dependency injection
        app.state.db_path = db_path
        app.state.data_dir = data_dir

        yield

    app = FastAPI(
        title="MyQuant API",
        version="0.9.0",
        lifespan=lifespan,
    )

    # CORS: allow frontend dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount routers
    app.include_router(strategies.router)
    app.include_router(evolution.router)
    app.include_router(data.router)
    app.include_router(ws.router)

    # Health check endpoint
    @app.get("/api/health", response_model=HealthResponse)
    def health_check() -> HealthResponse:
        return HealthResponse(
            status="ok",
            version="0.9.0",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    return app


# Default app instance for uvicorn
app = create_app()
