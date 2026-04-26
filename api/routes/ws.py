"""WebSocket endpoint for evolution progress updates.

Supports subscribing to specific task_id and receiving
generation_complete push messages from the EvolutionRunner.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])

# ---------------------------------------------------------------------------
# Connection manager: track active WS connections per task_id
# ---------------------------------------------------------------------------

class _ConnectionManager:
    """Manages WebSocket connections grouped by task_id."""

    def __init__(self) -> None:
        self._connections: Dict[str, Set[WebSocket]] = {}

    def add(self, task_id: str, ws: WebSocket) -> None:
        self._connections.setdefault(task_id, set()).add(ws)

    def remove(self, task_id: str, ws: WebSocket) -> None:
        conns = self._connections.get(task_id)
        if conns:
            conns.discard(ws)
            if not conns:
                del self._connections[task_id]

    async def push(self, task_id: str, payload: dict) -> None:
        """Send a JSON message to all connections subscribed to task_id."""
        conns = list(self._connections.get(task_id, set()))
        msg = json.dumps(payload, ensure_ascii=False, default=str)
        for ws in conns:
            try:
                await ws.send_text(msg)
            except Exception:
                pass


manager = _ConnectionManager()


def get_manager() -> _ConnectionManager:
    return manager


# ---------------------------------------------------------------------------
# Task snapshot helper
# ---------------------------------------------------------------------------

def _get_task_snapshot(websocket: WebSocket, task_id: str) -> Optional[Dict[str, Any]]:
    """Read task current state from DB and return a WS snapshot message."""
    try:
        db_path = websocket.app.state.db_path
        from core.persistence.db import get_task
        row = get_task(db_path, task_id)
        if row is None:
            return None
        # Only send snapshot for active or recently active tasks
        status = row.get("status", "")
        if status not in ("running", "paused", "pending", "completed"):
            return None
        return {
            "type": "task_snapshot",
            "task_id": task_id,
            "status": status,
            "current_generation": row.get("current_generation", 0),
            "best_score": row.get("best_score"),
            "target_score": row.get("target_score"),
            "max_generations": row.get("max_generations"),
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/ws/evolution/{task_id}")
async def evolution_ws(websocket: WebSocket, task_id: str) -> None:
    """WebSocket for real-time evolution progress updates.

    Protocol:
      Client -> Server:
        {"type": "ping"}
        {"type": "subscribe"}  (auto-subscribes to the URL's task_id)

      Server -> Client:
        {"type": "pong"}
        {"type": "subscribed", "task_id": "..."}
        {"type": "task_snapshot", ...}  (sent on connect for progress recovery)
        {"type": "task_started", ...}   (sent when runner begins execution)
        {"type": "generation_complete", "task_id": "...", "generation": N, ...}
        {"type": "evolution_complete", "task_id": "...", ...}
    """
    await websocket.accept()

    # Auto-subscribe
    manager.add(task_id, websocket)

    try:
        await websocket.send_json({"type": "subscribed", "task_id": task_id})

        # Send current task state snapshot for progress recovery on reconnect
        snapshot = _get_task_snapshot(websocket, task_id)
        if snapshot:
            await websocket.send_json(snapshot)

        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg_type == "subscribe":
                await websocket.send_json({
                    "type": "subscribed",
                    "task_id": task_id,
                })
            else:
                await websocket.send_json({
                    "type": "echo",
                    "data": data,
                })
    except WebSocketDisconnect:
        pass
    finally:
        manager.remove(task_id, websocket)
