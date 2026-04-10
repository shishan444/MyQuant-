"""WebSocket endpoint for evolution progress updates."""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/evolution/{task_id}")
async def evolution_ws(websocket: WebSocket, task_id: str) -> None:
    """WebSocket for real-time evolution progress updates.

    The server accepts a connection and responds to ping messages.
    In production, this would stream generation updates from the
    evolution engine.
    """
    await websocket.accept()
    try:
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
