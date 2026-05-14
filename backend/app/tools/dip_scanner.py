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

import json
import logging
import os
import pytz
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf
from app.tools.regime import classify_regime

logger = logging.getLogger(__name__)

# Near-miss log — signals that passed all pattern checks but scored 65-71 (just below threshold).
# Written to local_debugging/near_miss_log.jsonl for EOD analysis.
_NEAR_MISS_LOG = Path(
    os.getenv("NEAR_MISS_LOG", str(Path(__file__).resolve().parents[3] / "local_debugging" / "near_miss_log.jsonl"))
)

# In-memory dedup set — (date, ticker, window, time_et, score) → already-logged.
# Prevents the same intraday candle being logged twice when the scanner re-runs
# (e.g. backtest replay after a live run on the same day). Seeded from disk on
# first use so dedup survives process restarts within the same trading day.
_near_miss_seen: set[tuple[str, str, str, str, int]] | None = None


def _load_near_miss_seen() -> set[tuple[str, str, str, str, int]]:
    seen: set[tuple[str, str, str, str, int]] = set()
    if not _NEAR_MISS_LOG.exists():
        return seen
    try:
        for line in _NEAR_MISS_LOG.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
                seen.add((e["date"], e["ticker"], e["window"], e["time_et"], int(e["score"])))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
    except OSError:
        pass
    return seen


def _log_near_miss(
    ticker: str,
    score: int,
    signals: list,
    price: float,
    window: str,
    now_et: datetime | None = None,
) -> None:
    """Append one near-miss entry to the JSONL log. Silent on any failure.

    ``now_et`` is the bar timestamp of the signal — pass it from the caller so
    backtest entries record the actual intraday moment, not the wall-clock time
    the backtest ran. Falls back to ``datetime.now(ET)`` for live calls that
    don't thread the bar time through.
    """
    global _near_miss_seen
    try:
        ts = now_et or datetime.now(tz=pytz.timezone("America/New_York"))
        date_str = ts.date().isoformat()
        time_str = ts.strftime("%H:%M")
        key = (date_str, ticker, window, time_str, score)

        if _near_miss_seen is None:
            _near_miss_seen = _load_near_miss_seen()
        if key in _near_miss_seen:
            return
        _near_miss_seen.add(key)

        _NEAR_MISS_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "date":    date_str,
            "time_et": time_str,
            "ticker":  ticker,
            "score":   score,
            "window":  window,
            "price":   round(price, 2),
            "reasons": signals[:3],
        }
        with _NEAR_MISS_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # never let logging affect the scanner

ET_TZ = pytz.timezone("America/New_York")

# ── ETF universe ──────────────────────────────────────────────────────────────

ETF_TIERS: dict[int, list[str]] = {
    1: ["SPY", "QQQ"],
    2: ["XLK"],   # Data-driven cut: IWM 46.2%, DIA 54.5%, XLF 47.1%, XLV 36.6%, TLT 27.3% win rates — removed
}

SESSION_WINDOWS = {
    "power_hour":    {"label": "Power Hour (2–4 PM)",           "score_delta": 10},
    "morning_flush": {"label": "Morning Flush (9:40–10:30 AM)", "score_delta": 5},
    "morning_trend": {"label": "Morning Trend (10:30 AM–12 PM)","score_delta": 0},
    "lunch_drift":   {"label": "Lunch Drift (12–2 PM)",         "score_delta": -5},
    "pre_market":    {"label": "Pre-Market (4–9:30 AM)",        "score_delta": -10},
    "after_hours":   {"label": "After-Hours (4–8 PM)",          "score_delta": -10},
    "closed":        {"label": "Market Closed",                 "score_delta": None},
}

# ── Highest-EV cell whitelist ─────────────────────────────────────────────────
# Enable once n ≥ 5 resolved trades per cell. Based on current backtest:
# QQQ all sessions positive, SPY morning_trend positive, rest uncertain.
# Set ENABLE_WHITELIST = True to activate hard-blocking of low-EV cells.
ENABLE_WHITELIST = False
WHITELIST_CELLS: set[tuple[str, str]] = {
    ("QQQ", "morning_trend"),
    ("QQQ", "power_hour"),
    ("QQQ", "morning_flush"),
    ("SPY", "morning_trend"),
    ("SPY", "morning_flush"),
    ("IWM", "morning_trend"),
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


def _detect_hammer(candle: dict, prior_candles: list[dict] | None = None) -> bool:
    """Stricter hammer: lower wick >65%, closes in upper third, volume-confirmed."""
    high = candle.get("high", 0)
    low = candle.get("low", 0)
    close = candle.get("close", 0)
    candle_range = high - low
    if candle_range < 0.01:
        return False
    lower_wick = close - low
    upper_wick = high - close
    if not (lower_wick / candle_range > 0.65 and upper_wick < lower_wick * 0.4):
        return False
    if close < low + candle_range * 0.67:  # must close in upper third of range
        return False
    if prior_candles and len(prior_candles) >= 7:
        avg_vol = sum(c.get("volume", 0) for c in prior_candles[-7:-1]) / 6
        if avg_vol > 0 and candle.get("volume", 0) < avg_vol * 1.5:
            return False  # low-volume hammer = noise, not absorption
    return True


def _compute_cvd(candles: list[dict]) -> float:
    """Approximate Cumulative Volume Delta from OHLCV. Up-close bars add vol, down-close bars subtract."""
    cvd = 0.0
    for c in candles:
        o = c.get("open", 0) or c.get("close", 0)
        cl = c.get("close", 0)
        vol = c.get("volume", 0)
        if cl > o:
            cvd += vol
        elif cl < o:
            cvd -= vol
    return cvd


# ── Per-ETF ATR cache ─────────────────────────────────────────────────────────
# ATR normalises all thresholds so a "0.6% dip" means the same thing across DIA
# (low vol) and IWM (high vol). Cached 30 min — stale ATR is still useful.

_atr_cache: dict[str, dict] = {}
_ATR_REFRESH_SECONDS = 1800


def _get_atr_5m(ticker: str) -> float:
    """Wilder's ATR-14 on 5-min bars. Returns 0.0 on failure (caller uses price×0.002)."""
    global _atr_cache
    now = datetime.now()
    cached = _atr_cache.get(ticker)
    if cached and (now - cached["ts"]).total_seconds() < _ATR_REFRESH_SECONDS:
        return cached["atr"]
    try:
        hist = yf.Ticker(ticker).history(period="5d", interval="5m", prepost=False)
        if hist.empty or len(hist) < 15:
            return 0.0
        highs  = hist["High"].values
        lows   = hist["Low"].values
        closes = hist["Close"].values
        trs = [
            max(highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i]  - closes[i - 1]))
            for i in range(1, len(hist))
        ]
        if len(trs) < 14:
            return 0.0
        atr = sum(trs[:14]) / 14.0
        for tr in trs[14:]:
            atr = (atr * 13 + tr) / 14.0
        _atr_cache[ticker] = {"atr": round(atr, 4), "ts": now}
        return atr
    except Exception as exc:
        logger.warning("ATR computation failed for %s: %s", ticker, exc)
        return 0.0


def _compute_intraday_trend(candles: list[dict]) -> int:
    """Compare avg close of last 6 bars vs prior 6 bars. +5 recovering, -10 still falling, 0 flat."""
    if len(candles) < 12:
        return 0
    recent = [c.get("close", 0) for c in candles[-6:]]
    prior  = [c.get("close", 0) for c in candles[-12:-6]]
    if not all(recent) or not all(prior):
        return 0
    recent_avg = sum(recent) / 6
    prior_avg  = sum(prior) / 6
    if prior_avg == 0:
        return 0
    change_pct = (recent_avg - prior_avg) / prior_avg * 100
    if change_pct > 0.10:
        return 5    # 30-min recovery underway — buy side gaining
    if change_pct < -0.10:
        return -10  # still in free-fall — wait
    return 0


def _get_session_window(now_et: datetime) -> str:
    hm = now_et.hour * 60 + now_et.minute
    if hm < 4 * 60:
        return "closed"
    elif hm < 9 * 60 + 30:
        return "pre_market"
    elif hm < 10 * 60 + 30:
        return "morning_flush"
    elif hm < 12 * 60:
        return "morning_trend"
    elif hm < 14 * 60:
        return "lunch_drift"
    elif hm < 16 * 60:
        return "power_hour"
    elif hm < 20 * 60:
        return "after_hours"
    return "closed"


def _vix_thresholds(vix: float, loose: bool = False) -> dict | None:
    """ATR-normalised entry thresholds per VIX level. None = skip (extreme crash).
    min_dip_atr: minimum dip size as a multiple of the ETF's 5-min ATR-14.
    This replaces fixed % values — automatically tighter for DIA, wider for IWM.
    loose=True relaxes all three gates ~20-30% — for diagnostic/exploration scans only."""
    if vix < 18:
        base = {"min_dip_atr": 0.4, "max_rsi": 42, "min_rvol": 0.8}
    elif vix <= 25:
        base = {"min_dip_atr": 0.7, "max_rsi": 38, "min_rvol": 1.2}
    elif vix <= 35:
        base = {"min_dip_atr": 1.1, "max_rsi": 33, "min_rvol": 1.5}
    else:
        return None
    if loose:
        return {
            "min_dip_atr": base["min_dip_atr"] * 0.75,
            "max_rsi":     base["max_rsi"] + 5,
            "min_rvol":    base["min_rvol"] * 0.85,
        }
    return base


def _score_etf(
    ticker: str,
    price_data: dict,
    vix: float,
    now_et: datetime,
    vix_slope: float = 0.0,
    regime_info: dict | None = None,
    loose: bool = False,
) -> dict | None:
    """Score one ETF for dip-buy. Returns opportunity dict or None if conditions not met.
    loose=True bypasses regime gate + RVOL-declining gate, relaxes VIX thresholds, and
    lowers score thresholds (72→65, lunch 80→72). Diagnostic mode — do NOT trade these
    entries with full size; the gates exist because they raise win rate."""
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

    # Whitelist gate — only active when ENABLE_WHITELIST = True and n ≥ 5 per cell
    if ENABLE_WHITELIST and (ticker, window) not in WHITELIST_CELLS:
        return None

    # ── Market-regime gate (#2) ────────────────────────────────────────────────
    regime = (regime_info or {}).get("regime", "mean_revert")
    if regime == "trend_down" and not loose:
        return None  # dip buying has negative EV on trend-down days

    thresholds = _vix_thresholds(vix, loose=loose)
    if thresholds is None:
        return None  # extreme crash day

    # Per-ETF ATR — normalises dip/support thresholds across different vol regimes (#1)
    atr_5m = _get_atr_5m(ticker)
    atr_unit = atr_5m if atr_5m > 0 else current_price * 0.002  # fallback: 0.2% of price

    dip_dollars = day_open - current_price
    dip_pct = dip_dollars / day_open * 100  # kept for display
    if dip_dollars < atr_unit * thresholds["min_dip_atr"]:
        return None

    intraday_vwap = _compute_intraday_vwap(candles)
    closes = [c["close"] for c in candles if c.get("close")]
    rsi_5m = _compute_rsi(closes)

    # On trend_up days require RSI < 30 — only true exhaustion warrants a dip entry
    max_rsi = 30 if regime == "trend_up" else thresholds["max_rsi"]
    if rsi_5m > max_rsi:
        return None

    rvol_data = price_data.get("rvol", {})
    rvol_value = rvol_data.get("value", 1.0) if isinstance(rvol_data, dict) else 1.0
    if rvol_value < thresholds["min_rvol"]:
        return None

    # Require RVOL to be declining — sellers exhausting, not still in panic mode
    # Loose mode bypasses this — most common single blocker on knife-falling days
    recent_vols = [c.get("volume", 0) for c in candles[-6:]]
    rvol_declining = len(recent_vols) >= 4 and recent_vols[-1] < recent_vols[-4]
    if not rvol_declining and not loose:
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

    nearest_val = 0.0  # used later for invalidation level
    if valid_supports:
        nearest_label = min(valid_supports, key=lambda k: abs(current_price - valid_supports[k]))
        nearest_val = valid_supports[nearest_label]
        dist_abs = abs(current_price - nearest_val)
        # ATR-normalised tolerances: 0.10 / 0.20 / 0.35 × ATR (#1)
        # auto-widens for IWM/QQQ, tightens for DIA
        if dist_abs <= 0.10 * atr_unit:
            score += 15
            signals.append(f"Near {nearest_label} ({nearest_val:.2f})")
        elif dist_abs <= 0.20 * atr_unit:
            score += 10
            signals.append(f"Near {nearest_label} ({nearest_val:.2f})")
        elif dist_abs <= 0.35 * atr_unit:
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

    # Hammer candle on last bar — weight reduced to +5 (tiebreaker, not primary signal)
    if candles and _detect_hammer(candles[-1], candles):
        score += 5
        signals.append("Hammer candle")

    # Capitulation vs exhaustion detection (#5)
    # Compare last 4 bars vs bars 5-8 back to gauge how fast volume is drying
    recent_4 = [c.get("volume", 0) for c in candles[-4:]]
    prior_4  = [c.get("volume", 0) for c in candles[-8:-4]]
    avg_recent_4 = sum(recent_4) / max(len(recent_4), 1)
    avg_prior_4  = sum(prior_4) / max(len(prior_4), 1)
    rvol_drying_fast = avg_prior_4 > 0 and avg_recent_4 < avg_prior_4 * 0.55
    below_vwap_far = intraday_vwap > 0 and current_price < intraday_vwap * 0.993

    # Rising VIX + extreme RSI + far below VWAP in morning flush = knife still falling
    if rsi_5m < 25 and vix_slope > 0.03 and below_vwap_far and window == "morning_flush":
        score -= 15
        signals.append("Capitulation risk — wait for base")
    # Volume halved from peak + oversold + VIX calming = sellers genuinely done
    elif rvol_drying_fast and rsi_5m < 35 and vix_slope <= 0.01:
        score += 8
        signals.append("Volume exhaustion (sellers done)")

    # CVD — cumulative buy/sell pressure from 5-min bars, zero extra API calls (#8)
    recent_cvd = _compute_cvd(candles[-12:]) if len(candles) >= 12 else _compute_cvd(candles)
    prior_cvd: float | None = _compute_cvd(candles[-24:-12]) if len(candles) >= 24 else None
    if recent_cvd > 0:
        # Net buying in last 60 min — bounce already underway
        score += 8
        signals.append("CVD positive (buyers in control)")
    elif prior_cvd is not None and recent_cvd > prior_cvd:
        # Still net selling but improving — buying pressure building
        score += 5
        signals.append("CVD improving (selling pressure easing)")
    elif prior_cvd is not None and recent_cvd < prior_cvd * 0.5:
        # Selling accelerating — not ready yet
        score -= 5

    # VIX context — slope matters more than level
    if 18 <= vix <= 35:
        if vix_slope < -0.02:   # vol crush — ideal for mean reversion
            score += 12
            signals.append(f"VIX {vix:.1f} falling")
        elif vix_slope <= 0.02:  # stable
            score += 5
        else:                    # vol expanding — rising fear, dip may continue
            score -= 10
    # vix < 14: no bonus — complacency doesn't help dip-buys

    # 30-min trend alignment — existing 5-min bars, zero extra API calls (#7)
    trend_adj = _compute_intraday_trend(candles)
    score += trend_adj
    if trend_adj > 0:
        signals.append("30-min trend recovering")
    elif trend_adj < 0:
        signals.append("30-min still declining")

    score += score_delta  # session window bonus/penalty
    score = min(score, 100)

    # Confidence tier — plain-language score label for simple view (#20)
    if score >= 85:
        confidence_tier = "very_high"
    elif score >= 75:
        confidence_tier = "high"
    else:
        confidence_tier = "medium"
    _warn_words = ("Capitulation", "declining", "still")
    top_reasons = [s for s in signals if not any(w in s for w in _warn_words)][:2]
    if not top_reasons:
        top_reasons = signals[:2]

    score_threshold = 65 if loose else 72
    if score < score_threshold:
        if score >= 65 and not loose:  # near-miss: passed pattern checks, just below threshold
            _log_near_miss(ticker, score, signals, current_price, window, now_et=now_et)
        return None

    # Hard lunch block — backtest 0% win rate; -5 penalty alone is insufficient
    lunch_min = 72 if loose else 80
    if window == "lunch_drift" and score < lunch_min:
        return None

    entry_price = current_price
    # ATR-based stops and targets (#11) — scales with ETF volatility
    if atr_5m > 0:
        raw_target = entry_price + max(1.0 * atr_5m, entry_price * 0.004)
        raw_stop   = entry_price - max(0.5 * atr_5m, entry_price * 0.0025)
        target_price = round(min(raw_target, entry_price * 1.015), 2)  # cap: 1.5%
        stop_price   = round(max(raw_stop,  entry_price * 0.975),  2)  # floor: -2.5%
        atr_adjusted = True
    else:
        target_price = round(entry_price * 1.01, 2)
        stop_price   = round(entry_price * 0.995, 2)
        atr_adjusted = False

    # Invalidation levels — structural thesis controls (different from stop P&L control)
    invalidation = {
        "price_close_below": round(nearest_val * 0.998, 2) if nearest_val else round(stop_price * 0.998, 2),
        "vix_above": round(vix * 1.10, 1),
        "rvol_resurge_above": 1.8,
    }

    return {
        "ticker": ticker,
        "signal_type": "dip_buy",
        "score": score,
        "entry_price": entry_price,
        "target_price": target_price,
        "stop_price": stop_price,
        "signals": signals,
        "signal_hints": {s.split(" (")[0].split(f"RSI")[0].strip() if "RSI" in s else s.split(" (")[0]: SIGNAL_HINTS.get(s.split(" (")[0], "") for s in signals},
        "session_window": window,
        "session_window_label": window_cfg.get("label", window),
        "intraday_vwap": round(intraday_vwap, 2),
        "rsi_5m": rsi_5m,
        "rvol": round(rvol_value, 2),
        "vix": vix,
        "dip_pct": round(dip_pct, 2),
        "invalidation": invalidation,
        "side": "BUY",
        "time_stop_minutes": 25,
        "confidence_tier": confidence_tier,
        "top_reasons": top_reasons,
        "atr_5m": round(atr_5m, 4),
        "atr_adjusted": atr_adjusted,
        "loose_mode": loose,
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

def _detect_orb_breakout(ticker: str, price_data: dict, vix: float, now_et: datetime, loose: bool = False) -> dict | None:
    """ORB-15 breakout: price broke above opening range high with volume confirmation.
    loose=True lowers the RVOL gate from 1.5x → 1.2x (diagnostic mode)."""
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
    rvol_min = 1.2 if loose else 1.5
    if rvol_value < rvol_min:
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
    stop = round(orb_low * 0.999, 2)
    risk = current_price - stop
    # 3:1 R-multiple for trend continuation trades (#13); floor at 1.5× range extension
    r3_target    = current_price + risk * 3.0 if risk > 0 else orb_high + orb_range * 1.5
    range_target = orb_high + orb_range * 1.5
    target = round(max(r3_target, range_target), 2)

    return {
        "ticker": ticker,
        "signal_type": "orb_breakout",
        "score": min(score, 100),
        "entry_price": current_price,
        "target_price": target,
        "stop_price": stop,
        "time_stop_minutes": 60,  # trend trades take longer — wider window
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
        "side": "BUY",
        "orb_range": round(orb_range, 2),
        "confidence_tier": "high" if min(score, 100) >= 80 else "medium",
        "top_reasons": signals[:2],
        "loose_mode": loose,
    }


def _detect_vwap_reclaim(ticker: str, price_data: dict, vix: float, now_et: datetime, loose: bool = False) -> dict | None:
    """VWAP reclaim: price was below VWAP for 2+ candles, last candle closed back above.
    loose=True lowers the reclaim-RVOL gate from 1.2x → 1.0x (diagnostic mode)."""
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
    rvol_min = 1.0 if loose else 1.2
    if rvol_reclaim < rvol_min:
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
        "stop_price": round(intraday_vwap * 0.998, 2),
        "target_price": round(current_price + (current_price - intraday_vwap * 0.998) * 1.5, 2),  # 1.5:1 R (#13)
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
        "side": "BUY",
        "time_stop_minutes": 20,  # VWAP reclaims fail fast if they fail at all
        "confidence_tier": "high" if min(score, 100) >= 80 else "medium",
        "top_reasons": signals[:2],
        "loose_mode": loose,
    }


def _detect_failed_breakdown(ticker: str, price_data: dict, vix: float, now_et: datetime, loose: bool = False) -> dict | None:
    """Failed breakdown: price briefly broke below a key support then snapped back above it.
    Trapped shorts must cover → strong mean-reversion setup.
    loose=True lowers the reclaim-RVOL gate from 1.2x → 1.0x (diagnostic mode)."""
    window = _get_session_window(now_et)
    window_cfg = SESSION_WINDOWS.get(window, {})
    if window_cfg.get("score_delta") is None:
        return None

    candles = price_data.get("intraday_history", [])
    if len(candles) < 6:
        return None

    current_price = price_data.get("current_price", 0)
    if not current_price:
        return None

    pivots = price_data.get("pivots") or {}
    vp = price_data.get("volume_profile") or {}
    s1 = pivots.get("S1", 0) or 0
    s2 = pivots.get("S2", 0) or 0
    val = vp.get("val", 0) or 0

    support_levels = {k: v for k, v in {"S1": s1, "S2": s2, "VAL": val}.items() if v > 0}
    if not support_levels:
        return None

    # Find the highest support level that was briefly breached then reclaimed
    broken_support = None
    broken_label = None
    for label, level in sorted(support_levels.items(), key=lambda x: x[1], reverse=True):
        prior_lows = [c.get("low", float("inf")) for c in candles[-5:-1]]
        if any(low < level for low in prior_lows):
            if current_price > level * 1.001:  # confirmed reclaim — at least 0.1% above
                broken_support = level
                broken_label = label
                break

    if broken_support is None:
        return None

    # Volume confirmation on the reclaim candle — real buyers, not a dead-cat drift
    avg_vol = sum(c.get("volume", 0) for c in candles) / len(candles) if candles else 1
    reclaim_vol = candles[-1].get("volume", 0)
    rvol_reclaim = reclaim_vol / avg_vol if avg_vol > 0 else 1.0
    rvol_min = 1.0 if loose else 1.2
    if rvol_reclaim < rvol_min:
        return None

    score = 74
    signals = [
        f"Failed breakdown below {broken_label} ({broken_support:.2f})",
        f"Reclaim RVOL {rvol_reclaim:.1f}x",
    ]
    if rvol_reclaim >= 2.0:
        score += 10
        signals.append("High-volume reclaim (trapped shorts covering)")
    elif rvol_reclaim >= 1.5:
        score += 5

    if window == "morning_flush":
        score += 5  # morning failed breakdowns have highest historical probability
    elif window == "power_hour":
        score += 8

    rsi_5m = _compute_rsi([c["close"] for c in candles if c.get("close")])
    if rsi_5m < 40:
        score += 5  # still oversold = more room to recover

    if 14 <= vix <= 25:
        score += 5  # calm-moderate VIX ideal for quick reclaims

    window_delta = window_cfg.get("score_delta", 0) or 0
    score += window_delta
    score = min(score, 100)

    intraday_vwap = _compute_intraday_vwap(candles)
    rvol_data = price_data.get("rvol") or {}
    rvol_value = rvol_data.get("value", rvol_reclaim) if isinstance(rvol_data, dict) else rvol_reclaim
    day_open = price_data.get("day_open", current_price)
    dip_pct = round((day_open - current_price) / day_open * 100, 2) if day_open else 0.0

    return {
        "ticker": ticker,
        "signal_type": "failed_breakdown",
        "score": score,
        "entry_price": current_price,
        "stop_price": round(broken_support * 0.997, 2),
        "target_price": round(current_price + (current_price - broken_support * 0.997) * 2.5, 2),  # 2.5:1 R (#13)
        "signals": signals,
        "signal_hints": {
            f"Failed breakdown below {broken_label} ({broken_support:.2f})": f"Price broke below {broken_label} then reversed sharply — sellers who bet on the breakdown are now trapped and must buy to exit, fueling the bounce",
            f"Reclaim RVOL {rvol_reclaim:.1f}x": "Volume surge on the reclaim bar confirms real buying, not a low-volume drift back",
        },
        "session_window": window,
        "session_window_label": window_cfg.get("label", window),
        "intraday_vwap": round(intraday_vwap, 2),
        "rsi_5m": rsi_5m,
        "rvol": round(rvol_value, 2),
        "vix": vix,
        "dip_pct": dip_pct,
        "side": "BUY",
        "time_stop_minutes": 30,
        "confidence_tier": "high" if score >= 80 else "medium",
        "top_reasons": signals[:2],
        "loose_mode": loose,
    }


def _refine_entry_1min(ticker: str, signal: dict) -> dict:
    """
    Sharpen dip-buy entry using 1-min bars (#26).
    Mean-reversion edge is sensitive to entry price — 0.05% improvement is meaningful
    when the total target is 0.5–1.0%.  Entry moves DOWN only, never up.
    """
    try:
        hist = yf.Ticker(ticker).history(period="1d", interval="1m", prepost=False)
        if hist.empty or len(hist) < 3:
            return {**signal, "entry_refined": False}
        recent_lows = [float(hist.iloc[i]["Low"]) for i in range(-3, 0)]
        best_low = min(recent_lows)
        # Floor: never below 5-min bar's implied low (0.5% cushion)
        floor = signal["entry_price"] * 0.995
        refined = max(best_low, floor)
        if refined < signal["entry_price"] - 0.01:
            return {**signal, "entry_price": round(refined, 2), "entry_refined": True}
    except Exception as exc:
        logger.debug("1-min refinement failed %s: %s", ticker, exc)
    return {**signal, "entry_refined": False}


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
        atr_approx = current_price * 0.002  # rough fallback for diagnostic only
        if (day_open - current_price) < atr_approx * thresholds["min_dip_atr"]:
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
        elif stype == "failed_breakdown":
            return "buy_vwap_reclaim"  # closest semantic match — reclaim after breach
        else:
            return "buy_dip_at_support"

    if session_window == "power_hour":
        return "prep_power_hour"

    if no_signal_reasons:
        most_common = Counter(no_signal_reasons).most_common(1)[0][0]
        key_map = {
            "outside_hours":    "no_buy_outside_hours",
            "vix_extreme":      "no_buy_vix_extreme",
            "still_falling":    "no_buy_still_falling",
            "insufficient_dip": "no_buy_insufficient_dip",
            "rsi_not_oversold": "no_buy_rsi_not_oversold",
            "lunch_drift":      "no_buy_lunch_drift",
            "score_too_low":    "no_buy_score_too_low",
            "regime_trend_down": "no_buy_regime_trend_down",
        }
        return key_map.get(most_common, "no_buy_score_too_low")

    return "waiting"


# ── Public scanner function ───────────────────────────────────────────────────

def scan_dip_opportunities(
    tickers: list[str],
    capital: float = 1000.0,
    vix: float | None = None,
    loose: bool = False,
) -> dict:
    """Scan ETFs for dip-buy, ORB breakout, and VWAP reclaim opportunities. Zero LLM.
    loose=True relaxes all gate thresholds ~20-30% and bypasses the regime/RVOL-declining
    blocks. Diagnostic mode — results not persisted, used to see what would have qualified
    on a quiet day. Win rates not validated for this profile."""
    from app.tools.price import get_price

    now_et = datetime.now(ET_TZ)

    if vix is None:
        try:
            vix_info = yf.Ticker("^VIX").fast_info
            vix = float(vix_info.get("lastPrice", 18.0) or 18.0)
        except Exception:
            vix = 18.0

    # VIX slope — fetch once for all tickers (rising vs falling vol changes signal quality)
    vix_slope = 0.0
    try:
        vix_hist = yf.Ticker("^VIX").history(period="1d", interval="5m", prepost=False)
        if len(vix_hist) >= 7:
            vix_now = float(vix_hist.iloc[-1]["Close"])
            vix_30m_ago = float(vix_hist.iloc[-7]["Close"])  # 6 bars × 5min = 30 min
            vix_slope = (vix_now - vix_30m_ago) / vix_30m_ago if vix_30m_ago else 0.0
    except Exception:
        vix_slope = 0.0

    # Market regime — computed once, cached 60 s; gates all four signal types
    regime_info = classify_regime(vix, vix_slope)

    dip_opportunities: list[dict] = []
    orb_opportunities: list[dict] = []
    vwap_opportunities: list[dict] = []
    failed_breakdown_opportunities: list[dict] = []
    no_signal_reasons: list[str] = []
    price_cache: dict[str, dict] = {}

    for ticker in tickers:
        try:
            result = get_price.invoke({"ticker": ticker})
            if not isinstance(result, dict) or "error" in result:
                continue
            price_cache[ticker] = result

            dip = _score_etf(ticker, result, vix, now_et, vix_slope, regime_info, loose=loose)
            if dip:
                dip_opportunities.append(_add_pnl(dip, capital))
            else:
                # Add regime gate reason if applicable (only fires in strict mode)
                if regime_info.get("regime") == "trend_down" and not loose:
                    no_signal_reasons.append("regime_trend_down")
                else:
                    no_signal_reasons.append(_get_no_signal_reason(result, vix, now_et))

            orb = _detect_orb_breakout(ticker, result, vix, now_et, loose=loose)
            if orb:
                orb_opportunities.append(_add_pnl(orb, capital))

            vwap = _detect_vwap_reclaim(ticker, result, vix, now_et, loose=loose)
            if vwap:
                vwap_opportunities.append(_add_pnl(vwap, capital))

            fb = _detect_failed_breakdown(ticker, result, vix, now_et, loose=loose)
            if fb:
                failed_breakdown_opportunities.append(_add_pnl(fb, capital))

        except Exception as exc:
            logger.warning("dip_scanner: error scanning %s — %s", ticker, exc)

    for lst in (dip_opportunities, orb_opportunities, vwap_opportunities, failed_breakdown_opportunities):
        lst.sort(key=lambda x: x["score"], reverse=True)

    vix_spike = check_vix_spike()
    session_window = _get_session_window(now_et)

    all_opps = dip_opportunities + orb_opportunities + vwap_opportunities + failed_breakdown_opportunities
    best = max(all_opps, key=lambda x: x["score"]) if all_opps else None

    # 1-min entry refinement on best signal — improves slippage without extra scan cost (#26)
    if best and best.get("signal_type") in ("dip_buy", "vwap_reclaim", "failed_breakdown"):
        best = _refine_entry_1min(best["ticker"], best)

    scenario_key = _determine_scenario_key(
        dip_opportunities, orb_opportunities, vwap_opportunities + failed_breakdown_opportunities,
        vix_spike, session_window, vix, no_signal_reasons,
    )

    return {
        "opportunities": dip_opportunities,
        "orb_opportunities": orb_opportunities,
        "vwap_opportunities": vwap_opportunities,
        "failed_breakdown_opportunities": failed_breakdown_opportunities,
        "best": best,
        "vix_spike_prep": vix_spike,
        "scenario_key": scenario_key,
        "tickers_scanned": len(tickers),
        "session_window": session_window,
        "vix": round(vix, 2),
        "regime": regime_info,
        "timestamp": now_et.isoformat(),
        "capital": capital,
        "loose_gates_active": loose,
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
        # ATR approximation — 0.2% of open (same fallback as live scanner)
        atr_approx = day_open * 0.002

        # Track one signal per type per day (not one globally)
        fired_this_day: set[str] = set()

        # Pre-compute opening range (first 15 bars = 75 min) for ORB backfill
        first_15 = [
            {"close": float(r["Close"]), "high": float(r["High"]),
             "low": float(r["Low"]), "volume": int(r["Volume"])}
            for _, r in day_bars.iloc[:15].iterrows()
        ]
        orb_high = max(c["high"] for c in first_15) if first_15 else day_open
        orb_low  = min(c["low"]  for c in first_15) if first_15 else day_open
        orb_range = orb_high - orb_low

        for i in range(15, len(day_bars)):
            if len(fired_this_day) == 4:  # all signal types fired for today
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
            intraday_vwap = _compute_intraday_vwap(candles_so_far)
            avg_vol = sum(c["volume"] for c in candles_so_far) / len(candles_so_far)
            rvol_val = candles_so_far[-1]["volume"] / max(1, avg_vol)

            def _resolve(entry: float, target: float, stop: float, bar_idx: int) -> tuple[str, float, str, str | None]:
                """Simulate outcome by walking future bars. Returns (status, outcome_price, resolved_by, five_min_dir)."""
                future = day_bars.iloc[bar_idx + 1:]
                status_r = "expired"
                outcome_r = entry
                resolved_r = "eod_close"
                fmd = None
                for j, (_, fb) in enumerate(future.iterrows()):
                    fhigh = float(fb["High"])
                    flow  = float(fb["Low"])
                    fclose = float(fb["Close"])
                    if j == 0:
                        diff = (fclose - entry) / entry * 100
                        fmd = "up" if diff > 0.05 else ("down" if diff < -0.05 else "flat")
                    if fhigh >= target:
                        return "win", target, "target_hit", fmd
                    if flow <= stop:
                        return "loss", stop, "stop_hit", fmd
                    outcome_r = fclose
                if status_r == "expired":
                    status_r = "win" if outcome_r > entry else "loss"
                return status_r, outcome_r, resolved_r, fmd

            def _append(stype: str, entry: float, target: float, stop: float, score: int, sigs: list[str]) -> None:
                # Mirror live gates: backtest must persist only signals the live scanner
                # would fire. ORB/VWAP/Failed-Breakdown previously bypassed both checks
                # because they don't route through _score_etf.
                if score < 72:
                    return
                if window == "lunch_drift" and score < 80:
                    return
                status, outcome_price, resolved_by, fmd = _resolve(entry, target, stop, i)
                pnl_pct = (outcome_price - entry) / entry * 100
                alerts.append({
                    "ticker": ticker,
                    "signal_type": stype,
                    "side": "BUY",
                    "entry_price": round(entry, 2),
                    "target_price": round(target, 2),
                    "stop_price": round(stop, 2),
                    "entry_time": bar_time.isoformat(),
                    "score": score,
                    "signals": sigs,
                    "session_window": window,
                    "vix_at_entry": day_vix,
                    "capital_used": 1000.0,
                    "source": "backtest",
                    "status": status,
                    "outcome_price": round(outcome_price, 2),
                    "actual_pnl_pct": round(pnl_pct, 3),
                    "actual_pnl_dollar": round(pnl_pct / 100 * 1000.0, 2),
                    "resolved_by": resolved_by,
                    "five_min_direction": fmd,
                })
                fired_this_day.add(stype)

            # ── Dip Buy ──────────────────────────────────────────────────────────
            if "dip_buy" not in fired_this_day:
                dip_dollars = day_open - current_price
                if dip_dollars >= atr_approx * thresholds["min_dip_atr"]:
                    closes = [c["close"] for c in candles_so_far]
                    rsi_5m = _compute_rsi(closes)
                    if rsi_5m <= thresholds["max_rsi"]:
                        recent_vols = [c["volume"] for c in candles_so_far[-6:]]
                        if len(recent_vols) >= 4 and recent_vols[-1] < recent_vols[-4]:
                            mock_price_data = {
                                "current_price": current_price,
                                "day_open": day_open,
                                "intraday_history": candles_so_far,
                                "pivots": {"S1": s1, "S2": s2},
                                "volume_profile": {},
                                "rvol": {"value": rvol_val},
                            }
                            opp = _score_etf(ticker, mock_price_data, day_vix, now_et)
                            if opp:
                                _append(
                                    "dip_buy",
                                    current_price,
                                    opp.get("target_price", round(current_price * 1.01, 2)),
                                    opp.get("stop_price",   round(current_price * 0.995, 2)),
                                    opp["score"],
                                    opp["signals"],
                                )

            # ── ORB Breakout ─────────────────────────────────────────────────────
            if "orb_breakout" not in fired_this_day and window in ("morning_trend", "lunch_drift", "power_hour"):
                if current_price > orb_high * 1.001 and rvol_val > 1.3:
                    risk = max(current_price - (orb_high - orb_range * 0.5), current_price * 0.003)
                    stop  = round(current_price - risk, 2)
                    target = round(current_price + max(risk * 3.0, orb_range * 1.5), 2)
                    score = min(100, 65 + int((rvol_val - 1.3) * 15))
                    _append("orb_breakout", current_price, target, stop, score,
                            [f"ORB-15 breakout above {orb_high:.2f}", f"RVOL {rvol_val:.1f}x"])

            # ── VWAP Reclaim ─────────────────────────────────────────────────────
            if "vwap_reclaim" not in fired_this_day and i >= 5 and window in ("morning_flush", "morning_trend", "power_hour"):
                prev_candles = candles_so_far[:-1]
                prev_vwap = _compute_intraday_vwap(prev_candles)
                prev_close = prev_candles[-1]["close"] if prev_candles else current_price
                if prev_close < prev_vwap and current_price > intraday_vwap and rvol_val > 1.5:
                    stop  = round(intraday_vwap * 0.998, 2)
                    risk  = current_price - stop
                    target = round(current_price + risk * 1.5, 2)
                    score = min(100, 65 + int((rvol_val - 1.5) * 12))
                    _append("vwap_reclaim", current_price, target, stop, score,
                            [f"VWAP reclaim ({intraday_vwap:.2f})", f"Reclaim RVOL {rvol_val:.1f}x"])

            # ── Failed Breakdown ─────────────────────────────────────────────────
            if "failed_breakdown" not in fired_this_day and i >= 6 and window in ("morning_trend", "power_hour"):
                support = min(s1, s2, orb_low)
                lows = [c["low"] for c in candles_so_far[-6:]]
                # Price briefly pierced support then snapped back above it
                if min(lows[:-1]) < support and current_price > support * 1.001 and rvol_val > 1.4:
                    stop  = round(support * 0.997, 2)
                    risk  = current_price - stop
                    target = round(current_price + risk * 2.5, 2)
                    score = min(100, 65 + int((rvol_val - 1.4) * 12))
                    _append("failed_breakdown", current_price, target, stop, score,
                            [f"Failed breakdown below {support:.2f}", f"Reclaim RVOL {rvol_val:.1f}x"])

    return alerts
