from datetime import date, timedelta

import httpx

from app.config import get_settings

# Curated high-impact FRED release IDs
_RELEASES = {
    326: {"name": "FOMC Meeting", "impact": "high"},
    10: {"name": "CPI", "impact": "high"},
    50: {"name": "Jobs Report (NFP)", "impact": "high"},
    53: {"name": "GDP", "impact": "high"},
    54: {"name": "PCE / Personal Income", "impact": "high"},
    46: {"name": "PPI", "impact": "medium"},
    82: {"name": "Retail Sales", "impact": "medium"},
    175: {"name": "Consumer Sentiment", "impact": "medium"},
    22: {"name": "Housing Starts", "impact": "medium"},
}


def get_economic_calendar(days_ahead: int = 14) -> dict:
    settings = get_settings()
    api_key = settings.fred_api_key

    if not api_key:
        return {"error": "FRED_API_KEY not configured", "events": []}

    today = date.today()
    end = today + timedelta(days=days_ahead)

    try:
        resp = httpx.get(
            "https://api.stlouisfed.org/fred/releases/dates",
            params={
                "realtime_start": today.isoformat(),
                "realtime_end": end.isoformat(),
                "sort_order": "asc",
                "include_release_dates_with_no_data": "false",
                "file_type": "json",
                "api_key": api_key,
            },
            timeout=10,
        )
        resp.raise_for_status()
        release_dates = resp.json().get("release_dates", [])

        seen: set = set()
        events = []
        for item in release_dates:
            rid = item.get("release_id")
            if rid not in _RELEASES:
                continue
            key = (item["date"], rid)
            if key in seen:
                continue
            seen.add(key)
            meta = _RELEASES[rid]
            events.append(
                {
                    "date": item["date"],
                    "name": meta["name"],
                    "impact": meta["impact"],
                    "days_until": (date.fromisoformat(item["date"]) - today).days,
                }
            )

        return {
            "events": events,
            "days_ahead": days_ahead,
            "as_of": today.isoformat(),
        }
    except Exception as e:
        return {"error": str(e), "events": []}
