import yfinance as yf
import pandas as pd
import numpy as np

# Representative S&P 500 proxy — 6 stocks per sector, 11 sectors
_PROXY_TICKERS = [
    # Technology
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AVGO",
    # Financials
    "JPM", "BAC", "GS", "V", "MA", "BRK-B",
    # Healthcare
    "UNH", "JNJ", "LLY", "ABBV", "MRK", "TMO",
    # Consumer Discretionary
    "AMZN", "TSLA", "HD", "MCD", "NKE", "BKNG",
    # Industrials
    "CAT", "HON", "UPS", "GE", "RTX", "DE",
    # Communication Services
    "NFLX", "DIS", "CMCSA", "T", "VZ", "CHTR",
    # Energy
    "XOM", "CVX", "COP", "SLB", "EOG", "OXY",
    # Consumer Staples
    "PG", "KO", "PEP", "WMT", "COST", "CL",
    # Utilities
    "NEE", "DUK", "SO", "D", "AEP", "EXC",
    # Materials
    "LIN", "APD", "SHW", "ECL", "NEM", "FCX",
    # Real Estate
    "AMT", "PLD", "CCI", "EQIX", "PSA", "O",
]


def get_market_breadth() -> dict:
    """
    Compute market breadth indicators using a 66-stock S&P 500 proxy.
    Returns % above 50d/200d MA, advance/decline, 52-week H/L counts.
    """
    try:
        raw = yf.download(
            _PROXY_TICKERS,
            period="1y",
            auto_adjust=True,
            progress=False,
            threads=True,
        )

        if raw.empty:
            return {"error": "Could not fetch breadth data"}

        closes = raw["Close"] if "Close" in raw.columns else raw.xs("Close", axis=1, level=0)
        closes = closes.dropna(how="all")

        if closes.empty:
            return {"error": "No valid close data for breadth calculation"}

        above_50 = 0
        above_200 = 0
        near_52w_high = 0
        near_52w_low = 0
        advancing = 0
        declining = 0
        valid = 0

        for col in closes.columns:
            s = closes[col].dropna()
            if len(s) < 50:
                continue
            valid += 1
            price = float(s.iloc[-1])
            ma50 = float(s.rolling(50).mean().iloc[-1])
            ma200 = float(s.rolling(200).mean().iloc[-1]) if len(s) >= 200 else None
            high52 = float(s.rolling(252).max().iloc[-1]) if len(s) >= 252 else float(s.max())
            low52 = float(s.rolling(252).min().iloc[-1]) if len(s) >= 252 else float(s.min())

            if price > ma50:
                above_50 += 1
            if ma200 and price > ma200:
                above_200 += 1
            if price >= high52 * 0.95:
                near_52w_high += 1
            if price <= low52 * 1.05:
                near_52w_low += 1

            # Advance/Decline: positive 5-day return = advancing
            if len(s) >= 5 and float(s.pct_change(5).iloc[-1]) > 0:
                advancing += 1
            else:
                declining += 1

        if valid == 0:
            return {"error": "No valid tickers for breadth calculation"}

        pct_above_50d = round(above_50 / valid * 100, 1)
        pct_above_200d = round(above_200 / valid * 100, 1) if above_200 else None
        ad_ratio = round(advancing / max(declining, 1), 2)

        # Breadth verdict
        if pct_above_50d >= 70 and ad_ratio >= 1.5:
            verdict = "BROAD RALLY"
            verdict_color = "green"
            signal = "Most stocks participating — healthy market structure"
        elif pct_above_50d >= 50:
            verdict = "MODERATE"
            verdict_color = "neutral"
            signal = "Mixed breadth — leadership narrow, select stocks working"
        elif pct_above_50d >= 30:
            verdict = "WEAKENING"
            verdict_color = "amber"
            signal = "Breadth deteriorating — defensive posture warranted"
        else:
            verdict = "BEARISH BREADTH"
            verdict_color = "red"
            signal = "Most stocks below 50d MA — avoid long exposure"

        return {
            "pct_above_50d": pct_above_50d,
            "pct_above_200d": pct_above_200d,
            "advancing": advancing,
            "declining": declining,
            "ad_ratio": ad_ratio,
            "new_highs_proxy": near_52w_high,
            "new_lows_proxy": near_52w_low,
            "stocks_measured": valid,
            "verdict": verdict,
            "verdict_color": verdict_color,
            "signal": signal,
        }
    except Exception as e:
        return {"error": f"Market breadth calculation failed: {str(e)}"}
