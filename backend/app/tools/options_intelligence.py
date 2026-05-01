"""
Options Intelligence tool — Sprint 2.

Surfaces the options market signals professional traders pay $150/month for,
computed entirely from yfinance options chains (free).

Metrics:
  GEX (Gamma Exposure)     — are market makers dampening or amplifying moves?
  Max Pain                 — strike where most options expire worthless
  IV vs Realized Vol       — are options cheap or expensive right now?
  Put/Call Skew            — how aggressively is the market hedging downside?
  Vol Term Structure       — is near-term fear elevated vs longer-dated calm?

Every metric returns a full SignalResult so the verdict is always explicit.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

from langchain_core.tools import tool

from app.tools._yf_client import get_ticker
from app.tools.signal import build_signal, composite_verdict


# ── Math helpers (Black-Scholes, no scipy needed) ─────────────────────────────

def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def _bs_gamma(spot: float, strike: float, sigma: float, T: float, r: float = 0.05) -> float:
    """Black-Scholes gamma for a European option."""
    if T <= 0 or sigma <= 0 or spot <= 0 or strike <= 0:
        return 0.0
    try:
        d1 = (math.log(spot / strike) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        return _norm_pdf(d1) / (spot * sigma * math.sqrt(T))
    except (ValueError, ZeroDivisionError):
        return 0.0


def _days_to_expiry(expiry_str: str) -> float:
    """Return years to expiry (floored to 1/365 to avoid zero)."""
    try:
        exp_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
        days = (exp_date - date.today()).days
        return max(days, 1) / 365.0
    except Exception:
        return 1 / 365.0


def _realized_vol_30d(hist) -> float | None:
    """30-day annualised realised volatility from daily close prices."""
    try:
        closes = hist["Close"].dropna()
        if len(closes) < 22:
            return None
        log_returns = closes.pct_change().dropna().tail(21)
        return float(log_returns.std() * math.sqrt(252))
    except Exception:
        return None


# ── GEX ───────────────────────────────────────────────────────────────────────

def _compute_gex(calls, puts, spot: float, expiry: str) -> dict:
    """
    Net Gamma Exposure.

    Convention (SpotGamma):
      dealers are assumed SHORT both calls and puts to clients.
      Call GEX is positive (dealers short calls → long delta → sell into rallies).
      Put GEX is negative (dealers short puts → short delta → sell into drops).
      Net GEX = Call_GEX - Put_GEX.
      Positive net GEX → market makers dampen moves (range-bound).
      Negative net GEX → market makers amplify moves (volatile).
    """
    T = _days_to_expiry(expiry)
    CONTRACT = 100  # shares per contract

    call_gex = 0.0
    gex_by_strike: dict[float, float] = {}

    for _, row in calls.iterrows():
        K = float(row.get("strike", 0))
        oi = float(row.get("openInterest") or 0)
        iv = float(row.get("impliedVolatility") or 0)
        if K <= 0 or oi <= 0 or iv <= 0:
            continue
        g = _bs_gamma(spot, K, iv, T)
        contribution = g * oi * CONTRACT * spot ** 2 / 100
        call_gex += contribution
        gex_by_strike[K] = gex_by_strike.get(K, 0.0) + contribution

    put_gex = 0.0
    for _, row in puts.iterrows():
        K = float(row.get("strike", 0))
        oi = float(row.get("openInterest") or 0)
        iv = float(row.get("impliedVolatility") or 0)
        if K <= 0 or oi <= 0 or iv <= 0:
            continue
        g = _bs_gamma(spot, K, iv, T)
        contribution = g * oi * CONTRACT * spot ** 2 / 100
        put_gex += contribution
        gex_by_strike[K] = gex_by_strike.get(K, 0.0) - contribution

    net_gex = call_gex - put_gex

    # Find GEX flip level — strike where cumulative GEX crosses zero
    strikes_sorted = sorted(gex_by_strike.keys())
    flip_level = None
    cumulative = 0.0
    for k in strikes_sorted:
        prev = cumulative
        cumulative += gex_by_strike[k]
        if prev < 0 < cumulative or prev > 0 > cumulative:
            flip_level = k

    # Top strikes by absolute GEX
    top_levels = sorted(gex_by_strike.items(), key=lambda x: abs(x[1]), reverse=True)[:5]

    if net_gex > 0:
        verdict, conviction, score = "BUY", "MODERATE", 0.5
        headline = f"Positive GEX ${net_gex/1e6:.0f}M — market makers will DAMPEN moves today"
        why = ("Dealers are net long gamma. They buy dips and sell rallies to hedge, acting as a "
               "natural price stabiliser. Expect range-bound price action.")
        action = "Favour mean-reversion strategies. Tight ranges make premium-selling attractive."
        key_risk = "A news catalyst can overwhelm GEX suppression — watch for gap opens."
        direction = "STABLE"
    else:
        verdict, conviction, score = "SELL", "HIGH", -1.0
        headline = f"Negative GEX ${abs(net_gex)/1e6:.0f}M — market makers will AMPLIFY moves today"
        why = ("Dealers are net short gamma. They must chase moves to delta-hedge, adding fuel to "
               "both rallies and selloffs. Volatility expands.")
        action = "Favour momentum and breakout strategies. Widen stops to account for amplified swings."
        key_risk = "GEX flips rapidly — recalculate at each session open."
        direction = "DETERIORATING" if net_gex < -500_000_000 else "STABLE"

    return {
        "net_gex": round(net_gex),
        "call_gex": round(call_gex),
        "put_gex": round(put_gex),
        "flip_level": flip_level,
        "top_levels": [{"strike": k, "gex": round(v)} for k, v in top_levels],
        "signal": build_signal(
            value=round(net_gex / 1e6, 1),
            verdict=verdict,
            conviction=conviction,
            headline=headline,
            why=why,
            action=action,
            key_risk=key_risk,
            direction=direction,
            score_contribution=score,
        ),
    }


# ── Max Pain ──────────────────────────────────────────────────────────────────

def _compute_max_pain(calls, puts, spot: float) -> dict:
    """
    Max pain = strike where total option value (all calls + all puts) is minimised.
    Option sellers profit most when price lands here at expiry.
    """
    all_strikes = sorted(set(
        list(calls["strike"].dropna()) + list(puts["strike"].dropna())
    ))
    if not all_strikes:
        return {}

    min_pain = float("inf")
    max_pain_strike = all_strikes[0]

    for test_strike in all_strikes:
        call_pain = float(calls.apply(
            lambda r: max(0.0, test_strike - r["strike"]) * (r.get("openInterest") or 0), axis=1
        ).sum())
        put_pain = float(puts.apply(
            lambda r: max(0.0, r["strike"] - test_strike) * (r.get("openInterest") or 0), axis=1
        ).sum())
        total = call_pain + put_pain
        if total < min_pain:
            min_pain = total
            max_pain_strike = test_strike

    distance_pct = round((max_pain_strike - spot) / spot * 100, 2) if spot > 0 else 0.0
    abs_dist = abs(distance_pct)

    if abs_dist < 1.0:
        verdict, score = "HOLD", 0.0
        conviction = "MODERATE"
        headline = f"Max pain at ${max_pain_strike:.0f} — {abs_dist:.1f}% from current price (close)"
        action = "Price near max pain. Option sellers have minimal pressure to move price."
    elif distance_pct < -2.0:
        verdict, score = "SELL", -0.75
        conviction = "MODERATE"
        headline = f"Max pain at ${max_pain_strike:.0f} — {abs_dist:.1f}% below current price"
        action = "Gravitational pull is downward. Expect drift toward max pain near expiry."
    else:
        verdict, score = "BUY", 0.5
        conviction = "LOW"
        headline = f"Max pain at ${max_pain_strike:.0f} — {abs_dist:.1f}% above current price"
        action = "Option sellers benefit from price rising toward max pain."

    return {
        "strike": max_pain_strike,
        "distance_pct": distance_pct,
        "signal": build_signal(
            value=max_pain_strike,
            verdict=verdict,
            conviction=conviction,
            headline=headline,
            why=("Max pain is the price where all outstanding options lose the most total value. "
                 "Market makers and option sellers have a financial incentive to pin price here at expiry."),
            action=action,
            key_risk="Max pain is only relevant in the days leading up to expiration — less meaningful weeks out.",
            direction="UNKNOWN",
            score_contribution=score,
        ),
    }


# ── IV vs Realized Vol ────────────────────────────────────────────────────────

def _compute_iv_analysis(calls, puts, spot: float, hist) -> dict:
    """
    Compare ATM implied vol to 30-day realised vol.
    IV/RV ratio > 1.3 = options expensive (sell premium).
    IV/RV ratio < 0.8 = options cheap (buy premium).
    """
    # ATM implied vol: average IV of calls and puts nearest to spot
    atm_calls = calls.iloc[(calls["strike"] - spot).abs().argsort()[:3]]
    atm_puts  = puts.iloc[(puts["strike"]  - spot).abs().argsort()[:3]]
    atm_ivs   = list(atm_calls["impliedVolatility"].dropna()) + list(atm_puts["impliedVolatility"].dropna())
    atm_iv = float(sum(atm_ivs) / len(atm_ivs)) if atm_ivs else None

    rv_30d = _realized_vol_30d(hist)

    if atm_iv is None:
        return {}

    atm_iv_pct = round(atm_iv * 100, 1)
    rv_pct = round((rv_30d or 0) * 100, 1)

    if rv_30d and rv_30d > 0:
        ratio = atm_iv / rv_30d
    else:
        ratio = 1.0

    if ratio > 1.3:
        verdict, score, conviction = "SELL", -0.75, "MODERATE"
        headline = f"IV {atm_iv_pct}% vs RV {rv_pct}% — options are expensive, premium selling favoured"
        action = "Selling covered calls or cash-secured puts is high edge here. Avoid buying premium."
        direction = "DETERIORATING"
    elif ratio < 0.8:
        verdict, score, conviction = "BUY", 0.75, "MODERATE"
        headline = f"IV {atm_iv_pct}% vs RV {rv_pct}% — options are cheap, buying premium is attractive"
        action = "Protective puts or speculative calls are cheap relative to expected moves. Consider buying."
        direction = "IMPROVING"
    else:
        verdict, score, conviction = "HOLD", 0.0, "LOW"
        headline = f"IV {atm_iv_pct}% vs RV {rv_pct}% — options fairly priced"
        action = "No strong edge from IV mispricing. Neutral on directional option plays."
        direction = "STABLE"

    return {
        "atm_iv_pct": atm_iv_pct,
        "realized_vol_30d_pct": rv_pct if rv_30d else None,
        "iv_rv_ratio": round(ratio, 2),
        "signal": build_signal(
            value=atm_iv_pct,
            verdict=verdict,
            conviction=conviction,
            headline=headline,
            why=("IV/RV ratio compares how much the options market expects the stock to move (IV) "
                 "vs how much it has actually moved recently (realised vol). "
                 "A ratio above 1.3 means you're overpaying for options; below 0.8 means options are a bargain."),
            action=action,
            key_risk="IV can spike suddenly on news — even cheap IV can overshoot realised vol.",
            direction=direction,
            direction_note=f"IV/RV ratio {ratio:.2f}",
            score_contribution=score,
        ),
    }


# ── Put/Call Skew ─────────────────────────────────────────────────────────────

def _compute_skew(calls, puts, spot: float) -> dict:
    """
    25-delta equivalent skew: OTM put IV vs OTM call IV.
    High put skew = heavy downside hedging = bearish pressure.
    """
    otm_threshold = 0.05  # within 5–15% OTM

    otm_calls = calls[
        (calls["strike"] > spot * 1.03) & (calls["strike"] < spot * 1.15)
    ]["impliedVolatility"].dropna()

    otm_puts = puts[
        (puts["strike"] < spot * 0.97) & (puts["strike"] > spot * 0.85)
    ]["impliedVolatility"].dropna()

    if otm_calls.empty or otm_puts.empty:
        return {}

    avg_call_iv = float(otm_calls.mean())
    avg_put_iv  = float(otm_puts.mean())
    skew = avg_put_iv - avg_call_iv
    skew_pct = round(skew * 100, 1)

    if skew_pct > 8:
        verdict, score, conviction = "SELL", -1.0, "HIGH"
        headline = f"Put skew {skew_pct}% — heavy downside hedging, market expects a drop"
        direction = "DETERIORATING"
        action = "Smart money is buying downside protection aggressively. Reduce or hedge long exposure."
    elif skew_pct > 4:
        verdict, score, conviction = "SELL", -0.5, "MODERATE"
        headline = f"Put skew {skew_pct}% — elevated downside hedging, cautious bias"
        direction = "DETERIORATING"
        action = "Some downside protection being bought. Lean defensive or reduce position size."
    elif skew_pct < 1:
        verdict, score, conviction = "BUY", 0.5, "MODERATE"
        headline = f"Put skew {skew_pct}% — calls equally priced, market not hedging downside"
        direction = "IMPROVING"
        action = "Market is not pricing in downside risk. Bullish options flow supported."
    else:
        verdict, score, conviction = "HOLD", 0.0, "LOW"
        headline = f"Put skew {skew_pct}% — normal skew, no extreme hedging"
        direction = "STABLE"
        action = "Skew is within normal range. No strong directional options signal."

    return {
        "otm_put_iv_pct": round(avg_put_iv * 100, 1),
        "otm_call_iv_pct": round(avg_call_iv * 100, 1),
        "skew_pct": skew_pct,
        "signal": build_signal(
            value=skew_pct,
            verdict=verdict,
            conviction=conviction,
            headline=headline,
            why=("Put/call skew measures how much more expensive OTM puts are vs equivalent OTM calls. "
                 "High skew means investors are paying a premium to protect against a drop — "
                 "a consistent precursor to institutional risk-off moves."),
            action=action,
            key_risk="Skew can be elevated as a permanent risk premium for certain stocks — compare to its own history.",
            direction=direction,
            score_contribution=score,
        ),
    }


# ── Vol Term Structure ────────────────────────────────────────────────────────

def _compute_term_structure(stock, spot: float) -> dict:
    """
    ATM IV across multiple expirations.
    Backwardation (near > far) = near-term event fear.
    Contango (near < far) = normal — market calm short-term.
    """
    expiries = stock.options[:6] if stock.options else []
    term = []

    for exp in expiries:
        try:
            chain = stock.option_chain(exp)
            atm_calls = chain.calls.iloc[(chain.calls["strike"] - spot).abs().argsort()[:2]]
            atm_puts  = chain.puts.iloc[(chain.puts["strike"]  - spot).abs().argsort()[:2]]
            ivs = list(atm_calls["impliedVolatility"].dropna()) + list(atm_puts["impliedVolatility"].dropna())
            if ivs:
                term.append({"expiry": exp, "atm_iv_pct": round(float(sum(ivs) / len(ivs)) * 100, 1)})
        except Exception:
            continue

    if len(term) < 2:
        return {}

    near_iv = term[0]["atm_iv_pct"]
    far_iv  = term[-1]["atm_iv_pct"]
    slope   = round(far_iv - near_iv, 1)

    if near_iv > far_iv + 3:
        shape = "backwardation"
        verdict, score, conviction = "AVOID", -1.5, "HIGH"
        headline = f"Vol backwardation — near-term IV {near_iv}% >> far IV {far_iv}% (event fear)"
        action = "Near-term event risk is priced in. Avoid short-gamma positions before expiry."
        direction = "DETERIORATING"
    elif near_iv > far_iv:
        shape = "mild backwardation"
        verdict, score, conviction = "SELL", -0.5, "MODERATE"
        headline = f"Mild vol backwardation — near-term slightly elevated at {near_iv}% vs {far_iv}%"
        action = "Some near-term uncertainty. Consider waiting for event resolution before entering."
        direction = "STABLE"
    else:
        shape = "contango"
        verdict, score, conviction = "BUY", 0.5, "MODERATE"
        headline = f"Vol contango — near-term IV {near_iv}% < far IV {far_iv}% (market calm near-term)"
        action = "Near-term vol is cheap. Short-dated options or premium-selling are reasonable."
        direction = "IMPROVING"

    return {
        "shape": shape,
        "near_iv_pct": near_iv,
        "far_iv_pct": far_iv,
        "slope": slope,
        "term": term,
        "signal": build_signal(
            value=near_iv,
            verdict=verdict,
            conviction=conviction,
            headline=headline,
            why=("Vol term structure shows whether fear is concentrated near-term (backwardation) "
                 "or spread evenly (contango). Backwardation often precedes a binary event — "
                 "earnings, FOMC, FDA decisions — where near-term outcome is uncertain."),
            action=action,
            key_risk="Term structure can shift instantly on news — most useful in the week leading into events.",
            direction=direction,
            direction_note=f"Slope {slope:+.1f}%",
            score_contribution=score,
        ),
    }


# ── Main tool ─────────────────────────────────────────────────────────────────

@tool
def get_options_intelligence(ticker: str) -> dict:
    """
    Compute institutional-grade options market signals: GEX, max pain, IV analysis,
    put/call skew, and volatility term structure. All from free yfinance data.
    """
    try:
        stock = get_ticker(ticker)
        expiries = stock.options
        if not expiries:
            return {"error": f"No options data available for {ticker}"}

        nearest = expiries[0]
        chain = stock.option_chain(nearest)
        calls, puts = chain.calls, chain.puts

        # Spot price from info, fallback to last daily close
        info = stock.info
        spot = float(info.get("currentPrice") or info.get("regularMarketPrice") or 0)
        if spot <= 0:
            hist_tmp = stock.history(period="5d")
            spot = float(hist_tmp["Close"].iloc[-1]) if not hist_tmp.empty else 0
        if spot <= 0:
            return {"error": f"Could not determine spot price for {ticker}"}

        hist = stock.history(period="1y")

        gex      = _compute_gex(calls, puts, spot, nearest)
        max_pain = _compute_max_pain(calls, puts, spot)
        iv_anal  = _compute_iv_analysis(calls, puts, spot, hist)
        skew     = _compute_skew(calls, puts, spot)
        term     = _compute_term_structure(stock, spot)

        signals = [
            gex.get("signal"),
            max_pain.get("signal"),
            iv_anal.get("signal"),
            skew.get("signal"),
            term.get("signal"),
        ]
        composite = composite_verdict([s for s in signals if s])

        return {
            "ticker": ticker.upper(),
            "spot_price": spot,
            "nearest_expiry": nearest,
            "gex": gex,
            "max_pain": max_pain,
            "iv_analysis": iv_anal,
            "skew": skew,
            "term_structure": term,
            "composite": composite,
        }
    except Exception as e:
        return {"error": f"Failed to compute options intelligence for {ticker}: {str(e)}"}
