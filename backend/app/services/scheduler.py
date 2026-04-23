import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.config import get_settings

logger = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None


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

    scheduler.start()
    logger.info(
        f"Scheduler started — watchlist every {settings.watchlist_alert_interval_minutes}min, "
        f"screener every {settings.screener_interval_minutes}min"
    )


def stop_scheduler():
    """Stop the scheduler gracefully on app shutdown."""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
