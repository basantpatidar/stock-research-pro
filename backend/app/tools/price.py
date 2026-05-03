from langchain_core.tools import tool
from app.tools._yf_client import get_ticker
from datetime import datetime
from zoneinfo import ZoneInfo


def _compute_rvol(current_volume: int, avg_volume: int, market_state: str) -> dict:
    """
    Time-normalized Relative Volume.
    RVOL = current_volume / (avg_daily_volume × fraction_of_session_elapsed)
    Only meaningful during regular market hours; returns raw ratio outside.
    """
    if avg_volume <= 0:
        return {"rvol": None, "signal": "N/A", "time_normalized": False}

    if market_state != "REGULAR":
        raw = round(current_volume / avg_volume, 2)
        return {"rvol": raw, "signal": "N/A — extended hours", "time_normalized": False}

    try:
        now = datetime.now(ZoneInfo("America/New_York"))
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        elapsed_min = max((now - market_open).total_seconds() / 60, 1.0)
        fraction = min(elapsed_min / 390.0, 1.0)   # 390 min = full 6.5-hr session
        expected = avg_volume * fraction
        rvol = round(current_volume / expected, 2) if expected > 0 else 1.0
    except Exception:
        rvol = round(current_volume / avg_volume, 2)
        return {"rvol": rvol, "signal": "N/A", "time_normalized": False}

    signal = (
        "EXTREME" if rvol > 3.0 else
        "HIGH"    if rvol > 2.0 else
        "NORMAL"  if rvol > 0.5 else
        "LOW"
    )
    return {"rvol": rvol, "signal": signal, "time_normalized": True}


def _compute_pivots(hist) -> dict | None:
    """Classic pivot points (P, R1, R2, S1, S2) from the previous session's H/L/C."""
    if len(hist) < 2:
        return None
    prev = hist.iloc[-2]
    H = float(prev["High"])
    L = float(prev["Low"])
    C = float(prev["Close"])
    P  = (H + L + C) / 3
    R1 = 2 * P - L
    R2 = P + (H - L)
    S1 = 2 * P - H
    S2 = P - (H - L)
    return {
        "P":  round(P,  2),
        "R1": round(R1, 2),
        "R2": round(R2, 2),
        "S1": round(S1, 2),
        "S2": round(S2, 2),
    }


def _compute_support_resistance(hist, lookback: int = 30) -> dict:
    """Key S/R levels from swing highs/lows over the recent lookback period."""
    if len(hist) < 5:
        return {"resistance": [], "support": []}

    recent = hist.tail(lookback)
    highs  = recent["High"].values.astype(float)
    lows   = recent["Low"].values.astype(float)

    swing_highs, swing_lows = [], []
    for i in range(2, len(highs) - 2):
        if highs[i] >= highs[i-1] and highs[i] >= highs[i+1] and highs[i] >= highs[i-2] and highs[i] >= highs[i+2]:
            swing_highs.append(round(highs[i], 2))
    for i in range(2, len(lows) - 2):
        if lows[i] <= lows[i-1] and lows[i] <= lows[i+1] and lows[i] <= lows[i-2] and lows[i] <= lows[i+2]:
            swing_lows.append(round(lows[i], 2))

    def _dedup(levels: list[float], tol: float = 0.005) -> list[float]:
        if not levels:
            return []
        merged = [sorted(levels)[0]]
        for lvl in sorted(levels)[1:]:
            if (lvl - merged[-1]) / merged[-1] > tol:
                merged.append(lvl)
        return merged

    resistance = sorted(_dedup(swing_highs), reverse=True)[:3]
    support    = sorted(_dedup(swing_lows))[:3]
    return {"resistance": resistance, "support": support}


def _compute_orb(intraday_df) -> dict | None:
    """Opening Range Breakout — 15-min (3 × 5m) and 30-min (6 × 5m) levels."""
    try:
        if intraday_df is None or intraday_df.empty:
            return None

        et = ZoneInfo("America/New_York")
        df = intraday_df.copy()
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC").tz_convert(et)
        else:
            df.index = df.index.tz_convert(et)

        # Regular session only: 9:30 AM – 4:00 PM ET
        regular = df[
            ((df.index.hour == 9) & (df.index.minute >= 30)) |
            ((df.index.hour >= 10) & (df.index.hour < 16))
        ]

        if len(regular) < 3:
            return None

        current_price = float(df["Close"].iloc[-1])
        avg_vol = float(regular["Volume"].mean()) if len(regular) > 0 else 1.0

        def _orb_stats(bars, post_bars):
            high = round(float(bars["High"].max()), 2)
            low  = round(float(bars["Low"].min()), 2)
            position = (
                "above" if current_price > high else
                "below" if current_price < low  else
                "inside"
            )
            breakout = "none"
            if len(post_bars) > 0:
                if ((post_bars["Close"] > high) & (post_bars["Volume"] > avg_vol)).any():
                    breakout = "above"
                elif ((post_bars["Close"] < low) & (post_bars["Volume"] > avg_vol)).any():
                    breakout = "below"
            return {"high": high, "low": low, "position": position, "breakout": breakout}

        return {
            "orb_15": _orb_stats(regular.head(3), regular.iloc[3:]),
            "orb_30": _orb_stats(regular.head(6), regular.iloc[6:]),
        }
    except Exception:
        return None


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
        intraday_df = None
        intraday_history = []
        intraday_last = None
        try:
            intraday = stock.history(period="1d", interval="5m", prepost=True)
            if not intraday.empty:
                intraday_df = intraday
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

        volume_profile     = _compute_volume_profile(hist)
        pivots             = _compute_pivots(hist)
        support_resistance = _compute_support_resistance(hist)
        orb                = _compute_orb(intraday_df)

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
            "rvol": _compute_rvol(int(hist["Volume"].iloc[-1]), int(hist["Volume"].mean()), market_state),
            "company_name": info.get("longName", ticker),
            "market_cap": info.get("marketCap"),
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown"),
            "volume_profile": volume_profile,
            "pivots": pivots,
            "support_resistance": support_resistance,
            "orb": orb,
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
