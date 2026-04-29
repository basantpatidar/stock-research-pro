from langchain_core.tools import tool
from datetime import datetime, timedelta
import requests


_HOUSE_URL = "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"
_SENATE_URL = "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json"

_TIMEOUT = 10


def _fetch_house(ticker: str, days: int) -> list[dict]:
    try:
        resp = requests.get(_HOUSE_URL, timeout=_TIMEOUT)
        resp.raise_for_status()
        cutoff = datetime.utcnow() - timedelta(days=days)
        results = []
        for tx in resp.json():
            if ticker.upper() not in (tx.get("ticker") or "").upper():
                continue
            try:
                tx_date = datetime.strptime(tx.get("transaction_date", ""), "%Y-%m-%d")
            except ValueError:
                continue
            if tx_date < cutoff:
                continue
            results.append({
                "chamber": "House",
                "member": tx.get("representative", "Unknown"),
                "ticker": tx.get("ticker"),
                "transaction_type": tx.get("type", "unknown"),
                "amount_range": tx.get("amount", "unknown"),
                "date": tx.get("transaction_date"),
                "description": tx.get("asset_description", ""),
            })
        return results
    except Exception:
        return []


def _fetch_senate(ticker: str, days: int) -> list[dict]:
    try:
        resp = requests.get(_SENATE_URL, timeout=_TIMEOUT)
        resp.raise_for_status()
        cutoff = datetime.utcnow() - timedelta(days=days)
        results = []
        for tx in resp.json():
            if ticker.upper() not in (tx.get("ticker") or "").upper():
                continue
            try:
                tx_date = datetime.strptime(tx.get("transaction_date", ""), "%Y-%m-%d")
            except ValueError:
                continue
            if tx_date < cutoff:
                continue
            results.append({
                "chamber": "Senate",
                "member": tx.get("senator", "Unknown"),
                "ticker": tx.get("ticker"),
                "transaction_type": tx.get("type", "unknown"),
                "amount_range": tx.get("amount", "unknown"),
                "date": tx.get("transaction_date"),
                "description": tx.get("asset_description", ""),
            })
        return results
    except Exception:
        return []


@tool
def get_congressional_trades(ticker: str, days: int = 180) -> dict:
    """
    Fetch congressional stock trades (STOCK Act disclosures) for a ticker.
    Covers both House and Senate filings from the past N days (default 180).
    Returns individual trades, net buy/sell count, and notable members.
    """
    try:
        house = _fetch_house(ticker, days)
        senate = _fetch_senate(ticker, days)
        all_trades = house + senate

        buys = [t for t in all_trades if "purchase" in t.get("transaction_type", "").lower()
                or "buy" in t.get("transaction_type", "").lower()]
        sells = [t for t in all_trades if "sale" in t.get("transaction_type", "").lower()
                 or "sell" in t.get("transaction_type", "").lower()]

        members_buying = list({t["member"] for t in buys})
        members_selling = list({t["member"] for t in sells})

        sentiment = (
            "strongly bullish — more buys than sells" if len(buys) > len(sells) * 1.5
            else "slightly bullish" if len(buys) > len(sells)
            else "mixed" if len(buys) == len(sells)
            else "slightly bearish" if len(sells) > len(buys)
            else "strongly bearish — more sells than buys"
        ) if all_trades else "no recent activity"

        return {
            "ticker": ticker.upper(),
            "lookback_days": days,
            "total_trades": len(all_trades),
            "buys": len(buys),
            "sells": len(sells),
            "congressional_sentiment": sentiment,
            "members_buying": members_buying[:10],
            "members_selling": members_selling[:10],
            "recent_trades": sorted(all_trades, key=lambda x: x.get("date", ""), reverse=True)[:20],
            "note": "STOCK Act disclosures may lag by up to 45 days from actual trade date.",
        }
    except Exception as e:
        return {"error": f"Failed to fetch congressional trades for {ticker}: {str(e)}"}
