"""
Pre-Market Gap Scanner — Sprint 10.
Scans a list of tickers for pre/post-market gaps vs previous close.
Pure yfinance math, 0 tokens.
"""
from app.tools._yf_client import get_ticker
from datetime import datetime, timezone


def _float_class(float_shares: int | None) -> str:
    if not float_shares:
        return "unknown"
    if float_shares < 1_000_000:
        return "nano"
    if float_shares < 10_000_000:
        return "micro"
    if float_shares < 50_000_000:
        return "small"
    return "large"


def _gap_type(info: dict) -> str:
    """Classify gap cause: earnings, or no-catalyst."""
    ts = info.get("earningsTimestamp")
    if ts:
        now = datetime.now(timezone.utc).timestamp()
        # Earnings within last 24 h → earnings gap
        if abs(now - ts) < 86_400:
            return "earnings"
    return "no-catalyst"


def scan_gaps(tickers: list[str], threshold_pct: float = 2.0) -> dict:
    """
    For each ticker, compute pre/post-market gap vs previous close.
    Returns tickers gapping > threshold_pct, sorted by magnitude.
    """
    gaps = []

    for ticker in tickers:
        try:
            stock = get_ticker(ticker)
            info  = stock.info

            prev_close   = info.get("regularMarketPreviousClose") or info.get("previousClose")
            pre_price    = info.get("preMarketPrice")
            post_price   = info.get("postMarketPrice")
            market_state = info.get("marketState", "REGULAR")

            # Pick the most relevant extended-hours price
            if market_state in ("PRE", "PREPRE"):
                ext_price = pre_price
                session   = "pre-market"
            elif market_state in ("POST", "POSTPOST"):
                ext_price = post_price
                session   = "after-hours"
            else:
                ext_price = pre_price or post_price
                session   = "pre-market" if pre_price else "after-hours"

            if not ext_price or not prev_close or prev_close <= 0:
                continue

            gap_pct = round((ext_price - prev_close) / prev_close * 100, 2)
            if abs(gap_pct) < threshold_pct:
                continue

            # Volume ratio (today vs 10-day avg) — signal of unusual activity
            vol     = info.get("regularMarketVolume") or info.get("volume")
            avg_vol = info.get("averageVolume") or info.get("averageDailyVolume10Day")
            vol_ratio = round(vol / avg_vol, 2) if vol and avg_vol and avg_vol > 0 else None

            gaps.append({
                "ticker":           ticker.upper(),
                "company_name":     info.get("longName", ticker),
                "gap_pct":          gap_pct,
                "direction":        "up" if gap_pct > 0 else "down",
                "prev_close":       round(prev_close, 2),
                "ext_price":        round(ext_price, 2),
                "session":          session,
                "gap_type":         _gap_type(info),
                "float_shares":     info.get("floatShares"),
                "float_class":      _float_class(info.get("floatShares")),
                "vol_ratio":        vol_ratio,
                "market_cap":       info.get("marketCap"),
            })
        except Exception:
            continue

    gaps.sort(key=lambda x: abs(x["gap_pct"]), reverse=True)

    return {
        "gaps":          gaps,
        "scanned":       len(tickers),
        "threshold_pct": threshold_pct,
        "timestamp":     datetime.now(timezone.utc).isoformat(),
    }
