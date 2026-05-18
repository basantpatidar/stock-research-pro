"""
FRED Macro Dashboard — Sprint 3.

Fetches institutional-grade credit and rates data from the St. Louis Fed FRED API.
Free API key: https://fred.stlouisfed.org/docs/api/api_key.html

Metrics:
  HY Credit Spread  BAMLH0A0HYM2  — bond market's equity fear gauge
  IG Credit Spread  BAMLC0A0CM    — corporate credit health baseline
  10Y Real Yield    DFII10        — most important rate for growth stocks
  10Y Breakeven     T10YIE        — market-implied inflation expectations
  2s10s Curve       T10Y2Y        — every US recession preceded by inversion
  3m10y Curve       T10Y3M        — NY Fed preferred recession predictor
  M2 YoY            M2SL          — global liquidity proxy (6–12 month lead)
  SOFR              SOFR          — interbank stress indicator

Cross-asset (yfinance — no key required):
  Copper/Gold ratio  HG=F / GC=F  — risk-on vs risk-off
  Dollar Index       DX-Y.NYB     — headwind/tailwind for multinationals
"""

from __future__ import annotations

import requests
from langchain_core.tools import tool

from app.config import get_settings
from app.tools._yf_client import get_ticker

_FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
_TIMEOUT = 8  # seconds per request


# ── FRED fetch helpers ────────────────────────────────────────────────────────


def _fetch_series(series_id: str, api_key: str, limit: int = 40) -> list[dict]:
    try:
        r = requests.get(
            _FRED_BASE,
            params={
                "series_id": series_id,
                "api_key": api_key,
                "sort_order": "desc",
                "limit": limit,
                "file_type": "json",
            },
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return [o for o in r.json().get("observations", []) if o.get("value", ".") != "."]
    except Exception:
        return []


def _latest_and_change(obs: list[dict], days_back: int = 7) -> tuple[float | None, float | None]:
    """Return (current_value, absolute_7d_change) from descending observations."""
    if not obs:
        return None, None
    try:
        cur = float(obs[0]["value"])
    except (ValueError, KeyError):
        return None, None
    past_idx = min(days_back, len(obs) - 1)
    try:
        prev = float(obs[past_idx]["value"])
        return cur, round(cur - prev, 4)
    except (ValueError, KeyError):
        return cur, None


# ── Verdict functions ─────────────────────────────────────────────────────────


def _v_hy(v: float) -> tuple[str, str, str]:
    """HY OAS in %. Lower = calmer = bullish equities."""
    if v < 3.5:
        return "BUY", "#22cc66", "Credit markets calm — green light for equities"
    if v < 5.5:
        return "HOLD", "#ffaa00", "HY spreads widening — credit markets cautious"
    if v < 8.0:
        return "SELL", "#ff6644", "HY spreads elevated — bond market pricing significant stress"
    return "AVOID", "#ff2222", "HY spreads at crisis levels — credit market distress"


def _v_ig(v: float) -> tuple[str, str, str]:
    """IG OAS in %. < 1% = calm, > 1.5% = stress."""
    if v < 1.0:
        return "BUY", "#22cc66", "Investment-grade credit calm — healthy corporate sector"
    if v < 1.5:
        return "HOLD", "#ffaa00", "IG spreads moderately elevated — some corporate credit stress"
    return "SELL", "#ff6644", "IG spreads elevated — corporate credit stress spreading"


def _v_real_yield(v: float) -> tuple[str, str, str]:
    """10Y real yield %. Higher = tighter conditions = growth headwind."""
    if v < 1.0:
        return "BUY", "#22cc66", "Real yields low — loose conditions support growth valuations"
    if v < 2.0:
        return "HOLD", "#ffaa00", "Real yields moderate — neutral for equities"
    if v < 2.5:
        return "SELL", "#ff6644", "Real yields elevated — compresses growth stock multiples"
    return "AVOID", "#ff2222", "Real yields historically high — severe headwind for growth stocks"


def _v_breakeven(v: float) -> tuple[str, str, str]:
    """10Y breakeven inflation %. Market's 10-year inflation expectation."""
    if v < 2.0:
        return (
            "BUY",
            "#22cc66",
            "Inflation expectations anchored below 2% — no forced Fed tightening",
        )
    if v < 2.5:
        return "HOLD", "#ffaa00", "Inflation expectations near Fed target — neutral"
    if v < 3.0:
        return "SELL", "#ff6644", "Inflation expectations rising — risk of additional tightening"
    return (
        "AVOID",
        "#ff2222",
        "Inflation de-anchored — historically bearish for bonds and growth stocks",
    )


def _v_curve(v: float, label: str) -> tuple[str, str, str]:
    """Yield curve %. Positive = normal. Negative = inverted = recession signal."""
    if v > 0.5:
        return "BUY", "#22cc66", f"{label} positive — normal curve, no near-term recession signal"
    if v > 0.0:
        return "HOLD", "#ffaa00", f"{label} flat — normalising, watch for re-inversion"
    if v > -0.5:
        return "SELL", "#ff6644", f"{label} mildly inverted — historical recession precursor"
    return (
        "AVOID",
        "#ff2222",
        f"{label} deeply inverted — strong recession signal (12–18 month lead)",
    )


def _v_sofr(v: float) -> tuple[str, str, str]:
    """SOFR rate %. Higher = tighter interbank liquidity."""
    if v < 3.0:
        return "BUY", "#22cc66", "SOFR low — ample interbank liquidity, easy financial conditions"
    if v < 5.0:
        return "HOLD", "#ffaa00", "SOFR moderate — neutral financial conditions"
    return "SELL", "#ff6644", "SOFR elevated — tight interbank liquidity, high financing costs"


def _m2_analysis(obs: list[dict]) -> dict:
    """M2 is monthly; compute YoY % change from last 13 observations."""
    base = {
        "label": "M2 Money Supply (YoY)",
        "series_id": "M2SL",
        "unit": "% YoY",
        "change_7d": None,
        "date": obs[0]["date"] if obs else None,
    }
    if len(obs) < 13:
        return {
            **base,
            "current": None,
            "verdict": "HOLD",
            "color": "#ffaa00",
            "signal": "M2 data insufficient",
        }
    try:
        cur = float(obs[0]["value"])
        yr_ago = float(obs[12]["value"])
        yoy = round((cur - yr_ago) / yr_ago * 100, 2)
        if yoy > 5:
            v, c, s = (
                "BUY",
                "#22cc66",
                f"M2 expanding +{yoy:.1f}% YoY — liquidity tailwind for equities (6–12 month lead)",
            )
        elif yoy > 0:
            v, c, s = "HOLD", "#ffaa00", f"M2 growing +{yoy:.1f}% YoY — mild liquidity expansion"
        elif yoy > -5:
            v, c, s = (
                "SELL",
                "#ff6644",
                f"M2 contracting {yoy:.1f}% YoY — liquidity headwind for risk assets",
            )
        else:
            v, c, s = (
                "AVOID",
                "#ff2222",
                f"M2 sharply contracting {yoy:.1f}% YoY — historically precedes equity stress",
            )
        return {**base, "current": yoy, "verdict": v, "color": c, "signal": s}
    except Exception:
        return {
            **base,
            "current": None,
            "verdict": "HOLD",
            "color": "#ffaa00",
            "signal": "M2 data unavailable",
        }


# ── Cross-asset signals (yfinance) ────────────────────────────────────────────


def _cross_asset() -> dict:
    result: dict = {}

    try:
        cu_hist = get_ticker("HG=F").history(period="1mo")
        au_hist = get_ticker("GC=F").history(period="1mo")
        if not cu_hist.empty and not au_hist.empty:
            cu = float(cu_hist["Close"].iloc[-1])
            au = float(au_hist["Close"].iloc[-1])
            cu0 = float(cu_hist["Close"].iloc[-6]) if len(cu_hist) >= 7 else cu
            au0 = float(au_hist["Close"].iloc[-6]) if len(au_hist) >= 7 else au
            ratio = round(cu / au * 1000, 4)
            ratio_prev = round(cu0 / au0 * 1000, 4)
            chg = round(ratio - ratio_prev, 4)
            if chg > 0:
                v, c, s = (
                    "BUY",
                    "#22cc66",
                    "Copper/Gold rising — risk-on. Industrial demand outpacing safe-haven demand.",
                )
            else:
                v, c, s = (
                    "SELL",
                    "#ff6644",
                    "Copper/Gold falling — risk-off. Investors rotating into gold.",
                )
            result["copper_gold_ratio"] = {
                "label": "Copper/Gold Ratio",
                "current": ratio,
                "change_7d": chg,
                "unit": "×1000",
                "verdict": v,
                "color": c,
                "signal": s,
            }
    except Exception:
        pass

    try:
        dxy_hist = get_ticker("DX-Y.NYB").history(period="1mo")
        if not dxy_hist.empty:
            cur = round(float(dxy_hist["Close"].iloc[-1]), 2)
            prev = round(float(dxy_hist["Close"].iloc[-6]), 2) if len(dxy_hist) >= 7 else cur
            chg = round(cur - prev, 2)
            if chg < -0.5:
                v, c, s = (
                    "BUY",
                    "#22cc66",
                    "Dollar weakening — tailwind for multinationals, commodities, and EM assets",
                )
            elif chg > 0.5:
                v, c, s = (
                    "SELL",
                    "#ff6644",
                    "Dollar strengthening — headwind for multinationals, commodities, and emerging markets",
                )
            else:
                v, c, s = "HOLD", "#ffaa00", "Dollar range-bound — neutral cross-asset impact"
            result["dxy"] = {
                "label": "US Dollar Index (DXY)",
                "current": cur,
                "change_7d": chg,
                "unit": "index",
                "verdict": v,
                "color": c,
                "signal": s,
            }
    except Exception:
        pass

    return result


# ── Main tool ─────────────────────────────────────────────────────────────────


@tool
def get_fred_macro() -> dict:
    """
    Fetch institutional-grade credit, rates, liquidity, and cross-asset data.
    Sources: St. Louis Fed FRED API (free key required) + yfinance cross-asset.
    Returns HY/IG spreads, real yields, yield curves, M2, SOFR, Copper/Gold, DXY.
    """
    settings = get_settings()
    api_key = settings.fred_api_key

    if not api_key:
        return {
            "error": "FRED_API_KEY not configured",
            "setup_url": "https://fred.stlouisfed.org/docs/api/api_key.html",
        }

    def _ind(series_id: str, label: str, unit: str, verdict_fn, days_back: int = 7) -> dict:
        obs = _fetch_series(series_id, api_key, limit=40)
        cur, chg = _latest_and_change(obs, days_back)
        if cur is None:
            return {
                "error": "unavailable",
                "label": label,
                "series_id": series_id,
                "current": None,
                "change_7d": None,
                "unit": unit,
                "verdict": "HOLD",
                "color": "#666",
                "signal": "Data unavailable",
                "date": None,
            }
        v, c, s = verdict_fn(cur)
        return {
            "label": label,
            "series_id": series_id,
            "current": round(cur, 4),
            "change_7d": chg,
            "unit": unit,
            "verdict": v,
            "color": c,
            "signal": s,
            "date": obs[0]["date"] if obs else None,
        }

    hy = _ind("BAMLH0A0HYM2", "HY Credit Spread", "%", _v_hy)
    ig = _ind("BAMLC0A0CM", "IG Credit Spread", "%", _v_ig)
    ry = _ind("DFII10", "10Y Real Yield", "%", _v_real_yield)
    be = _ind("T10YIE", "10Y Breakeven Inflation", "%", _v_breakeven)
    c210 = _ind("T10Y2Y", "2s10s Yield Curve", "%", lambda v: _v_curve(v, "2s10s"))
    c310 = _ind("T10Y3M", "3m10y Yield Curve", "%", lambda v: _v_curve(v, "3m10y"))
    sofr = _ind("SOFR", "SOFR Rate", "%", _v_sofr)

    m2_obs = _fetch_series("M2SL", api_key, limit=14)
    m2 = _m2_analysis(m2_obs)

    cross = _cross_asset()

    # Composite
    all_v = [hy, ig, ry, be, c210, c310, sofr, m2]
    verdicts = [x.get("verdict") for x in all_v if x.get("verdict") not in (None, "HOLD")]
    bearish = sum(1 for v in verdicts if v in ("SELL", "AVOID"))
    bullish = sum(1 for v in verdicts if v in ("BUY", "STRONG_BUY"))
    total = len(all_v)

    if bearish / total > 0.5:
        composite = "SELL"
    elif bearish / total > 0.35:
        composite = "HOLD"
    elif bullish / total > 0.5:
        composite = "BUY"
    else:
        composite = "HOLD"

    return {
        "credit_spreads": {"hy_spread": hy, "ig_spread": ig},
        "rates": {
            "real_yield_10y": ry,
            "breakeven_10y": be,
            "yield_curve_2s10s": c210,
            "yield_curve_3m10y": c310,
            "sofr": sofr,
        },
        "liquidity": {"m2": m2},
        "cross_asset": cross,
        "composite_verdict": composite,
        "composite_summary": f"{bullish} bullish / {bearish} bearish of {total} indicators",
    }
