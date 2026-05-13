import asyncio
import logging
import uuid
from datetime import date, datetime, timedelta, timezone

import yfinance as yf
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, func, and_, delete
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
    loose_gates: bool = False  # diagnostic mode — relaxes thresholds, skips persistence


class BackfillRequest(BaseModel):
    tiers: list[int] = [1]
    days: int = 60


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_tickers(tiers: list[int]) -> list[str]:
    tickers = []
    for t in tiers:
        tickers.extend(ETF_TIERS.get(t, []))
    return list(dict.fromkeys(tickers))  # deduplicate, preserve order


DEDUP_WINDOW_MINUTES = 15


async def _save_alert(db: AsyncSession, opp: dict) -> None:
    """Persist a live scanner opportunity. Suppresses near-duplicates per ticker
    within DEDUP_WINDOW_MINUTES — prevents correlated risk from back-to-back
    fires on the same name (e.g., XLF firing twice 12 min apart on 2026-05-08).
    Backtest rows skip this gate (source != 'live').
    """
    entry_ts = datetime.fromisoformat(opp.get("entry_time", datetime.now(timezone.utc).isoformat()))
    source = opp.get("source", "live")

    if source == "live":
        cutoff = entry_ts - timedelta(minutes=DEDUP_WINDOW_MINUTES)
        existing = await db.execute(
            select(ScannerAlert.id).where(
                and_(
                    ScannerAlert.ticker == opp["ticker"],
                    ScannerAlert.source == "live",
                    ScannerAlert.entry_time >= cutoff,
                )
            ).limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            logger.info(
                "dedup-skip: %s within %dmin of prior alert",
                opp["ticker"], DEDUP_WINDOW_MINUTES,
            )
            return

    alert = ScannerAlert(
        id=uuid.uuid4(),
        ticker=opp["ticker"],
        signal_type=opp.get("signal_type"),
        entry_price=opp["entry_price"],
        target_price=opp["target_price"],
        stop_price=opp["stop_price"],
        entry_time=entry_ts,
        score=opp.get("score"),
        signals=opp.get("signals"),
        session_window=opp.get("session_window"),
        vix_at_entry=opp.get("vix"),
        capital_used=opp.get("capital_used", DEFAULT_CAPITAL),
        source=source,
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
    """Manual scan trigger. Returns best opportunity across selected ETF tiers.
    Loose-gates results are NOT persisted — they would contaminate win/loss analytics
    since they were generated under relaxed thresholds with unvalidated win rates."""
    tickers = _get_tickers(request.tiers)
    result = await asyncio.to_thread(
        scan_dip_opportunities, tickers, request.capital, request.vix, request.loose_gates
    )

    # Persist all opportunity types as open live alerts — not just dip_buy.
    # Skip persistence for loose-gates scans to keep analytics clean.
    if not request.loose_gates:
        all_live_opps = [
            *result.get("opportunities", []),
            *result.get("orb_opportunities", []),
            *result.get("vwap_opportunities", []),
            *result.get("failed_breakdown_opportunities", []),
        ]
        for opp in all_live_opps:
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
        "trading_hours_et": {"regular_open": "9:40 AM", "regular_close": "4:00 PM", "pre_market": "4:00 AM", "after_hours_close": "8:00 PM"},
    }


@router.get("/analytics")
async def analytics(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Win/loss stats across all recorded alerts (backtest + live)."""
    from fastapi import HTTPException
    try:
        rows = (await db.execute(
            select(ScannerAlert).where(ScannerAlert.status != "open")
            .order_by(ScannerAlert.entry_time.desc())
        )).scalars().all()
    except Exception as exc:
        logger.error("analytics query failed — migrations may be missing: %s", exc)
        raise HTTPException(status_code=500, detail="scanner_alerts table not ready — run: make migrate")

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

    # Breakdown by signal_type × ticker × session — powers the heatmap (#28)
    by_signal_type: dict[str, dict] = {}
    for r in rows:
        st = r.signal_type or "dip_buy"
        tk = r.ticker
        sw = r.session_window or "unknown"
        cell_key = f"{tk}:{sw}"
        if st not in by_signal_type:
            by_signal_type[st] = {}
        if cell_key not in by_signal_type[st]:
            by_signal_type[st][cell_key] = {
                "ticker": tk, "session": sw,
                "signals": 0, "wins": 0, "losses": 0, "pnl_sum": 0.0,
            }
        cell = by_signal_type[st][cell_key]
        cell["signals"] += 1
        if r.status == "win":
            cell["wins"] += 1
        elif r.status == "loss":
            cell["losses"] += 1
        cell["pnl_sum"] += r.actual_pnl_pct or 0
    for st, cells in by_signal_type.items():
        for ck, cell in cells.items():
            t = cell["wins"] + cell["losses"]
            cell["win_rate_pct"] = round(cell["wins"] / t * 100, 1) if t else None
            cell["ev_pct"] = round(cell["pnl_sum"] / t, 3) if t else None
            cell.pop("pnl_sum")

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

    # Signal type summary — aggregate win rate + EV per type (used to decide which types to keep)
    by_signal_type_summary: dict[str, dict] = {}
    for r in rows:
        st = r.signal_type or "dip_buy"
        if st not in by_signal_type_summary:
            by_signal_type_summary[st] = {"signals": 0, "wins": 0, "losses": 0, "pnl_sum": 0.0}
        by_signal_type_summary[st]["signals"] += 1
        if r.status == "win":
            by_signal_type_summary[st]["wins"] += 1
        elif r.status == "loss":
            by_signal_type_summary[st]["losses"] += 1
        by_signal_type_summary[st]["pnl_sum"] += r.actual_pnl_pct or 0
    for st, d in by_signal_type_summary.items():
        t = d["wins"] + d["losses"]
        d["win_rate_pct"] = round(d["wins"] / t * 100, 1) if t else None
        d["ev_pct"] = round(d["pnl_sum"] / t, 3) if t else None
        d["ev_dollar"] = round(d["ev_pct"] / 100 * DEFAULT_CAPITAL, 2) if d["ev_pct"] is not None else None
        d.pop("pnl_sum")

    # Score band breakdown — shows if higher scores actually win more (guides threshold decisions)
    score_bands = {"72-79": {"signals": 0, "wins": 0, "losses": 0, "pnl_sum": 0.0},
                   "80-89": {"signals": 0, "wins": 0, "losses": 0, "pnl_sum": 0.0},
                   "90+":   {"signals": 0, "wins": 0, "losses": 0, "pnl_sum": 0.0}}
    for r in rows:
        s = r.score or 0
        band = "90+" if s >= 90 else ("80-89" if s >= 80 else "72-79")
        score_bands[band]["signals"] += 1
        if r.status == "win":
            score_bands[band]["wins"] += 1
        elif r.status == "loss":
            score_bands[band]["losses"] += 1
        score_bands[band]["pnl_sum"] += r.actual_pnl_pct or 0
    for band, d in score_bands.items():
        t = d["wins"] + d["losses"]
        d["win_rate_pct"] = round(d["wins"] / t * 100, 1) if t else None
        d["ev_dollar"] = round((d["pnl_sum"] / t) / 100 * DEFAULT_CAPITAL, 2) if t else None
        d.pop("pnl_sum")

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

    # Forward 5-min bar directional accuracy (#29) — how often price moved the right way within 5 min of entry
    fwd_rows = [r for r in rows if r.five_min_direction in ("up", "down", "flat")]
    fwd_up = sum(1 for r in fwd_rows if r.five_min_direction == "up")
    forward_accuracy_pct = round(fwd_up / len(fwd_rows) * 100, 1) if fwd_rows else None

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
        "by_signal_type": by_signal_type,
        "by_signal_type_summary": by_signal_type_summary,
        "by_score_band": score_bands,
        "recent_alerts": recent,
        "cumulative_pnl": cumulative,
        "forward_accuracy_pct": forward_accuracy_pct,
        "forward_accuracy_n": len(fwd_rows),
        "note": "Includes backtest data" if backtest_count > 0 else "Live signals only",
    }


@router.get("/similar")
async def similar_setups(
    ticker: str,
    session: str,
    signal_type: str = "dip_buy",
    limit: int = 4,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Last N closed signals for the same ticker + session window (#17 — reference cases)."""
    rows = (await db.execute(
        select(ScannerAlert)
        .where(
            and_(
                ScannerAlert.ticker == ticker.upper(),
                ScannerAlert.session_window == session,
                ScannerAlert.signal_type == signal_type,
                ScannerAlert.status != "open",
            )
        )
        .order_by(ScannerAlert.entry_time.desc())
        .limit(limit)
    )).scalars().all()

    return {
        "ticker": ticker.upper(),
        "session": session,
        "signal_type": signal_type,
        "setups": [
            {
                "entry_time": r.entry_time.isoformat() if r.entry_time else None,
                "entry_price": r.entry_price,
                "outcome_price": r.outcome_price,
                "status": r.status,
                "actual_pnl_pct": r.actual_pnl_pct,
                "actual_pnl_dollar": r.actual_pnl_dollar,
                "score": r.score,
                "resolved_by": r.resolved_by,
            }
            for r in rows
        ],
    }


@router.get("/ticker-history/{ticker}")
async def ticker_history(
    ticker: str,
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """All past scanner_alerts for a ticker, newest first."""
    rows = (await db.execute(
        select(ScannerAlert)
        .where(ScannerAlert.ticker == ticker.upper())
        .order_by(ScannerAlert.entry_time.desc())
        .limit(limit)
    )).scalars().all()

    return {
        "ticker": ticker.upper(),
        "count": len(rows),
        "signals": [
            {
                "id": str(r.id),
                "signal_type": r.signal_type or "dip_buy",
                "side": "BUY",
                "entry_time": r.entry_time.isoformat() if r.entry_time else None,
                "session_window": r.session_window,
                "score": r.score,
                "entry_price": r.entry_price,
                "target_price": r.target_price,
                "stop_price": r.stop_price,
                "status": r.status,
                "outcome_price": r.outcome_price,
                "actual_pnl_pct": r.actual_pnl_pct,
                "actual_pnl_dollar": r.actual_pnl_dollar,
                "resolved_by": r.resolved_by,
                "five_min_direction": r.five_min_direction,
            }
            for r in rows
        ],
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

    # Clear existing backtest records so re-seed always reflects the latest logic
    deleted = (await db.execute(
        delete(ScannerAlert).where(ScannerAlert.source == "backtest")
    )).rowcount
    await db.commit()
    if deleted:
        logger.info("backfill: cleared %d existing backtest records", deleted)

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
                            signal_type=alert_data.get("signal_type", "dip_buy"),
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
                            five_min_direction=alert_data.get("five_min_direction"),
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
        "cleared": deleted,
        "message": f"Cleared {deleted} old records. Backfilling {len(tickers)} ETFs × {request.days} days (4 signal types) in background.",
    }


class AnalyzeRequest(BaseModel):
    ticker: str
    signal_type: str
    score: int
    confidence_tier: str | None = None
    session_window: str
    session_window_label: str
    entry_price: float
    target_price: float
    stop_price: float
    rsi_5m: float
    rvol: float
    vix: float
    dip_pct: float
    risk_reward_ratio: float
    atr_5m: float | None = None
    signals: list[str] = []
    top_reasons: list[str] = []


@router.post("/analyze")
async def analyze_signal(
    request: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """LLM plain-English analysis of a scanner signal — click-triggered, ~500 tokens."""
    import json as _json
    from langchain_core.messages import HumanMessage
    from app.config import get_settings
    from app.llm.factory import get_llm_with_fallback

    # Pull historical win/loss stats for this ticker + signal_type from the DB
    history_rows = (await db.execute(
        select(ScannerAlert).where(
            and_(
                ScannerAlert.ticker == request.ticker.upper(),
                ScannerAlert.signal_type == request.signal_type,
                ScannerAlert.status.in_(["win", "loss"]),
            )
        ).order_by(ScannerAlert.entry_time.desc()).limit(30)
    )).scalars().all()

    h_total = len(history_rows)
    h_wins = [r for r in history_rows if r.status == "win"]
    h_losses = [r for r in history_rows if r.status == "loss"]
    win_rate = round(len(h_wins) / h_total * 100, 1) if h_total else None
    avg_win = round(sum(r.actual_pnl_pct or 0 for r in h_wins) / len(h_wins), 2) if h_wins else None
    avg_loss = round(sum(r.actual_pnl_pct or 0 for r in h_losses) / len(h_losses), 2) if h_losses else None

    signal_type_label = {
        "dip_buy": "Dip Buy", "orb_breakout": "ORB Breakout",
        "vwap_reclaim": "VWAP Reclaim", "failed_breakdown": "Failed Breakdown",
    }.get(request.signal_type, request.signal_type)

    history_line = (
        f"{h_total} past signals — {win_rate}% win rate · avg win +{avg_win}% · avg loss {avg_loss}%"
        if h_total >= 3
        else "Not enough history yet for this ticker + signal type combination."
    )
    reasons = (request.top_reasons or request.signals)[:5]
    rsi_note = "oversold — sellers may be exhausted" if request.rsi_5m < 35 else "neutral"
    rvol_note = "elevated — real institutional participation" if request.rvol > 1.3 else "light activity"

    prompt = f"""You are a concise trading signal analyst. Explain this ETF scanner signal to a retail trader who may not know technical analysis. Be practical and direct — no fluff.

SIGNAL:
- Ticker: {request.ticker}  Type: {signal_type_label}
- Score: {request.score}/100{f"  ({request.confidence_tier})" if request.confidence_tier else ""}
- Session: {request.session_window_label}

LEVELS:
- Entry: ${request.entry_price:.2f}  Target: ${request.target_price:.2f}  Stop: ${request.stop_price:.2f}
- R/R: {request.risk_reward_ratio}:1{f"  ATR: ${request.atr_5m:.3f}" if request.atr_5m else ""}

INDICATORS:
- RSI (5-min): {request.rsi_5m:.1f} ({rsi_note})
- Rel. Volume: {request.rvol:.2f}x ({rvol_note})
- VIX: {request.vix:.1f}  Dip from open: -{request.dip_pct}%

KEY SIGNALS: {", ".join(reasons) if reasons else "none"}

HISTORY FOR THIS SETUP ON {request.ticker}:
{history_line}

Reply with ONLY this JSON — no other text:
{{
  "verdict": "FAVORABLE" or "MIXED" or "UNFAVORABLE",
  "plain_english": "2-3 plain sentences explaining what is happening in the market right now for this ETF and why the setup could work. No jargon.",
  "key_risk": "One sentence: the most likely reason this trade fails.",
  "watch_for": "One sentence: a specific price level or market condition that confirms the trade is working, or tells you to exit early."
}}"""

    try:
        settings = get_settings()
        llm = get_llm_with_fallback(settings, "tier2")
        response = await asyncio.to_thread(llm.invoke, [HumanMessage(content=prompt)])
        raw = response.content.strip()
        start, end = raw.find("{"), raw.rfind("}") + 1
        if start == -1 or end <= start:
            raise ValueError("no JSON block in LLM response")
        parsed = _json.loads(raw[start:end])
        return {
            "ticker": request.ticker.upper(),
            "verdict": parsed.get("verdict", "MIXED"),
            "plain_english": parsed.get("plain_english", ""),
            "key_risk": parsed.get("key_risk", ""),
            "watch_for": parsed.get("watch_for", ""),
            "history_count": h_total,
            "win_rate_pct": win_rate,
            "tokens_used": 500,
        }
    except Exception as exc:
        logger.warning("analyze_signal LLM failed for %s — using rule-based fallback: %s", request.ticker, exc)
        verdict = "FAVORABLE" if request.score >= 80 else "MIXED" if request.score >= 65 else "UNFAVORABLE"
        exhaustion = "sellers appear to be running out of steam" if request.rsi_5m < 35 else "sellers are still active"
        participation = "with real institutional participation" if request.rvol > 1.3 else "on light volume"
        return {
            "ticker": request.ticker.upper(),
            "verdict": verdict,
            "plain_english": (
                f"{request.ticker} is showing a {signal_type_label.lower()} setup scoring {request.score}/100. "
                f"RSI at {request.rsi_5m:.0f} suggests {exhaustion}, and relative volume of {request.rvol:.1f}x indicates {participation}. "
                f"The scanner sees a potential bounce from the -{request.dip_pct}% intraday dip toward the ${request.target_price:.2f} target."
            ),
            "key_risk": f"If price closes below the stop at ${request.stop_price:.2f}, the setup has failed — exit immediately to cap the loss.",
            "watch_for": (
                f"Watch for price to move toward ${request.target_price:.2f} within your time stop window. "
                f"If it stalls sideways near the entry with no follow-through, exit early — the bounce is not coming."
            ),
            "history_count": h_total,
            "win_rate_pct": win_rate,
            "tokens_used": 0,
        }


def _fetch_intraday(ticker: str) -> list[dict]:
    stock = yf.Ticker(ticker)
    df = stock.history(period="1d", interval="5m", prepost=True)
    if df.empty:
        return []
    return [
        {
            "time": idx.isoformat(),
            "open":  round(float(row["Open"]),  2),
            "high":  round(float(row["High"]),  2),
            "low":   round(float(row["Low"]),   2),
            "close": round(float(row["Close"]), 2),
        }
        for idx, row in df.iterrows()
    ]


@router.get("/chart/{ticker}")
async def intraday_chart(ticker: str, _: str = Depends(verify_api_key)):
    """1-day 5-minute candles for the mini chart on the dashboard."""
    candles = await asyncio.to_thread(_fetch_intraday, ticker.upper())
    return {"ticker": ticker.upper(), "candles": candles}


@router.get("/weekly")
async def weekly_pnl(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Current week's realized P&L from closed scanner alerts (Mon–today)."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    week_start = datetime(monday.year, monday.month, monday.day, tzinfo=timezone.utc)

    rows = (await db.execute(
        select(ScannerAlert).where(
            ScannerAlert.status.in_(["win", "loss"]),
            ScannerAlert.source == "live",
            ScannerAlert.entry_time >= week_start,
        )
    )).scalars().all()

    total_pnl = sum(r.actual_pnl_dollar or 0 for r in rows)
    wins = [r for r in rows if r.status == "win"]
    losses = [r for r in rows if r.status == "loss"]

    daily: dict[str, float] = {}
    for r in rows:
        if r.entry_time:
            day_key = r.entry_time.strftime("%a")
            daily[day_key] = round(daily.get(day_key, 0) + (r.actual_pnl_dollar or 0), 2)

    return {
        "week_start": monday.isoformat(),
        "total_pnl_dollar": round(total_pnl, 2),
        "wins": len(wins),
        "losses": len(losses),
        "trade_count": len(rows),
        "by_day": daily,
        "best_day": max(daily.items(), key=lambda x: x[1])[0] if daily else None,
        "worst_day": min(daily.items(), key=lambda x: x[1])[0] if daily else None,
    }
