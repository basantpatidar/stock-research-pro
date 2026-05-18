"""Telegram bot inbound handler — long-poll loop + command router.

Registration:
  Any Telegram user can send /start <invite_code>. On match they are added to
  telegram_users with is_active=True. The first user whose chat_id matches
  TELEGRAM_CHAT_ID in config is auto-promoted to admin on registration.

Security:
  Every command except /start checks that the sender's chat_id exists in
  telegram_users with is_active=True. Admin commands also require is_admin=True.
  Unknown senders receive a single "not registered" reply — no further response.

Polling:
  Uses getUpdates long-poll (timeout=25s). Runs as an asyncio background task
  started in the FastAPI lifespan. Gracefully stops when _running is set False.
"""

import asyncio
import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

_API = "https://api.telegram.org/bot{token}/{method}"
_running = False
_poll_task: asyncio.Task | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────


def _token() -> str:
    from app.config import get_settings

    return get_settings().telegram_bot_token or ""


def _invite_code() -> str:
    from app.config import get_settings

    return get_settings().telegram_invite_code or ""


def _owner_chat_id() -> str:
    from app.config import get_settings

    return get_settings().telegram_chat_id or ""


def _enabled() -> bool:
    from app.config import get_settings

    return get_settings().telegram_enabled


async def _api(method: str, **kwargs) -> dict:
    token = _token()
    if not token:
        return {}
    try:
        async with httpx.AsyncClient(timeout=35) as client:
            r = await client.post(_API.format(token=token, method=method), json=kwargs)
            return r.json()
    except Exception as exc:
        logger.warning("Telegram API %s error: %s", method, exc)
        return {}


async def _reply(chat_id: str, text: str) -> None:
    await _api("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML")


# ── DB helpers ────────────────────────────────────────────────────────────────


async def _get_user(chat_id: str):
    from sqlalchemy import select

    from app.db.database import get_db_direct
    from app.db.models import TelegramUser

    try:
        async for db in get_db_direct():
            row = (
                await db.execute(select(TelegramUser).where(TelegramUser.chat_id == chat_id))
            ).scalar_one_or_none()
            return row
    except Exception:
        return None


async def _register_user(
    chat_id: str, username: str | None, display_name: str | None
) -> tuple[bool, bool]:
    """Register a new user. Returns (already_existed, is_admin)."""
    import uuid

    from sqlalchemy import select

    from app.db.database import get_db_direct
    from app.db.models import TelegramUser

    async for db in get_db_direct():
        existing = (
            await db.execute(select(TelegramUser).where(TelegramUser.chat_id == chat_id))
        ).scalar_one_or_none()

        if existing:
            if not existing.is_active:
                existing.is_active = True
                await db.commit()
            return True, existing.is_admin

        # First user or owner chat_id → auto-admin
        is_admin = chat_id == _owner_chat_id()
        user = TelegramUser(
            id=uuid.uuid4(),
            chat_id=chat_id,
            username=username,
            display_name=display_name,
            is_admin=is_admin,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        return False, is_admin


async def _get_all_users():
    from sqlalchemy import select

    from app.db.database import get_db_direct
    from app.db.models import TelegramUser

    async for db in get_db_direct():
        return (
            (await db.execute(select(TelegramUser).order_by(TelegramUser.registered_at)))
            .scalars()
            .all()
        )
    return []


async def _set_active(chat_id: str, active: bool) -> bool:
    from sqlalchemy import select

    from app.db.database import get_db_direct
    from app.db.models import TelegramUser

    async for db in get_db_direct():
        row = (
            await db.execute(select(TelegramUser).where(TelegramUser.chat_id == chat_id))
        ).scalar_one_or_none()
        if not row:
            return False
        row.is_active = active
        await db.commit()
        return True
    return False


async def _set_admin(chat_id: str, is_admin: bool) -> bool:
    from sqlalchemy import select

    from app.db.database import get_db_direct
    from app.db.models import TelegramUser

    async for db in get_db_direct():
        row = (
            await db.execute(select(TelegramUser).where(TelegramUser.chat_id == chat_id))
        ).scalar_one_or_none()
        if not row:
            return False
        row.is_admin = is_admin
        await db.commit()
        return True
    return False


# ── Session state (in-memory, resets on restart) ──────────────────────────────

_sessions: dict[str, dict] = {}


def _get_mode(chat_id: str) -> str:
    return _sessions.get(chat_id, {}).get("exec_mode", "saver")


def _set_mode(chat_id: str, mode: str) -> None:
    _sessions.setdefault(chat_id, {})["exec_mode"] = mode


def _is_paused(chat_id: str) -> bool:
    until = _sessions.get(chat_id, {}).get("paused_until")
    if until and datetime.now(timezone.utc) < until:
        return True
    return False


def _pause(chat_id: str, until: datetime) -> None:
    _sessions.setdefault(chat_id, {})["paused_until"] = until


def _resume(chat_id: str) -> None:
    _sessions.get(chat_id, {}).pop("paused_until", None)


# ── Command handlers ──────────────────────────────────────────────────────────


async def _cmd_start(
    chat_id: str, username: str | None, display_name: str | None, args: str
) -> None:
    code = args.strip()
    expected = _invite_code()

    if not expected:
        await _reply(chat_id, "⚠️ Bot is not configured for registration yet. Contact the admin.")
        return

    if code != expected:
        await _reply(chat_id, "❌ Invalid invite code. Ask the admin for the correct code.")
        return

    already, is_admin = await _register_user(chat_id, username, display_name)
    name = display_name or username or "there"

    if already:
        await _reply(
            chat_id, f"✅ You're already registered, {name}! Send /help to see available commands."
        )
    else:
        admin_note = "\n\n👑 You have been granted <b>admin access</b>." if is_admin else ""
        await _reply(
            chat_id,
            f"🎉 Welcome, <b>{name}</b>! You're now registered.\n\n"
            f"You'll receive signal alerts, EOD reports, and pre-market briefs.{admin_note}\n\n"
            f"Send /help to see all available commands.",
        )


async def _cmd_help(chat_id: str, user) -> None:
    admin_section = ""
    if user.is_admin:
        admin_section = (
            "\n\n<b>Admin commands:</b>\n"
            "/users — list all registered users\n"
            "/remove &lt;chat_id&gt; — deactivate a user\n"
            "/promote &lt;chat_id&gt; — grant admin access\n"
            "/demote &lt;chat_id&gt; — remove admin access"
        )
    text = (
        "<b>Stock Research Pro — Commands</b>\n\n"
        "<b>Scanner:</b>\n"
        "/scan — trigger MCF + dip scan\n"
        "/scan loose — MCF scan with loose gates\n"
        "/alerts [N] — last N signals (default 5)\n\n"
        "<b>Mode:</b>\n"
        "/mode — show current exec mode\n"
        "/mode saver|normal|deep — change mode\n\n"
        "<b>Status:</b>\n"
        "/status — scanner health + today's signal count\n"
        "/usage — today's token + API usage\n\n"
        "<b>Watchlist:</b>\n"
        "/watchlist — list active watchlist tickers\n"
        "/add TICKER — add to watchlist\n"
        "/remove_ticker TICKER — remove from watchlist\n\n"
        "<b>Notifications:</b>\n"
        "/pause [30m|1h|2h|4h] — silence alerts\n"
        "/resume — re-enable alerts"
        f"{admin_section}"
    )
    await _reply(chat_id, text)


async def _cmd_status(chat_id: str) -> None:
    import pytz
    from sqlalchemy import func, select

    from app.db.database import get_db_direct
    from app.db.models import ScannerAlert

    et_tz = pytz.timezone("America/New_York")
    now_et = datetime.now(et_tz)
    market_open = (now_et.weekday() < 5) and (
        9 * 60 + 30 <= now_et.hour * 60 + now_et.minute < 16 * 60
    )
    market_str = "🟢 Open" if market_open else "🔴 Closed"

    try:
        today_start = datetime.combine(now_et.date(), datetime.min.time()).replace(
            tzinfo=timezone.utc
        )
        async for db in get_db_direct():
            count = (
                await db.execute(
                    select(func.count())
                    .select_from(ScannerAlert)
                    .where(ScannerAlert.entry_time >= today_start)
                )
            ).scalar_one()
    except Exception:
        count = 0

    mode = _get_mode(chat_id)
    text = (
        f"📡 <b>Scanner Status</b>\n\n"
        f"Market: {market_str}\n"
        f"Signals today: <b>{count}</b>\n"
        f"Your exec mode: <b>{mode}</b>\n"
        f"Time (ET): {now_et.strftime('%H:%M')}"
    )
    await _reply(chat_id, text)


async def _cmd_mode(chat_id: str, args: str) -> None:
    valid = {"saver", "normal", "deep"}
    arg = args.strip().lower()
    if not arg:
        await _reply(
            chat_id,
            f"Current exec mode: <b>{_get_mode(chat_id)}</b>\n\nChange with: /mode saver | /mode normal | /mode deep",
        )
        return
    if arg not in valid:
        await _reply(chat_id, f"❌ Unknown mode <code>{arg}</code>. Choose: saver, normal, deep")
        return
    _set_mode(chat_id, arg)
    descriptions = {
        "saver": "0 tokens — Tier 1 data only, instant",
        "normal": "Tier 1 auto + Tier 2 on demand",
        "deep": "All tiers auto — highest token use",
    }
    await _reply(chat_id, f"✅ Mode set to <b>{arg}</b>\n{descriptions[arg]}")


async def _cmd_scan(chat_id: str, args: str) -> None:
    loose = "loose" in args.lower()
    await _reply(chat_id, f"🔍 Running {'loose-gate ' if loose else ''}MCF scan...")
    try:
        from app.services.scheduler import _run_mcf_scan

        await _run_mcf_scan(force=True, loose=loose)
        await _reply(chat_id, "✅ Scan complete. Any signals will be pushed as alerts.")
    except Exception as exc:
        await _reply(chat_id, f"❌ Scan failed: {exc}")


async def _cmd_alerts(chat_id: str, args: str) -> None:
    try:
        n = min(int(args.strip()), 20) if args.strip().isdigit() else 5
    except Exception:
        n = 5

    from sqlalchemy import select

    from app.db.database import get_db_direct
    from app.db.models import ScannerAlert

    async for db in get_db_direct():
        rows = (
            (
                await db.execute(
                    select(ScannerAlert).order_by(ScannerAlert.entry_time.desc()).limit(n)
                )
            )
            .scalars()
            .all()
        )

    if not rows:
        await _reply(chat_id, "No signals found.")
        return

    lines = [f"<b>Last {len(rows)} signals:</b>\n"]
    for r in rows:
        status_emoji = {"win": "✅", "loss": "❌", "open": "🟡"}.get(r.status, "⚪")
        loose_tag = " [LOOSE]" if r.loose_gates else ""
        lines.append(
            f"{status_emoji} <b>{r.ticker}</b>{loose_tag} — Score {r.score} — "
            f"{r.entry_time.strftime('%m/%d %H:%M') if r.entry_time else 'N/A'}"
        )
    await _reply(chat_id, "\n".join(lines))


async def _cmd_usage(chat_id: str) -> None:
    try:
        from app.services.usage.tracker import UsageTracker

        tracker = UsageTracker()
        today = await tracker.get_today()
        tokens = today.get("tokens", 0)
        calls = today.get("api_calls", 0)
        from app.config import get_settings

        s = get_settings()
        token_pct = round(tokens / s.token_daily_limit * 100) if s.token_daily_limit else 0
        call_pct = round(calls / s.api_calls_daily_limit * 100) if s.api_calls_daily_limit else 0
        text = (
            f"📈 <b>Usage Today</b>\n\n"
            f"Tokens: <code>{tokens:,}</code> / {s.token_daily_limit:,} ({token_pct}%)\n"
            f"API calls: <code>{calls}</code> / {s.api_calls_daily_limit} ({call_pct}%)"
        )
    except Exception as exc:
        text = f"⚠️ Could not fetch usage: {exc}"
    await _reply(chat_id, text)


async def _cmd_watchlist(chat_id: str) -> None:
    from sqlalchemy import select

    from app.db.database import get_db_direct
    from app.db.models import WatchlistItem

    async for db in get_db_direct():
        items = (
            (await db.execute(select(WatchlistItem).where(WatchlistItem.is_active.is_(True))))
            .scalars()
            .all()
        )
    if not items:
        await _reply(chat_id, "Your watchlist is empty. Add tickers with /add TICKER")
        return
    lines = ["<b>Watchlist:</b>\n"]
    for item in items:
        score_str = f"  Score {item.last_score}" if item.last_score else ""
        lines.append(f"• <b>{item.ticker}</b>{score_str} — {item.last_signal or 'not evaluated'}")
    await _reply(chat_id, "\n".join(lines))


async def _cmd_add(chat_id: str, args: str) -> None:
    ticker = args.strip().upper()
    if not ticker:
        await _reply(chat_id, "Usage: /add TICKER")
        return
    import uuid

    from sqlalchemy import select

    from app.db.database import get_db_direct
    from app.db.models import WatchlistItem

    async for db in get_db_direct():
        existing = (
            await db.execute(select(WatchlistItem).where(WatchlistItem.ticker == ticker))
        ).scalar_one_or_none()
        if existing:
            if not existing.is_active:
                existing.is_active = True
                await db.commit()
                await _reply(chat_id, f"✅ {ticker} re-activated in watchlist.")
            else:
                await _reply(chat_id, f"ℹ️ {ticker} is already in your watchlist.")
            return
        db.add(WatchlistItem(id=uuid.uuid4(), ticker=ticker, is_active=True))
        await db.commit()
    await _reply(chat_id, f"✅ {ticker} added to watchlist.")


async def _cmd_remove_ticker(chat_id: str, args: str) -> None:
    ticker = args.strip().upper()
    if not ticker:
        await _reply(chat_id, "Usage: /remove_ticker TICKER")
        return
    from sqlalchemy import select

    from app.db.database import get_db_direct
    from app.db.models import WatchlistItem

    async for db in get_db_direct():
        item = (
            await db.execute(
                select(WatchlistItem).where(
                    WatchlistItem.ticker == ticker, WatchlistItem.is_active.is_(True)
                )
            )
        ).scalar_one_or_none()
        if not item:
            await _reply(chat_id, f"ℹ️ {ticker} not found in watchlist.")
            return
        item.is_active = False
        await db.commit()
    await _reply(chat_id, f"✅ {ticker} removed from watchlist.")


async def _cmd_pause(chat_id: str, args: str) -> None:
    durations = {"30m": 30, "1h": 60, "2h": 120, "4h": 240, "8h": 480}
    arg = args.strip().lower() or "2h"
    minutes = durations.get(arg, 120)
    until = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    until = until.replace(second=0, microsecond=0)
    import datetime as dt

    until = datetime.now(timezone.utc) + dt.timedelta(minutes=minutes)
    _pause(chat_id, until)
    await _reply(chat_id, f"🔕 Notifications paused for <b>{arg}</b>. Send /resume to re-enable.")


async def _cmd_resume(chat_id: str) -> None:
    _resume(chat_id)
    await _reply(chat_id, "🔔 Notifications resumed.")


# ── Admin commands ────────────────────────────────────────────────────────────


async def _cmd_users(chat_id: str) -> None:
    users = await _get_all_users()
    if not users:
        await _reply(chat_id, "No registered users yet.")
        return
    lines = [f"<b>Registered users ({len(users)}):</b>\n"]
    for u in users:
        status = "✅" if u.is_active else "❌"
        admin = " 👑" if u.is_admin else ""
        handle = f" @{u.username}" if u.username else ""
        name = u.display_name or "Unknown"
        lines.append(f"{status}{admin} <b>{name}</b>{handle}\n  ID: <code>{u.chat_id}</code>")
    await _reply(chat_id, "\n".join(lines))


async def _cmd_remove_user(chat_id: str, args: str) -> None:
    target = args.strip()
    if not target:
        await _reply(chat_id, "Usage: /remove &lt;chat_id&gt;")
        return
    if target == chat_id:
        await _reply(chat_id, "❌ You cannot remove yourself.")
        return
    ok = await _set_active(target, False)
    if ok:
        await _reply(chat_id, f"✅ User <code>{target}</code> has been deactivated.")
    else:
        await _reply(chat_id, f"❌ User <code>{target}</code> not found.")


async def _cmd_promote(chat_id: str, args: str) -> None:
    target = args.strip()
    if not target:
        await _reply(chat_id, "Usage: /promote &lt;chat_id&gt;")
        return
    ok = await _set_admin(target, True)
    await _reply(
        chat_id,
        (
            f"✅ <code>{target}</code> promoted to admin."
            if ok
            else f"❌ User <code>{target}</code> not found."
        ),
    )


async def _cmd_demote(chat_id: str, args: str) -> None:
    target = args.strip()
    if not target:
        await _reply(chat_id, "Usage: /demote &lt;chat_id&gt;")
        return
    if target == chat_id:
        await _reply(chat_id, "❌ You cannot demote yourself.")
        return
    ok = await _set_admin(target, False)
    await _reply(
        chat_id,
        (
            f"✅ <code>{target}</code> admin access removed."
            if ok
            else f"❌ User <code>{target}</code> not found."
        ),
    )


# ── Update router ─────────────────────────────────────────────────────────────


async def _handle_update(update: dict) -> None:
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return

    chat_id = str(msg.get("chat", {}).get("id", ""))
    text = (msg.get("text") or "").strip()
    if not chat_id or not text:
        return

    from_user = msg.get("from", {})
    username = from_user.get("username")
    display_name = (
        " ".join(filter(None, [from_user.get("first_name"), from_user.get("last_name")])) or None
    )

    # Parse command and args
    parts = text.split(None, 1)
    raw_cmd = parts[0].lower().split("@")[0]  # strip @botname suffix
    args = parts[1] if len(parts) > 1 else ""

    # /start is always allowed — it's the registration entry point
    if raw_cmd == "/start":
        await _cmd_start(chat_id, username, display_name, args)
        return

    # All other commands require registration
    user = await _get_user(chat_id)
    if not user or not user.is_active:
        await _reply(
            chat_id,
            "❌ You're not registered.\n\nSend <code>/start &lt;invite_code&gt;</code> to register.",
        )
        return

    # Skip if paused (user still gets command responses, just not broadcasts)
    # Pausing only suppresses broadcast notifications, not command replies.

    # User commands
    if raw_cmd == "/help":
        await _cmd_help(chat_id, user)
    elif raw_cmd == "/status":
        await _cmd_status(chat_id)
    elif raw_cmd == "/mode":
        await _cmd_mode(chat_id, args)
    elif raw_cmd == "/scan":
        await _cmd_scan(chat_id, args)
    elif raw_cmd == "/alerts":
        await _cmd_alerts(chat_id, args)
    elif raw_cmd == "/usage":
        await _cmd_usage(chat_id)
    elif raw_cmd == "/watchlist":
        await _cmd_watchlist(chat_id)
    elif raw_cmd == "/add":
        await _cmd_add(chat_id, args)
    elif raw_cmd == "/remove_ticker":
        await _cmd_remove_ticker(chat_id, args)
    elif raw_cmd == "/pause":
        await _cmd_pause(chat_id, args)
    elif raw_cmd == "/resume":
        await _cmd_resume(chat_id)

    # Admin commands
    elif raw_cmd in ("/users", "/remove", "/promote", "/demote"):
        if not user.is_admin:
            await _reply(chat_id, "❌ Admin access required.")
            return
        if raw_cmd == "/users":
            await _cmd_users(chat_id)
        elif raw_cmd == "/remove":
            await _cmd_remove_user(chat_id, args)
        elif raw_cmd == "/promote":
            await _cmd_promote(chat_id, args)
        elif raw_cmd == "/demote":
            await _cmd_demote(chat_id, args)

    else:
        await _reply(chat_id, "Unknown command. Send /help to see available commands.")


# ── Long-poll loop ────────────────────────────────────────────────────────────


async def _poll_loop() -> None:
    global _running
    offset = 0
    logger.info("Telegram poll loop started")
    while _running:
        try:
            resp = await _api("getUpdates", offset=offset, timeout=25, allowed_updates=["message"])
            updates = resp.get("result", [])
            for update in updates:
                offset = update["update_id"] + 1
                try:
                    await _handle_update(update)
                except Exception as exc:
                    logger.warning("Telegram update handler error: %s", exc)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("Telegram poll error: %s — retrying in 5s", exc)
            await asyncio.sleep(5)
    logger.info("Telegram poll loop stopped")


def start_polling() -> None:
    global _running, _poll_task
    if not _enabled():
        logger.info("Telegram polling disabled (TELEGRAM_ENABLED=false)")
        return
    if not _token():
        logger.warning("Telegram polling skipped — TELEGRAM_BOT_TOKEN not set")
        return
    _running = True
    _poll_task = asyncio.create_task(_poll_loop())
    logger.info("Telegram polling started")


def stop_polling() -> None:
    global _running, _poll_task
    _running = False
    if _poll_task and not _poll_task.done():
        _poll_task.cancel()
    logger.info("Telegram polling stopped")
