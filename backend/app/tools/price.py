from langchain_core.tools import tool
from app.tools._yf_client import get_ticker
from datetime import datetime


@tool
def get_price(ticker: str, period: str = "1y") -> dict:
    """
    Fetch current price, today's OHLCV, and historical price data for a stock.
    Period options: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y
    Returns current price, day high/low/open, volume, and price history.
    """
    try:
        stock = get_ticker(ticker)
        info = stock.info
        hist = stock.history(period=period)

        if hist.empty:
            quote_type = info.get("quoteType", "")
            if not quote_type:
                return {"error": f"Ticker '{ticker}' not found — check the symbol is correct"}
            return {"error": f"No price data for '{ticker}' — it may be delisted or have no recent trading activity"}

        current = hist["Close"].iloc[-1]
        prev_close = hist["Close"].iloc[-2] if len(hist) > 1 else current
        change_pct = ((current - prev_close) / prev_close) * 100

        # 7-day change
        week_ago = hist["Close"].iloc[-6] if len(hist) >= 7 else hist["Close"].iloc[0]
        week_change_pct = ((current - week_ago) / week_ago) * 100

        # Intraday 5-min candles for the 1d chart view
        intraday_history = []
        try:
            intraday = stock.history(period="1d", interval="5m")
            if not intraday.empty:
                intraday_history = [
                    {
                        "date": idx.isoformat(),
                        "close": round(row["Close"], 2),
                        "volume": int(row["Volume"]),
                        "high": round(row["High"], 2),
                        "low": round(row["Low"], 2),
                    }
                    for idx, row in intraday.iterrows()
                ]
        except Exception:
            pass

        return {
            "ticker": ticker.upper(),
            "current_price": round(current, 2),
            "previous_close": round(prev_close, 2),
            "change_pct_today": round(change_pct, 2),
            "change_pct_7d": round(week_change_pct, 2),
            "day_open": round(hist["Open"].iloc[-1], 2),
            "day_high": round(hist["High"].iloc[-1], 2),
            "day_low": round(hist["Low"].iloc[-1], 2),
            "volume": int(hist["Volume"].iloc[-1]),
            "avg_volume": int(hist["Volume"].mean()),
            "volume_ratio": round(hist["Volume"].iloc[-1] / hist["Volume"].mean(), 2),
            "company_name": info.get("longName", ticker),
            "market_cap": info.get("marketCap"),
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown"),
            "history_period": period,
            "history_points": len(hist),
            "intraday_history": intraday_history,
            "price_history": [
                {
                    "date": str(idx.date()),
                    "close": round(row["Close"], 2),
                    "volume": int(row["Volume"]),
                    "high": round(row["High"], 2),
                    "low": round(row["Low"], 2),
                }
                for idx, row in hist.iterrows()
            ],
        }
    except Exception as e:
        return {"error": f"Failed to fetch price for {ticker}: {str(e)}"}
