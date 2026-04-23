from langchain_core.tools import tool
import requests
from datetime import datetime, timedelta
from app.config import get_settings


@tool
def get_news_impact(ticker: str, company_name: str = "", days: int = 7) -> dict:
    """
    Fetch recent news for a stock and analyze the impact of each headline.
    Returns headlines tagged positive/negative/neutral with estimated price impact.
    Uses NewsAPI — requires NEWSAPI_KEY in .env
    """
    try:
        settings = get_settings()

        if not settings.newsapi_key:
            return {"error": "NEWSAPI_KEY not configured. Get a free key at newsapi.org"}

        query = company_name if company_name else ticker
        from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        url = "https://newsapi.org/v2/everything"
        params = {
            "q": f"{query} stock",
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

            # Simple sentiment classification on headline
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

            if neg_count > pos_count:
                sentiment = "negative"
            elif pos_count > neg_count:
                sentiment = "positive"
            else:
                sentiment = "neutral"

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
