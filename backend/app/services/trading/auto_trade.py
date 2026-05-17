"""Auto-trade subscriber — turns scanner_alert rows into paper bracket orders.

Phase 3 design (see docs/trading.md SEC:PHASES). The subscriber is the
unbiased validation harness for the scanner: every signal in the allowlist
becomes a paper trade, so the resulting P&L reflects the strategy and not
a human's selection bias.

Three pieces live here:
  1. `count_alerts_today` — ET-midnight-anchored count for the scanner halt.
  2. `should_halt_scanner` — used by `_run_dip_scan` / `_run_mcf_scan` to skip
     ticks once the daily signal cap is hit.
  3. `submit_order_for_alert` + `_run_auto_trade_subscriber` — read open
     alerts, build bracket orders, run the same risk caps the manual route
     uses, submit via the broker, link the BrokerOrder back to its source.

Manual orders continue to flow through `POST /broker/orders`. The route and
the subscriber both call `check_order_caps`; the single risk gate is the
single source of truth.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, time, timezone
from typing import TYPE_CHECKING

import pytz
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.brokers import (
    BaseBroker,
    BrokerError,
    BrokerRejected,
    BrokerUnreachable,
    OrderSide,
    OrderType,
    PlaceOrderRequest,
    TimeInForce,
    get_broker,
)
from app.db.database import get_db_direct
from app.db.models import BrokerOrder, ScannerAlert
from app.services.trading.limits import check_order_caps

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)

_ET = pytz.timezone("America/New_York")


# ── Time helpers ──────────────────────────────────────────────────────────────

def _today_et_midnight_utc() -> datetime:
    """Today's midnight ET as a tz-aware UTC datetime — same anchor the risk
    limits use, so 'today' means the same thing in both places."""
    now_et = datetime.now(_ET)
    return _ET.localize(datetime.combine(now_et.date(), time.min)).astimezone(pytz.UTC)


def _is_market_hours_et() -> bool:
    """9:30–16:00 ET, Mon–Fri. The subscriber skips outside this window so we
    don't queue up orders at 3am that fill at the open with stale stops."""
    now_et = datetime.now(_ET)
    if now_et.weekday() >= 5:
        return False
    hm = now_et.hour * 60 + now_et.minute
    return 9 * 60 + 30 <= hm < 16 * 60


# ── Scanner halt ──────────────────────────────────────────────────────────────

async def count_alerts_today(db: AsyncSession) -> int:
    """Count of `scanner_alerts` rows with entry_time >= today-midnight-ET.
    Used by the scanner halt — once this reaches `scanner_daily_signal_cap`,
    the dip + MCF scanners skip remaining ticks for the day."""
    cutoff = _today_et_midnight_utc()
    n = await db.scalar(
        select(func.count(ScannerAlert.id)).where(ScannerAlert.entry_time >= cutoff)
    )
    return int(n or 0)


async def should_halt_scanner(settings: "Settings") -> bool:
    """True if today's scanner_alert count has hit the cap. Opens its own DB
    session so scanner jobs (which don't have one) can call this directly."""
    try:
        async for db in get_db_direct():
            n = await count_alerts_today(db)
            return n >= settings.scanner_daily_signal_cap
    except Exception as exc:
        # Halt-check failure should not stop scanning — log and let the scan run.
        logger.warning("scanner halt-check failed (allowing scan): %s", exc)
        return False
    return False


# ── Allowlist ─────────────────────────────────────────────────────────────────

def _parse_allowlist(raw: str) -> set[str]:
    """`AUTO_TRADE_SIGNAL_TYPES` is comma-separated. Empty = nothing fires
    (intentional — auto-trade is opt-in *per signal type*, not en-bloc)."""
    return {s.strip() for s in (raw or "").split(",") if s.strip()}


# ── Order submission ──────────────────────────────────────────────────────────

def _alert_to_order_request(alert: ScannerAlert, capital: float) -> PlaceOrderRequest | None:
    """Convert a ScannerAlert into a bracket limit order. Returns None when
    the alert is missing the prices we need to construct a safe bracket.

    `capital` is the dollar allocation per signal (defaults to alert.capital_used
    or 1000.0 from `dip_scanner.DEFAULT_CAPITAL`). Shares = floor(capital / entry).
    Scanner signals are entries on dips, so we always BUY (the bracket exits
    are a stop-loss below + take-profit above — Alpaca handles the OCO).
    """
    if alert.entry_price is None or alert.stop_price is None or alert.target_price is None:
        return None
    if alert.entry_price <= 0:
        return None
    shares = int(capital // alert.entry_price)
    if shares <= 0:
        return None
    return PlaceOrderRequest(
        symbol=alert.ticker.upper(),
        side=OrderSide.BUY,
        qty=float(shares),
        order_type=OrderType.LIMIT,
        limit_price=float(alert.entry_price),
        stop_price=float(alert.stop_price),
        take_profit_price=float(alert.target_price),
        time_in_force=TimeInForce.DAY,
        client_order_id=f"auto-{alert.id}",  # idempotent — same alert never fires twice
    )


async def submit_order_for_alert(
    alert: ScannerAlert,
    db: AsyncSession,
    broker: BaseBroker,
    settings: "Settings",
) -> tuple[BrokerOrder | None, str | None]:
    """Mirror of `place_broker_order` for the no-HTTP path. Returns (row, None)
    on success or (None, reason) on rejection. Caller commits the txn.

    The risk caps in `services/trading/limits.py` are still the gate — auto-
    trade never bypasses them, that is the whole point.
    """
    req = _alert_to_order_request(alert, capital=float(alert.capital_used or 1000.0))
    if req is None:
        return None, "alert_missing_prices_or_invalid_qty"

    # Idempotency — if this alert already produced an order, don't double-submit.
    # client_order_id = f"auto-{alert.id}" makes this both DB- and broker-safe.
    existing = (await db.scalars(
        select(BrokerOrder).where(BrokerOrder.client_order_id == req.client_order_id)
    )).one_or_none()
    if existing is not None:
        return existing, None

    cap = await check_order_caps(req, db, broker, settings)
    if not cap.allowed:
        return None, cap.reason or "cap_rejected"

    row = BrokerOrder(
        broker=broker.name,
        mode=broker.mode,
        symbol=req.symbol,
        side=req.side.value,
        qty=req.qty,
        order_type=req.order_type.value,
        limit_price=req.limit_price,
        stop_price=req.stop_price,
        take_profit_price=req.take_profit_price,
        time_in_force=req.time_in_force.value,
        status="new",
        source="scanner_alert",
        scanner_alert_id=alert.id,
        client_order_id=req.client_order_id,
    )
    db.add(row)
    await db.flush()  # row.id assigned, txn still open

    try:
        placed = await asyncio.to_thread(broker.place_order, req)
    except BrokerRejected as exc:
        row.status = "rejected"
        row.rejected_reason = str(exc)[:200]
        return None, f"broker_rejected:{exc}"
    except BrokerUnreachable as exc:
        # Row stays status='new' with broker_order_id=None — a future reconciler
        # can match by client_order_id (same pattern as the manual route).
        return None, f"broker_unreachable:{exc}"

    row.broker_order_id = placed.broker_order_id
    row.status = placed.status.value if hasattr(placed.status, "value") else str(placed.status)
    row.filled_qty = placed.filled_qty
    row.filled_avg_price = placed.filled_avg_price
    row.filled_at = placed.filled_at
    return row, None


# ── Subscriber loop ───────────────────────────────────────────────────────────

async def _run_auto_trade_subscriber():
    """Scheduler tick — scan open alerts, fire orders for the ones we haven't
    acted on yet. Bounded by the same daily cap as manual trading so a runaway
    scanner can't drain buying power.

    Failure isolation: each alert is its own try/except. One bad signal does
    not stop the loop; one DB or broker hiccup does not poison the next tick.
    """
    from app.config import get_settings  # local import — avoids circular at startup

    settings = get_settings()
    if not settings.auto_trade_enabled:
        return
    allowlist = _parse_allowlist(settings.auto_trade_signal_types)
    if not allowlist:
        return  # opt-in per signal type — empty allowlist = no-op
    if not _is_market_hours_et():
        return

    try:
        broker = get_broker(settings)
    except (BrokerError, BrokerUnreachable) as exc:
        logger.warning("auto_trade: broker unavailable, skipping tick: %s", exc)
        return

    async for db in get_db_direct():
        try:
            # Open alerts within the allowlist that have NOT yet produced a
            # BrokerOrder (left join on scanner_alert_id is null). Limit keeps
            # one tick bounded — leftovers get picked up next poll.
            stmt = (
                select(ScannerAlert)
                .outerjoin(BrokerOrder, BrokerOrder.scanner_alert_id == ScannerAlert.id)
                .where(
                    ScannerAlert.status == "open",
                    ScannerAlert.signal_type.in_(allowlist),
                    ScannerAlert.entry_time >= _today_et_midnight_utc(),
                    ScannerAlert.loose_gates.is_not(True),
                    BrokerOrder.id.is_(None),
                )
                .order_by(ScannerAlert.entry_time.asc())
                .limit(20)
            )
            alerts = (await db.execute(stmt)).scalars().all()

            for alert in alerts:
                try:
                    row, reason = await submit_order_for_alert(alert, db, broker, settings)
                    if row is not None:
                        await db.commit()
                        logger.info(
                            "auto_trade: submitted order for alert %s (%s) — client_order_id=%s",
                            alert.id, alert.ticker, row.client_order_id,
                        )
                    else:
                        # Roll back the in-progress row insert before next alert
                        await db.rollback()
                        logger.info(
                            "auto_trade: skipped alert %s (%s) — %s",
                            alert.id, alert.ticker, reason,
                        )
                        # Daily count cap → stop processing for the rest of the tick
                        if reason == "daily_order_count_cap_reached":
                            logger.info("auto_trade: daily order cap reached — pausing subscriber")
                            break
                except Exception as exc:
                    await db.rollback()
                    logger.warning("auto_trade: alert %s raised: %s", alert.id, exc)
        finally:
            # get_db_direct yields one session; loop exits after first iteration
            break
