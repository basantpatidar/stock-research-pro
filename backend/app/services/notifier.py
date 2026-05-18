import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

_API = "https://api.telegram.org/bot{token}/{method}"


def _cfg() -> tuple[bool, str, str]:
    from app.config import get_settings

    s = get_settings()
    return s.telegram_enabled, s.telegram_bot_token or "", s.telegram_chat_id or ""


async def _get_active_chat_ids() -> list[str]:
    """Return chat_ids of all active registered users.
    Falls back to the single TELEGRAM_CHAT_ID from config if the table is empty
    or the DB is unreachable (e.g. during startup before migrations run).
    """
    enabled, _, fallback_id = _cfg()
    if not enabled:
        return []
    try:
        from sqlalchemy import select

        from app.db.database import get_db_direct
        from app.db.models import TelegramUser

        async for db in get_db_direct():
            rows = (
                (
                    await db.execute(
                        select(TelegramUser.chat_id).where(TelegramUser.is_active.is_(True))
                    )
                )
                .scalars()
                .all()
            )
        if rows:
            return list(rows)
    except Exception as exc:
        logger.warning("Telegram: could not query telegram_users, using config fallback: %s", exc)
    return [fallback_id] if fallback_id else []


async def _post_to(chat_id: str, method: str, payload: dict) -> bool:
    """Send a single Telegram API call to a specific chat_id."""
    enabled, token, _ = _cfg()
    if not enabled or not token:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                _API.format(token=token, method=method),
                json={**payload, "chat_id": chat_id},
            )
            return r.json().get("ok", False)
    except Exception as exc:
        logger.warning("Telegram %s → %s error: %s", method, chat_id, exc)
        return False


async def _broadcast(method: str, payload: dict) -> bool:
    """Send to all active registered users. Returns True if at least one succeeded."""
    chat_ids = await _get_active_chat_ids()
    if not chat_ids:
        return False
    results = [await _post_to(cid, method, payload) for cid in chat_ids]
    return any(results)


# ── Public API ────────────────────────────────────────────────────────────────


async def send_to(chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
    """Send a message to a specific chat_id (used by command handler for replies)."""
    return await _post_to(chat_id, "sendMessage", {"text": text, "parse_mode": parse_mode})


async def send_text(text: str) -> bool:
    """Broadcast a raw text message to all active users."""
    return await _broadcast("sendMessage", {"text": text, "parse_mode": "HTML"})


async def send_scanner_alert(alert) -> bool:
    """Broadcast a ScannerAlert (MCF or dip scanner) card to all active users."""
    try:
        entry = float(alert.entry_price or 0)
        stop = float(alert.stop_price or 0)
        target = float(alert.target_price or 0)
        risk = entry - stop
        rr = round((target - entry) / risk, 2) if risk > 0 else 0
        gate = "LOOSE ⚠" if alert.loose_gates else "STRICT ✓"
        emoji = "🟡" if alert.loose_gates else "🟢"
        sig_type = (alert.signal_type or "signal").replace("_", " ").upper()
        text = (
            f"{emoji} <b>{sig_type} — {alert.ticker}</b>   Score: {alert.score}\n"
            f"Entry <code>${entry:.2f}</code> | Stop <code>${stop:.2f}</code> | Target <code>${target:.2f}</code>\n"
            f"R/R: 1:{rr} | Gate: {gate}"
        )
    except Exception as exc:
        logger.warning("Telegram send_scanner_alert format error: %s", exc)
        return False
    return await _broadcast("sendMessage", {"text": text, "parse_mode": "HTML"})


async def send_watchlist_alert(
    ticker: str, signal: str, score: int, price: float, change_7d: float
) -> bool:
    """Broadcast a watchlist signal alert to all active users."""
    emoji = "🟢" if score >= 70 else "🔴"
    arrow = "▲" if change_7d >= 0 else "▼"
    text = (
        f"{emoji} <b>WATCHLIST — {ticker}</b>   Score: {score}\n"
        f"Signal: {signal}\n"
        f"Price: <code>${price:.2f}</code> | 7d: {arrow}{abs(change_7d):.1f}%"
    )
    return await _broadcast("sendMessage", {"text": text, "parse_mode": "HTML"})


async def send_daily_report(
    signals_today: int, wins: int, losses: int, open_count: int, near_misses: int
) -> bool:
    """Broadcast EOD daily summary to all active users."""
    resolved = wins + losses
    win_rate = f"{round(wins / resolved * 100)}%" if resolved > 0 else "N/A"
    date_str = datetime.now(timezone.utc).strftime("%b %d")
    text = (
        f"📊 <b>EOD Summary — {date_str}</b>\n\n"
        f"Signals fired: <b>{signals_today}</b>  ({open_count} still open)\n"
        f"Wins: {wins} | Losses: {losses} | Win rate: {win_rate}\n"
        f"Near misses: {near_misses}"
    )
    return await _broadcast("sendMessage", {"text": text, "parse_mode": "HTML"})


async def send_pre_market_digest(
    vix: float | None, spy_bias: str, watchlist_count: int, top_tickers: list[str]
) -> bool:
    """Broadcast pre-market morning brief to all active users."""
    vix_str = f"{vix:.1f}" if vix is not None else "N/A"
    tickers_str = ", ".join(top_tickers[:5]) if top_tickers else "none"
    text = (
        f"☀️ <b>Pre-Market Brief</b>\n\n"
        f"VIX: <code>{vix_str}</code> | Market bias: {spy_bias}\n"
        f"Watchlist: {watchlist_count} active tickers\n"
        f"Watching: {tickers_str}"
    )
    return await _broadcast("sendMessage", {"text": text, "parse_mode": "HTML"})
