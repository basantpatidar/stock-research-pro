from langchain_core.tools import tool

from app.tools._yf_client import get_ticker


@tool
def bull_bear_debate(ticker: str) -> dict:
    """
    Generate a structured Bull vs Bear debate for a stock.
    Returns fundamental and technical data with instructions for the agent to
    argue both sides and render a judge verdict with a final recommendation.
    """
    try:
        stock = get_ticker(ticker)
        info = stock.info
        hist = stock.history(period="6mo")

        if hist.empty:
            return {"error": f"No data for {ticker}"}

        close = hist["Close"]
        current = round(float(close.iloc[-1]), 2)

        # RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rsi = round(float((100 - (100 / (1 + gain / loss))).iloc[-1]), 1)

        # MACD
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9).mean()
        macd_signal = "bullish" if float(macd.iloc[-1]) > float(signal.iloc[-1]) else "bearish"

        # 50d / 200d MA
        ma50 = round(float(close.rolling(50).mean().iloc[-1]), 2) if len(close) >= 50 else None
        ma200 = round(float(close.rolling(200).mean().iloc[-1]), 2) if len(close) >= 200 else None

        # 6-month performance
        perf_6m = round((current - float(close.iloc[0])) / float(close.iloc[0]) * 100, 1)

        # Volume trend
        avg_vol_30d = int(hist["Volume"].tail(30).mean())
        recent_vol = int(hist["Volume"].tail(5).mean())
        volume_trend = (
            "rising"
            if recent_vol > avg_vol_30d * 1.1
            else "falling" if recent_vol < avg_vol_30d * 0.9 else "stable"
        )

        data = {
            "ticker": ticker.upper(),
            "company_name": info.get("longName", ticker.upper()),
            "sector": info.get("sector", "Unknown"),
            "current_price": current,
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "profit_margin": info.get("profitMargins"),
            "debt_to_equity": info.get("debtToEquity"),
            "free_cashflow": info.get("freeCashflow"),
            "analyst_target": info.get("targetMeanPrice"),
            "analyst_recommendation": info.get("recommendationKey"),
            "short_float": info.get("shortPercentOfFloat"),
            "beta": info.get("beta"),
            "rsi_14": rsi,
            "macd_signal": macd_signal,
            "ma50": ma50,
            "ma200": ma200,
            "above_ma50": current > ma50 if ma50 else None,
            "above_ma200": current > ma200 if ma200 else None,
            "perf_6m_pct": perf_6m,
            "volume_trend": volume_trend,
        }

        return {
            "ticker": ticker.upper(),
            "data": data,
            "debate_instructions": {
                "bull_case": (
                    f"Argue the strongest possible BULL case for {ticker.upper()} in 3 concise bullet points. "
                    f"Focus on: growth catalysts, competitive advantages, undervaluation, and technical momentum. "
                    f"Be specific — use the data provided. No generic statements."
                ),
                "bear_case": (
                    f"Argue the strongest possible BEAR case for {ticker.upper()} in 3 concise bullet points. "
                    f"Focus on: valuation risk, competitive threats, macro headwinds, and technical weakness. "
                    f"Be specific — use the data provided. No generic statements."
                ),
                "judge_verdict": (
                    f"As an impartial judge, weigh the bull and bear arguments for {ticker.upper()}. "
                    f"State which side is stronger and why. "
                    f"Give a final recommendation: STRONG BUY / BUY / HOLD / SELL / STRONG SELL "
                    f"with a 12-month price target and the single biggest risk to your thesis."
                ),
            },
        }
    except Exception as e:
        return {"error": f"Failed to run bull/bear debate for {ticker}: {str(e)}"}
