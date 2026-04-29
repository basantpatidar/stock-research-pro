from langchain_core.tools import tool
from app.tools._yf_client import get_ticker
from typing import Literal


def _backtest_rsi(close, oversold: float = 30.0, overbought: float = 70.0) -> dict:
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rsi = 100 - (100 / (1 + gain / loss))

    in_trade = False
    entry_price = 0.0
    trades = []

    for i in range(1, len(close)):
        if not in_trade and rsi.iloc[i - 1] < oversold and rsi.iloc[i] >= oversold:
            in_trade = True
            entry_price = float(close.iloc[i])
        elif in_trade and rsi.iloc[i] > overbought:
            exit_price = float(close.iloc[i])
            pnl = (exit_price - entry_price) / entry_price * 100
            trades.append({"entry": round(entry_price, 2), "exit": round(exit_price, 2), "pnl_pct": round(pnl, 2)})
            in_trade = False

    return trades


def _backtest_macd(close) -> list[dict]:
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()

    in_trade = False
    entry_price = 0.0
    trades = []

    for i in range(1, len(close)):
        prev_diff = float(macd.iloc[i - 1]) - float(signal.iloc[i - 1])
        curr_diff = float(macd.iloc[i]) - float(signal.iloc[i])

        if not in_trade and prev_diff < 0 and curr_diff >= 0:
            in_trade = True
            entry_price = float(close.iloc[i])
        elif in_trade and prev_diff > 0 and curr_diff <= 0:
            exit_price = float(close.iloc[i])
            pnl = (exit_price - entry_price) / entry_price * 100
            trades.append({"entry": round(entry_price, 2), "exit": round(exit_price, 2), "pnl_pct": round(pnl, 2)})
            in_trade = False

    return trades


def _backtest_golden_cross(close) -> list[dict]:
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()

    in_trade = False
    entry_price = 0.0
    trades = []

    for i in range(1, len(close)):
        if ma50.isna().iloc[i] or ma200.isna().iloc[i]:
            continue
        prev_above = float(ma50.iloc[i - 1]) > float(ma200.iloc[i - 1])
        curr_above = float(ma50.iloc[i]) > float(ma200.iloc[i])

        if not in_trade and not prev_above and curr_above:
            in_trade = True
            entry_price = float(close.iloc[i])
        elif in_trade and prev_above and not curr_above:
            exit_price = float(close.iloc[i])
            pnl = (exit_price - entry_price) / entry_price * 100
            trades.append({"entry": round(entry_price, 2), "exit": round(exit_price, 2), "pnl_pct": round(pnl, 2)})
            in_trade = False

    return trades


def _summarize(trades: list[dict], buy_hold_pct: float) -> dict:
    if not trades:
        return {
            "total_trades": 0,
            "win_rate_pct": None,
            "avg_return_pct": None,
            "total_return_pct": None,
            "best_trade_pct": None,
            "worst_trade_pct": None,
            "buy_and_hold_pct": round(buy_hold_pct, 1),
            "outperforms_buy_hold": None,
        }
    wins = [t for t in trades if t["pnl_pct"] > 0]
    pnls = [t["pnl_pct"] for t in trades]
    total = sum(pnls)
    return {
        "total_trades": len(trades),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 1),
        "avg_return_pct": round(total / len(trades), 2),
        "total_return_pct": round(total, 2),
        "best_trade_pct": round(max(pnls), 2),
        "worst_trade_pct": round(min(pnls), 2),
        "buy_and_hold_pct": round(buy_hold_pct, 1),
        "outperforms_buy_hold": total > buy_hold_pct,
        "trades": trades[-10:],
    }


@tool
def run_backtest(
    ticker: str,
    strategy: Literal["rsi", "macd", "golden_cross", "all"] = "all",
    period: str = "2y",
) -> dict:
    """
    Backtest technical trading strategies on a stock's historical price data.
    Strategies: rsi (oversold/overbought), macd (crossover), golden_cross (50d/200d MA), all.
    Period: 1y, 2y, 5y. Returns win rate, avg return, total return vs buy-and-hold.
    """
    try:
        stock = get_ticker(ticker)
        hist = stock.history(period=period)

        if hist.empty or len(hist) < 50:
            return {"error": f"Insufficient data for {ticker} — need at least 50 trading days"}

        close = hist["Close"]
        buy_hold = (float(close.iloc[-1]) - float(close.iloc[0])) / float(close.iloc[0]) * 100

        results = {"ticker": ticker.upper(), "period": period, "buy_and_hold_pct": round(buy_hold, 1)}

        if strategy in ("rsi", "all"):
            results["rsi"] = _summarize(_backtest_rsi(close), buy_hold)

        if strategy in ("macd", "all"):
            results["macd"] = _summarize(_backtest_macd(close), buy_hold)

        if strategy in ("golden_cross", "all"):
            if len(close) >= 200:
                results["golden_cross"] = _summarize(_backtest_golden_cross(close), buy_hold)
            else:
                results["golden_cross"] = {"error": "Need at least 200 trading days for golden cross"}

        return results
    except Exception as e:
        return {"error": f"Backtest failed for {ticker}: {str(e)}"}
