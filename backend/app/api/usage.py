from fastapi import APIRouter, Depends
from app.auth import verify_api_key
import json
import os
from datetime import date, timedelta

router = APIRouter(prefix="/usage", tags=["usage"])

_USAGE_FILE = os.environ.get("USAGE_FILE", "./data/usage.json")
_TOKEN_DAILY_LIMIT = int(os.environ.get("TOKEN_DAILY_LIMIT", 50_000))
_TOKEN_WEEKLY_LIMIT = int(os.environ.get("TOKEN_WEEKLY_LIMIT", 200_000))
_TOKEN_MONTHLY_LIMIT = int(os.environ.get("TOKEN_MONTHLY_LIMIT", 500_000))
_API_CALLS_DAILY_LIMIT = int(os.environ.get("API_CALLS_DAILY_LIMIT", 500))


def _load() -> dict:
    try:
        with open(_USAGE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"daily": {}, "weekly": {}, "monthly": {}, "all_time": {}}


@router.get("/today")
async def usage_today(_: str = Depends(verify_api_key)):
    data = _load()
    today_key = date.today().isoformat()
    today = data.get("daily", {}).get(today_key, {})

    tokens = today.get("tokens", 0)
    api_calls = today.get("api_calls", 0)
    pct = round(tokens / _TOKEN_DAILY_LIMIT * 100, 1) if _TOKEN_DAILY_LIMIT > 0 else 0.0
    api_pct = round(api_calls / _API_CALLS_DAILY_LIMIT * 100, 1) if _API_CALLS_DAILY_LIMIT > 0 else 0.0

    warning: str | None = None
    if pct >= 90:
        warning = f"Token usage at {pct:.1f}% of daily limit — approaching cap"
    elif api_pct >= 90:
        warning = f"API call usage at {api_pct:.1f}% of daily limit — approaching cap"
    elif pct >= 75 or api_pct >= 75:
        warning = f"Approaching daily limits (tokens {pct:.1f}%, api {api_pct:.1f}%)"

    return {
        "tokens_today": tokens,
        "tokens_today_pct": pct,
        "token_daily_limit": _TOKEN_DAILY_LIMIT,
        "api_calls_today": api_calls,
        "api_calls_today_pct": api_pct,
        "api_calls_daily_limit": _API_CALLS_DAILY_LIMIT,
        "tickers_today": today.get("tickers", []),
        "warning": warning,
    }


@router.get("/history")
async def usage_history(_: str = Depends(verify_api_key)):
    data = _load()
    daily_raw = data.get("daily", {})

    daily = []
    for i in range(29, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        entry = daily_raw.get(d, {})
        daily.append({
            "date": d,
            "tokens": entry.get("tokens", 0),
            "api_calls": entry.get("api_calls", 0),
        })

    return {
        "daily": daily,
        "limits": {
            "token_daily_limit": _TOKEN_DAILY_LIMIT,
            "token_weekly_limit": _TOKEN_WEEKLY_LIMIT,
            "token_monthly_limit": _TOKEN_MONTHLY_LIMIT,
            "api_calls_daily_limit": _API_CALLS_DAILY_LIMIT,
        },
    }
