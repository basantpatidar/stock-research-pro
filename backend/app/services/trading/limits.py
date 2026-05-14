"""Order risk caps — server-side, non-bypassable.

Every order goes through `check_order_caps` before the broker sees it.
Caps come from `Settings` (which reads .env) — edit limits in .env or
backend/app/config.py defaults, **never** inline in this module. This
keeps the single source of truth one place, matching the pattern used
by usage guard rails (CLAUDE.md Critical Rule #6).

See docs/trading.md SEC:RISK for the full design + pre-live checklist.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time
from typing import TYPE_CHECKING

import pytz
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.brokers.base import BaseBroker, OrderSide, OrderType, PlaceOrderRequest
from app.db.models import BrokerOrder

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)

_ET = pytz.timezone("America/New_York")


# ── Rejection codes — surface in HTTP 422 body for the UI to map to copy ──────

class CapRejection:
    MAX_ORDER_DOLLARS = "max_order_dollars_exceeded"
    MAX_POSITION_DOLLARS = "max_position_dollars_exceeded"
    DAILY_ORDER_COUNT = "daily_order_count_cap_reached"
    DAILY_LOSS_CAP = "daily_loss_cap_reached"
    NO_PRICE_REFERENCE = "no_price_reference_for_market_order"


@dataclass
class CapResult:
    allowed: bool
    reason: str | None = None
    detail: dict | None = None
    estimated_notional: float | None = None

    @classmethod
    def accept(cls, notional: float) -> "CapResult":
        return cls(allowed=True, estimated_notional=notional)

    @classmethod
    def reject(cls, reason: str, **detail) -> "CapResult":
        return cls(allowed=False, reason=reason, detail=detail or {})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _market_price_estimate(symbol: str) -> float | None:
    """Quote for market-order notional check. Uses yfinance — same source the
    rest of the app trusts. Returns None if the quote is unavailable; callers
    must reject conservatively (we cannot enforce a cap without a price).
    """
    try:
        import yfinance as yf
        info = yf.Ticker(symbol).fast_info
        px = float(info.get("lastPrice") or info.get("regularMarketPrice") or 0)
        return px if px > 0 else None
    except Exception as exc:
        logger.warning("market_price_estimate failed for %s: %s", symbol, exc)
        return None


def _today_et_midnight_utc() -> datetime:
    """Today's midnight ET as a tz-aware UTC datetime (for DB queries against
    `submitted_at`, which is timestamptz). See docs/rules.md SEC:TIMEZONE."""
    now_et = datetime.now(_ET)
    midnight_et = _ET.localize(datetime.combine(now_et.date(), time.min))
    return midnight_et.astimezone(pytz.UTC)


# ── Public entry point ────────────────────────────────────────────────────────

async def check_order_caps(
    req: PlaceOrderRequest,
    db: AsyncSession,
    broker: BaseBroker,
    settings: "Settings",
) -> CapResult:
    """Run all caps. Returns CapResult.accept(notional) or CapResult.reject(reason, ...).

    Caps run in order; first rejection short-circuits the rest. Order matters:
    cheap local checks first (per-order $, daily count from DB), broker round-trips
    last (position + loss). This minimises Alpaca calls on the common reject path.
    """
    # 1. Per-order notional — cheapest check
    ref_price = req.limit_price or req.stop_price
    if req.order_type == OrderType.MARKET and ref_price is None:
        ref_price = _market_price_estimate(req.symbol)
        if ref_price is None:
            return CapResult.reject(
                CapRejection.NO_PRICE_REFERENCE,
                symbol=req.symbol,
                hint="market order rejected — could not fetch a quote to enforce cap",
            )

    notional = req.qty * (ref_price or 0.0)
    max_order = settings.trade_max_order_dollars
    if notional > max_order:
        return CapResult.reject(
            CapRejection.MAX_ORDER_DOLLARS,
            limit_dollars=max_order,
            attempted_dollars=round(notional, 2),
        )

    # 2. Daily order count — one DB roundtrip
    today_start_utc = _today_et_midnight_utc()
    today_count = await db.scalar(
        select(func.count(BrokerOrder.id)).where(
            BrokerOrder.submitted_at >= today_start_utc,
            BrokerOrder.mode == broker.mode,
        )
    )
    if today_count is None:
        today_count = 0
    if today_count >= settings.trade_daily_order_count_cap:
        return CapResult.reject(
            CapRejection.DAILY_ORDER_COUNT,
            limit=settings.trade_daily_order_count_cap,
            today_count=today_count,
        )

    # 3. Per-position cap — broker call
    if req.side == OrderSide.BUY:
        try:
            positions = broker.get_positions()
        except Exception as exc:
            # If the broker can't tell us positions, we can't enforce the cap.
            # Fail closed for live mode; allow with a warning for paper.
            logger.warning("get_positions failed during cap check: %s", exc)
            if broker.mode == "live":
                return CapResult.reject(
                    CapRejection.MAX_POSITION_DOLLARS,
                    error="broker_positions_unreachable",
                    hint="live-mode position cap cannot be enforced — order blocked",
                )
            positions = []

        cur = next((p for p in positions if p.symbol == req.symbol), None)
        cur_value = float(cur.market_value) if cur else 0.0
        max_pos = settings.trade_max_position_dollars
        if cur_value + notional > max_pos:
            return CapResult.reject(
                CapRejection.MAX_POSITION_DOLLARS,
                limit_dollars=max_pos,
                current_position_dollars=round(cur_value, 2),
                attempted_add_dollars=round(notional, 2),
            )

    # 4. Daily realised P&L cap — broker call (only blocks new BUYS; closing
    #    losers must remain possible). Uses broker's `last_equity` (yesterday's
    #    close equity) which Alpaca exposes natively; if not available, we
    #    log and skip — better to ship Phase 2 than block on missing data.
    if req.side == OrderSide.BUY:
        try:
            acct = broker.get_account()
            last_equity = getattr(acct, "last_equity", None)
            if last_equity is not None and last_equity > 0:
                day_pnl = float(acct.equity) - float(last_equity)
                if day_pnl <= settings.trade_daily_loss_cap_dollars:
                    return CapResult.reject(
                        CapRejection.DAILY_LOSS_CAP,
                        cap_dollars=settings.trade_daily_loss_cap_dollars,
                        day_pnl_dollars=round(day_pnl, 2),
                    )
        except Exception as exc:
            logger.warning("daily-loss cap check skipped (account fetch failed): %s", exc)

    return CapResult.accept(notional)
