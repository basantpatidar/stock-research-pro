"""
Market Context First (MCF) Funnel Scanner
Implements the 3-layer funnel strategy: Weather, Tide, and Setup.
"""

import logging
from datetime import datetime

import pytz
import yfinance as yf

from app.tools.dip_scanner import _compute_intraday_vwap, _get_atr_5m

logger = logging.getLogger(__name__)
ET_TZ = pytz.timezone("America/New_York")

MCF_TIER_1_ETFS = ["SPY", "QQQ", "IWM", "DIA"]


def _get_weather() -> dict:
    """
    Layer 1: Weather (Daily trend + VIX)
    """
    weather = {"spy_trend": "neutral", "vix": 20.0, "status": "pass"}

    try:
        # Fetch SPY Daily
        spy = yf.Ticker("SPY").history(period="1mo", interval="1d")
        if not spy.empty and len(spy) >= 20:
            closes = spy["Close"].values
            ema_20 = sum(closes[-20:]) / 20.0  # Simple approx for EMA/SMA
            current_spy = closes[-1]
            weather["spy_trend"] = "bullish" if current_spy > ema_20 else "bearish"

        # Fetch VIX
        vix_data = yf.Ticker("^VIX").history(period="1d")
        if not vix_data.empty:
            weather["vix"] = round(float(vix_data["Close"].iloc[-1]), 2)

        # Disable if SPY is in a deep downtrend or VIX is apocalyptic
        if weather["spy_trend"] == "bearish" and weather["vix"] > 30:
            weather["status"] = "fail"

    except Exception as exc:
        logger.warning("MCF _get_weather failed: %s", exc)
        weather["status"] = "error"

    return weather


def _get_tide(loose: bool = False) -> dict:
    """
    Layer 2: Tide (Intraday breadth correlation and momentum fading)
    """
    tide = {
        "status": "fail",
        "correlated_selling": False,
        "momentum_fading": False,
        "down_count": 0,
        "fading_count": 0,
        "etf_data": {},
    }

    down_threshold_pct = -0.30 if loose else -0.75
    down_count = 0
    fading_count = 0

    try:
        tickers = yf.Tickers(" ".join(MCF_TIER_1_ETFS))
        for tk in MCF_TIER_1_ETFS:
            hist = tickers.tickers[tk].history(period="1d", interval="5m", prepost=False)
            if hist.empty or len(hist) < 2:
                continue

            day_open = hist["Open"].iloc[0]
            current_close = hist["Close"].iloc[-1]
            change_pct = (current_close - day_open) / day_open * 100

            # Momentum fading check (current candle low > previous candle low)
            current_low = float(hist["Low"].iloc[-1])
            prev_low = float(hist["Low"].iloc[-2])
            fading = bool(current_low > prev_low)

            tide["etf_data"][tk] = {"change_pct": round(float(change_pct), 2), "fading": fading}

            if change_pct < down_threshold_pct:
                down_count += 1
            if fading:
                fading_count += 1

        tide["down_count"] = int(down_count)
        tide["fading_count"] = int(fading_count)

        # Gates: 3 of 4 must be down significantly (2 if loose), 2 of 4 must have fading momentum
        req_down = 2 if loose else 3
        tide["correlated_selling"] = bool(down_count >= req_down)
        tide["momentum_fading"] = bool(fading_count >= 2)

        if tide["correlated_selling"] and tide["momentum_fading"]:
            tide["status"] = "pass"

    except Exception as exc:
        logger.warning("MCF _get_tide failed: %s", exc)
        tide["status"] = "error"

    return tide


def _detect_rejection_candle(candle: dict, prev_candle: dict, loose: bool = False) -> bool:
    """
    High-volume Hammer or Bullish Engulfing.
    """
    high = candle.get("high", 0)
    low = candle.get("low", 0)
    close = candle.get("close", 0)
    open_val = candle.get("open", 0)
    vol = candle.get("volume", 0)

    prev_close = prev_candle.get("close", 0)
    prev_open = prev_candle.get("open", 0)
    prev_vol = prev_candle.get("volume", 0)

    vol_mult = 1.05 if loose else 1.2
    if vol < prev_vol * vol_mult:  # Must be higher volume than previous
        return False

    candle_range = high - low
    if candle_range <= 0:
        return False

    # Hammer logic
    lower_wick = min(open_val, close) - low
    if lower_wick / candle_range > 0.6 and close > (low + candle_range * 0.5):
        return True

    # Bullish engulfing
    if close > open_val and prev_close < prev_open:
        if close > prev_open and open_val < prev_close:
            return True

    return False


def _evaluate_setup(
    ticker: str, price_data: dict, atr: float, vwap: float, loose: bool = False
) -> dict | None:
    """
    Layer 3: Setup (Price near support + Rejection Candle)
    """
    candles = price_data.get("intraday_history", [])
    if len(candles) < 2:
        return None

    current_price = price_data.get("current_price", 0)

    # Are we near a support? For MCF we will use VWAP and basic Pivots
    pivots = price_data.get("pivots", {})
    s1 = pivots.get("S1", 0)
    s2 = pivots.get("S2", 0)

    supports = [s for s in [s1, s2, vwap] if s > 0]
    if not supports:
        return None

    nearest_support = min(supports, key=lambda s: abs(current_price - s))
    dist_to_support = abs(current_price - nearest_support)

    # Must be near support (within 0.35 * ATR, or 0.50 if loose)
    dist_limit = 0.50 if loose else 0.35
    if dist_to_support > dist_limit * atr:
        return None

    # Check rejection candle
    if not _detect_rejection_candle(candles[-1], candles[-2], loose):
        return None

    # Target 1% strict (0.75% if loose), or structural resistance (VWAP) if closer
    target_mult = 1.0075 if loose else 1.01
    target = round(current_price * target_mult, 2)
    if vwap > current_price and vwap < target:
        target = round(vwap, 2)

    # Stop tight below the rejection candle low
    stop = round(candles[-1].get("low", current_price * 0.99) * 0.998, 2)

    return {
        "ticker": ticker,
        "entry_price": current_price,
        "target_price": target,
        "stop_price": stop,
        "support_level": nearest_support,
        "signals": ["Near Support", "Bullish Rejection Candle", "Volume Confirmation"],
    }


def scan_mcf_opportunities(capital: float = 1000.0, loose: bool = False) -> dict:
    """
    Main MCF Scan Orchestrator
    """
    timestamp = datetime.now(ET_TZ).isoformat()

    weather = _get_weather()
    tide = {"status": "fail"}  # default
    opportunities = []

    if weather["status"] == "pass":
        tide = _get_tide(loose)
        if tide["status"] == "pass":
            # Proceed to Layer 3 for all Tier 1 + 2 ETFs
            from app.tools.dip_scanner import ETF_TIERS

            all_tickers = ETF_TIERS[1] + ETF_TIERS[2]

            # Fetch intraday data + pivots for each (in a real scenario we'd batch or use data_cache)
            # For simplicity, using yf directly or adapting dip_scanner helpers
            for tk in all_tickers:
                try:
                    hist = yf.Ticker(tk).history(period="1d", interval="5m")
                    if hist.empty:
                        continue

                    candles = []
                    for idx, row in hist.iterrows():
                        candles.append(
                            {
                                "open": row["Open"],
                                "high": row["High"],
                                "low": row["Low"],
                                "close": row["Close"],
                                "volume": row["Volume"],
                            }
                        )

                    current_price = candles[-1]["close"]
                    vwap = _compute_intraday_vwap(candles)
                    atr = _get_atr_5m(tk) or (current_price * 0.002)

                    price_data = {
                        "current_price": current_price,
                        "intraday_history": candles,
                        "pivots": {
                            "S1": current_price * 0.99,
                            "S2": current_price * 0.98,
                        },  # Approximation if missing
                    }

                    setup = _evaluate_setup(tk, price_data, atr, vwap, loose)
                    if setup:
                        setup["signal_type"] = "mcf_dip_buy"
                        setup["score"] = (
                            75 if loose else 90
                        )  # loose = relaxed gates, lower conviction
                        setup["capital_used"] = capital
                        setup["source"] = "live"
                        opportunities.append(setup)
                except Exception as exc:
                    logger.warning("MCF Setup evaluation failed for %s: %s", tk, exc)

    return {
        "timestamp": timestamp,
        "weather": weather,
        "tide": tide,
        "opportunities": opportunities,
        "loose_gates_active": loose,
    }
