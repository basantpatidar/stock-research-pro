from langchain_core.tools import tool
from app.tools._yf_client import get_ticker
import pandas as pd
import numpy as np


def _compute_rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2)


def _compute_macd(series: pd.Series):
    ema12 = series.ewm(span=12).mean()
    ema26 = series.ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    histogram = macd - signal
    return {
        "macd": round(float(macd.iloc[-1]), 4),
        "signal": round(float(signal.iloc[-1]), 4),
        "histogram": round(float(histogram.iloc[-1]), 4),
        "crossover": "bullish" if macd.iloc[-1] > signal.iloc[-1] else "bearish",
    }


def _compute_bollinger(series: pd.Series, period: int = 20):
    sma = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = sma + (2 * std)
    lower = sma - (2 * std)
    current_price = series.iloc[-1]
    band_width = float(upper.iloc[-1] - lower.iloc[-1])
    position = (current_price - float(lower.iloc[-1])) / band_width if band_width > 0 else 0.5
    return {
        "upper": round(float(upper.iloc[-1]), 2),
        "middle": round(float(sma.iloc[-1]), 2),
        "lower": round(float(lower.iloc[-1]), 2),
        "position": round(position, 2),
        "interpretation": (
            "near upper band — overbought territory" if position > 0.8
            else "near lower band — oversold territory" if position < 0.2
            else "middle of bands — neutral"
        ),
    }


def _detect_ma_crossover(close: pd.Series):
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()
    if len(close) < 200:
        return {"status": "insufficient data for 200d MA"}
    current_ma50 = float(ma50.iloc[-1])
    current_ma200 = float(ma200.iloc[-1])
    prev_ma50 = float(ma50.iloc[-2])
    prev_ma200 = float(ma200.iloc[-2])

    if prev_ma50 <= prev_ma200 and current_ma50 > current_ma200:
        crossover = "golden_cross"
        meaning = "Bullish — 50d MA just crossed above 200d MA"
    elif prev_ma50 >= prev_ma200 and current_ma50 < current_ma200:
        crossover = "death_cross"
        meaning = "Bearish — 50d MA just crossed below 200d MA"
    elif current_ma50 > current_ma200:
        crossover = "above_200d"
        meaning = "Bullish — price trading above 200d MA"
    else:
        crossover = "below_200d"
        meaning = "Bearish — price trading below 200d MA"

    return {
        "ma_50d": round(current_ma50, 2),
        "ma_200d": round(current_ma200, 2),
        "crossover": crossover,
        "meaning": meaning,
    }


def _compute_rs_rating(stock_hist, spy_hist) -> dict | None:
    """
    IBD-style RS Rating (1–99) vs S&P 500.
    Weighted 52-week performance: recent quarter counts 2×.
    Formula: (Q1*2 + Q2 + Q3 + Q4) / 5, then normalised vs SPY.
    NOTE: true IBD ranks against ~3 000 stocks; this approximates
    using SPY as the baseline (50 = inline with SPY).
    """
    def _weighted(hist) -> float | None:
        if len(hist) < 252:
            return None
        c = hist["Close"]
        # 63 trading days ≈ 1 quarter
        q1 = float(c.iloc[-1]   / c.iloc[-64]  - 1) * 100
        q2 = float(c.iloc[-64]  / c.iloc[-127] - 1) * 100
        q3 = float(c.iloc[-127] / c.iloc[-190] - 1) * 100
        q4 = float(c.iloc[-190] / c.iloc[-252] - 1) * 100
        return (q1 * 2 + q2 + q3 + q4) / 5

    stock_score = _weighted(stock_hist)
    spy_score   = _weighted(spy_hist)
    if stock_score is None or spy_score is None:
        return None

    raw = stock_score - spy_score
    # Each 0.5 percentage point of outperformance = 1 RS point above 50
    rs  = max(1, min(99, round(50 + raw * 2)))

    signal = (
        "Top performer — strong relative strength" if rs >= 80 else
        "Above market average"                     if rs >= 60 else
        "In line with market"                      if rs >= 40 else
        "Underperforming market"
    )
    return {"rs_rating": rs, "rs_signal": signal}


@tool
def get_technicals(ticker: str) -> dict:
    """
    Compute technical indicators for a stock: RSI, MACD, Bollinger Bands,
    VWAP, 50d/200d moving averages, and golden/death cross detection.
    Essential for day trade and short-term swing trade decisions.
    """
    try:
        stock = get_ticker(ticker)
        hist = stock.history(period="1y")

        if hist.empty or len(hist) < 30:
            return {"error": f"Insufficient history for {ticker} technical analysis"}

        # Fetch SPY for RS rating — lightweight, well-cached by yfinance
        try:
            spy_hist = get_ticker("SPY").history(period="1y")
        except Exception:
            spy_hist = None

        close = hist["Close"]
        volume = hist["Volume"]

        # VWAP (rolling 20-day approximation)
        typical_price = (hist["High"] + hist["Low"] + hist["Close"]) / 3
        vwap_series = (typical_price * volume).rolling(20).sum() / volume.rolling(20).sum()
        vwap = float(vwap_series.iloc[-1])

        rsi = _compute_rsi(close)
        rsi_signal = (
            "oversold — potential buy signal" if rsi < 30
            else "overbought — potential sell signal" if rsi > 70
            else "neutral range"
        )

        rs = _compute_rs_rating(hist, spy_hist) if spy_hist is not None and not spy_hist.empty else None

        return {
            "ticker": ticker.upper(),
            "rsi_14": rsi,
            "rsi_signal": rsi_signal,
            "macd": _compute_macd(close),
            "bollinger_bands": _compute_bollinger(close),
            "moving_averages": _detect_ma_crossover(close),
            "vwap_20d": round(vwap, 2),
            "current_price": round(float(close.iloc[-1]), 2),
            "price_vs_vwap": "above VWAP" if close.iloc[-1] > vwap else "below VWAP",
            "volume_trend": {
                "today": int(volume.iloc[-1]),
                "avg_20d": int(volume.rolling(20).mean().iloc[-1]),
                "above_average": bool(volume.iloc[-1] > volume.rolling(20).mean().iloc[-1]),
            },
            "rs_rating": rs["rs_rating"] if rs else None,
            "rs_signal":  rs["rs_signal"]  if rs else None,
        }
    except Exception as e:
        return {"error": f"Failed to compute technicals for {ticker}: {str(e)}"}
