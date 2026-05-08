"""
Dip-buy ETF scanner — zero LLM, pure computation.

Runs every 5 min via APScheduler during market hours (9:40 AM – 3:15 PM ET).
Also callable on-demand via POST /dip-scanner/scan.

Scoring uses intraday 5-min candle data already fetched by get_price():
  - Intraday VWAP (computed from candles)
  - Intraday RSI-14 (computed from candle closes)
  - Hammer candle detection
  - Proximity to S1/S2 pivot and VAL support levels
  - RVOL exhaustion signal (elevated then declining)
  - VIX-adjusted entry thresholds
  - Session window bonus/penalty
"""

import logging
import pytz
from datetime import datetime, timedelta, timezone

import yfinance as yf

logger = logging.getLogger(__name__)

ET_TZ = pytz.timezone("America/New_York")

# ── ETF universe ──────────────────────────────────────────────────────────────

ETF_TIERS: dict[int, list[str]] = {
    1: ["SPY", "QQQ", "IWM", "DIA"],
    2: ["XLK", "XLF", "XLV", "GLD"],
}

SESSION_WINDOWS = {
    "power_hour":    {"label": "Power Hour (2–3:15 PM)",    "score_delta": 10},
    "morning_flush": {"label": "Morning Flush (9:40–10:30 AM)", "score_delta": 5},
    "morning_trend": {"label": "Morning Trend (10:30 AM–12 PM)", "score_delta": 0},
    "lunch_drift":   {"label": "Lunch Drift (12–2 PM)",     "score_delta": -5},
    "pre_market":    {"label": "Pre-Market",                 "score_delta": None},
    "closed":        {"label": "Market Closed",              "score_delta": None},
}

SIGNAL_HINTS: dict[str, str] = {
    "Below VWAP":        "Price is below today's volume-weighted average — institutions typically buy back above this level",
    "Near S1":           "S1 is yesterday's support projected into today — price often bounces here because traders expect it to",
    "Near S2":           "S2 is a deeper support level — reaching here means a larger dip, but also a stronger potential bounce",
    "Near VAL":          "VAL is the bottom of yesterday's value area — 70% of volume traded above this level, making it a strong floor",
    "Near VWAP":         "Price is touching today's VWAP from below — this level acts as a magnet for mean reversion",
    "Hammer candle":     "Long lower wick = buyers pushed back hard after the dip — the market rejected lower prices in real time",
    "RVOL declining":    "Volume surged then pulled back — a classic sign the selling wave is ending",
    "RSI oversold":      "Short-term sellers may be exhausted — price often snaps back from these oversold levels",
    "VIX elevated":      "Elevated volatility means bigger swings both ways — entry criteria tightened, but the recovery bounce is larger",
    "ORB-15 breakout":   "Price broke above the first 15-min trading range — institutional momentum signal with volume confirmation",
    "VWAP reclaim":      "Price crossed back above today's volume-weighted average — institutions stepped in to buy the dip",
}


# ── Pure computation helpers ──────────────────────────────────────────────────

def _compute_intraday_vwap(candles: list[dict]) -> float:
    total_vol = sum(c.get("volume", 0) for c in candles)
    if total_vol == 0:
        return 0.0
    return sum(c.get("close", 0) * c.get("volume", 0) for c in candles) / total_vol


def _compute_rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d for d in deltas[-period:] if d > 0]
    losses = [-d for d in deltas[-period:] if d < 0]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def _detect_hammer(candle: dict) -> bool:
    high = candle.get("high", 0)
    low = candle.get("low", 0)
    close = candle.get("close", 0)
    candle_range = high - low
    if candle_range < 0.01:
        return False
    lower_wick = close - low
    upper_wick = high - close
    return (lower_wick / candle_range > 0.6) and (upper_wick < lower_wick * 0.4)


def _get_session_window(now_et: datetime) -> str:
    hm = now_et.hour * 60 + now_et.minute
    if hm < 9 * 60 + 40:
        return "pre_market"
    elif hm < 10 * 60 + 30:
        return "morning_flush"
    elif hm < 12 * 60:
        return "morning_trend"
    elif hm < 14 * 60:
        return "lunch_drift"
    elif hm <= 15 * 60 + 15:
        return "power_hour"
    return "closed"


def _vix_thresholds(vix: float) -> dict | None:
    """Returns adjusted entry thresholds per VIX level. None = skip (extreme crash)."""
    if vix < 18:
        return {"min_dip_pct": 0.3, "max_rsi": 42, "min_rvol": 0.8}
    elif vix <= 25:
        return {"min_dip_pct": 0.6, "max_rsi": 38, "min_rvol": 1.2}
    elif vix <= 35:
        return {"min_dip_pct": 1.0, "max_rsi": 33, "min_rvol": 1.5}
    return None


def _score_etf(ticker: str, price_data: dict, vix: float, now_et: datetime) -> dict | None:
    """Score one ETF for dip-buy. Returns opportunity dict or None if conditions not met."""
    candles = price_data.get("intraday_history", [])
    if len(candles) < 15:
        return None

    current_price = price_data.get("current_price", 0)
    day_open = price_data.get("day_open", current_price)
    if not current_price or not day_open:
        return None

    window = _get_session_window(now_et)
    window_cfg = SESSION_WINDOWS.get(window, {})
    score_delta = window_cfg.get("score_delta")
    if score_delta is None:
        return None  # outside trading hours

    thresholds = _vix_thresholds(vix)
    if thresholds is None:
        return None  # extreme crash day

    dip_pct = (day_open - current_price) / day_open * 100
    if dip_pct < thresholds["min_dip_pct"]:
        return None

    intraday_vwap = _compute_intraday_vwap(candles)
    closes = [c["close"] for c in candles if c.get("close")]
    rsi_5m = _compute_rsi(closes)
    if rsi_5m > thresholds["max_rsi"]:
        return None

    rvol_data = price_data.get("rvol", {})
    rvol_value = rvol_data.get("value", 1.0) if isinstance(rvol_data, dict) else 1.0
    if rvol_value < thresholds["min_rvol"]:
        return None

    # Require RVOL to be declining — sellers exhausting, not still in panic mode
    recent_vols = [c.get("volume", 0) for c in candles[-6:]]
    rvol_declining = len(recent_vols) >= 4 and recent_vols[-1] < recent_vols[-4]
    if not rvol_declining:
        return None

    # ── Scoring ────────────────────────────────────────────────────────────────
    score = 50
    signals: list[str] = []

    pivots = price_data.get("pivots") or {}
    vp = price_data.get("volume_profile") or {}
    s1 = pivots.get("S1", 0) or 0
    s2 = pivots.get("S2", 0) or 0
    val = vp.get("val", 0) or 0

    support_map = {
        "S1": s1, "S2": s2, "VAL": val,
        "VWAP": intraday_vwap if intraday_vwap > 0 else 0,
    }
    valid_supports = {k: v for k, v in support_map.items() if v > 0}

    if valid_supports:
        nearest_label = min(valid_supports, key=lambda k: abs(current_price - valid_supports[k]))
        nearest_val = valid_supports[nearest_label]
        dist_pct = abs(current_price - nearest_val) / nearest_val * 100
        if dist_pct <= 0.2:
            score += 15
            signals.append(f"Near {nearest_label} ({nearest_val:.2f})")
        elif dist_pct <= 0.4:
            score += 10
            signals.append(f"Near {nearest_label} ({nearest_val:.2f})")
        elif dist_pct <= 0.7:
            score += 5
        else:
            score -= 5

    # RSI
    if rsi_5m < 30:
        score += 15
        signals.append(f"RSI {rsi_5m} (very oversold)")
    elif rsi_5m < 35:
        score += 12
        signals.append(f"RSI {rsi_5m}")
    elif rsi_5m < thresholds["max_rsi"]:
        score += 8
        signals.append(f"RSI {rsi_5m}")

    # RVOL exhaustion
    if rvol_value >= 1.5:
        score += 10
        signals.append(f"RVOL {rvol_value:.1f}x declining")
    elif rvol_value >= 1.0:
        score += 6
        signals.append(f"RVOL {rvol_value:.1f}x declining")

    # Price vs intraday VWAP
    if intraday_vwap > 0:
        if current_price < intraday_vwap:
            score += 10
            if not any("VWAP" in s for s in signals):
                signals.append("Below VWAP")
        elif current_price > intraday_vwap * 1.005:
            score -= 5

    # Hammer candle on last bar
    if candles and _detect_hammer(candles[-1]):
        score += 15
        signals.append("Hammer candle")

    # VIX context
    if 20 <= vix <= 35:
        score += 10
        signals.append(f"VIX {vix:.1f} elevated")
    elif vix < 14:
        score += 2

    score += score_delta  # session window bonus/penalty
    score = min(score, 100)

    if score < 65:
        return None

    return {
        "ticker": ticker,
        "signal_type": "dip_buy",
        "score": score,
        "entry_price": current_price,
        "target_price": round(current_price * 1.01, 2),
        "stop_price": round(current_price * 0.995, 2),
        "signals": signals,
        "signal_hints": {s.split(" (")[0].split(f"RSI")[0].strip() if "RSI" in s else s.split(" (")[0]: SIGNAL_HINTS.get(s.split(" (")[0], "") for s in signals},
        "session_window": window,
        "session_window_label": window_cfg.get("label", window),
        "intraday_vwap": round(intraday_vwap, 2),
        "rsi_5m": rsi_5m,
        "rvol": round(rvol_value, 2),
        "vix": vix,
        "dip_pct": round(dip_pct, 2),
    }


def _add_pnl(opp: dict, capital: float) -> dict:
    entry = opp["entry_price"]
    target = opp["target_price"]
    stop = opp["stop_price"]
    shares = capital / entry if entry > 0 else 0
    profit = (target - entry) * shares
    risk = (entry - stop) * shares
    rr = profit / risk if risk > 0 else 0
    return {
        **opp,
        "shares": round(shares, 4),
        "expected_profit_dollar": round(profit, 2),
        "max_risk_dollar": round(risk, 2),
        "risk_reward_ratio": round(rr, 2),
        "capital_used": capital,
    }


# ── Additional signal detectors ───────────────────────────────────────────────

def _detect_orb_breakout(ticker: str, price_data: dict, vix: float, now_et: datetime) -> dict | None:
    """ORB-15 breakout: price broke above opening range high with volume confirmation."""
    window = _get_session_window(now_et)
    # ORB breakout only valid after the range is set — not during morning_flush itself
    if window not in ("morning_trend", "lunch_drift", "power_hour"):
        return None

    orb = price_data.get("orb") or {}
    orb_15 = orb.get("orb_15") or {}
    if not orb_15:
        return None

    if orb_15.get("position") != "above" or orb_15.get("breakout") != "above":
        return None

    orb_high = orb_15.get("high", 0) or 0
    orb_low = orb_15.get("low", 0) or 0
    current_price = price_data.get("current_price", 0)
    if not all([orb_high, orb_low, current_price]):
        return None

    orb_range = orb_high - orb_low
    if orb_range <= 0:
        return None

    rvol_data = price_data.get("rvol") or {}
    rvol_value = rvol_data.get("value", 1.0) if isinstance(rvol_data, dict) else 1.0
    if rvol_value < 1.5:
        return None

    score = 72
    signals = [f"ORB-15 breakout above {orb_high:.2f}", f"RVOL {rvol_value:.1f}x"]
    if rvol_value >= 2.0:
        score += 8
        signals.append("Strong volume confirmation")
    if 14 <= vix <= 25:
        score += 5  # calm-moderate VIX is ideal for trend following
    if window == "power_hour":
        score += 8

    window_cfg = SESSION_WINDOWS.get(window, {})
    target = round(orb_high + orb_range * 1.5, 2)
    stop = round(orb_low * 0.999, 2)

    return {
        "ticker": ticker,
        "signal_type": "orb_breakout",
        "score": min(score, 100),
        "entry_price": current_price,
        "target_price": target,
        "stop_price": stop,
        "signals": signals,
        "signal_hints": {
            f"ORB-15 breakout above {orb_high:.2f}": SIGNAL_HINTS.get("ORB-15 breakout", "Price broke above the first 15-min trading range — institutional momentum signal"),
            f"RVOL {rvol_value:.1f}x": SIGNAL_HINTS.get("RVOL declining", "Elevated volume confirms real buying, not a false breakout"),
        },
        "session_window": window,
        "session_window_label": window_cfg.get("label", window),
        "intraday_vwap": _compute_intraday_vwap(price_data.get("intraday_history", [])),
        "rsi_5m": _compute_rsi([c["close"] for c in price_data.get("intraday_history", []) if c.get("close")]),
        "rvol": round(rvol_value, 2),
        "vix": vix,
        "dip_pct": 0.0,
        "orb_range": round(orb_range, 2),
    }


def _detect_vwap_reclaim(ticker: str, price_data: dict, vix: float, now_et: datetime) -> dict | None:
    """VWAP reclaim: price was below VWAP for 2+ candles, last candle closed back above."""
    window = _get_session_window(now_et)
    window_cfg = SESSION_WINDOWS.get(window, {})
    if window_cfg.get("score_delta") is None:
        return None

    candles = price_data.get("intraday_history", [])
    if len(candles) < 6:
        return None

    intraday_vwap = _compute_intraday_vwap(candles)
    if not intraday_vwap:
        return None

    current_price = price_data.get("current_price", 0)
    if not current_price or current_price <= intraday_vwap:
        return None  # not above VWAP

    # Last 3 candles before current must have been below VWAP
    prev_closes = [c["close"] for c in candles[-4:-1] if c.get("close")]
    if len(prev_closes) < 2 or not all(c < intraday_vwap for c in prev_closes[-2:]):
        return None

    # RVOL on reclaim candle vs session average
    avg_vol = sum(c.get("volume", 0) for c in candles) / len(candles) if candles else 1
    reclaim_vol = candles[-1].get("volume", 0)
    rvol_reclaim = reclaim_vol / avg_vol if avg_vol > 0 else 1.0
    if rvol_reclaim < 1.2:
        return None

    score = 68
    signals = [f"VWAP reclaim ({intraday_vwap:.2f})", f"Reclaim RVOL {rvol_reclaim:.1f}x"]
    if rvol_reclaim >= 1.8:
        score += 10
        signals.append("Strong reclaim volume")
    if window == "power_hour":
        score += 8

    rsi_5m = _compute_rsi([c["close"] for c in candles if c.get("close")])
    if rsi_5m < 50:
        score += 5  # still recovering, more upside

    dip_pct = 0.0
    day_open = price_data.get("day_open", current_price)
    if day_open:
        dip_pct = round((day_open - current_price) / day_open * 100, 2)

    return {
        "ticker": ticker,
        "signal_type": "vwap_reclaim",
        "score": min(score, 100),
        "entry_price": current_price,
        "target_price": round(current_price * 1.008, 2),   # 0.8% target — tighter than dip buy
        "stop_price": round(intraday_vwap * 0.998, 2),      # just below VWAP
        "signals": signals,
        "signal_hints": {
            f"VWAP reclaim ({intraday_vwap:.2f})": SIGNAL_HINTS.get("Near VWAP", "Price crossed back above today's average — institutions are buying"),
            f"Reclaim RVOL {rvol_reclaim:.1f}x": "Volume surge on the reclaim bar confirms real buying pressure, not a dead-cat bounce",
        },
        "session_window": window,
        "session_window_label": window_cfg.get("label", window),
        "intraday_vwap": round(intraday_vwap, 2),
        "rsi_5m": rsi_5m,
        "rvol": round(rvol_reclaim, 2),
        "vix": vix,
        "dip_pct": dip_pct,
    }


def check_vix_spike() -> dict | None:
    """Check if VIX is spiking intraday — prep alert. Fires before a dip-buy entry appears."""
    try:
        vix_hist = yf.Ticker("^VIX").history(period="1d", interval="5m", prepost=False)
        spy_hist = yf.Ticker("SPY").history(period="1d", interval="5m", prepost=False)
        if vix_hist.empty or len(vix_hist) < 3:
            return None

        vix_open = float(vix_hist.iloc[0]["Close"])
        vix_current = float(vix_hist.iloc[-1]["Close"])
        vix_spike_pct = (vix_current - vix_open) / vix_open * 100

        spy_change_pct = 0.0
        if not spy_hist.empty and len(spy_hist) > 1:
            spy_open = float(spy_hist.iloc[0]["Open"])
            spy_current = float(spy_hist.iloc[-1]["Close"])
            spy_change_pct = (spy_current - spy_open) / spy_open * 100 if spy_open else 0

        if vix_spike_pct >= 8 and -2.0 <= spy_change_pct <= -0.4:
            return {
                "type": "vix_spike_prep",
                "vix_open": round(vix_open, 2),
                "vix_current": round(vix_current, 2),
                "vix_spike_pct": round(vix_spike_pct, 1),
                "spy_change_pct": round(spy_change_pct, 2),
            }
    except Exception as exc:
        logger.debug("check_vix_spike error: %s", exc)
    return None


def _get_no_signal_reason(price_data: dict, vix: float, now_et: datetime) -> str:
    """Diagnose why no dip-buy signal fired for a ticker."""
    window = _get_session_window(now_et)
    if SESSION_WINDOWS.get(window, {}).get("score_delta") is None:
        return "outside_hours"
    if vix > 35:
        return "vix_extreme"

    thresholds = _vix_thresholds(vix)
    if thresholds is None:
        return "vix_extreme"

    current_price = price_data.get("current_price", 0)
    day_open = price_data.get("day_open", current_price)
    if day_open and current_price:
        dip_pct = (day_open - current_price) / day_open * 100
        if dip_pct < thresholds["min_dip_pct"]:
            return "insufficient_dip"

    candles = price_data.get("intraday_history", [])
    closes = [c["close"] for c in candles if c.get("close")]
    if closes:
        rsi = _compute_rsi(closes)
        if rsi > thresholds["max_rsi"]:
            return "rsi_not_oversold"

    recent_vols = [c.get("volume", 0) for c in candles[-6:]]
    if len(recent_vols) >= 4 and recent_vols[-1] >= recent_vols[-4]:
        return "still_falling"

    if window == "lunch_drift":
        return "lunch_drift"

    return "score_too_low"


def _determine_scenario_key(
    dip_opps: list,
    orb_opps: list,
    vwap_opps: list,
    vix_spike: dict | None,
    session_window: str,
    vix: float,
    no_signal_reasons: list[str],
) -> str:
    """Map current scan conditions to a scenario key for the JSON text library."""
    from collections import Counter

    if session_window == "pre_market":
        return "prep_orb_forming"
    if session_window == "closed":
        return "market_closed"
    if vix > 35:
        return "no_buy_vix_extreme"
    if vix_spike:
        return "prep_vix_spike"

    all_opps = orb_opps + vwap_opps + dip_opps
    if all_opps:
        best = max(all_opps, key=lambda x: x["score"])
        stype = best.get("signal_type", "dip_buy")
        if stype == "orb_breakout":
            return "buy_orb_breakout"
        elif stype == "vwap_reclaim":
            return "buy_vwap_reclaim"
        else:
            return "buy_dip_at_support"

    if session_window == "power_hour":
        return "prep_power_hour"

    if no_signal_reasons:
        most_common = Counter(no_signal_reasons).most_common(1)[0][0]
        key_map = {
            "outside_hours": "no_buy_outside_hours",
            "vix_extreme":   "no_buy_vix_extreme",
            "still_falling": "no_buy_still_falling",
            "insufficient_dip": "no_buy_insufficient_dip",
            "rsi_not_oversold": "no_buy_rsi_not_oversold",
            "lunch_drift":   "no_buy_lunch_drift",
            "score_too_low": "no_buy_score_too_low",
        }
        return key_map.get(most_common, "no_buy_score_too_low")

    return "waiting"


# ── Public scanner function ───────────────────────────────────────────────────

def scan_dip_opportunities(
    tickers: list[str],
    capital: float = 1000.0,
    vix: float | None = None,
) -> dict:
    """Scan ETFs for dip-buy, ORB breakout, and VWAP reclaim opportunities. Zero LLM."""
    from app.tools.price import get_price

    now_et = datetime.now(ET_TZ)

    if vix is None:
        try:
            vix_info = yf.Ticker("^VIX").fast_info
            vix = float(vix_info.get("lastPrice", 18.0) or 18.0)
        except Exception:
            vix = 18.0

    dip_opportunities: list[dict] = []
    orb_opportunities: list[dict] = []
    vwap_opportunities: list[dict] = []
    no_signal_reasons: list[str] = []
    price_cache: dict[str, dict] = {}

    for ticker in tickers:
        try:
            result = get_price.invoke({"ticker": ticker})
            if not isinstance(result, dict) or "error" in result:
                continue
            price_cache[ticker] = result

            dip = _score_etf(ticker, result, vix, now_et)
            if dip:
                dip_opportunities.append(_add_pnl(dip, capital))
            else:
                no_signal_reasons.append(_get_no_signal_reason(result, vix, now_et))

            orb = _detect_orb_breakout(ticker, result, vix, now_et)
            if orb:
                orb_opportunities.append(_add_pnl(orb, capital))

            vwap = _detect_vwap_reclaim(ticker, result, vix, now_et)
            if vwap:
                vwap_opportunities.append(_add_pnl(vwap, capital))

        except Exception as exc:
            logger.warning("dip_scanner: error scanning %s — %s", ticker, exc)

    for lst in (dip_opportunities, orb_opportunities, vwap_opportunities):
        lst.sort(key=lambda x: x["score"], reverse=True)

    vix_spike = check_vix_spike()
    session_window = _get_session_window(now_et)

    all_opps = dip_opportunities + orb_opportunities + vwap_opportunities
    best = max(all_opps, key=lambda x: x["score"]) if all_opps else None

    scenario_key = _determine_scenario_key(
        dip_opportunities, orb_opportunities, vwap_opportunities,
        vix_spike, session_window, vix, no_signal_reasons,
    )

    return {
        "opportunities": dip_opportunities,
        "orb_opportunities": orb_opportunities,
        "vwap_opportunities": vwap_opportunities,
        "best": best,
        "vix_spike_prep": vix_spike,
        "scenario_key": scenario_key,
        "tickers_scanned": len(tickers),
        "session_window": session_window,
        "vix": round(vix, 2),
        "timestamp": now_et.isoformat(),
        "capital": capital,
    }


# ── Historical backfill ───────────────────────────────────────────────────────

def _backfill_ticker(ticker: str, days: int = 60) -> list[dict]:
    """
    Replay scanner logic over `days` of 5-min history for one ticker.
    Returns list of would-have alert dicts with outcomes already resolved.
    """
    try:
        stock = yf.Ticker(ticker)
        intraday = stock.history(period=f"{days}d", interval="5m", prepost=False)
        daily = stock.history(period=f"{days + 5}d", interval="1d")
        vix_hist = yf.Ticker("^VIX").history(period=f"{days + 5}d", interval="1d")
    except Exception as exc:
        logger.warning("backfill fetch failed for %s: %s", ticker, exc)
        return []

    if intraday.empty or daily.empty:
        return []

    intraday.index = intraday.index.tz_convert(ET_TZ)
    daily.index = daily.index.tz_localize("UTC") if daily.index.tzinfo is None else daily.index.tz_convert("UTC")

    alerts = []

    # Group 5-min bars by trading date
    trading_dates = sorted(set(intraday.index.date))

    for trade_date in trading_dates:
        day_bars = intraday[intraday.index.date == trade_date]
        if len(day_bars) < 20:
            continue

        # Previous day's daily bar for pivot calculation
        prev_days = daily[daily.index.date < trade_date]
        if prev_days.empty:
            continue
        prev_day = prev_days.iloc[-1]
        prev_high = float(prev_day["High"])
        prev_low = float(prev_day["Low"])
        prev_close = float(prev_day["Close"])
        pivot_p = (prev_high + prev_low + prev_close) / 3
        s1 = 2 * pivot_p - prev_high
        s2 = pivot_p - (prev_high - prev_low)

        # VIX for that day
        vix_days = vix_hist[vix_hist.index.date <= trade_date]
        day_vix = float(vix_days.iloc[-1]["Close"]) if not vix_days.empty else 18.0

        thresholds = _vix_thresholds(day_vix)
        if thresholds is None:
            continue

        day_open = float(day_bars.iloc[0]["Open"])
        fired_this_day = False  # one alert per day per ticker

        for i in range(15, len(day_bars)):
            if fired_this_day:
                break

            bar_time = day_bars.index[i]
            now_et = bar_time
            window = _get_session_window(now_et)
            if SESSION_WINDOWS.get(window, {}).get("score_delta") is None:
                continue

            candles_so_far = [
                {"close": float(r["Close"]), "high": float(r["High"]),
                 "low": float(r["Low"]), "volume": int(r["Volume"])}
                for _, r in day_bars.iloc[:i + 1].iterrows()
            ]
            current_price = candles_so_far[-1]["close"]

            dip_pct = (day_open - current_price) / day_open * 100
            if dip_pct < thresholds["min_dip_pct"]:
                continue

            intraday_vwap = _compute_intraday_vwap(candles_so_far)
            closes = [c["close"] for c in candles_so_far]
            rsi_5m = _compute_rsi(closes)
            if rsi_5m > thresholds["max_rsi"]:
                continue

            recent_vols = [c["volume"] for c in candles_so_far[-6:]]
            if len(recent_vols) < 4 or recent_vols[-1] >= recent_vols[-4]:
                continue  # still falling

            # Build mock price_data for scorer
            mock_price_data = {
                "current_price": current_price,
                "day_open": day_open,
                "intraday_history": candles_so_far,
                "pivots": {"S1": s1, "S2": s2},
                "volume_profile": {},
                "rvol": {"value": candles_so_far[-1]["volume"] / max(1, sum(c["volume"] for c in candles_so_far) / len(candles_so_far))},
            }

            opp = _score_etf(ticker, mock_price_data, day_vix, now_et)
            if not opp:
                continue

            # Resolve outcome using remaining bars of the same day
            entry = current_price
            target = round(entry * 1.01, 2)
            stop = round(entry * 0.995, 2)
            status = "expired"
            outcome_price = entry
            resolved_by = "eod_close"

            future_bars = day_bars.iloc[i + 1:]
            for _, fbar in future_bars.iterrows():
                fhigh = float(fbar["High"])
                flow = float(fbar["Low"])
                fclose = float(fbar["Close"])
                if fhigh >= target:
                    status = "win"
                    outcome_price = target
                    resolved_by = "target_hit"
                    break
                if flow <= stop:
                    status = "loss"
                    outcome_price = stop
                    resolved_by = "stop_hit"
                    break
                outcome_price = fclose  # track EOD

            if status == "expired":
                status = "win" if outcome_price > entry else "loss"
                resolved_by = "eod_close"

            pnl_pct = (outcome_price - entry) / entry * 100
            pnl_dollar = pnl_pct / 100 * 1000.0  # backtest uses $1k default

            alerts.append({
                "ticker": ticker,
                "entry_price": entry,
                "target_price": target,
                "stop_price": stop,
                "entry_time": bar_time.isoformat(),
                "score": opp["score"],
                "signals": opp["signals"],
                "session_window": opp["session_window"],
                "vix_at_entry": day_vix,
                "capital_used": 1000.0,
                "source": "backtest",
                "status": status,
                "outcome_price": round(outcome_price, 2),
                "actual_pnl_pct": round(pnl_pct, 3),
                "actual_pnl_dollar": round(pnl_dollar, 2),
                "resolved_by": resolved_by,
            })

            fired_this_day = True  # one alert per day per ticker

    return alerts
