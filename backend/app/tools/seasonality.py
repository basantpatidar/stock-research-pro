from langchain_core.tools import tool
from app.tools._yf_client import get_ticker
from datetime import datetime


MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@tool
def get_seasonality(ticker: str) -> dict:
    """
    Compute 10-year monthly seasonality patterns for a stock.
    Shows average return and win rate for each calendar month.
    Useful for timing entries — e.g. 'July is positive 8/10 years.'
    """
    try:
        stock = get_ticker(ticker)
        hist = stock.history(period="10y")

        if hist.empty or len(hist) < 60:
            return {"error": f"Insufficient history for {ticker} seasonality analysis"}

        # Resample daily closes to end-of-month, then compute month-over-month %
        monthly = hist["Close"].resample("ME").last()
        monthly_returns = monthly.pct_change().dropna() * 100  # in %

        months = []
        for m in range(1, 13):
            mask = monthly_returns.index.month == m
            rets = monthly_returns[mask]

            if len(rets) == 0:
                months.append({
                    "month": MONTH_NAMES[m - 1],
                    "month_num": m,
                    "avg_return": None,
                    "positive_years": 0,
                    "total_years": 0,
                    "best_return": None,
                    "worst_return": None,
                })
                continue

            months.append({
                "month":          MONTH_NAMES[m - 1],
                "month_num":      m,
                "avg_return":     round(float(rets.mean()), 2),
                "positive_years": int((rets > 0).sum()),
                "total_years":    len(rets),
                "best_return":    round(float(rets.max()), 2),
                "worst_return":   round(float(rets.min()), 2),
            })

        years_span = (
            int(monthly_returns.index.year.max() - monthly_returns.index.year.min() + 1)
            if len(monthly_returns) > 0 else 0
        )

        # Best and worst months by average return
        valid = [mo for mo in months if mo["avg_return"] is not None]
        best  = max(valid, key=lambda x: x["avg_return"]) if valid else None
        worst = min(valid, key=lambda x: x["avg_return"]) if valid else None

        return {
            "ticker":        ticker.upper(),
            "months":        months,
            "current_month": datetime.now().month,
            "years_of_data": years_span,
            "best_month":    best,
            "worst_month":   worst,
        }
    except Exception as e:
        return {"error": f"Failed to compute seasonality for {ticker}: {str(e)}"}
