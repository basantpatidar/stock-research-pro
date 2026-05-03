from langchain_core.tools import tool
from app.tools._yf_client import get_ticker
import pandas as pd
import numpy as np


@tool
def get_vcp_pattern(ticker: str) -> dict:
    """
    Minervini Volatility Contraction Pattern (VCP) + Stage 2 trend template detector.
    Checks 5 criteria: above key MAs, proximity to 52w high/low, RS rating, volatility contraction.
    """
    try:
        stock = get_ticker(ticker)
        hist = stock.history(period="1y")

        if hist.empty or len(hist) < 60:
            return {"error": f"Insufficient history for VCP analysis on {ticker}"}

        closes = hist["Close"].dropna()
        highs = hist["High"].dropna()
        lows = hist["Low"].dropna()
        current = float(closes.iloc[-1])

        # MAs
        ma150 = float(closes.rolling(150).mean().iloc[-1]) if len(closes) >= 150 else None
        ma200 = float(closes.rolling(200).mean().iloc[-1]) if len(closes) >= 200 else None
        ma50 = float(closes.rolling(50).mean().iloc[-1])

        # 52-week high / low
        high_52w = float(closes.rolling(252, min_periods=50).max().iloc[-1])
        low_52w = float(closes.rolling(252, min_periods=50).min().iloc[-1])

        pct_from_high = (high_52w - current) / high_52w * 100
        pct_above_low = (current - low_52w) / low_52w * 100

        criteria = {}

        # 1. Stage 2 uptrend: price > 150d > 200d SMA
        stage2 = ma150 and ma200 and current > ma150 and ma150 > ma200
        criteria["stage2_uptrend"] = {
            "pass": bool(stage2),
            "label": "Stage 2 Uptrend (Price > 150d > 200d SMA)",
            "detail": (
                f"Price ${current:.2f} vs 150d ${ma150:.2f} vs 200d ${ma200:.2f}"
                if ma150 and ma200 else "Insufficient data for 200d MA"
            ),
        }

        # 2. 52-week low ≥ 30% below current (has recovered from base)
        recovered = pct_above_low >= 30
        criteria["above_52w_low"] = {
            "pass": recovered,
            "label": "52-Week Low ≥30% Below Current",
            "detail": f"52w low: ${low_52w:.2f} — {pct_above_low:.0f}% below current (need ≥30%)",
        }

        # 3. Within 25% of 52-week high
        near_high = pct_from_high <= 25
        criteria["near_52w_high"] = {
            "pass": near_high,
            "label": "Price Within 25% of 52-Week High",
            "detail": f"52w high: ${high_52w:.2f} — {pct_from_high:.1f}% below high (need ≤25%)",
        }

        # 4. RS Rating > 70 (SPY-relative 52w performance proxy)
        rs_pass = None
        rs_detail = "RS not computed"
        try:
            import yfinance as yf
            spy = yf.Ticker("SPY").history(period="1y")["Close"]
            stk_ret = float(closes.pct_change(252).dropna().iloc[-1]) if len(closes) >= 252 else float(closes.pct_change(len(closes)-1).iloc[-1])
            spy_ret = float(spy.pct_change(252).dropna().iloc[-1]) if len(spy) >= 252 else float(spy.pct_change(len(spy)-1).iloc[-1])
            rs_proxy = min(99, max(0, int(50 + (stk_ret - spy_ret) * 100)))
            rs_pass = rs_proxy >= 70
            rs_detail = f"RS proxy: {rs_proxy}/99 (need ≥70)"
        except Exception:
            pass
        criteria["rs_rating"] = {"pass": rs_pass, "label": "RS Rating ≥70", "detail": rs_detail}

        # 5. Volatility contraction — recent ATR contracting vs earlier
        vcp_pass = None
        vcp_detail = "Not enough data"
        contraction_count = 0
        try:
            tr = pd.concat([
                highs - lows,
                (highs - closes.shift()).abs(),
                (lows - closes.shift()).abs(),
            ], axis=1).max(axis=1)
            atr_recent = float(tr.rolling(10).mean().iloc[-1])
            atr_mid = float(tr.rolling(10).mean().iloc[-20])
            atr_early = float(tr.rolling(10).mean().iloc[-40]) if len(tr) >= 40 else atr_mid
            contracting = atr_recent < atr_mid < atr_early
            vcp_pass = contracting
            pct_contract = (atr_early - atr_recent) / atr_early * 100 if atr_early > 0 else 0
            vcp_detail = f"ATR contracting {'✓' if contracting else '✗'} — {pct_contract:.0f}% compression from 40d ago"
            contraction_count = sum([atr_recent < atr_mid, atr_mid < atr_early])
        except Exception:
            pass
        criteria["vol_contraction"] = {
            "pass": vcp_pass,
            "label": "Volatility Contracting (Tight Coil)",
            "detail": vcp_detail,
            "contractions": contraction_count,
        }

        passed = sum(1 for c in criteria.values() if c.get("pass") is True)

        if passed == 5:
            verdict = "VCP SETUP — HIGH QUALITY"
            verdict_color = "green"
            setup_quality = "A+"
        elif passed >= 4:
            verdict = "PARTIAL VCP — WATCHLIST"
            verdict_color = "amber"
            setup_quality = "B"
        elif passed >= 3:
            verdict = "DEVELOPING — NOT READY"
            verdict_color = "amber"
            setup_quality = "C"
        else:
            verdict = "NO SETUP"
            verdict_color = "red"
            setup_quality = "F"

        return {
            "ticker": ticker.upper(),
            "verdict": verdict,
            "verdict_color": verdict_color,
            "setup_quality": setup_quality,
            "criteria_passed": passed,
            "criteria_total": 5,
            "criteria": criteria,
            "current_price": round(current, 2),
            "ma50": round(ma50, 2),
            "ma150": round(ma150, 2) if ma150 else None,
            "ma200": round(ma200, 2) if ma200 else None,
            "high_52w": round(high_52w, 2),
            "low_52w": round(low_52w, 2),
        }
    except Exception as e:
        return {"error": f"VCP pattern detection failed for {ticker}: {str(e)}"}
