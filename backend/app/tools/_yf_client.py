"""
Shared yfinance client with thread-safe rate limiting and crumb management.

Root cause of Yahoo Finance 429 errors in Docker:
  - yfinance 0.2.x uses Chrome 39 (2015) as its User-Agent — Yahoo blocks old agents
  - When the crumb endpoint returns a 429, yfinance stores "Edge: Too Many Requests"
    as the crumb (validation only checks for None / '<html>'), so every subsequent
    API call sends a poisoned crumb and fails with "Expecting value: line 1 column 1"

Fixes applied here:
  1. Patch YfData.user_agent_headers at class level → modern Chrome 124 UA
  2. _crumb_is_poisoned() detects bad crumbs before they reach API calls
  3. reset_yf_session() clears crumb+cookie on the singleton, forcing a fresh fetch
  4. get_ticker() checks crumb health on every call, auto-resets if poisoned
"""

import time
import threading
import logging

import yfinance as yf
from yfinance.data import YfData

from app.config import get_settings

logger = logging.getLogger(__name__)

# ── 1. Patch: replace stale Chrome-39 UA with modern Chrome-124 ───────────────
#    YfData.user_agent_headers is a class attribute (no instance shadowing),
#    so patching the class updates the singleton and all future instances.
YfData.user_agent_headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ── 2. Crumb health check ──────────────────────────────────────────────────────

def _crumb_is_poisoned(crumb: str | None) -> bool:
    """
    Real crumbs are short alphanumeric tokens (~11 chars, e.g. "AQ4mn7sFGHD").
    A poisoned crumb comes from a 429/error page body stored verbatim.
    """
    if not crumb:
        return False
    if len(crumb) > 50:
        return True
    lower = crumb.lower()
    return any(kw in lower for kw in ("too many", "edge", "429", "error", "html", "rate limit"))


# ── 3. Session/crumb reset ────────────────────────────────────────────────────

def _get_yf_singleton() -> YfData | None:
    """Access the YfData singleton without triggering _set_session()."""
    return YfData._instances.get(YfData)


def reset_yf_session() -> None:
    """
    Clear the YfData singleton's crumb + cookie cache so the next call
    triggers a fresh fetch. Thread-safe via the singleton's own lock.
    """
    instance = _get_yf_singleton()
    if instance is None:
        return
    with instance._cookie_lock:
        instance._crumb = None
        instance._cookie = None
        instance._cookie_strategy = "basic"
    logger.info("yfinance session reset — crumb/cookie cleared, will re-fetch")


# ── 4. Rate-limited get_ticker with crumb health guard ────────────────────────

_lock = threading.Lock()
_last_call_time: float = 0.0


def _min_interval() -> float:
    settings = get_settings()
    rps = getattr(settings, "yf_requests_per_second", 2.0)
    return 1.0 / max(rps, 0.1)


def get_ticker(symbol: str) -> yf.Ticker:
    """
    Rate-limited drop-in replacement for yf.Ticker(symbol).
    Automatically resets a poisoned crumb before returning the Ticker.
    """
    global _last_call_time

    # Rate limiting
    with _lock:
        now = time.monotonic()
        wait = _min_interval() - (now - _last_call_time)
        if wait > 0:
            time.sleep(wait)
        _last_call_time = time.monotonic()

    # Crumb health guard — check the singleton's cached crumb
    singleton = _get_yf_singleton()
    if singleton and _crumb_is_poisoned(singleton._crumb):
        logger.warning(
            "Poisoned crumb detected ('%s') — resetting yfinance session",
            singleton._crumb[:40],
        )
        reset_yf_session()

    return yf.Ticker(symbol.upper())
