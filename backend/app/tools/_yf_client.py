"""
Shared yfinance client with thread-safe rate limiting.

All tools call get_ticker() instead of yf.Ticker() directly so that
Yahoo Finance requests are throttled through one global gate.
YF_REQUESTS_PER_SECOND in .env controls the rate (default: 2).
"""
import time
import threading
import yfinance as yf

from app.config import get_settings

_lock = threading.Lock()
_last_call_time: float = 0.0


def _min_interval() -> float:
    settings = get_settings()
    rps = getattr(settings, "yf_requests_per_second", 2.0)
    return 1.0 / max(rps, 0.1)


def get_ticker(symbol: str) -> yf.Ticker:
    """Rate-limited drop-in replacement for yf.Ticker(symbol)."""
    global _last_call_time
    with _lock:
        now = time.monotonic()
        wait = _min_interval() - (now - _last_call_time)
        if wait > 0:
            time.sleep(wait)
        _last_call_time = time.monotonic()
    return yf.Ticker(symbol.upper())
