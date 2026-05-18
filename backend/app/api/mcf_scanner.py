import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import verify_api_key
from app.db.database import get_db
from app.db.models import ScannerAlert
from app.services.data_cache import get_stock_cache
from app.services.scheduler import _run_mcf_scan

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mcf-scanner", tags=["mcf-scanner"])


class McfScanRequest(BaseModel):
    loose_gates: bool = False


@router.post("/force-run")
async def force_mcf_scan(req: McfScanRequest = McfScanRequest(), _: str = Depends(verify_api_key)):
    """Manually trigger the MCF scanner. loose_gates=true persists results tagged for separate analytics."""
    await _run_mcf_scan(force=True, loose=req.loose_gates)
    msg = (
        "Loose scan complete — results saved with loose_gates=true"
        if req.loose_gates
        else "Scan complete"
    )
    return {"status": "success", "message": msg, "loose_gates": req.loose_gates}


@router.get("/state")
async def get_mcf_state(db: AsyncSession = Depends(get_db), _: str = Depends(verify_api_key)):
    """
    Fetch the latest pre-calculated MCF state from the database.
    This avoids redundant yfinance API calls.
    """
    state_data = await get_stock_cache(db, ticker="MCF", data_type="state")
    if not state_data:
        return {
            "status": "waiting",
            "weather": {"spy_trend": "unknown", "vix": 0.0, "status": "unknown"},
            "tide": {"correlated_selling": False, "momentum_fading": False, "status": "unknown"},
            "timestamp": None,
            "message": "No MCF state cached yet.",
        }

    return state_data


@router.get("/analytics")
async def mcf_analytics(
    loose: bool = Query(
        False, description="true = loose-gate signals only; false (default) = strict signals only"
    ),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Win/loss stats for MCF signals. Default: strict only. ?loose=true: loose-gate only."""
    loose_filter = (
        ScannerAlert.loose_gates.is_(True) if loose else ScannerAlert.loose_gates.is_not(True)
    )
    try:
        rows = (
            (
                await db.execute(
                    select(ScannerAlert)
                    .where(
                        and_(
                            ScannerAlert.signal_type == "mcf_dip_buy",
                            ScannerAlert.status != "open",
                            loose_filter,
                        )
                    )
                    .order_by(ScannerAlert.entry_time.desc())
                )
            )
            .scalars()
            .all()
        )
    except Exception as exc:
        logger.error("MCF analytics query failed: %s", exc)
        return {"error": "Database error"}

    if not rows:
        return {
            "total_signals": 0,
            "win_rate_pct": None,
            "wins": 0,
            "losses": 0,
            "expected_value_dollar": None,
            "recent_alerts": [],
            "loose_gates": loose,
        }

    wins = [r for r in rows if r.status == "win"]
    losses = [r for r in rows if r.status == "loss"]
    total = len(wins) + len(losses)

    win_rate = len(wins) / total * 100 if total else 0
    avg_win = sum(r.actual_pnl_pct for r in wins if r.actual_pnl_pct) / len(wins) if wins else 0
    avg_loss = (
        sum(r.actual_pnl_pct for r in losses if r.actual_pnl_pct) / len(losses) if losses else 0
    )
    ev_pct = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss)
    ev_dollar = ev_pct / 100 * 1000.0  # Assumes 1000 default capital

    recent = [
        {
            "ticker": r.ticker,
            "entry_time": r.entry_time.isoformat() if r.entry_time else None,
            "entry_price": r.entry_price,
            "target_price": r.target_price,
            "stop_price": r.stop_price,
            "outcome_price": r.outcome_price,
            "actual_pnl_pct": r.actual_pnl_pct,
            "actual_pnl_dollar": r.actual_pnl_dollar,
            "status": r.status,
            "resolved_by": r.resolved_by,
            "loose_gates": bool(r.loose_gates),
        }
        for r in rows[:20]
    ]

    return {
        "total_signals": total,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(win_rate, 1),
        "avg_win_pct": round(avg_win, 3),
        "avg_loss_pct": round(avg_loss, 3),
        "expected_value_pct": round(ev_pct, 3),
        "expected_value_dollar": round(ev_dollar, 2),
        "recent_alerts": recent,
        "loose_gates": loose,
    }
