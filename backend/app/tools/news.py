from langchain_core.tools import tool
import requests
from datetime import datetime, timedelta
from app.config import get_settings


def _resolve_query(ticker: str, company_name: str) -> str:
    """
    Build the best possible NewsAPI search query for a ticker.

    Priority:
      1. Caller-supplied company_name  → use as-is (already authoritative)
      2. yfinance longName             → look it up from the ticker's info
      3. Fallback                      → ticker symbol only

    The query is quoted ("ServiceNow") so NewsAPI does exact-phrase matching
    instead of treating each word independently.  This prevents ambiguous
    tickers like NOW, IT, A, or WELL from matching unrelated articles.
    """
    if company_name:
        name = company_name
    else:
        try:
            from app.tools._yf_client import get_ticker
            info = get_ticker(ticker).info
            name = info.get("longName") or info.get("shortName") or ""
        except Exception:
            name = ""

    # Strip common legal suffixes that add noise to the search
    for suffix in (", Inc.", " Inc.", ", Corp.", " Corp.", ", Ltd.", " Ltd.",
                   ", LLC", " LLC", " Holdings", " Group", " Corporation"):
        name = name.replace(suffix, "")
    name = name.strip()

    # Use the cleaner of company name vs ticker (prefer name when available)
    search_term = name if name else ticker.upper()

    # Exact-phrase quoting: "ServiceNow" beats  NOW stock
    return f'"{search_term}"'


@tool
def get_news_impact(ticker: str, company_name: str = "", days: int = 7) -> dict:
    """
    Fetch recent news for a stock and analyze the impact of each headline.
    Returns headlines tagged positive/negative/neutral with estimated price impact.
    Uses NewsAPI — requires NEWSAPI_KEY in .env.

    company_name is optional — when omitted the tool looks it up from yfinance
    so that ambiguous tickers (NOW, IT, A, WELL, etc.) return relevant results.
    """
    try:
        settings = get_settings()

        if not settings.newsapi_key:
            return {"error": "NEWSAPI_KEY not configured. Get a free key at newsapi.org"}

        query = _resolve_query(ticker, company_name)
        from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "from": from_date,
            "sortBy": "publishedAt",
            "language": "en",
            "pageSize": 20,
            "apiKey": settings.newsapi_key,
        }

        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if data.get("status") != "ok":
            return {"error": f"NewsAPI error: {data.get('message', 'Unknown error')}"}

        articles = data.get("articles", [])
        if not articles:
            return {"ticker": ticker, "articles_found": 0, "news": [], "summary": "No recent news found"}

        news_items = []
        for article in articles[:15]:
            title = article.get("title", "")
            description = article.get("description", "")
            published = article.get("publishedAt", "")[:10]
            source = article.get("source", {}).get("name", "Unknown")
            url_link = article.get("url", "")

            title_lower = title.lower()
            negative_words = [
                "lawsuit", "investigation", "decline", "fall", "drop", "loss",
                "miss", "cut", "downgrade", "bearish", "sell", "ban", "fine",
                "probe", "antitrust", "breach", "hack", "layoff", "warning",
                "recall", "fraud", "scandal", "crash", "plunge", "tumble"
            ]
            positive_words = [
                "beat", "rise", "gain", "profit", "upgrade", "bullish", "buy",
                "record", "growth", "partnership", "deal", "award", "launch",
                "surge", "rally", "strong", "exceed", "milestone", "approval"
            ]

            neg_count = sum(1 for w in negative_words if w in title_lower)
            pos_count = sum(1 for w in positive_words if w in title_lower)

            sentiment = (
                "negative" if neg_count > pos_count
                else "positive" if pos_count > neg_count
                else "neutral"
            )

            news_items.append({
                "headline": title,
                "description": description[:200] if description else "",
                "source": source,
                "published": published,
                "sentiment": sentiment,
                "url": url_link,
            })

        negative_count = sum(1 for n in news_items if n["sentiment"] == "negative")
        positive_count = sum(1 for n in news_items if n["sentiment"] == "positive")
        neutral_count = sum(1 for n in news_items if n["sentiment"] == "neutral")

        overall = (
            "predominantly negative" if negative_count > positive_count + neutral_count
            else "predominantly positive" if positive_count > negative_count + neutral_count
            else "mixed"
        )

        return {
            "ticker": ticker.upper(),
            "query_used": query,
            "period_days": days,
            "articles_found": len(news_items),
            "sentiment_breakdown": {
                "positive": positive_count,
                "negative": negative_count,
                "neutral": neutral_count,
                "overall": overall,
            },
            "news": news_items,
        }
    except Exception as e:
        return {"error": f"Failed to fetch news for {ticker}: {str(e)}"}
