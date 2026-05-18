import logging
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf
from langchain_core.tools import tool

from app.tools._yf_client import get_ticker

logger = logging.getLogger(__name__)

# ── Market-regime gate for dip scanner ────────────────────────────────────────
# classify_regime() is NOT a LangGraph tool — imported directly by dip_scanner.py.

_regime_cache: dict = {}
_cache_ts: datetime | None = None
_CACHE_TTL_SECONDS = 60


def _ema(values: list[float], period: int) -> float:
    if not values:
        return 0.0
    k = 2 / (period + 1)
    ema = values[0]
    for v in values[1:]:
        ema = v * k + ema * (1 - k)
    return ema


def classify_regime(vix: float, vix_slope: float) -> dict:
    """
    Classify current market regime from SPY daily data + VIX history.
    Cached 60 s — safe to call per ticker inside a scan loop.

    Returns dict keys:
      regime          — "mean_revert" | "chop" | "trend_up" | "trend_down"
      reason          — human-readable explanation
      spy_above_ema   — bool
      vix_5d_change_pct
      spy_vs_ema_pct
      range_vs_atr    — today's SPY range / 20-day ATR (>1.5 = expanding vol)
    """
    global _regime_cache, _cache_ts

    now = datetime.now()
    if _cache_ts and (now - _cache_ts).total_seconds() < _CACHE_TTL_SECONDS and _regime_cache:
        return _regime_cache

    result: dict = {
        "regime": "mean_revert",
        "reason": "Default (data unavailable) — full scoring active",
        "spy_above_ema": True,
        "vix_5d_change_pct": 0.0,
        "spy_vs_ema_pct": 0.0,
        "range_vs_atr": 1.0,
    }

    try:
        spy_daily = yf.Ticker("SPY").history(period="30d", interval="1d")
        vix_daily = yf.Ticker("^VIX").history(period="10d", interval="1d")

        if spy_daily.empty or len(spy_daily) < 5:
            return result

        spy_closes = [float(r["Close"]) for _, r in spy_daily.iterrows()]
        spy_highs = [float(r["High"]) for _, r in spy_daily.iterrows()]
        spy_lows = [float(r["Low"]) for _, r in spy_daily.iterrows()]

        spy_ema_20 = _ema(spy_closes, 20)
        spy_current = spy_closes[-1]
        spy_above_ema = spy_current > spy_ema_20
        spy_vs_ema_pct = (spy_current - spy_ema_20) / spy_ema_20 * 100 if spy_ema_20 else 0.0

        vix_5d_change_pct = 0.0
        if not vix_daily.empty and len(vix_daily) >= 5:
            vix_5d_ago = float(vix_daily.iloc[-5]["Close"])
            if vix_5d_ago:
                vix_5d_change_pct = (
                    (float(vix_daily.iloc[-1]["Close"]) - vix_5d_ago) / vix_5d_ago * 100
                )

        daily_ranges = [hi - lo for hi, lo in zip(spy_highs, spy_lows)]
        atr_20 = sum(daily_ranges[-20:]) / min(len(daily_ranges), 20) if daily_ranges else 0
        today_range = float(spy_daily.iloc[-1]["High"]) - float(spy_daily.iloc[-1]["Low"])
        range_vs_atr = today_range / atr_20 if atr_20 > 0 else 1.0
        expanding_vol = range_vs_atr > 1.5

        result.update(
            {
                "spy_above_ema": spy_above_ema,
                "vix_5d_change_pct": round(vix_5d_change_pct, 1),
                "spy_vs_ema_pct": round(spy_vs_ema_pct, 2),
                "range_vs_atr": round(range_vs_atr, 2),
            }
        )

        if vix_5d_change_pct > 15:
            result["regime"] = "trend_down"
            result["reason"] = (
                f"VIX +{vix_5d_change_pct:.0f}% in 5 days — fear expansion, knife-catch risk"
            )
        elif vix_slope > 0.04 and vix > 22:
            result["regime"] = "trend_down"
            result["reason"] = (
                f"VIX rising {vix_slope*100:.1f}%/30min + elevated ({vix:.0f}) — vol accelerating"
            )
        elif expanding_vol and not spy_above_ema:
            result["regime"] = "trend_down"
            result["reason"] = (
                f"SPY range {range_vs_atr:.1f}× ATR + below 20 EMA — trend continuation risk"
            )
        elif expanding_vol and spy_above_ema:
            result["regime"] = "trend_up"
            result["reason"] = (
                f"SPY range {range_vs_atr:.1f}× ATR + above 20 EMA — uptrend with momentum"
            )
        elif spy_above_ema:
            result["regime"] = "mean_revert"
            result["reason"] = (
                f"SPY +{spy_vs_ema_pct:.1f}% above 20 EMA, normal vol — mean reversion active"
            )
        else:
            result["regime"] = "chop"
            result["reason"] = (
                f"SPY {spy_vs_ema_pct:.1f}% below 20 EMA, normal vol — range-bound, bounces likely"
            )

    except Exception as exc:
        logger.warning("regime classifier: %s", exc)

    _regime_cache = result
    _cache_ts = now
    return result


def _hmm_regime(returns: pd.Series) -> dict:
    try:
        from hmmlearn import hmm

        X = returns.values.reshape(-1, 1)
        model = hmm.GaussianHMM(n_components=2, covariance_type="full", n_iter=200, random_state=42)
        model.fit(X)
        states = model.predict(X)
        # Identify which state has higher mean return (trending = bullish state)
        means = [model.means_[i][0] for i in range(2)]
        trending_state = int(np.argmax(means))
        current_state = int(states[-1])
        # Regime probabilities for last observation
        log_prob, posteriors = model.score_samples(X[-20:])
        current_prob = float(np.mean(posteriors[:, current_state]))
        return {
            "ok": True,
            "current_state": current_state,
            "trending_state": trending_state,
            "is_trending": current_state == trending_state,
            "confidence": round(current_prob * 100, 1),
            "state_means": [round(float(m[0]) * 100, 4) for m in model.means_],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@tool
def get_regime(ticker: str) -> dict:
    """
    Hidden Markov Model regime classifier — trending vs mean-reverting.
    Determines which market regime the stock is currently in.
    """
    try:
        stock = get_ticker(ticker)
        hist = stock.history(period="1y")
        if hist.empty or len(hist) < 60:
            return {"error": f"Insufficient price history for {ticker}"}

        closes = hist["Close"].dropna()
        returns = closes.pct_change().dropna()

        hmm_result = _hmm_regime(returns)
        if not hmm_result.get("ok"):
            # Fallback: simple heuristic — compare 20d vs 60d return momentum
            r20 = float(closes.pct_change(20).iloc[-1])
            r60 = float(closes.pct_change(60).iloc[-1])
            vol20 = float(returns.rolling(20).std().iloc[-1])
            vol60 = float(returns.rolling(60).std().iloc[-1])
            is_trending = (abs(r20) > 0.05 and vol20 < vol60 * 1.3) or abs(r20) > 0.12
            hmm_result = {
                "ok": True,
                "is_trending": is_trending,
                "confidence": 60.0,
                "state_means": [],
            }

        is_trending = hmm_result["is_trending"]

        # Compute supporting metrics
        adx_proxy = _adx_proxy(hist)
        r20 = float(closes.pct_change(20).iloc[-1]) * 100
        r60 = float(closes.pct_change(60).iloc[-1]) * 100

        if is_trending:
            regime = "TRENDING"
            regime_color = "blue"
            description = "Stock is in a directional trending regime"
            strategy = "Trend-following: buy breakouts, trail stops, avoid mean-reversion entries"
        else:
            regime = "MEAN-REVERTING"
            regime_color = "purple"
            description = "Stock is oscillating around a mean — range-bound"
            strategy = "Mean-reversion: buy support, sell resistance, target VWAP/MA fills"

        return {
            "ticker": ticker.upper(),
            "regime": regime,
            "regime_color": regime_color,
            "description": description,
            "recommended_strategy": strategy,
            "confidence_pct": hmm_result.get("confidence", 0),
            "adx_proxy": round(adx_proxy, 1),
            "return_20d_pct": round(r20, 1),
            "return_60d_pct": round(r60, 1),
            "model": (
                "HMM-2state"
                if hmm_result.get("ok") and not hmm_result.get("error")
                else "heuristic"
            ),
        }
    except Exception as e:
        return {"error": f"Regime detection failed for {ticker}: {str(e)}"}


def _adx_proxy(hist: pd.DataFrame) -> float:
    """Approximate ADX-style trend strength from 14-day range data."""
    try:
        hi = hist["High"]
        lo = hist["Low"]
        cl = hist["Close"]
        tr = pd.concat([hi - lo, (hi - cl.shift()).abs(), (lo - cl.shift()).abs()], axis=1).max(
            axis=1
        )
        atr14 = tr.rolling(14).mean().iloc[-1]
        price_move = abs(float(cl.iloc[-1] - cl.iloc[-15]))
        return (price_move / atr14) * 10 if atr14 > 0 else 0
    except Exception:
        return 0
