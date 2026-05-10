from langchain_core.tools import tool
from app.tools._yf_client import get_ticker
import pandas as pd
import numpy as np


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
        mean_reverting_state = 1 - trending_state
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
            "model": "HMM-2state" if hmm_result.get("ok") and not hmm_result.get("error") else "heuristic",
        }
    except Exception as e:
        return {"error": f"Regime detection failed for {ticker}: {str(e)}"}


def _adx_proxy(hist: pd.DataFrame) -> float:
    """Approximate ADX-style trend strength from 14-day range data."""
    try:
        hi = hist["High"]
        lo = hist["Low"]
        cl = hist["Close"]
        tr = pd.concat([hi - lo, (hi - cl.shift()).abs(), (lo - cl.shift()).abs()], axis=1).max(axis=1)
        atr14 = tr.rolling(14).mean().iloc[-1]
        price_move = abs(float(cl.iloc[-1] - cl.iloc[-15]))
        return (price_move / atr14) * 10 if atr14 > 0 else 0
    except Exception:
        return 0
