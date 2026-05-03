from langchain_core.tools import tool
from app.tools._yf_client import get_ticker
import pandas as pd
import numpy as np


def _garch_forecast(returns: pd.Series, horizon: int = 5) -> dict:
    try:
        from arch import arch_model
        scaled = returns * 100
        am = arch_model(scaled, vol="Garch", p=1, q=1, dist="Normal")
        res = am.fit(disp="off", show_warning=False)
        fc = res.forecast(horizon=horizon, reindex=False)
        var_h = fc.variance.iloc[-1].values
        vol_h = np.sqrt(var_h) / 100  # back to decimal
        return {"ok": True, "daily_vol": vol_h.tolist(), "annualized_vol": float(np.mean(vol_h) * np.sqrt(252))}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@tool
def get_volatility_forecast(ticker: str) -> dict:
    """
    GARCH(1,1) volatility forecast for the next 5 trading days.
    Returns expected daily price range and annualized volatility regime.
    """
    try:
        stock = get_ticker(ticker)
        hist = stock.history(period="2y")
        if hist.empty or len(hist) < 60:
            return {"error": f"Insufficient price history for {ticker}"}

        closes = hist["Close"].dropna()
        returns = closes.pct_change().dropna()
        current_price = float(closes.iloc[-1])

        garch = _garch_forecast(returns)
        if not garch.get("ok"):
            # Fallback: simple rolling std
            daily_vol = float(returns.rolling(20).std().iloc[-1])
            ann_vol = daily_vol * np.sqrt(252)
            daily_vols = [daily_vol] * 5
        else:
            daily_vols = garch["daily_vol"]
            ann_vol = garch["annualized_vol"]
            daily_vol = float(np.mean(daily_vols))

        # Build 5-day range forecast
        forecasts = []
        for i, v in enumerate(daily_vols, 1):
            half = current_price * v
            forecasts.append({
                "day": i,
                "expected_range_low": round(current_price - half, 2),
                "expected_range_high": round(current_price + half, 2),
                "daily_vol_pct": round(v * 100, 2),
            })

        ann_vol_pct = round(ann_vol * 100, 1)
        if ann_vol_pct < 20:
            regime = "LOW"
            regime_color = "green"
            regime_tip = "Calm — tighter stops acceptable"
        elif ann_vol_pct < 40:
            regime = "NORMAL"
            regime_color = "neutral"
            regime_tip = "Normal — standard position sizing"
        elif ann_vol_pct < 70:
            regime = "HIGH"
            regime_color = "amber"
            regime_tip = "Elevated — widen stops, reduce size"
        else:
            regime = "EXTREME"
            regime_color = "red"
            regime_tip = "Extreme — options play or sit out"

        # Historical realized vol context
        hist_20d = round(float(returns.rolling(20).std().iloc[-1]) * np.sqrt(252) * 100, 1)
        hist_60d = round(float(returns.rolling(60).std().iloc[-1]) * np.sqrt(252) * 100, 1)

        return {
            "ticker": ticker.upper(),
            "current_price": round(current_price, 2),
            "forecasts": forecasts,
            "annualized_vol_pct": ann_vol_pct,
            "realized_vol_20d_pct": hist_20d,
            "realized_vol_60d_pct": hist_60d,
            "vol_regime": regime,
            "vol_regime_color": regime_color,
            "vol_regime_tip": regime_tip,
            "model": "GARCH(1,1)" if garch.get("ok") else "rolling-std-fallback",
        }
    except Exception as e:
        return {"error": f"Volatility forecast failed for {ticker}: {str(e)}"}
