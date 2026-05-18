from typing import Optional

from langchain_core.tools import tool

from app.tools._yf_client import get_ticker


@tool
def analyze_paper_trade(
    ticker: str,
    entry_price: float,
    entry_date: str,
    position_size: float = 1000.0,
    trade_type: str = "long",
    stop_loss: Optional[float] = None,
    target_price: Optional[float] = None,
    exit_price: Optional[float] = None,
    exit_date: Optional[str] = None,
    notes: str = "",
) -> dict:
    """
    Analyze a paper trade and provide AI coaching.
    For open trades: evaluates current P&L, checks stop/target, advises hold/exit.
    For closed trades: diagnoses what went right/wrong and how to improve.
    entry_date format: YYYY-MM-DD. trade_type: long or short.
    """
    try:
        stock = get_ticker(ticker)
        hist = stock.history(period="1y")
        info = stock.info

        if hist.empty:
            return {"error": f"No price data for {ticker}"}

        current_price = round(float(hist["Close"].iloc[-1]), 2)
        is_closed = exit_price is not None

        # P&L calculation
        if trade_type.lower() == "long":
            if is_closed:
                pnl_pct = (exit_price - entry_price) / entry_price * 100
                pnl_dollar = (exit_price - entry_price) / entry_price * position_size
            else:
                pnl_pct = (current_price - entry_price) / entry_price * 100
                pnl_dollar = (current_price - entry_price) / entry_price * position_size
        else:  # short
            if is_closed:
                pnl_pct = (entry_price - exit_price) / entry_price * 100
                pnl_dollar = (entry_price - exit_price) / entry_price * position_size
            else:
                pnl_pct = (entry_price - current_price) / entry_price * 100
                pnl_dollar = (entry_price - current_price) / entry_price * position_size

        # Technical context at current price
        close = hist["Close"]
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rsi = round(float((100 - (100 / (1 + gain / loss))).iloc[-1]), 1)

        ma50 = round(float(close.rolling(50).mean().iloc[-1]), 2) if len(close) >= 50 else None
        ma200 = round(float(close.rolling(200).mean().iloc[-1]), 2) if len(close) >= 200 else None

        # Stop/target distance
        stop_distance_pct = (
            round((entry_price - stop_loss) / entry_price * 100, 1) if stop_loss else None
        )
        target_distance_pct = (
            round((target_price - entry_price) / entry_price * 100, 1) if target_price else None
        )
        rr_ratio = (
            round(target_distance_pct / stop_distance_pct, 2)
            if (stop_distance_pct and target_distance_pct and stop_distance_pct != 0)
            else None
        )

        trade_data = {
            "ticker": ticker.upper(),
            "trade_type": trade_type,
            "entry_price": round(entry_price, 2),
            "entry_date": entry_date,
            "position_size_usd": round(position_size, 2),
            "stop_loss": stop_loss,
            "target_price": target_price,
            "stop_distance_pct": stop_distance_pct,
            "target_distance_pct": target_distance_pct,
            "risk_reward_ratio": rr_ratio,
            "current_price": current_price,
            "pnl_pct": round(pnl_pct, 2),
            "pnl_dollar": round(pnl_dollar, 2),
            "status": "closed" if is_closed else "open",
            "exit_price": exit_price,
            "exit_date": exit_date,
            "notes": notes,
            "technical_context": {
                "rsi_14": rsi,
                "ma50": ma50,
                "ma200": ma200,
                "above_ma50": current_price > ma50 if ma50 else None,
                "above_ma200": current_price > ma200 if ma200 else None,
                "analyst_target": info.get("targetMeanPrice"),
                "analyst_recommendation": info.get("recommendationKey"),
            },
        }

        coaching_prompt = (
            f"You are an expert trading coach. Review this {'closed' if is_closed else 'open'} "
            f"{trade_type} paper trade on {ticker.upper()}.\n\n"
            f"Trade data: {trade_data}\n\n"
        )

        if is_closed:
            coaching_prompt += (
                f"This trade is CLOSED with a {'profit' if pnl_pct > 0 else 'loss'} of {round(pnl_pct, 2)}% "
                f"(${round(pnl_dollar, 2)}).\n"
                f"Provide coaching on:\n"
                f"1. Entry quality — was the entry well-timed given the technicals?\n"
                f"2. Exit quality — did they exit at the right time or too early/late?\n"
                f"3. Risk management — was the stop loss appropriate?\n"
                f"4. Key lesson — the single most important thing to improve next time.\n"
                f"Be direct and specific. Use the technical data provided."
            )
        else:
            hit_stop = stop_loss and (
                (trade_type == "long" and current_price <= stop_loss)
                or (trade_type == "short" and current_price >= stop_loss)
            )
            hit_target = target_price and (
                (trade_type == "long" and current_price >= target_price)
                or (trade_type == "short" and current_price <= target_price)
            )
            coaching_prompt += (
                f"This trade is OPEN with current P&L of {round(pnl_pct, 2)}% (${round(pnl_dollar, 2)}).\n"
                + (
                    f"⚠️ STOP LOSS HIT — price has breached your stop at {stop_loss}.\n"
                    if hit_stop
                    else ""
                )
                + (
                    f"🎯 TARGET REACHED — price has hit your target at {target_price}.\n"
                    if hit_target
                    else ""
                )
                + f"Provide coaching on:\n"
                f"1. Hold or exit — should they stay in the trade or take profits/cut losses now?\n"
                f"2. Stop adjustment — should the stop loss be moved (trail it, tighten it)?\n"
                f"3. Target validity — is the original target still realistic given current technicals?\n"
                f"4. Key risk — what single event could invalidate this trade?\n"
                f"Be direct. Use the RSI ({rsi}), MA positioning, and P&L context."
            )

        return {
            "ticker": ticker.upper(),
            "trade_data": trade_data,
            "coaching_instruction": coaching_prompt,
        }
    except Exception as e:
        return {"error": f"Failed to analyze paper trade for {ticker}: {str(e)}"}
