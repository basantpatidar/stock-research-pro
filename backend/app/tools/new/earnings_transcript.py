from datetime import datetime

from langchain_core.tools import tool

from app.tools._yf_client import get_ticker


@tool
def analyze_earnings_transcript(ticker: str) -> dict:
    """
    Analyze the most recent earnings call for a stock.
    Fetches earnings history, guidance signals, and revenue/EPS beat/miss data.
    Returns structured data and instructions for the agent to infer management tone,
    key risks, forward guidance quality, and a trade implication.
    """
    try:
        stock = get_ticker(ticker)
        info = stock.info

        # Earnings history
        try:
            earnings_hist = stock.earnings_history
            recent_quarters = []
            if earnings_hist is not None and not earnings_hist.empty:
                for _, row in earnings_hist.tail(8).iterrows():
                    actual = row.get("epsActual")
                    estimate = row.get("epsEstimate")
                    surprise = row.get("epsDifference")
                    surprise_pct = row.get("surprisePercent")
                    period = row.get("period") if hasattr(row, "get") else None
                    recent_quarters.append(
                        {
                            "period": str(period) if period else None,
                            "eps_actual": round(float(actual), 3) if actual else None,
                            "eps_estimate": round(float(estimate), 3) if estimate else None,
                            "eps_surprise": round(float(surprise), 3) if surprise else None,
                            "eps_surprise_pct": (
                                round(float(surprise_pct) * 100, 1) if surprise_pct else None
                            ),
                            "beat": float(surprise) > 0 if surprise else None,
                        }
                    )
        except Exception:
            recent_quarters = []

        # Revenue trend
        try:
            financials = stock.quarterly_financials
            rev_trend = []
            if (
                financials is not None
                and not financials.empty
                and "Total Revenue" in financials.index
            ):
                rev_row = financials.loc["Total Revenue"]
                for col in list(rev_row.index)[:4]:
                    val = rev_row[col]
                    if val and not (
                        hasattr(val, "__float__") and __import__("math").isnan(float(val))
                    ):
                        rev_trend.append(
                            {
                                "quarter": str(col.date()) if hasattr(col, "date") else str(col),
                                "revenue": int(float(val)),
                            }
                        )
        except Exception:
            rev_trend = []

        # Next earnings date
        next_earnings = info.get("earningsTimestamp")
        if next_earnings:
            try:
                next_earnings = datetime.utcfromtimestamp(next_earnings).strftime("%Y-%m-%d")
            except Exception:
                next_earnings = None

        consecutive_beats = 0
        if recent_quarters:
            for q in reversed(recent_quarters):
                if q.get("beat"):
                    consecutive_beats += 1
                else:
                    break

        data = {
            "ticker": ticker.upper(),
            "company_name": info.get("longName", ticker.upper()),
            "next_earnings_date": next_earnings,
            "recent_quarters": recent_quarters,
            "consecutive_beats": consecutive_beats,
            "revenue_trend": rev_trend,
            "annual_revenue": info.get("totalRevenue"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "profit_margin": info.get("profitMargins"),
            "forward_pe": info.get("forwardPE"),
            "trailing_pe": info.get("trailingPE"),
            "analyst_target": info.get("targetMeanPrice"),
            "analyst_recommendation": info.get("recommendationKey"),
            "guidance_eps_current_year": info.get("earningsCurrentYear"),
            "guidance_eps_next_year": info.get("earningsNextYear"),
        }

        return {
            "ticker": ticker.upper(),
            "data": data,
            "analysis_instructions": {
                "management_tone": (
                    f"Based on {ticker.upper()}'s recent earnings track record "
                    f"({consecutive_beats} consecutive beats, revenue trend: {[r.get('revenue') for r in rev_trend]}), "
                    f"infer management tone: confident/cautious/defensive. "
                    f"Explain what signals in the data support your assessment."
                ),
                "guidance_quality": (
                    f"Evaluate the forward guidance quality for {ticker.upper()}. "
                    f"Is forward EPS growth realistic given current revenue growth of {info.get('revenueGrowth')}? "
                    f"Is the forward P/E of {info.get('forwardPE')} justified? "
                    f"Rate guidance as: beat-and-raise, in-line, or reduced-expectations."
                ),
                "key_risks": (
                    f"Identify 2-3 key risks that could cause {ticker.upper()} to miss next quarter. "
                    f"Focus on: margin compression, revenue deceleration, macro headwinds, or competitive pressure."
                ),
                "trade_implication": (
                    f"Given the earnings history and guidance, what is the trade setup for {ticker.upper()} "
                    f"into the next earnings date ({next_earnings or 'upcoming'})? "
                    f"Is this a buy-the-dip, hold, trim, or avoid situation? "
                    f"Specify entry, risk level, and what would invalidate the thesis."
                ),
            },
        }
    except Exception as e:
        return {"error": f"Failed to analyze earnings for {ticker}: {str(e)}"}
