import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.config import get_settings

logger = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None

# ── Dip scanner background jobs ───────────────────────────────────────────────

async def _run_dip_scan():
    """Fire dip-buy alerts every 5 min during market hours. Zero LLM calls."""
    import pytz
    from datetime import datetime
    from app.tools.dip_scanner import ETF_TIERS, scan_dip_opportunities, _get_session_window, SESSION_WINDOWS
    from app.api.alerts import broadcast

    et_tz = pytz.timezone("America/New_York")
    now_et = datetime.now(et_tz)
    window = _get_session_window(now_et)
    if SESSION_WINDOWS.get(window, {}).get("score_delta") is None:
        return  # outside trading hours — silent skip

    tickers = ETF_TIERS[1]  # Tier 1 only for background job
    try:
        result = scan_dip_opportunities(tickers, capital=1000.0)
        best = result.get("best")
        if best:
            await broadcast({
                "type": "dip_buy_alert",
                "ticker": best["ticker"],
                "score": best["score"],
                "entry_price": best["entry_price"],
                "target_price": best["target_price"],
                "stop_price": best["stop_price"],
                "expected_profit_dollar": best.get("expected_profit_dollar"),
                "max_risk_dollar": best.get("max_risk_dollar"),
                "risk_reward_ratio": best.get("risk_reward_ratio"),
                "capital_used": best.get("capital_used", 1000.0),
                "signals": best.get("signals", []),
                "session_window": best.get("session_window_label", best.get("session_window")),
                "vix": best.get("vix"),
                "title": f"{best['ticker']} Dip Buy — Entry Zone (score {best['score']})",
                "body": f"{best['ticker']} near support. Signals: {', '.join(best.get('signals', [])[:3])}",
                "timestamp": result.get("timestamp"),
            })
            logger.info(
                "dip_scan: fired alert %s score=%d window=%s",
                best["ticker"], best["score"], best.get("session_window"),
            )
    except Exception as exc:
        logger.warning("dip_scan job error: %s", exc)


async def _resolve_open_alerts():
    """Check open scanner alerts every 5 min and resolve target/stop/EOD."""
    import pytz
    from datetime import datetime, timezone
    import yfinance as yf
    from sqlalchemy import select
    from app.db.database import get_db_direct
    from app.db.models import ScannerAlert

    et_tz = pytz.timezone("America/New_York")
    now_et = datetime.now(et_tz)
    now_utc = datetime.now(timezone.utc)
    eod_cutoff = now_et.hour * 60 + now_et.minute >= 15 * 60 + 45  # 3:45 PM ET

    try:
        async for db in get_db_direct():
            rows = (await db.execute(
                select(ScannerAlert).where(ScannerAlert.status == "open")
            )).scalars().all()

            if not rows:
                return

            tickers_needed = list({r.ticker for r in rows})
            prices: dict[str, float] = {}
            for ticker in tickers_needed:
                try:
                    info = yf.Ticker(ticker).fast_info
                    prices[ticker] = float(info.get("lastPrice") or info.get("regularMarketPrice") or 0)
                except Exception:
                    pass

            for row in rows:
                price = prices.get(row.ticker, 0)
                if not price:
                    continue

                if price >= row.target_price:
                    row.status = "win"
                    row.outcome_price = row.target_price
                    row.resolved_by = "target_hit"
                elif price <= row.stop_price:
                    row.status = "loss"
                    row.outcome_price = row.stop_price
                    row.resolved_by = "stop_hit"
                elif eod_cutoff:
                    row.status = "win" if price > row.entry_price else "loss"
                    row.outcome_price = price
                    row.resolved_by = "eod_close"
                else:
                    continue

                row.outcome_time = now_utc
                row.actual_pnl_pct = round((row.outcome_price - row.entry_price) / row.entry_price * 100, 3)
                row.actual_pnl_dollar = round(row.actual_pnl_pct / 100 * (row.capital_used or 1000.0), 2)

            await db.commit()
    except Exception as exc:
        logger.warning("resolve_alerts job error: %s", exc)


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def start_scheduler():
    """
    Register and start all background jobs.
    Called once at app startup.
    """
    settings = get_settings()
    scheduler = get_scheduler()

    from app.services.alert_engine import evaluate_watchlist, run_screener_background

    # Watchlist evaluation — every N minutes
    scheduler.add_job(
        evaluate_watchlist,
        trigger=IntervalTrigger(minutes=settings.watchlist_alert_interval_minutes),
        id="watchlist_evaluation",
        name="Evaluate watchlist signals",
        replace_existing=True,
        misfire_grace_time=60,
    )

    # Screener auto-monitor — every N minutes
    scheduler.add_job(
        run_screener_background,
        trigger=IntervalTrigger(minutes=settings.screener_interval_minutes),
        id="screener_background",
        name="Run screener presets",
        replace_existing=True,
        misfire_grace_time=120,
    )

    # Dip scanner — every 5 min (zero LLM, safe all day)
    scheduler.add_job(
        _run_dip_scan,
        trigger=IntervalTrigger(minutes=5),
        id="dip_scan",
        name="Dip-buy ETF scanner",
        replace_existing=True,
        misfire_grace_time=60,
    )

    # Outcome resolver — every 5 min, checks open alerts for target/stop/EOD
    scheduler.add_job(
        _resolve_open_alerts,
        trigger=IntervalTrigger(minutes=5),
        id="resolve_alerts",
        name="Resolve open scanner alerts",
        replace_existing=True,
        misfire_grace_time=60,
    )

    scheduler.start()
    logger.info(
        f"Scheduler started — watchlist every {settings.watchlist_alert_interval_minutes}min, "
        f"screener every {settings.screener_interval_minutes}min, "
        f"dip scanner every 5min"
    )


def stop_scheduler():
    """Stop the scheduler gracefully on app shutdown."""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
