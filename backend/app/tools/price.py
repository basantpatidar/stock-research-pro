from langchain_core.tools import tool
from app.tools._yf_client import get_ticker
from datetime import datetime


def _compute_volume_profile(hist, n_bins: int = 100) -> dict | None:
    """
    Compute VPOC, VAH, VAL from daily OHLCV data.
    Uses typical price ((H+L+C)/3) weighted by volume for accurate price-volume distribution.
    """
    try:
        if len(hist) < 20:
            return None

        highs   = hist["High"].values.astype(float)
        lows    = hist["Low"].values.astype(float)
        closes  = hist["Close"].values.astype(float)
        volumes = hist["Volume"].values.astype(float)

        # Typical price for each bar
        typical = (highs + lows + closes) / 3.0
        p_min, p_max = typical.min(), typical.max()
        price_range = p_max - p_min

        if price_range < 0.01:
            return None

        bin_size = price_range / n_bins
        bins: dict[int, float] = {}

        for tp, vol in zip(typical, volumes):
            idx = min(int((tp - p_min) / bin_size), n_bins - 1)
            bins[idx] = bins.get(idx, 0.0) + vol

        if not bins:
            return None

        # VPOC — bin with highest volume
        vpoc_idx = max(bins, key=lambda k: bins[k])
        vpoc = round(p_min + (vpoc_idx + 0.5) * bin_size, 2)

        # Value area: 70% of total volume, expanding from VPOC
        total_vol = sum(bins.values())
        target    = total_vol * 0.70
        sorted_by_vol = sorted(bins.items(), key=lambda x: x[1], reverse=True)
        va_indices: set[int] = set()
        accumulated = 0.0
        for idx, vol in sorted_by_vol:
            va_indices.add(idx)
            accumulated += vol
            if accumulated >= target:
                break

        vah_idx = max(va_indices)
        val_idx = min(va_indices)
        vah = round(p_min + (vah_idx + 0.5) * bin_size, 2)
        val = round(p_min + (val_idx + 0.5) * bin_size, 2)

        # HVN levels: top-volume bins excluding those in the value area (act as support/resistance)
        hvn_candidates = [
            round(p_min + (idx + 0.5) * bin_size, 2)
            for idx, _ in sorted_by_vol[:10]
            if idx not in va_indices
        ]
        hvn_levels = sorted(hvn_candidates[:4])

        return {
            "vpoc": vpoc,
            "vah":  vah,
            "val":  val,
            "hvn_levels": hvn_levels,
            "period_days": len(hist),
        }
    except Exception:
        return None


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

        regular_close = hist["Close"].iloc[-1]
        prev_close = hist["Close"].iloc[-2] if len(hist) > 1 else regular_close

        # 7-day change
        week_ago = hist["Close"].iloc[-6] if len(hist) >= 7 else hist["Close"].iloc[0]
        week_change_pct = ((regular_close - week_ago) / week_ago) * 100

        # Intraday 5-min candles (prepost=True covers pre-market + after-hours)
        # Fetch first so we can use its last price as current when in extended session
        intraday_history = []
        intraday_last = None
        try:
            intraday = stock.history(period="1d", interval="5m", prepost=True)
            if not intraday.empty:
                intraday_last = round(float(intraday["Close"].iloc[-1]), 2)
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

        # marketState: REGULAR | PRE | POST | CLOSED | PREPRE | POSTPOST
        market_state = info.get("marketState", "REGULAR")
        in_extended = market_state in ("PRE", "PREPRE", "POST", "POSTPOST")

        # Show the live extended-hours price when outside regular session
        current = intraday_last if (in_extended and intraday_last is not None) else regular_close
        change_pct = ((current - prev_close) / prev_close) * 100
        extended_change_pct = (
            round((current - regular_close) / regular_close * 100, 2)
            if in_extended and regular_close > 0 else None
        )

        volume_profile = _compute_volume_profile(hist)

        return {
            "ticker": ticker.upper(),
            "current_price": round(current, 2),
            "regular_close": round(regular_close, 2),
            "market_state": market_state,
            "extended_change_pct": extended_change_pct,
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
            "volume_profile": volume_profile,
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
