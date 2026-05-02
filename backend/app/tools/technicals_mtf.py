from langchain_core.tools import tool
from app.tools._yf_client import get_ticker
from app.tools.technicals import _compute_rsi, _compute_macd
import pandas as pd


# Weight allocation mirrors how day traders prioritize timeframes:
# daily trend > hourly momentum > 15m setup > 5m entry
_TIMEFRAMES = {
    "5m":  {"period": "1d",  "interval": "5m",  "weight": 0.10},
    "15m": {"period": "5d",  "interval": "15m", "weight": 0.20},
    "1h":  {"period": "30d", "interval": "1h",  "weight": 0.30},
    "1d":  {"period": "1y",  "interval": "1d",  "weight": 0.40},
}


def _analyze_timeframe(hist: pd.DataFrame) -> dict | None:
    if hist.empty or len(hist) < 15:
        return None

    close = hist["Close"]

    rsi = _compute_rsi(close)
    rsi_bullish = rsi > 50.0

    macd = _compute_macd(close)
    macd_bullish = macd["crossover"] == "bullish"

    # Rolling VWAP (20-period typical price weighted by volume)
    typical = (hist["High"] + hist["Low"] + hist["Close"]) / 3
    rolling_vol = hist["Volume"].rolling(20).sum()
    vwap = ((typical * hist["Volume"]).rolling(20).sum() / rolling_vol).iloc[-1]
    price_above_vwap = float(close.iloc[-1]) > float(vwap)

    bullish_count = sum([rsi_bullish, macd_bullish, price_above_vwap])
    direction = "BULLISH" if bullish_count >= 2 else ("NEUTRAL" if bullish_count == 1 else "BEARISH")

    return {
        "direction": direction,
        "bullish_signals": bullish_count,
        "total_signals": 3,
        "rsi": round(rsi, 1),
        "rsi_bullish": bool(rsi_bullish),
        "macd_bullish": bool(macd_bullish),
        "price_above_vwap": bool(price_above_vwap),
        "score": round(bullish_count / 3, 4),
    }


@tool
def get_mtf_confluence(ticker: str) -> dict:
    """
    Multi-timeframe confluence analysis across 5m, 15m, 1h, and 1d.
    Checks RSI, MACD crossover, and price vs VWAP on each timeframe.
    Returns a weighted 0-100 score: >70 = strong bullish alignment.
    0 LLM tokens — pure computation from yfinance data.
    """
    try:
        stock = get_ticker(ticker)
        results: dict[str, dict] = {}
        weighted_score = 0.0
        valid_weight = 0.0

        for tf, cfg in _TIMEFRAMES.items():
            try:
                hist = stock.history(period=cfg["period"], interval=cfg["interval"])
                analysis = _analyze_timeframe(hist)
                if analysis:
                    results[tf] = analysis
                    weighted_score += analysis["score"] * cfg["weight"]
                    valid_weight += cfg["weight"]
                else:
                    results[tf] = {"direction": "INSUFFICIENT_DATA", "bullish_signals": 0, "score": 0.0}
            except Exception:
                results[tf] = {"direction": "ERROR", "bullish_signals": 0, "score": 0.0}

        final_score = round((weighted_score / valid_weight * 100) if valid_weight > 0 else 50.0, 1)

        label = (
            "STRONG BULL" if final_score >= 75 else
            "BULL"        if final_score >= 55 else
            "NEUTRAL"     if final_score >= 45 else
            "BEAR"        if final_score >= 25 else
            "STRONG BEAR"
        )

        valid = {tf: r for tf, r in results.items() if r.get("direction") not in ("ERROR", "INSUFFICIENT_DATA")}
        bullish_tfs  = [tf for tf, r in valid.items() if r["direction"] == "BULLISH"]
        bearish_tfs  = [tf for tf, r in valid.items() if r["direction"] == "BEARISH"]
        neutral_tfs  = [tf for tf, r in valid.items() if r["direction"] == "NEUTRAL"]

        if len(bullish_tfs) == len(valid) and valid:
            alignment = "All timeframes aligned bullish — high conviction long setup"
        elif len(bearish_tfs) == len(valid) and valid:
            alignment = "All timeframes aligned bearish — avoid long entries"
        else:
            parts = []
            if bullish_tfs: parts.append(f"{', '.join(bullish_tfs)} bullish")
            if neutral_tfs: parts.append(f"{', '.join(neutral_tfs)} neutral")
            if bearish_tfs: parts.append(f"{', '.join(bearish_tfs)} bearish")
            alignment = " · ".join(parts) if parts else "Insufficient data"

        return {
            "ticker": ticker.upper(),
            "confluence_score": final_score,
            "label": label,
            "alignment": alignment,
            "timeframes": results,
        }
    except Exception as e:
        return {"error": f"Failed to compute MTF confluence for {ticker}: {str(e)}"}
