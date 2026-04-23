import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import WatchlistItem, AlertHistory, ScreenerPreset
from app.db.database import AsyncSessionLocal
from app.tools.price import get_price
from app.tools.technicals import get_technicals
from app.tools.remaining_tools import get_convergence_score

logger = logging.getLogger(__name__)


def _compute_quick_signal(price_data: dict, tech_data: dict) -> tuple[str, int]:
    """
    Fast signal computation without full agent run.
    Returns (signal_label, score_0_to_100).
    Used for background watchlist evaluation.
    """
    score = 50
    change_7d = price_data.get("change_pct_7d", 0)
    rsi = tech_data.get("rsi_14", 50)
    macd = tech_data.get("macd", {})
    volume_ratio = price_data.get("volume_ratio", 1.0)

    # Price drop — potential opportunity
    if change_7d < -10:
        score += 8
    elif change_7d < -5:
        score += 4
    elif change_7d > 10:
        score -= 8

    # RSI
    if rsi < 30:
        score += 12
    elif rsi > 70:
        score -= 12
    elif rsi < 40:
        score += 5

    # MACD
    if macd.get("crossover") == "bullish":
        score += 8
    elif macd.get("crossover") == "bearish":
        score -= 8

    # Volume confirmation
    if volume_ratio > 1.5:
        score += 5

    score = max(0, min(100, score))

    if score >= 72:
        signal = "Buy now"
    elif score >= 60:
        signal = "Buy — 1 week"
    elif score >= 50:
        signal = "Buy — 1 month"
    elif score >= 40:
        signal = "Hold"
    elif score >= 30:
        signal = "Watch — wait"
    else:
        signal = "Avoid"

    return signal, score


async def evaluate_watchlist():
    """
    Background job: evaluate all watchlist items and fire alerts for signals.
    Runs every N minutes as configured by WATCHLIST_ALERT_INTERVAL_MINUTES.
    """
    logger.info("Running watchlist evaluation...")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(WatchlistItem).where(WatchlistItem.is_active == True)
        )
        items = result.scalars().all()

        for item in items:
            try:
                # Fetch price and technicals in thread pool
                price_data = await asyncio.to_thread(
                    get_price.invoke, {"ticker": item.ticker, "period": "1mo"}
                )
                tech_data = await asyncio.to_thread(
                    get_technicals.invoke, {"ticker": item.ticker}
                )

                if "error" in price_data or "error" in tech_data:
                    continue

                signal, score = _compute_quick_signal(price_data, tech_data)
                current_price = price_data.get("current_price")
                change_7d = price_data.get("change_pct_7d", 0)

                # Update watchlist item
                item.last_signal = signal
                item.last_score = score
                item.last_price = current_price
                item.last_evaluated = datetime.now(timezone.utc)

                # Fire alert for strong signals
                should_alert = score >= 70 or score <= 30
                if should_alert:
                    alert_type = "buy_now" if score >= 70 else "avoid"
                    title = f"{item.ticker} — {signal}"

                    if score >= 70:
                        body = (
                            f"{item.ticker} is showing a strong buy setup (score: {score}/100). "
                            f"7-day change: {change_7d:.1f}%. RSI: {price_data.get('rsi', 'N/A')}. "
                            f"Current price: ${current_price}."
                        )
                    else:
                        body = (
                            f"{item.ticker} is showing bearish signals (score: {score}/100). "
                            f"7-day change: {change_7d:.1f}%. Consider reviewing your position."
                        )

                    alert = AlertHistory(
                        ticker=item.ticker,
                        alert_type=alert_type,
                        title=title,
                        body=body,
                        score=score,
                        source="watchlist",
                    )
                    db.add(alert)

                    # Broadcast via WebSocket
                    try:
                        from app.api.alerts import broadcast
                        await broadcast({
                            "type": "watchlist_alert",
                            "ticker": item.ticker,
                            "signal": signal,
                            "score": score,
                            "price": current_price,
                            "change_7d": change_7d,
                            "title": title,
                            "body": body,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                    except Exception as e:
                        logger.warning(f"WebSocket broadcast failed: {e}")

            except Exception as e:
                logger.error(f"Failed to evaluate {item.ticker}: {e}")
                continue

        await db.commit()
    logger.info(f"Watchlist evaluation complete — {len(items)} tickers checked")


async def run_screener_background():
    """
    Background job: run all auto-monitor screener presets.
    Fires alerts when new qualifying stocks are found.
    """
    logger.info("Running background screener...")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ScreenerPreset).where(ScreenerPreset.auto_monitor == True)
        )
        presets = result.scalars().all()

        for preset in presets:
            try:
                from app.tools.remaining_tools import run_screener
                screener_result = await asyncio.to_thread(
                    run_screener.invoke, preset.filters
                )

                matches = screener_result.get("results", [])
                if matches:
                    for match in matches[:3]:
                        ticker = match["ticker"]
                        change = match["change_7d_pct"]
                        title = f"{ticker} matches screener '{preset.name}' — down {abs(change):.1f}%"
                        body = (
                            f"{match['company']} qualifies: ${match['market_cap_b']}B cap, "
                            f"{match['avg_volume']:,} avg volume, {change:.1f}% 7-day change. "
                            f"Sector: {match['sector']}."
                        )

                        alert = AlertHistory(
                            ticker=ticker,
                            alert_type="screener_match",
                            title=title,
                            body=body,
                            score=None,
                            source="screener",
                        )
                        db.add(alert)

                        try:
                            from app.api.alerts import broadcast
                            await broadcast({
                                "type": "screener_alert",
                                "ticker": ticker,
                                "preset": preset.name,
                                "title": title,
                                "body": body,
                                "stock": match,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            })
                        except Exception:
                            pass

                preset.last_run = datetime.now(timezone.utc)

            except Exception as e:
                logger.error(f"Screener preset {preset.id} failed: {e}")

        await db.commit()
    logger.info("Background screener complete")
