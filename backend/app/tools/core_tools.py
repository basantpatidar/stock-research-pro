from langchain_core.tools import tool

from app.tools._yf_client import get_ticker


@tool
def get_analyst_consensus(ticker: str) -> dict:
    """
    Fetch analyst buy/hold/sell consensus, price targets, and recent rating changes.
    """
    try:
        stock = get_ticker(ticker)
        info = stock.info
        recs = stock.recommendations

        buy = info.get("recommendationMean", None)
        target = info.get("targetMeanPrice")
        current = info.get("currentPrice") or info.get("regularMarketPrice")

        upside = round(((target - current) / current) * 100, 1) if target and current else None

        recent_changes = []
        if recs is not None and not recs.empty:
            for _, row in recs.tail(8).iterrows():
                recent_changes.append(
                    {
                        "firm": row.get("Firm", ""),
                        "to_grade": row.get("To Grade", ""),
                        "from_grade": row.get("From Grade", ""),
                        "action": row.get("Action", ""),
                    }
                )

        # Buy/Hold/Sell counts from recommendations_summary (current month = row 0)
        rating_counts = {"strong_buy": 0, "buy": 0, "hold": 0, "sell": 0, "strong_sell": 0}
        try:
            summary = stock.recommendations_summary
            if summary is not None and not summary.empty:
                row = summary.iloc[0]
                rating_counts = {
                    "strong_buy": int(row.get("strongBuy", 0)),
                    "buy": int(row.get("buy", 0)),
                    "hold": int(row.get("hold", 0)),
                    "sell": int(row.get("sell", 0)),
                    "strong_sell": int(row.get("strongSell", 0)),
                }
        except Exception:
            pass

        total_ratings = sum(rating_counts.values())

        consensus_label = "Unknown"
        if buy:
            if buy <= 1.5:
                consensus_label = "Strong Buy"
            elif buy <= 2.5:
                consensus_label = "Buy"
            elif buy <= 3.5:
                consensus_label = "Hold"
            elif buy <= 4.5:
                consensus_label = "Underperform"
            else:
                consensus_label = "Sell"

        # Price target range from analyst_price_targets if available
        target_low = info.get("targetLowPrice")
        target_high = info.get("targetHighPrice")
        target_median = info.get("targetMedianPrice")

        # Rating momentum: split recent_changes into last 90d vs prior 90d
        momentum_recent = {"upgrades": 0, "downgrades": 0}
        momentum_prior = {"upgrades": 0, "downgrades": 0}
        try:
            from datetime import datetime, timedelta, timezone

            cutoff_recent = datetime.now(timezone.utc) - timedelta(days=90)
            cutoff_prior = datetime.now(timezone.utc) - timedelta(days=180)
            if recs is not None and not recs.empty:
                for ts, row in recs.iterrows():
                    action = str(row.get("Action", "")).lower()
                    is_up = action in ("upgrade", "init", "initiated", "reiterated")
                    is_down = action == "downgrade"
                    ts_aware = ts.to_pydatetime()
                    if ts_aware.tzinfo is None:
                        ts_aware = ts_aware.replace(tzinfo=timezone.utc)
                    if ts_aware >= cutoff_recent:
                        if is_up:
                            momentum_recent["upgrades"] += 1
                        if is_down:
                            momentum_recent["downgrades"] += 1
                    elif ts_aware >= cutoff_prior:
                        if is_up:
                            momentum_prior["upgrades"] += 1
                        if is_down:
                            momentum_prior["downgrades"] += 1
        except Exception:
            pass

        recent_net = momentum_recent["upgrades"] - momentum_recent["downgrades"]
        prior_net = momentum_prior["upgrades"] - momentum_prior["downgrades"]
        if recent_net > prior_net:
            target_trend = "RISING"
            target_trend_color = "green"
        elif recent_net < prior_net:
            target_trend = "FALLING"
            target_trend_color = "red"
        else:
            target_trend = "STABLE"
            target_trend_color = "neutral"

        return {
            "ticker": ticker.upper(),
            "consensus": consensus_label,
            "mean_rating": buy,
            "price_target": target,
            "target_low": target_low,
            "target_high": target_high,
            "target_median": target_median,
            "current_price": current,
            "upside_pct": upside,
            "num_analysts": info.get("numberOfAnalystOpinions"),
            "rating_counts": rating_counts,
            "total_ratings": total_ratings,
            "recent_rating_changes": recent_changes,
            "target_trend": target_trend,
            "target_trend_color": target_trend_color,
            "momentum_recent_90d": momentum_recent,
            "momentum_prior_90d": momentum_prior,
        }
    except Exception as e:
        return {"error": f"Failed to fetch analyst data for {ticker}: {str(e)}"}


@tool
def get_earnings(ticker: str) -> dict:
    """
    Fetch earnings history (beat/miss), next earnings date, EPS details, and quarterly revenue.
    """
    try:
        stock = get_ticker(ticker)
        calendar = stock.calendar

        next_earnings = None
        if calendar is not None:
            earnings_dates = calendar.get("Earnings Date", [])
            if earnings_dates:
                if hasattr(earnings_dates, "__iter__"):
                    dates = list(earnings_dates)
                    next_earnings = str(dates[0]) if dates else None
                else:
                    next_earnings = str(earnings_dates)

        # Build revenue lookup: quarter-end timestamp → actual revenue value
        revenue_map: dict = {}
        try:
            import pandas as pd

            qi = stock.quarterly_income_stmt
            if qi is not None and not qi.empty:
                rev_label = next(
                    (lbl for lbl in qi.index if "revenue" in str(lbl).lower()),
                    None,
                )
                if rev_label is not None:
                    for col, val in qi.loc[rev_label].items():
                        try:
                            if val is not None and val == val:  # skip NaN
                                revenue_map[pd.Timestamp(col)] = float(val)
                        except Exception:
                            pass
        except Exception:
            pass

        def _nearest_revenue(date_str: str):
            if not revenue_map or not date_str:
                return None
            try:
                import pandas as pd

                target = pd.Timestamp(date_str)
                best_val, best_days = None, 120
                for rev_ts, rev_val in revenue_map.items():
                    diff = abs((target - rev_ts).days)
                    if diff < best_days:
                        best_days = diff
                        best_val = rev_val
                return best_val
            except Exception:
                return None

        history = []
        try:
            earnings_hist = stock.earnings_history
            if earnings_hist is not None and not earnings_hist.empty:
                for _, row in earnings_hist.tail(8).iterrows():
                    eps_est = row.get("epsEstimate")
                    eps_act = row.get("epsActual")
                    surprise = row.get("epsDifference")
                    surprise_pct = row.get("surprisePercent")
                    beat = None
                    if eps_est is not None and eps_act is not None:
                        beat = bool(eps_act >= eps_est)

                    date_str = str(row.name)[:10] if hasattr(row, "name") else ""
                    history.append(
                        {
                            "date": date_str,
                            "eps_estimate": (
                                round(float(eps_est), 2) if eps_est is not None else None
                            ),
                            "eps_actual": round(float(eps_act), 2) if eps_act is not None else None,
                            "surprise": round(float(surprise), 2) if surprise is not None else None,
                            "surprise_pct": (
                                round(float(surprise_pct), 2) if surprise_pct is not None else None
                            ),
                            "beat": beat,
                            "revenue_actual": _nearest_revenue(date_str),
                        }
                    )
        except Exception:
            pass

        beats = sum(1 for h in history if h.get("beat") is True)
        misses = sum(1 for h in history if h.get("beat") is False)

        return {
            "ticker": ticker.upper(),
            "next_earnings_date": next_earnings,
            "earnings_history": history,
            "beat_count": beats,
            "miss_count": misses,
            "beat_rate_pct": (
                round((beats / (beats + misses)) * 100, 1) if (beats + misses) > 0 else None
            ),
        }
    except Exception as e:
        return {"error": f"Failed to fetch earnings for {ticker}: {str(e)}"}


@tool
def get_fundamentals(ticker: str) -> dict:
    """
    Fetch fundamental financial ratios: P/E, PEG, revenue growth,
    profit margins, debt/equity, free cash flow, and dividend info.
    """
    try:
        stock = get_ticker(ticker)
        info = stock.info

        return {
            "ticker": ticker.upper(),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "price_to_book": info.get("priceToBook"),
            "price_to_sales": info.get("priceToSalesTrailing12Months"),
            "revenue_ttm": info.get("totalRevenue"),
            "revenue_growth_yoy": info.get("revenueGrowth"),
            "earnings_growth_yoy": info.get("earningsGrowth"),
            "gross_margin": info.get("grossMargins"),
            "operating_margin": info.get("operatingMargins"),
            "profit_margin": info.get("profitMargins"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "free_cash_flow": info.get("freeCashflow"),
            "return_on_equity": info.get("returnOnEquity"),
            "return_on_assets": info.get("returnOnAssets"),
            "dividend_yield": info.get("dividendYield"),
            "payout_ratio": info.get("payoutRatio"),
            "beta": info.get("beta"),
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "shares_outstanding": info.get("sharesOutstanding"),
            "float_shares": info.get("floatShares"),
            "52_week_high": info.get("fiftyTwoWeekHigh"),
            "52_week_low": info.get("fiftyTwoWeekLow"),
        }
    except Exception as e:
        return {"error": f"Failed to fetch fundamentals for {ticker}: {str(e)}"}


@tool
def get_options_signals(ticker: str) -> dict:
    """
    Fetch options market signals: put/call ratio, implied volatility,
    and unusual options activity. Smart money often moves in options first.
    """
    try:
        stock = get_ticker(ticker)
        options_dates = stock.options

        if not options_dates:
            return {"ticker": ticker.upper(), "error": "No options data available"}

        nearest_date = options_dates[0]
        chain = stock.option_chain(nearest_date)
        calls = chain.calls
        puts = chain.puts

        total_call_volume = int(calls["volume"].fillna(0).sum())
        total_put_volume = int(puts["volume"].fillna(0).sum())
        put_call_ratio = (
            round(total_put_volume / total_call_volume, 2) if total_call_volume > 0 else None
        )

        avg_call_iv = (
            round(float(calls["impliedVolatility"].mean()) * 100, 1) if not calls.empty else None
        )
        avg_put_iv = (
            round(float(puts["impliedVolatility"].mean()) * 100, 1) if not puts.empty else None
        )

        pcr_signal = (
            "bearish — high put buying, fear/hedging detected"
            if put_call_ratio and put_call_ratio > 1.2
            else (
                "bullish — more call buying than puts"
                if put_call_ratio and put_call_ratio < 0.7
                else "neutral"
            )
        )

        unusual_calls = calls[calls["volume"] > calls["openInterest"] * 0.5].head(3)
        unusual_puts = puts[puts["volume"] > puts["openInterest"] * 0.5].head(3)

        return {
            "ticker": ticker.upper(),
            "nearest_expiry": nearest_date,
            "total_call_volume": total_call_volume,
            "total_put_volume": total_put_volume,
            "put_call_ratio": put_call_ratio,
            "pcr_signal": pcr_signal,
            "avg_call_iv_pct": avg_call_iv,
            "avg_put_iv_pct": avg_put_iv,
            "unusual_call_activity": unusual_calls[
                ["strike", "volume", "openInterest", "impliedVolatility"]
            ].to_dict("records"),
            "unusual_put_activity": unusual_puts[
                ["strike", "volume", "openInterest", "impliedVolatility"]
            ].to_dict("records"),
        }
    except Exception as e:
        return {"error": f"Failed to fetch options for {ticker}: {str(e)}"}


@tool
def get_insider_activity(ticker: str) -> dict:
    """
    Fetch recent insider trading activity from SEC Form 4 filings.
    Insider buying is one of the strongest bullish signals available.
    """
    try:
        stock = get_ticker(ticker)
        insider_trades = stock.insider_transactions

        if insider_trades is None or insider_trades.empty:
            return {
                "ticker": ticker.upper(),
                "message": "No recent insider transaction data",
                "trades": [],
            }

        trades = []
        for _, row in insider_trades.head(15).iterrows():
            trade_type = str(row.get("Transaction", "")).lower()
            is_buy = any(w in trade_type for w in ["purchase", "buy", "acquisition"])
            is_sell = any(w in trade_type for w in ["sale", "sell", "disposition"])

            trades.append(
                {
                    "insider": str(row.get("Insider", "")),
                    "relationship": str(row.get("Relation", "")),
                    "transaction": str(row.get("Transaction", "")),
                    "shares": row.get("Shares"),
                    "value": row.get("Value"),
                    "date": str(row.get("Start Date", ""))[:10],
                    "signal": "bullish" if is_buy else "bearish" if is_sell else "neutral",
                }
            )

        buy_count = sum(1 for t in trades if t["signal"] == "bullish")
        sell_count = sum(1 for t in trades if t["signal"] == "bearish")

        return {
            "ticker": ticker.upper(),
            "total_trades": len(trades),
            "buy_count": buy_count,
            "sell_count": sell_count,
            "overall_signal": (
                "bullish — insiders buying"
                if buy_count > sell_count
                else (
                    "bearish — insiders selling"
                    if sell_count > buy_count
                    else "neutral — mixed activity"
                )
            ),
            "trades": trades,
        }
    except Exception as e:
        return {"error": f"Failed to fetch insider data for {ticker}: {str(e)}"}


@tool
def get_institutional_changes(ticker: str) -> dict:
    """
    Fetch institutional ownership changes from SEC 13F filings.
    Shows whether major funds (Blackrock, Vanguard, etc.) are adding or reducing positions.
    """
    try:
        stock = get_ticker(ticker)
        inst = stock.institutional_holders

        if inst is None or inst.empty:
            return {
                "ticker": ticker.upper(),
                "message": "No institutional data available",
                "holders": [],
            }

        holders = []
        for _, row in inst.head(10).iterrows():
            holders.append(
                {
                    "institution": str(row.get("Holder", "")),
                    "shares": row.get("Shares"),
                    "pct_held": row.get("% Out"),
                    "value": row.get("Value"),
                    "date_reported": str(row.get("Date Reported", ""))[:10],
                }
            )

        return {
            "ticker": ticker.upper(),
            "top_holders": holders,
            "total_institutions": len(inst),
        }
    except Exception as e:
        return {"error": f"Failed to fetch institutional data for {ticker}: {str(e)}"}


def _float_class(float_shares) -> str:
    if not float_shares:
        return "unknown"
    if float_shares < 1_000_000:
        return "nano"
    if float_shares < 10_000_000:
        return "micro"
    if float_shares < 50_000_000:
        return "small"
    return "large"


def _squeeze_score(short_pct_val, float_shares, days_to_cover, vol_ratio) -> dict:
    """Squeeze Probability Score (0–100) combining float, short %, DTC, volume."""
    score = 0
    if short_pct_val:
        if short_pct_val > 20:
            score += 35
        elif short_pct_val > 10:
            score += 25
        elif short_pct_val > 5:
            score += 10
    if float_shares:
        if float_shares < 5_000_000:
            score += 30
        elif float_shares < 20_000_000:
            score += 20
        elif float_shares < 50_000_000:
            score += 10
    if days_to_cover:
        if days_to_cover > 5:
            score += 20
        elif days_to_cover > 2:
            score += 10
    if vol_ratio:
        if vol_ratio > 2.0:
            score += 15
        elif vol_ratio > 1.5:
            score += 8
    score = min(score, 100)
    tier = (
        "Short Squeeze Setup"
        if score >= 65
        else (
            "Elevated Squeeze Risk"
            if score >= 45
            else "Low Float Momentum" if score >= 25 else "No Setup"
        )
    )
    return {"squeeze_score": score, "squeeze_tier": tier}


@tool
def get_short_interest(ticker: str) -> dict:
    """
    Fetch short interest data: percentage of float being shorted
    and days to cover. High short interest can signal bearish sentiment
    or potential short squeeze opportunity.
    """
    try:
        stock = get_ticker(ticker)
        info = stock.info

        short_pct = info.get("shortPercentOfFloat")
        short_ratio = info.get("shortRatio")
        shares_short = info.get("sharesShort")
        shares_short_prior = info.get("sharesShortPriorMonth")
        float_shares = info.get("floatShares")

        change_pct = None
        if shares_short and shares_short_prior and shares_short_prior > 0:
            change_pct = round(((shares_short - shares_short_prior) / shares_short_prior) * 100, 1)

        short_pct_val = round(short_pct * 100, 1) if short_pct else None
        signal = (
            "extreme — short squeeze risk possible"
            if short_pct_val and short_pct_val > 20
            else (
                "high — significant bearish positioning"
                if short_pct_val and short_pct_val > 10
                else (
                    "elevated"
                    if short_pct_val and short_pct_val > 5
                    else "normal" if short_pct_val else "unknown"
                )
            )
        )

        vol = info.get("regularMarketVolume") or info.get("volume")
        avg_vol = info.get("averageVolume") or info.get("averageDailyVolume10Day")
        vol_ratio = round(vol / avg_vol, 2) if vol and avg_vol and avg_vol > 0 else None

        squeeze = _squeeze_score(short_pct_val, float_shares, short_ratio, vol_ratio)

        return {
            "ticker": ticker.upper(),
            "short_pct_of_float": short_pct_val,
            "days_to_cover": short_ratio,
            "shares_short": shares_short,
            "shares_short_prior_month": shares_short_prior,
            "change_vs_prior_month_pct": change_pct,
            "signal": signal,
            "squeeze_potential": short_pct_val > 15 if short_pct_val else False,
            "float_shares": float_shares,
            "float_class": _float_class(float_shares),
            "vol_ratio": vol_ratio,
            "squeeze_score": squeeze["squeeze_score"],
            "squeeze_tier": squeeze["squeeze_tier"],
        }
    except Exception as e:
        return {"error": f"Failed to fetch short interest for {ticker}: {str(e)}"}
