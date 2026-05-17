import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from app.config import get_settings

logger = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None

# Heartbeat log — append-only proof-of-life for the dip scanner job. EOD report
# reads this to distinguish "scanner ran but found nothing" from "scanner did
# not run today" (the 2026-05-13 failure mode).
_HEARTBEAT_LOG = Path(
    os.getenv(
        "SCANNER_HEARTBEAT_LOG",
        str(Path(__file__).resolve().parents[3] / "local_debugging" / "scanner_heartbeat.jsonl"),
    )
)


def _write_heartbeat(record: dict) -> None:
    try:
        _HEARTBEAT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _HEARTBEAT_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except Exception:
        pass  # never let logging affect the scanner


# ── Dip scanner background jobs ───────────────────────────────────────────────

async def _run_dip_scan():
    """Fire dip-buy alerts every 5 min during market hours. Zero LLM calls."""
    import pytz
    from app.tools.dip_scanner import ETF_TIERS, scan_dip_opportunities, _get_session_window, SESSION_WINDOWS
    from app.api.alerts import broadcast
    from app.services.trading.auto_trade import should_halt_scanner

    et_tz = pytz.timezone("America/New_York")
    now_et = datetime.now(et_tz)
    window = _get_session_window(now_et)
    if SESSION_WINDOWS.get(window, {}).get("score_delta") is None:
        _write_heartbeat({
            "ts_utc": datetime.now(timezone.utc).isoformat(),
            "ts_et":  now_et.isoformat(),
            "status": "skipped_closed",
            "window": window,
        })
        return  # outside trading hours — heartbeat still recorded

    # Daily-signal halt — once today's scanner_alerts >= cap, stop firing.
    # Matches the auto-trade order cap so a full day of auto-fired orders also
    # silences the source feeding it.
    if await should_halt_scanner(get_settings()):
        logger.info("dip_scan: halted for the day — signal cap reached")
        return

    tickers = ETF_TIERS[1]  # Tier 1 only for background job
    t0 = time.monotonic()
    result: dict = {}
    error: str | None = None
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
        error = f"{type(exc).__name__}: {exc}"
        logger.warning("dip_scan job error: %s", exc)

    best = result.get("best") if isinstance(result, dict) else None
    candidates = (
        len(result.get("opportunities", []))
        + len(result.get("orb_opportunities", []))
        + len(result.get("vwap_opportunities", []))
        + len(result.get("failed_breakdown_opportunities", []))
    ) if isinstance(result, dict) else 0
    _write_heartbeat({
        "ts_utc":       datetime.now(timezone.utc).isoformat(),
        "ts_et":        now_et.isoformat(),
        "status":       "error" if error else "ok",
        "window":       window,
        "tickers":      tickers,
        "candidates":   candidates,
        "best_ticker":  best.get("ticker") if best else None,
        "best_score":   best.get("score")  if best else None,
        "duration_ms":  int((time.monotonic() - t0) * 1000),
        "error":        error,
    })


async def _run_mcf_scan(force: bool = False):
    """Fire MCF (Market Context First) funnel scan every 5 min."""
    import pytz
    from datetime import datetime, timedelta, timezone
    from app.tools.mcf_scanner import scan_mcf_opportunities
    from app.db.database import get_db_direct
    from app.services.data_cache import set_stock_cache
    from app.services.trading.auto_trade import should_halt_scanner
    from app.db.models import ScannerAlert
    import uuid

    # Run check
    et_tz = pytz.timezone("America/New_York")
    now_et = datetime.now(et_tz)
    hm = now_et.hour * 60 + now_et.minute
    if not force and (hm < 9 * 60 + 30 or hm >= 16 * 60):
        return  # outside trading hours

    # Daily-signal halt — same gate as the dip scanner.
    if not force and await should_halt_scanner(get_settings()):
        logger.info("mcf_scan: halted for the day — signal cap reached")
        return
        
    try:
        # 1. Generate scan
        result = scan_mcf_opportunities(capital=1000.0)
        
        # 2. Extract State (Weather + Tide)
        state_data = {
            "timestamp": result["timestamp"],
            "weather": result["weather"],
            "tide": result["tide"],
        }
        
        # 3. Save to Cache and DB
        async for db in get_db_direct():
            # Cache the state so frontend can fetch it quickly
            await set_stock_cache(
                db=db,
                ticker="MCF",
                data_type="state",
                data=state_data,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=15)
            )
            
            # Save any new alerts
            opps = result.get("opportunities", [])
            new_alerts = []
            for opp in opps:
                alert = ScannerAlert(
                    id=uuid.uuid4(),
                    ticker=opp["ticker"],
                    signal_type="mcf_dip_buy",
                    entry_price=opp["entry_price"],
                    target_price=opp["target_price"],
                    stop_price=opp["stop_price"],
                    entry_time=datetime.fromisoformat(result["timestamp"]),
                    score=opp.get("score", 90),
                    signals=opp.get("signals", []),
                    capital_used=opp.get("capital_used", 1000.0),
                    source="live",
                    status="open",
                )
                db.add(alert)
                new_alerts.append(alert)
                logger.info("mcf_scan: fired alert %s", opp["ticker"])

            if new_alerts:
                await db.commit()
                from app.services import notifier
                for alert in new_alerts:
                    await notifier.send_scanner_alert(alert)
                
    except Exception as exc:
        logger.warning("mcf_scan job error: %s", exc)

def _compute_fmd(bars, entry_time, entry_price: float) -> tuple[str | None, str]:
    """Forward 5-min direction. Returns (fmd, reason). fmd is None if can't compute.

    yfinance's 1-min DatetimeIndex is tz-aware (America/New_York). entry_time
    from the DB is tz-aware UTC. Pandas comparison auto-aligns tz, but the
    bars-index may also be tz-naive in some yfinance versions — normalize.
    """
    from datetime import timedelta
    import pandas as pd

    if bars is None:
        return None, "no_history"
    if bars.empty:
        return None, "empty_history"
    if entry_time is None:
        return None, "no_entry_time"

    target_ts = entry_time + timedelta(minutes=5)

    # Normalize tz: if bars.index is naive, assume ET; then convert target_ts to that tz
    idx = bars.index
    try:
        if getattr(idx, "tz", None) is None:
            idx = idx.tz_localize("America/New_York")
        # target_ts is tz-aware (timestamptz from DB) — pandas handles cross-tz compare,
        # but be explicit to avoid version quirks.
        target_ts_pd = pd.Timestamp(target_ts).tz_convert(idx.tz)
    except Exception as exc:
        return None, f"tz_normalize_failed:{exc}"

    bars_after = bars.loc[idx >= target_ts_pd]
    if bars_after.empty:
        return None, "no_bars_after_target"

    try:
        fwd_close = float(bars_after.iloc[0]["Close"])
    except Exception as exc:
        return None, f"bar_read_failed:{exc}"

    diff_pct = (fwd_close - entry_price) / entry_price * 100
    if diff_pct > 0.05:
        return "up", "ok"
    if diff_pct < -0.05:
        return "down", "ok"
    return "flat", "ok"


async def _resolve_open_alerts():
    """Check open scanner alerts every 5 min and resolve target/stop/EOD.

    Also opportunistically backfills five_min_direction for closed rows in the
    last 7 days that still have null fmd (e.g., live dip_buy resolutions where
    the original yfinance fetch failed).
    """
    import pytz
    from datetime import datetime, timezone, timedelta
    import yfinance as yf
    from sqlalchemy import select, or_, and_
    from app.db.database import get_db_direct
    from app.db.models import ScannerAlert

    et_tz = pytz.timezone("America/New_York")
    now_et = datetime.now(et_tz)
    now_utc = datetime.now(timezone.utc)
    eod_cutoff = now_et.hour * 60 + now_et.minute >= 15 * 60 + 45  # 3:45 PM ET
    fmd_backfill_horizon = now_utc - timedelta(days=7)

    # Time stops by signal_type — mirror values set in dip_scanner.py at signal
    # creation. Frees capital from dead-money trades that would otherwise drift
    # to ~breakeven by EOD (the dominant 2026-05-08 dip_buy failure mode).
    TIME_STOP_MINUTES = {
        "dip_buy":          25,
        "orb_breakout":     60,
        "vwap_reclaim":     20,
        "failed_breakdown": 30,
    }

    try:
        async for db in get_db_direct():
            rows = (await db.execute(
                select(ScannerAlert).where(
                    or_(
                        ScannerAlert.status == "open",
                        and_(
                            ScannerAlert.five_min_direction.is_(None),
                            ScannerAlert.entry_time >= fmd_backfill_horizon,
                            ScannerAlert.status.in_(("win", "loss")),
                        ),
                    )
                )
            )).scalars().all()

            if not rows:
                return

            open_rows = [r for r in rows if r.status == "open"]
            fmd_rows  = [r for r in rows if r.five_min_direction is None]

            tickers_needed = list({r.ticker for r in rows})
            prices: dict[str, float] = {}
            if open_rows:
                for ticker in {r.ticker for r in open_rows}:
                    try:
                        info = yf.Ticker(ticker).fast_info
                        prices[ticker] = float(info.get("lastPrice") or info.get("regularMarketPrice") or 0)
                    except Exception as exc:
                        logger.debug("fast_info failed for %s: %s", ticker, exc)

            # 1-min history per unique ticker — needed for fmd computation.
            # period="8d" covers the 7-day backfill horizon (yfinance hard-caps 1m at 8d).
            one_min_bars: dict[str, object] = {}
            if fmd_rows:
                for ticker in {r.ticker for r in fmd_rows}:
                    try:
                        bars = yf.Ticker(ticker).history(period="8d", interval="1m", prepost=False)
                        if bars is None or bars.empty:
                            logger.info("fmd-backfill: no 1m bars for %s", ticker)
                        one_min_bars[ticker] = bars
                    except Exception as exc:
                        logger.warning("fmd-backfill: history fetch failed for %s: %s", ticker, exc)
                        one_min_bars[ticker] = None

            # Resolve open positions
            for row in open_rows:
                price = prices.get(row.ticker, 0)
                if not price:
                    continue

                # Target / stop checked first — they describe the intended exit.
                if price >= row.target_price:
                    row.status = "win"
                    row.outcome_price = row.target_price
                    row.resolved_by = "target_hit"
                elif price <= row.stop_price:
                    row.status = "loss"
                    row.outcome_price = row.stop_price
                    row.resolved_by = "stop_hit"
                else:
                    # Time stop — fire before EOD so the row resolves while the
                    # market is still open (capital frees for next setup).
                    time_stop_min = TIME_STOP_MINUTES.get(row.signal_type or "dip_buy", 25)
                    age_min = (now_utc - row.entry_time).total_seconds() / 60 if row.entry_time else 0
                    if age_min >= time_stop_min and not eod_cutoff:
                        row.status = "win" if price > row.entry_price else "loss"
                        row.outcome_price = price
                        row.resolved_by = "time_stop"
                    elif eod_cutoff:
                        row.status = "win" if price > row.entry_price else "loss"
                        row.outcome_price = price
                        row.resolved_by = "eod_close"
                    else:
                        continue

                row.outcome_time = now_utc
                row.actual_pnl_pct = round((row.outcome_price - row.entry_price) / row.entry_price * 100, 3)
                row.actual_pnl_dollar = round(row.actual_pnl_pct / 100 * (row.capital_used or 1000.0), 2)

            # Compute / backfill fmd for any row missing it (covers freshly-resolved
            # opens AND historical closed rows within the 7-day horizon)
            for row in fmd_rows:
                if row.five_min_direction is not None:
                    continue  # may have been set by another path
                bars = one_min_bars.get(row.ticker)
                fmd, reason = _compute_fmd(bars, row.entry_time, row.entry_price)
                if fmd is not None:
                    row.five_min_direction = fmd
                else:
                    logger.debug(
                        "fmd skip ticker=%s entry=%s reason=%s",
                        row.ticker, row.entry_time, reason,
                    )

            await db.commit()
    except Exception as exc:
        logger.warning("resolve_alerts job error: %s", exc)


async def _run_eod_dump():
    """Generate the daily EOD signal dump at market close.

    Runs `local_debugging/eod_dump.py` in-process via a subprocess so a
    Docker-only laptop never needs a host Python env or a manual
    `docker compose exec`. Read-only: the script SELECTs from scanner_alerts +
    broker_orders and writes one JSON to local_debugging/eod_signals/ (the
    host bind mount), where it's ready to copy back for analysis.

    The script is located via LOG_DIR — already set to /app/local_debugging in
    docker-compose.yml — so the path is correct both in Docker and locally.
    """
    import subprocess
    import sys

    log_dir = os.getenv("LOG_DIR") or str(
        Path(__file__).resolve().parents[3] / "local_debugging"
    )
    script = Path(log_dir) / "eod_dump.py"
    if not script.exists():
        logger.warning("eod_dump: script not found at %s — skipping", script)
        return
    try:
        proc = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode == 0:
            lines = (proc.stdout or "").strip().splitlines()
            logger.info("eod_dump: report generated — %s", lines[-1].strip() if lines else "ok")
        else:
            logger.warning("eod_dump: failed rc=%d — %s", proc.returncode, (proc.stderr or "")[-400:])
    except Exception as exc:
        logger.warning("eod_dump job error: %s", exc)

    # Send EOD Telegram summary — best-effort, runs regardless of eod_dump result
    try:
        from sqlalchemy import select, func, and_
        from app.db.database import get_db_direct
        from app.db.models import ScannerAlert
        from app.services import notifier
        import pytz
        today_et = datetime.now(pytz.timezone("America/New_York")).date()
        today_start = datetime.combine(today_et, datetime.min.time()).replace(tzinfo=timezone.utc)
        async for db in get_db_direct():
            rows = (await db.execute(
                select(ScannerAlert).where(ScannerAlert.entry_time >= today_start)
            )).scalars().all()
        wins = sum(1 for r in rows if r.status == "win")
        losses = sum(1 for r in rows if r.status == "loss")
        open_count = sum(1 for r in rows if r.status == "open")
        await notifier.send_daily_report(
            signals_today=len(rows),
            wins=wins,
            losses=losses,
            open_count=open_count,
            near_misses=0,
        )
    except Exception as exc:
        logger.warning("eod Telegram summary error: %s", exc)


async def _run_pre_market_digest():
    """Send a pre-market morning brief to Telegram."""
    from app.services import notifier
    from app.db.database import get_db_direct
    from app.db.models import WatchlistItem
    from sqlalchemy import select
    try:
        import yfinance as yf
        vix = yf.Ticker("^VIX").fast_info.get("last_price")
        spy = yf.Ticker("SPY").fast_info
        spy_price = spy.get("last_price", 0)
        spy_prev = spy.get("previous_close", spy_price)
        spy_chg = spy_price - spy_prev
        spy_bias = "Bullish ▲" if spy_chg > 0 else "Bearish ▼" if spy_chg < 0 else "Flat"
    except Exception:
        vix, spy_bias = None, "Unknown"

    try:
        async for db in get_db_direct():
            items = (await db.execute(
                select(WatchlistItem).where(WatchlistItem.is_active == True)
            )).scalars().all()
        tickers = [i.ticker for i in items]
    except Exception:
        tickers = []

    await notifier.send_pre_market_digest(
        vix=vix,
        spy_bias=spy_bias,
        watchlist_count=len(tickers),
        top_tickers=tickers,
    )


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

    # MCF scanner — every 5 min
    scheduler.add_job(
        _run_mcf_scan,
        trigger=IntervalTrigger(minutes=5),
        id="mcf_scan",
        name="MCF funnel scanner",
        replace_existing=True,
        misfire_grace_time=60,
    )

    # Auto-trade subscriber — turns scanner_alert rows into paper bracket
    # orders when AUTO_TRADE_ENABLED=true and the alert's signal_type is in
    # AUTO_TRADE_SIGNAL_TYPES. The job itself is registered unconditionally;
    # it self-skips when the flag is off, so flipping the env requires only
    # a restart, not a job-graph change.
    from app.services.trading.auto_trade import _run_auto_trade_subscriber
    scheduler.add_job(
        _run_auto_trade_subscriber,
        trigger=IntervalTrigger(seconds=settings.auto_trade_poll_seconds),
        id="auto_trade_subscriber",
        name="Auto-trade scanner alerts",
        replace_existing=True,
        misfire_grace_time=30,
    )

    # EOD signal dump — Mon-Fri 4:35 PM ET, after the 3:45 PM resolution pass
    # has closed every open alert. Writes local_debugging/eod_signals/<date>.json
    # so the Docker-only laptop produces the daily report with no manual step.
    # Also sends a Telegram EOD summary if TELEGRAM_ENABLED=true.
    import pytz
    scheduler.add_job(
        _run_eod_dump,
        trigger=CronTrigger(
            day_of_week="mon-fri", hour=16, minute=35,
            timezone=pytz.timezone("America/New_York"),
        ),
        id="eod_dump",
        name="EOD signal dump",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Pre-market Telegram brief — Mon-Fri 9:00 AM ET (TELEGRAM_ENABLED gates the send)
    scheduler.add_job(
        _run_pre_market_digest,
        trigger=CronTrigger(
            day_of_week="mon-fri", hour=9, minute=0,
            timezone=pytz.timezone("America/New_York"),
        ),
        id="pre_market_digest",
        name="Pre-market Telegram brief",
        replace_existing=True,
        misfire_grace_time=600,
    )

    scheduler.start()
    logger.info(
        f"Scheduler started — watchlist every {settings.watchlist_alert_interval_minutes}min, "
        f"screener every {settings.screener_interval_minutes}min, "
        f"dip scanner every 5min, "
        f"auto-trade every {settings.auto_trade_poll_seconds}s "
        f"(enabled={settings.auto_trade_enabled}), "
        f"eod dump + Telegram summary 4:35 PM ET Mon-Fri, "
        f"pre-market brief 9:00 AM ET Mon-Fri (telegram={settings.telegram_enabled})"
    )


def stop_scheduler():
    """Stop the scheduler gracefully on app shutdown."""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
