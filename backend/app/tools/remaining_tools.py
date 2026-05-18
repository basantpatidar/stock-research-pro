from langchain_core.tools import tool

from app.tools._yf_client import get_ticker


@tool
def get_macro_environment() -> dict:
    """
    Fetch macro market environment: VIX fear index, S&P 500 trend,
    oil prices, 10Y treasury yield, gold, USD index.
    Determines if market is risk-on or risk-off.
    """
    try:
        tickers = {
            "vix": "^VIX",
            "sp500": "^GSPC",
            "nasdaq": "^IXIC",
            "oil_wti": "CL=F",
            "gold": "GC=F",
            "treasury_10y": "^TNX",
            "usd_index": "DX-Y.NYB",
        }

        results = {}
        for name, symbol in tickers.items():
            try:
                t = get_ticker(symbol)
                hist = t.history(period="3mo")
                if not hist.empty:
                    current = round(float(hist["Close"].iloc[-1]), 2)
                    n = len(hist)

                    def _chg(base: float) -> float:
                        return round(((current - base) / base) * 100, 2) if base else 0.0

                    prev = float(hist["Close"].iloc[-2]) if n >= 2 else current
                    week_ago = float(hist["Close"].iloc[-6]) if n >= 6 else prev
                    month_ago = (
                        float(hist["Close"].iloc[-22]) if n >= 22 else float(hist["Close"].iloc[0])
                    )
                    three_m_ago = float(hist["Close"].iloc[0])

                    results[name] = {
                        "current": current,
                        "change_today_pct": _chg(prev),
                        "change_1d_pct": _chg(prev),
                        "change_7d_pct": _chg(week_ago),
                        "change_1m_pct": _chg(month_ago),
                        "change_3m_pct": _chg(three_m_ago),
                    }
            except Exception:
                results[name] = {"error": "unavailable"}

        vix_val = results.get("vix", {}).get("current", 0)
        environment = (
            "RISK-OFF — extreme fear"
            if vix_val > 30
            else (
                "RISK-OFF — elevated fear"
                if vix_val > 20
                else "NEUTRAL — moderate volatility" if vix_val > 15 else "RISK-ON — low fear"
            )
        )

        rec = (
            "Reduce position sizes significantly. Widen stop losses."
            if vix_val > 30
            else (
                "Trade smaller. Be selective. Avoid new long positions in weak sectors."
                if vix_val > 20
                else (
                    "Normal sizing acceptable. Standard risk management applies."
                    if vix_val > 15
                    else "Favorable conditions for new positions."
                )
            )
        )

        return {
            "environment": environment,
            "vix": results.get("vix"),
            "sp500": results.get("sp500"),
            "nasdaq": results.get("nasdaq"),
            "oil_wti": results.get("oil_wti"),
            "gold": results.get("gold"),
            "treasury_10y": results.get("treasury_10y"),
            "usd_index": results.get("usd_index"),
            "trading_recommendation": rec,
        }
    except Exception as e:
        return {"error": f"Failed to fetch macro environment: {str(e)}"}


@tool
def get_sector_heatmap() -> dict:
    """
    Fetch sector performance heatmap — shows which sectors are up/down.
    Helps determine if a stock's move is sector-wide or company-specific.
    """
    try:
        sector_etfs = {
            "Technology": "XLK",
            "Healthcare": "XLV",
            "Financials": "XLF",
            "Consumer Discretionary": "XLY",
            "Consumer Staples": "XLP",
            "Energy": "XLE",
            "Utilities": "XLU",
            "Real Estate": "XLRE",
            "Materials": "XLB",
            "Industrials": "XLI",
            "Communication Services": "XLC",
        }

        sectors = []
        for sector_name, etf in sector_etfs.items():
            try:
                t = get_ticker(etf)
                hist = t.history(period="3mo")
                if not hist.empty and len(hist) >= 2:
                    current = float(hist["Close"].iloc[-1])
                    n = len(hist)

                    def _chg(base: float) -> float:
                        return round(((current - base) / base) * 100, 2) if base else 0.0

                    prev_day = float(hist["Close"].iloc[-2]) if n >= 2 else current
                    week_start = (
                        float(hist["Close"].iloc[-6]) if n >= 6 else float(hist["Close"].iloc[0])
                    )
                    month_ago = (
                        float(hist["Close"].iloc[-22]) if n >= 22 else float(hist["Close"].iloc[0])
                    )
                    three_m_ago = float(hist["Close"].iloc[0])

                    change_5d = _chg(week_start)
                    sectors.append(
                        {
                            "sector": sector_name,
                            "etf": etf,
                            "change_1d_pct": _chg(prev_day),
                            "change_5d_pct": change_5d,
                            "change_7d_pct": change_5d,
                            "change_1m_pct": _chg(month_ago),
                            "change_3m_pct": _chg(three_m_ago),
                            "trend": (
                                "up" if change_5d > 0.5 else "down" if change_5d < -0.5 else "flat"
                            ),
                        }
                    )
            except Exception:
                continue

        sectors.sort(key=lambda x: x["change_5d_pct"], reverse=True)
        return {"sectors": sectors, "period": "5 days"}
    except Exception as e:
        return {"error": f"Failed to fetch sector heatmap: {str(e)}"}


@tool
def get_cascade_impact(ticker: str, event_description: str) -> dict:
    """
    Analyze how a macro or geopolitical event cascades to impact a specific stock.
    Builds the reasoning chain: event → intermediate effects → stock impact.
    Example: "Iran blocks Strait of Hormuz" → oil spike → inflation → rate fears → GOOGL drops.
    """
    return {
        "ticker": ticker.upper(),
        "event": event_description,
        "instruction": (
            f"Analyze how '{event_description}' impacts {ticker.upper()} step by step. "
            f"Build the causal chain: event → macro effect → sector effect → {ticker.upper()} impact. "
            f"Distinguish between direct impact (company is directly affected) and "
            f"indirect impact (broad market sell-off pulling all stocks down). "
            f"Estimate what % of a price move is macro drag vs company-specific."
        ),
    }


@tool
def get_price_forecast(ticker: str) -> dict:
    """
    Generate directional price forecast for a stock across three horizons:
    days (technical), weeks (momentum + events), quarter (fundamental).
    Uses technical indicators and fundamental data to reason about direction.
    """
    try:
        stock = get_ticker(ticker)
        info = stock.info
        hist = stock.history(period="1y")

        if hist.empty:
            return {"error": f"No data for {ticker}"}

        close = hist["Close"]

        # RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rsi = float(100 - (100 / (1 + gain / loss)).iloc[-1])

        # Price vs 200d MA
        ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
        current = float(close.iloc[-1])
        above_200 = current > ma200 if ma200 else None

        # 52-week position
        high_52 = float(close.max())
        low_52 = float(close.min())
        position_52w = round((current - low_52) / (high_52 - low_52) * 100, 1)

        pe = info.get("trailingPE")
        growth = info.get("earningsGrowth")
        target = info.get("targetMeanPrice")
        upside = round(((target - current) / current * 100), 1) if target else None

        return {
            "ticker": ticker.upper(),
            "current_price": round(current, 2),
            "rsi_14": round(rsi, 1),
            "above_200d_ma": above_200,
            "position_in_52w_range_pct": position_52w,
            "analyst_target": target,
            "analyst_upside_pct": upside,
            "pe_ratio": pe,
            "earnings_growth": growth,
            "forecast_inputs": {
                "days_signal": (
                    "oversold — technical bounce likely"
                    if rsi < 30
                    else (
                        "overbought — pullback possible"
                        if rsi > 70
                        else "neutral — no strong technical signal"
                    )
                ),
                "weeks_signal": (
                    "bullish — above long-term MA"
                    if above_200
                    else (
                        "bearish — below long-term MA"
                        if above_200 is False
                        else "insufficient data"
                    )
                ),
                "quarter_signal": (
                    "bullish — analysts see significant upside"
                    if upside and upside > 15
                    else (
                        "bearish — analysts see downside"
                        if upside and upside < -5
                        else "neutral — limited analyst upside"
                    )
                ),
            },
        }
    except Exception as e:
        return {"error": f"Failed to generate forecast for {ticker}: {str(e)}"}


@tool
def get_risk_reward(ticker: str, entry_price: float = 0.0) -> dict:
    """
    Calculate risk/reward ratio for a trade using support/resistance levels.
    If entry_price is 0, uses current market price.
    Returns R/R ratio, suggested stop loss, and target price.
    """
    try:
        stock = get_ticker(ticker)
        hist = stock.history(period="3mo")
        info = stock.info

        if hist.empty:
            return {"error": f"No data for {ticker}"}

        current = float(hist["Close"].iloc[-1])
        price = entry_price if entry_price > 0 else current

        recent_lows = hist["Low"].rolling(5).min()
        support = round(float(recent_lows.iloc[-5:].min()), 2)

        target = info.get("targetMeanPrice")
        if not target:
            target = round(current * 1.15, 2)

        stop_loss = round(support * 0.99, 2)
        reward = target - price
        risk = price - stop_loss
        rr_ratio = round(reward / risk, 2) if risk > 0 else None

        return {
            "ticker": ticker.upper(),
            "entry_price": round(price, 2),
            "target_price": round(target, 2),
            "stop_loss": stop_loss,
            "support_level": support,
            "potential_gain_pct": round((target - price) / price * 100, 1),
            "potential_loss_pct": round((price - stop_loss) / price * 100, 1),
            "risk_reward_ratio": rr_ratio,
            "trade_quality": (
                "excellent"
                if rr_ratio and rr_ratio >= 4
                else (
                    "good"
                    if rr_ratio and rr_ratio >= 3
                    else (
                        "acceptable"
                        if rr_ratio and rr_ratio >= 2
                        else "poor — skip this trade" if rr_ratio else "unable to calculate"
                    )
                )
            ),
        }
    except Exception as e:
        return {"error": f"Failed to calculate R/R for {ticker}: {str(e)}"}


@tool
def run_screener(
    min_market_cap_b: float = 100.0,
    min_volume: int = 1_000_000,
    min_price_drop_pct: float = 10.0,
    sector: str = "all",
    max_pe: float = 0.0,
    universe: str = "sp500",
    limit: int = 50,
) -> dict:
    """
    Screen stocks based on filters: market cap, volume, price drop, sector.
    Returns qualifying stocks that may represent trading opportunities.
    min_market_cap_b: minimum market cap in billions (e.g. 100 = $100B)
    min_price_drop_pct: minimum 7-day price decline to qualify (e.g. 10 = -10%)
    universe: which ticker pool to screen — "sp500" (default, ~150 names),
              "nasdaq100" (growth/tech focus), "etfs" (sector + factor),
              "mega" ($200B+ for fast scans), or "legacy" (old 30-symbol list)
    limit: max tickers to fetch per run. Each one is a yfinance call (~200ms),
           so 50 ≈ 10 s, 100 ≈ 20 s. Hard-capped at 150 to keep API latency sane.
    """
    try:
        from app.tools.universe import get_universe

        # Resolve universe; cap to 150 max so a "limit=99999" can't DOS the API
        ticker_pool = get_universe(universe)
        screen_count = max(1, min(int(limit), 150))

        results = []
        for ticker in ticker_pool[:screen_count]:
            try:
                stock = get_ticker(ticker)
                info = stock.info
                hist = stock.history(period="3mo")

                if hist.empty or len(hist) < 5:
                    continue

                market_cap = info.get("marketCap", 0)
                if market_cap < min_market_cap_b * 1_000_000_000:
                    continue

                avg_vol = float(hist["Volume"].mean())
                if avg_vol < min_volume:
                    continue

                current = float(hist["Close"].iloc[-1])
                n = len(hist)

                def _chg(base: float) -> float:
                    return round(((current - base) / base) * 100, 2) if base else 0.0

                prev_day = float(hist["Close"].iloc[-2]) if n >= 2 else current
                week_ago = float(hist["Close"].iloc[-6]) if n >= 6 else float(hist["Close"].iloc[0])
                month_ago = (
                    float(hist["Close"].iloc[-22]) if n >= 22 else float(hist["Close"].iloc[0])
                )
                three_m_ago = float(hist["Close"].iloc[0])

                drop_pct = _chg(week_ago)

                if drop_pct > -min_price_drop_pct:
                    continue

                if sector != "all":
                    stock_sector = info.get("sector", "").lower()
                    if sector.lower() not in stock_sector:
                        continue

                results.append(
                    {
                        "ticker": ticker,
                        "company": info.get("longName", ticker),
                        "price": round(current, 2),
                        "change_1d_pct": _chg(prev_day),
                        "change_7d_pct": drop_pct,
                        "change_1m_pct": _chg(month_ago),
                        "change_3m_pct": _chg(three_m_ago),
                        "market_cap_b": round(market_cap / 1_000_000_000, 1),
                        "avg_volume": int(avg_vol),
                        "sector": info.get("sector", "Unknown"),
                        "pe_ratio": info.get("trailingPE"),
                    }
                )
            except Exception:
                continue

        results.sort(key=lambda x: x["change_7d_pct"])

        return {
            "filters_applied": {
                "min_market_cap_b": min_market_cap_b,
                "min_volume": min_volume,
                "min_price_drop_pct": min_price_drop_pct,
                "sector": sector,
            },
            "matches_found": len(results),
            "results": results,
        }
    except Exception as e:
        return {"error": f"Screener failed: {str(e)}"}


@tool
def get_convergence_score(
    ticker: str,
    rsi: float = 0.0,
    analyst_consensus: str = "",
    sentiment: str = "",
    macd_signal: str = "",
    insider_signal: str = "",
    options_signal: str = "",
    macro_environment: str = "",
    news_sentiment: str = "",
) -> dict:
    """
    Aggregate all signals into a single 0-100 confidence score.
    Higher score = stronger buy conviction. Below 40 = avoid.
    Pass in signals collected from other tools.
    """
    score = 50
    signals = []

    if rsi > 0:
        if rsi < 30:
            score += 12
            signals.append(
                {
                    "signal": "RSI",
                    "value": f"{rsi} — oversold",
                    "direction": "bullish",
                    "points": 12,
                }
            )
        elif rsi > 70:
            score -= 12
            signals.append(
                {
                    "signal": "RSI",
                    "value": f"{rsi} — overbought",
                    "direction": "bearish",
                    "points": -12,
                }
            )
        else:
            signals.append(
                {"signal": "RSI", "value": f"{rsi} — neutral", "direction": "neutral", "points": 0}
            )

    if analyst_consensus:
        ac = analyst_consensus.lower()
        if "strong buy" in ac or "buy" in ac:
            score += 10
            signals.append(
                {
                    "signal": "Analyst consensus",
                    "value": analyst_consensus,
                    "direction": "bullish",
                    "points": 10,
                }
            )
        elif "sell" in ac:
            score -= 10
            signals.append(
                {
                    "signal": "Analyst consensus",
                    "value": analyst_consensus,
                    "direction": "bearish",
                    "points": -10,
                }
            )

    if sentiment:
        s = sentiment.lower()
        if "bullish" in s:
            score += 8
            signals.append(
                {
                    "signal": "Social sentiment",
                    "value": sentiment,
                    "direction": "bullish",
                    "points": 8,
                }
            )
        elif "bearish" in s:
            score -= 8
            signals.append(
                {
                    "signal": "Social sentiment",
                    "value": sentiment,
                    "direction": "bearish",
                    "points": -8,
                }
            )

    if macd_signal:
        if "bullish" in macd_signal.lower():
            score += 8
            signals.append(
                {"signal": "MACD", "value": macd_signal, "direction": "bullish", "points": 8}
            )
        elif "bearish" in macd_signal.lower():
            score -= 8
            signals.append(
                {"signal": "MACD", "value": macd_signal, "direction": "bearish", "points": -8}
            )

    if insider_signal:
        if "bullish" in insider_signal.lower() or "buying" in insider_signal.lower():
            score += 15
            signals.append(
                {
                    "signal": "Insider activity",
                    "value": insider_signal,
                    "direction": "bullish",
                    "points": 15,
                }
            )
        elif "bearish" in insider_signal.lower() or "selling" in insider_signal.lower():
            score -= 10
            signals.append(
                {
                    "signal": "Insider activity",
                    "value": insider_signal,
                    "direction": "bearish",
                    "points": -10,
                }
            )

    if options_signal:
        if "bullish" in options_signal.lower():
            score += 8
            signals.append(
                {
                    "signal": "Options flow",
                    "value": options_signal,
                    "direction": "bullish",
                    "points": 8,
                }
            )
        elif "bearish" in options_signal.lower() or "put heavy" in options_signal.lower():
            score -= 8
            signals.append(
                {
                    "signal": "Options flow",
                    "value": options_signal,
                    "direction": "bearish",
                    "points": -8,
                }
            )

    if macro_environment:
        m = macro_environment.lower()
        if "risk-off" in m or "extreme fear" in m:
            score -= 15
            signals.append(
                {
                    "signal": "Macro environment",
                    "value": macro_environment,
                    "direction": "bearish",
                    "points": -15,
                }
            )
        elif "risk-on" in m:
            score += 8
            signals.append(
                {
                    "signal": "Macro environment",
                    "value": macro_environment,
                    "direction": "bullish",
                    "points": 8,
                }
            )

    if news_sentiment:
        n = news_sentiment.lower()
        if "positive" in n:
            score += 7
            signals.append(
                {
                    "signal": "News sentiment",
                    "value": news_sentiment,
                    "direction": "bullish",
                    "points": 7,
                }
            )
        elif "negative" in n:
            score -= 7
            signals.append(
                {
                    "signal": "News sentiment",
                    "value": news_sentiment,
                    "direction": "bearish",
                    "points": -7,
                }
            )

    score = max(0, min(100, score))

    label = (
        "Strong buy — high conviction"
        if score >= 75
        else (
            "Buy — good setup"
            if score >= 60
            else (
                "Weak buy — wait for better entry"
                if score >= 50
                else (
                    "Neutral — insufficient signal"
                    if score >= 40
                    else "Avoid — bearish signals dominant"
                )
            )
        )
    )

    return {
        "ticker": ticker.upper(),
        "convergence_score": score,
        "label": label,
        "signals": signals,
        "bullish_signals": sum(1 for s in signals if s["direction"] == "bullish"),
        "bearish_signals": sum(1 for s in signals if s["direction"] == "bearish"),
    }


@tool
def get_trends(ticker: str, company_name: str = "") -> dict:
    """
    Check Google Trends for search interest spikes on a stock.
    Rising search interest often precedes retail buying pressure.
    Note: Uses pytrends library — install separately if needed.
    """
    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="en-US", tz=360)
        kw = company_name if company_name else ticker
        pytrends.build_payload([kw], timeframe="now 7-d", geo="US")
        interest = pytrends.interest_over_time()

        if interest.empty:
            return {"ticker": ticker, "trend": "no data", "spike_detected": False}

        values = interest[kw].tolist()
        avg = sum(values) / len(values)
        latest = values[-1]
        spike = latest > avg * 1.5

        return {
            "ticker": ticker.upper(),
            "search_term": kw,
            "avg_interest": round(avg, 1),
            "latest_interest": latest,
            "spike_detected": spike,
            "trend": "spiking — retail attention increasing" if spike else "normal",
            "values_7d": values,
        }
    except ImportError:
        return {
            "ticker": ticker,
            "note": "pytrends not installed. Run: pip install pytrends",
            "spike_detected": False,
        }
    except Exception as e:
        return {"error": f"Google Trends fetch failed: {str(e)}", "spike_detected": False}
