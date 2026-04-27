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
                recent_changes.append({
                    "firm": row.get("Firm", ""),
                    "to_grade": row.get("To Grade", ""),
                    "from_grade": row.get("From Grade", ""),
                    "action": row.get("Action", ""),
                })

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

        return {
            "ticker": ticker.upper(),
            "consensus": consensus_label,
            "mean_rating": buy,
            "price_target": target,
            "current_price": current,
            "upside_pct": upside,
            "num_analysts": info.get("numberOfAnalystOpinions"),
            "rating_counts": rating_counts,
            "total_ratings": total_ratings,
            "recent_rating_changes": recent_changes,
        }
    except Exception as e:
        return {"error": f"Failed to fetch analyst data for {ticker}: {str(e)}"}


@tool
def get_earnings(ticker: str) -> dict:
    """
    Fetch earnings history (beat/miss), next earnings date, and earnings surprises.
    """
    try:
        stock = get_ticker(ticker)
        info = stock.info
        calendar = stock.calendar

        next_earnings = None
        if calendar is not None:
            earnings_dates = calendar.get("Earnings Date", [])
            if earnings_dates:
                if hasattr(earnings_dates, '__iter__'):
                    dates = list(earnings_dates)
                    next_earnings = str(dates[0]) if dates else None
                else:
                    next_earnings = str(earnings_dates)

        history = []
        try:
            earnings_hist = stock.earnings_history
            if earnings_hist is not None and not earnings_hist.empty:
                for _, row in earnings_hist.tail(8).iterrows():
                    eps_est = row.get("epsEstimate")
                    eps_act = row.get("epsActual")
                    surprise = row.get("epsDifference")
                    beat = None
                    if eps_est is not None and eps_act is not None:
                        beat = eps_act >= eps_est

                    history.append({
                        "date": str(row.name)[:10] if hasattr(row, 'name') else "",
                        "eps_estimate": eps_est,
                        "eps_actual": eps_act,
                        "surprise": surprise,
                        "beat": beat,
                    })
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
            "beat_rate_pct": round((beats / (beats + misses)) * 100, 1) if (beats + misses) > 0 else None,
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
        put_call_ratio = round(total_put_volume / total_call_volume, 2) if total_call_volume > 0 else None

        avg_call_iv = round(float(calls["impliedVolatility"].mean()) * 100, 1) if not calls.empty else None
        avg_put_iv = round(float(puts["impliedVolatility"].mean()) * 100, 1) if not puts.empty else None

        pcr_signal = (
            "bearish — high put buying, fear/hedging detected" if put_call_ratio and put_call_ratio > 1.2
            else "bullish — more call buying than puts" if put_call_ratio and put_call_ratio < 0.7
            else "neutral"
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
            "unusual_call_activity": unusual_calls[["strike", "volume", "openInterest", "impliedVolatility"]].to_dict("records"),
            "unusual_put_activity": unusual_puts[["strike", "volume", "openInterest", "impliedVolatility"]].to_dict("records"),
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
            return {"ticker": ticker.upper(), "message": "No recent insider transaction data", "trades": []}

        trades = []
        for _, row in insider_trades.head(15).iterrows():
            trade_type = str(row.get("Transaction", "")).lower()
            is_buy = any(w in trade_type for w in ["purchase", "buy", "acquisition"])
            is_sell = any(w in trade_type for w in ["sale", "sell", "disposition"])

            trades.append({
                "insider": str(row.get("Insider", "")),
                "relationship": str(row.get("Relation", "")),
                "transaction": str(row.get("Transaction", "")),
                "shares": row.get("Shares"),
                "value": row.get("Value"),
                "date": str(row.get("Start Date", ""))[:10],
                "signal": "bullish" if is_buy else "bearish" if is_sell else "neutral",
            })

        buy_count = sum(1 for t in trades if t["signal"] == "bullish")
        sell_count = sum(1 for t in trades if t["signal"] == "bearish")

        return {
            "ticker": ticker.upper(),
            "total_trades": len(trades),
            "buy_count": buy_count,
            "sell_count": sell_count,
            "overall_signal": (
                "bullish — insiders buying" if buy_count > sell_count
                else "bearish — insiders selling" if sell_count > buy_count
                else "neutral — mixed activity"
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
            return {"ticker": ticker.upper(), "message": "No institutional data available", "holders": []}

        holders = []
        for _, row in inst.head(10).iterrows():
            holders.append({
                "institution": str(row.get("Holder", "")),
                "shares": row.get("Shares"),
                "pct_held": row.get("% Out"),
                "value": row.get("Value"),
                "date_reported": str(row.get("Date Reported", ""))[:10],
            })

        return {
            "ticker": ticker.upper(),
            "top_holders": holders,
            "total_institutions": len(inst),
        }
    except Exception as e:
        return {"error": f"Failed to fetch institutional data for {ticker}: {str(e)}"}


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

        change_pct = None
        if shares_short and shares_short_prior and shares_short_prior > 0:
            change_pct = round(((shares_short - shares_short_prior) / shares_short_prior) * 100, 1)

        short_pct_val = short_pct * 100 if short_pct else None
        signal = (
            "extreme — short squeeze risk possible" if short_pct_val and short_pct_val > 20
            else "high — significant bearish positioning" if short_pct_val and short_pct_val > 10
            else "elevated" if short_pct_val and short_pct_val > 5
            else "normal" if short_pct_val
            else "unknown"
        )

        return {
            "ticker": ticker.upper(),
            "short_pct_of_float": round(short_pct_val, 1) if short_pct_val else None,
            "days_to_cover": short_ratio,
            "shares_short": shares_short,
            "shares_short_prior_month": shares_short_prior,
            "change_vs_prior_month_pct": change_pct,
            "signal": signal,
            "squeeze_potential": short_pct_val > 15 if short_pct_val else False,
        }
    except Exception as e:
        return {"error": f"Failed to fetch short interest for {ticker}: {str(e)}"}
