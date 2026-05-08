import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import verify_api_key
from app.db.database import get_db
from app.db.models import ScannerAlert
from app.tools.dip_scanner import ETF_TIERS, scan_dip_opportunities, _backfill_ticker, SESSION_WINDOWS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dip-scanner", tags=["dip-scanner"])

DEFAULT_CAPITAL = 1000.0


class ScanRequest(BaseModel):
    tiers: list[int] = [1]
    capital: float = DEFAULT_CAPITAL
    vix: float | None = None


class BackfillRequest(BaseModel):
    tiers: list[int] = [1]
    days: int = 60


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_tickers(tiers: list[int]) -> list[str]:
    tickers = []
    for t in tiers:
        tickers.extend(ETF_TIERS.get(t, []))
    return list(dict.fromkeys(tickers))  # deduplicate, preserve order


async def _save_alert(db: AsyncSession, opp: dict) -> None:
    alert = ScannerAlert(
        id=uuid.uuid4(),
        ticker=opp["ticker"],
        entry_price=opp["entry_price"],
        target_price=opp["target_price"],
        stop_price=opp["stop_price"],
        entry_time=datetime.fromisoformat(opp.get("entry_time", datetime.now(timezone.utc).isoformat())),
        score=opp.get("score"),
        signals=opp.get("signals"),
        session_window=opp.get("session_window"),
        vix_at_entry=opp.get("vix"),
        capital_used=opp.get("capital_used", DEFAULT_CAPITAL),
        source=opp.get("source", "live"),
        status=opp.get("status", "open"),
        outcome_price=opp.get("outcome_price"),
        actual_pnl_pct=opp.get("actual_pnl_pct"),
        actual_pnl_dollar=opp.get("actual_pnl_dollar"),
        resolved_by=opp.get("resolved_by"),
    )
    db.add(alert)
    await db.commit()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/scan")
async def scan(
    request: ScanRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Manual scan trigger. Returns best opportunity across selected ETF tiers."""
    tickers = _get_tickers(request.tiers)
    result = await asyncio.to_thread(
        scan_dip_opportunities, tickers, request.capital, request.vix
    )

    # Persist any opportunities found as open live alerts
    for opp in result.get("opportunities", []):
        try:
            opp["entry_time"] = result["timestamp"]
            await _save_alert(db, opp)
        except Exception as exc:
            logger.warning("failed to save alert for %s: %s", opp.get("ticker"), exc)

    return result


@router.get("/config")
async def get_config(_: str = Depends(verify_api_key)):
    """Return ETF tiers and session window reference."""
    return {
        "etf_tiers": ETF_TIERS,
        "session_windows": {k: v["label"] for k, v in SESSION_WINDOWS.items()},
        "default_capital": DEFAULT_CAPITAL,
        "score_threshold": 65,
        "trading_hours_et": {"open": "9:40 AM", "close": "3:15 PM"},
    }


@router.get("/analytics")
async def analytics(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Win/loss stats across all recorded alerts (backtest + live)."""
    rows = (await db.execute(
        select(ScannerAlert).where(ScannerAlert.status != "open")
        .order_by(ScannerAlert.entry_time.desc())
    )).scalars().all()

    if not rows:
        return {
            "total_signals": 0,
            "wins": 0, "losses": 0,
            "win_rate_pct": None,
            "avg_win_pct": None,
            "avg_loss_pct": None,
            "expected_value_pct": None,
            "expected_value_dollar": None,
            "current_streak": None,
            "by_ticker": {},
            "by_window": {},
            "recent_alerts": [],
            "note": "No resolved signals yet — run /dip-scanner/backfill to seed historical data",
        }

    wins = [r for r in rows if r.status == "win"]
    losses = [r for r in rows if r.status == "loss"]
    total = len(wins) + len(losses)

    win_rate = len(wins) / total * 100 if total else 0
    avg_win = sum(r.actual_pnl_pct for r in wins if r.actual_pnl_pct) / len(wins) if wins else 0
    avg_loss = sum(r.actual_pnl_pct for r in losses if r.actual_pnl_pct) / len(losses) if losses else 0
    ev_pct = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss)
    ev_dollar = ev_pct / 100 * DEFAULT_CAPITAL

    # Current streak
    streak_type = rows[0].status
    streak_count = 0
    for r in rows:
        if r.status == streak_type:
            streak_count += 1
        else:
            break

    # Breakdown by ticker
    by_ticker: dict[str, dict] = {}
    for r in rows:
        if r.ticker not in by_ticker:
            by_ticker[r.ticker] = {"signals": 0, "wins": 0, "losses": 0, "pnl_sum": 0.0}
        by_ticker[r.ticker]["signals"] += 1
        if r.status == "win":
            by_ticker[r.ticker]["wins"] += 1
        elif r.status == "loss":
            by_ticker[r.ticker]["losses"] += 1
        by_ticker[r.ticker]["pnl_sum"] += r.actual_pnl_pct or 0

    for tk, d in by_ticker.items():
        t = d["wins"] + d["losses"]
        d["win_rate_pct"] = round(d["wins"] / t * 100, 1) if t else 0
        d["avg_pnl_pct"] = round(d["pnl_sum"] / t, 3) if t else 0
        d.pop("pnl_sum")

    # Breakdown by session window
    by_window: dict[str, dict] = {}
    for r in rows:
        w = r.session_window or "unknown"
        if w not in by_window:
            by_window[w] = {"signals": 0, "wins": 0, "losses": 0}
        by_window[w]["signals"] += 1
        if r.status == "win":
            by_window[w]["wins"] += 1
        elif r.status == "loss":
            by_window[w]["losses"] += 1
    for w, d in by_window.items():
        t = d["wins"] + d["losses"]
        d["win_rate_pct"] = round(d["wins"] / t * 100, 1) if t else 0
        d["label"] = SESSION_WINDOWS.get(w, {}).get("label", w)

    # Recent 20 alerts
    recent = [
        {
            "id": str(r.id),
            "ticker": r.ticker,
            "entry_time": r.entry_time.isoformat() if r.entry_time else None,
            "entry_price": r.entry_price,
            "outcome_price": r.outcome_price,
            "actual_pnl_pct": r.actual_pnl_pct,
            "actual_pnl_dollar": r.actual_pnl_dollar,
            "status": r.status,
            "resolved_by": r.resolved_by,
            "session_window": r.session_window,
            "score": r.score,
            "source": r.source,
        }
        for r in rows[:20]
    ]

    # Cumulative P&L series (chronological order for chart)
    cumulative = []
    running = 0.0
    for r in reversed(rows):
        running += r.actual_pnl_dollar or 0
        cumulative.append({
            "date": r.entry_time.isoformat() if r.entry_time else None,
            "cumulative_pnl": round(running, 2),
        })

    data_sources = list({r.source for r in rows})
    live_count = sum(1 for r in rows if r.source == "live")
    backtest_count = sum(1 for r in rows if r.source == "backtest")

    return {
        "total_signals": total,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(win_rate, 1),
        "avg_win_pct": round(avg_win, 3),
        "avg_loss_pct": round(avg_loss, 3),
        "expected_value_pct": round(ev_pct, 3),
        "expected_value_dollar": round(ev_dollar, 2),
        "current_streak": {"type": streak_type, "count": streak_count},
        "data_sources": data_sources,
        "live_signals": live_count,
        "backtest_signals": backtest_count,
        "by_ticker": by_ticker,
        "by_window": by_window,
        "recent_alerts": recent,
        "cumulative_pnl": cumulative,
        "note": "Includes backtest data" if backtest_count > 0 else "Live signals only",
    }


@router.post("/backfill")
async def backfill(
    request: BackfillRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Seed analytics with historical data — run once at setup.
    Replays scanner logic over the last N days of 5-min data.
    Skips if backtest records already exist for these tickers.
    """
    tickers = _get_tickers(request.tiers)

    # Check if already backfilled
    existing = (await db.execute(
        select(func.count(ScannerAlert.id)).where(ScannerAlert.source == "backtest")
    )).scalar()

    if existing and existing > 0:
        return {
            "status": "already_backfilled",
            "existing_records": existing,
            "message": "Backtest data already exists. Delete scanner_alerts with source='backtest' to re-run.",
        }

    async def _run_backfill():
        total_saved = 0
        for ticker in tickers:
            try:
                alerts = await asyncio.to_thread(_backfill_ticker, ticker, request.days)
                for alert_data in alerts:
                    try:
                        alert = ScannerAlert(
                            id=uuid.uuid4(),
                            ticker=alert_data["ticker"],
                            entry_price=alert_data["entry_price"],
                            target_price=alert_data["target_price"],
                            stop_price=alert_data["stop_price"],
                            entry_time=datetime.fromisoformat(alert_data["entry_time"]),
                            score=alert_data.get("score"),
                            signals=alert_data.get("signals"),
                            session_window=alert_data.get("session_window"),
                            vix_at_entry=alert_data.get("vix_at_entry"),
                            capital_used=alert_data.get("capital_used", DEFAULT_CAPITAL),
                            source="backtest",
                            status=alert_data["status"],
                            outcome_price=alert_data.get("outcome_price"),
                            actual_pnl_pct=alert_data.get("actual_pnl_pct"),
                            actual_pnl_dollar=alert_data.get("actual_pnl_dollar"),
                            resolved_by=alert_data.get("resolved_by"),
                        )
                        db.add(alert)
                        total_saved += 1
                    except Exception as exc:
                        logger.warning("backfill save error %s: %s", ticker, exc)
                await db.commit()
                logger.info("backfill: saved %d alerts for %s", len(alerts), ticker)
            except Exception as exc:
                logger.error("backfill failed for %s: %s", ticker, exc)
        logger.info("backfill complete — %d total alerts saved", total_saved)

    background_tasks.add_task(_run_backfill)

    return {
        "status": "started",
        "tickers": tickers,
        "days": request.days,
        "message": f"Backfilling {len(tickers)} ETFs × {request.days} days in background. Check /dip-scanner/analytics when complete.",
    }
