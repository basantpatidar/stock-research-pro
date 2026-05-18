import asyncio
import json
from datetime import datetime, timezone
from typing import Set

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import verify_api_key
from app.config import get_settings
from app.db.database import get_db
from app.db.models import AlertHistory

router = APIRouter(prefix="/alerts", tags=["alerts"])

# In-memory set of active WebSocket connections
_connections: Set[WebSocket] = set()


async def broadcast(message: dict):
    """Broadcast a message to all connected WebSocket clients."""
    if not _connections:
        return
    disconnected = set()
    payload = json.dumps(message)
    for ws in _connections:
        try:
            await ws.send_text(payload)
        except Exception:
            disconnected.add(ws)
    _connections.difference_update(disconnected)


def get_connection_manager():
    """Returns the broadcast function — used by background services."""
    return broadcast


@router.websocket("/ws")
async def alerts_websocket(
    websocket: WebSocket,
    api_key: str = Query(default=""),
):
    """
    WebSocket endpoint for real-time dashboard alerts.
    Connect with: ws://localhost:8000/alerts/ws?api_key=YOUR_KEY
    """
    settings = get_settings()
    if settings.environment != "development":
        if not api_key or api_key != settings.api_key:
            await websocket.close(code=4001)
            return

    await websocket.accept()
    _connections.add(websocket)

    try:
        # Send connection confirmation
        await websocket.send_text(
            json.dumps(
                {
                    "type": "connected",
                    "message": "Stock Research Pro — real-time alerts active",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        )

        # Keep connection alive — client sends pings
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                # Send server-side keepalive
                await websocket.send_text(json.dumps({"type": "heartbeat"}))
            except Exception:
                break

    except WebSocketDisconnect:
        pass
    finally:
        _connections.discard(websocket)


@router.get("/history")
async def get_alert_history(
    limit: int = 20,
    dismissed: bool = False,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Get recent alert history from the database."""
    result = await db.execute(
        select(AlertHistory)
        .where(AlertHistory.dismissed == dismissed)
        .order_by(AlertHistory.triggered_at.desc())
        .limit(limit)
    )
    alerts = result.scalars().all()
    return {
        "alerts": [
            {
                "id": a.id,
                "ticker": a.ticker,
                "type": a.alert_type,
                "title": a.title,
                "body": a.body,
                "score": a.score,
                "triggered_at": a.triggered_at.isoformat(),
                "source": a.source,
            }
            for a in alerts
        ]
    }


@router.patch("/history/{alert_id}/dismiss")
async def dismiss_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Dismiss an alert."""
    result = await db.execute(select(AlertHistory).where(AlertHistory.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        return {"message": "Alert not found"}
    alert.dismissed = True
    await db.commit()
    return {"message": "Alert dismissed"}
