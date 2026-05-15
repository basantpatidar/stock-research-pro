"""Broker / order execution routes.

See docs/api.md SEC:BROKER_ROUTES for the route catalog and
docs/trading.md SEC:PHASES for the rollout plan.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import verify_api_key
from app.brokers import (
    AccountInfo,
    BaseBroker,
    BrokerError,
    BrokerRejected,
    BrokerUnreachable,
    Order,
    OrderSide,
    OrderType,
    PlaceOrderRequest,
    Position,
    TimeInForce,
    get_broker,
)
from app.config import get_settings
from app.db.database import get_db
from app.db.models import BrokerOrder
from app.services.trading.limits import check_order_caps

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/broker", tags=["broker"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_broker_or_raise(response: Response) -> BaseBroker:
    """Resolve broker from settings; map config/connectivity failures to 503
    so the UI shows the same banner for both. Header distinguishes the two."""
    settings = get_settings()
    try:
        return get_broker(settings)
    except BrokerUnreachable as exc:
        response.headers["X-Broker-Status"] = "unreachable"
        raise HTTPException(status_code=503, detail=str(exc))
    except BrokerError as exc:
        response.headers["X-Broker-Status"] = "misconfigured"
        raise HTTPException(status_code=503, detail=str(exc))


def _broker_order_to_dto(row: BrokerOrder) -> Order:
    """Map the DB row back to the public DTO so the API contract is identical
    whether the row is local-only (broker_order_id is None) or post-fill."""
    return Order(
        broker_order_id=row.broker_order_id or str(row.id),
        client_order_id=row.client_order_id,
        symbol=row.symbol,
        side=OrderSide(row.side),
        qty=row.qty,
        order_type=OrderType(row.order_type),
        limit_price=row.limit_price,
        stop_price=row.stop_price,
        take_profit_price=row.take_profit_price,
        time_in_force=TimeInForce(row.time_in_force),
        status=row.status,  # already broker-DTO string
        filled_qty=row.filled_qty,
        filled_avg_price=row.filled_avg_price,
        submitted_at=row.submitted_at,
        filled_at=row.filled_at,
        canceled_at=row.canceled_at,
        rejected_reason=row.rejected_reason,
    )


# ── Account / Clock / Positions ───────────────────────────────────────────────

@router.get("/account", response_model=AccountInfo, dependencies=[Depends(verify_api_key)])
def get_broker_account(response: Response) -> AccountInfo:
    """Smoke test for broker connectivity. Returns broker, mode, and account
    snapshot. 503 with X-Broker-Status header if the broker is unreachable
    or misconfigured (see _get_broker_or_raise)."""
    broker = _get_broker_or_raise(response)
    try:
        return broker.get_account()
    except BrokerUnreachable as exc:
        response.headers["X-Broker-Status"] = "unreachable"
        raise HTTPException(status_code=503, detail=str(exc))


class ClockResponse(BaseModel):
    is_open: bool
    broker: str
    mode: Literal["paper", "live"]


@router.get("/clock", response_model=ClockResponse, dependencies=[Depends(verify_api_key)])
def get_broker_clock(response: Response) -> ClockResponse:
    """Mirrors the broker's market clock. The UI uses this to disable buy
    buttons when the market is closed instead of computing locally — broker
    clock is the source of truth for halts, holidays, and early closes."""
    broker = _get_broker_or_raise(response)
    try:
        return ClockResponse(is_open=broker.is_market_open(), broker=broker.name, mode=broker.mode)
    except BrokerUnreachable as exc:
        response.headers["X-Broker-Status"] = "unreachable"
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/positions", response_model=list[Position], dependencies=[Depends(verify_api_key)])
def get_broker_positions(response: Response) -> list[Position]:
    """Current open positions per the broker. Phase 2 ships uncached;
    we'll add a 30s Redis layer if the polling cost becomes meaningful."""
    broker = _get_broker_or_raise(response)
    try:
        return broker.get_positions()
    except BrokerUnreachable as exc:
        response.headers["X-Broker-Status"] = "unreachable"
        raise HTTPException(status_code=503, detail=str(exc))


# ── Orders — read ─────────────────────────────────────────────────────────────

@router.get("/orders", response_model=list[Order], dependencies=[Depends(verify_api_key)])
async def list_broker_orders(
    response: Response,
    status: Literal["open", "all", "closed"] = Query("open"),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> list[Order]:
    """Merge: local BrokerOrder rows (source of truth for what we submitted)
    + broker's current fill state (source of truth for status / filled_qty).
    Falls back to local rows alone if the broker is unreachable, so the page
    isn't blank during an Alpaca outage."""
    broker = _get_broker_or_raise(response)

    # Local rows for current mode only — paper and live MUST never mix.
    rows = (await db.scalars(
        select(BrokerOrder)
        .where(BrokerOrder.mode == broker.mode)
        .order_by(BrokerOrder.submitted_at.desc())
        .limit(limit)
    )).all()

    try:
        live = broker.get_orders(status=status, limit=limit)
        live_by_id = {o.broker_order_id: o for o in live}
    except BrokerUnreachable as exc:
        logger.warning("broker get_orders failed, returning local-only: %s", exc)
        live_by_id = {}
        response.headers["X-Broker-Status"] = "unreachable"

    merged: list[Order] = []
    for row in rows:
        if row.broker_order_id and row.broker_order_id in live_by_id:
            merged.append(live_by_id[row.broker_order_id])
        else:
            merged.append(_broker_order_to_dto(row))

    if status == "open":
        merged = [o for o in merged if o.status in ("new", "accepted", "partially_filled")]
    elif status == "closed":
        merged = [o for o in merged if o.status in ("filled", "canceled", "rejected", "expired")]

    return merged


@router.get("/orders/{order_id}", response_model=Order, dependencies=[Depends(verify_api_key)])
def get_broker_order(response: Response, order_id: str) -> Order:
    """Single-order lookup against the broker. Use the local DB row if you
    only need our snapshot — this endpoint always round-trips."""
    broker = _get_broker_or_raise(response)
    try:
        return broker.get_order(order_id)
    except BrokerUnreachable as exc:
        response.headers["X-Broker-Status"] = "unreachable"
        raise HTTPException(status_code=503, detail=str(exc))
    except BrokerError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/orders/{order_id}", status_code=204, dependencies=[Depends(verify_api_key)])
async def cancel_broker_order(
    response: Response,
    order_id: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Best-effort cancel. Already-filled / already-canceled returns 204
    silently (broker layer handles the no-op). Also marks the local row
    as canceled so the UI reflects intent even if the broker round-trip
    is slow."""
    broker = _get_broker_or_raise(response)
    try:
        broker.cancel_order(order_id)
    except BrokerUnreachable as exc:
        response.headers["X-Broker-Status"] = "unreachable"
        raise HTTPException(status_code=503, detail=str(exc))
    except BrokerError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    row = (await db.scalars(
        select(BrokerOrder).where(BrokerOrder.broker_order_id == order_id)
    )).one_or_none()
    if row is not None and row.status not in ("filled", "canceled", "rejected", "expired"):
        row.status = "canceled"
        row.canceled_at = datetime.now(timezone.utc)
    return Response(status_code=204)


# ── Orders — write ────────────────────────────────────────────────────────────

class PlaceOrderBody(PlaceOrderRequest):
    """Public request body. Adds source linkage so Phase 3 auto-trade can
    record which scanner signal triggered the order."""
    source: Literal["manual", "scanner_alert"] = "manual"
    scanner_alert_id: uuid.UUID | None = None
    # Required in live mode to gate against fat-finger fills. The expected
    # string is "{SIDE} {QTY} {SYMBOL}" upper-cased (e.g. "BUY 10 SPY"). The
    # frontend computes and prompts for it; the route compares exact match.
    confirm_token: str | None = None


def _expected_confirm_token(req: PlaceOrderRequest) -> str:
    qty_str = str(int(req.qty)) if req.qty == int(req.qty) else f"{req.qty:g}"
    return f"{req.side.value.upper()} {qty_str} {req.symbol.upper()}"


@router.post("/orders", response_model=Order, dependencies=[Depends(verify_api_key)])
async def place_broker_order(
    response: Response,
    body: PlaceOrderBody = Body(...),
    db: AsyncSession = Depends(get_db),
) -> Order:
    """Submit an order. Pipeline:

      1. Resolve broker (503 on misconfig/unreachable)
      2. Live-mode typed-confirmation gate (422 on mismatch)
      3. Risk caps (422 with structured reason on reject)
      4. Persist BrokerOrder local row (idempotent on client_order_id)
      5. Submit to broker (BrokerRejected → 422, BrokerUnreachable → 503)
      6. Update local row with broker_order_id and live status

    The local row is written BEFORE the broker call so a network failure
    mid-flight still leaves us with evidence of intent (status="new",
    broker_order_id=None). A future reconciler can match by client_order_id.
    """
    broker = _get_broker_or_raise(response)
    settings = get_settings()

    # Live-mode confirmation — kills fat-finger fills before any cap check
    if broker.mode == "live":
        expected = _expected_confirm_token(body)
        if (body.confirm_token or "").strip() != expected:
            raise HTTPException(
                status_code=422,
                detail={"error": "confirm_token_mismatch", "expected": expected},
            )

    # Idempotency: if a row with this client_order_id already exists, return it
    # rather than placing twice. Frontend generates the UUID, so retries are safe.
    if not body.client_order_id:
        body.client_order_id = str(uuid.uuid4())
    existing = (await db.scalars(
        select(BrokerOrder).where(BrokerOrder.client_order_id == body.client_order_id)
    )).one_or_none()
    if existing is not None:
        return _broker_order_to_dto(existing)

    # Risk caps
    place_req = PlaceOrderRequest(
        symbol=body.symbol.upper(),
        side=body.side,
        qty=body.qty,
        order_type=body.order_type,
        limit_price=body.limit_price,
        stop_price=body.stop_price,
        take_profit_price=body.take_profit_price,
        time_in_force=body.time_in_force,
        client_order_id=body.client_order_id,
    )
    cap = await check_order_caps(place_req, db, broker, settings)
    if not cap.allowed:
        raise HTTPException(
            status_code=422,
            detail={"error": cap.reason, **(cap.detail or {})},
        )

    # Persist local row first — evidence of intent even if broker call fails
    row = BrokerOrder(
        broker=broker.name,
        mode=broker.mode,
        symbol=place_req.symbol,
        side=place_req.side.value,
        qty=place_req.qty,
        order_type=place_req.order_type.value,
        limit_price=place_req.limit_price,
        stop_price=place_req.stop_price,
        take_profit_price=place_req.take_profit_price,
        time_in_force=place_req.time_in_force.value,
        status="new",
        source=body.source,
        scanner_alert_id=body.scanner_alert_id,
        client_order_id=body.client_order_id,
    )
    db.add(row)
    await db.flush()  # assign row.id without committing — keeps the txn open

    # Submit to broker (sync alpaca-py call → run in threadpool)
    try:
        placed: Order = await asyncio.to_thread(broker.place_order, place_req)
    except BrokerRejected as exc:
        row.status = "rejected"
        row.rejected_reason = str(exc)[:200]
        raise HTTPException(status_code=422, detail={"error": "broker_rejected", "message": str(exc)})
    except BrokerUnreachable as exc:
        # Leave row in status='new' — Phase 3 reconciler will resolve it.
        response.headers["X-Broker-Status"] = "unreachable"
        raise HTTPException(status_code=503, detail=str(exc))

    # Update local row with broker's view
    row.broker_order_id = placed.broker_order_id
    row.status = placed.status.value if hasattr(placed.status, "value") else str(placed.status)
    row.filled_qty = placed.filled_qty
    row.filled_avg_price = placed.filled_avg_price
    row.filled_at = placed.filled_at
    return placed
