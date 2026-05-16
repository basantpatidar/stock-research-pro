from langchain_core.tools import tool
import requests
from datetime import datetime, timedelta
from app.config import get_settings


def _resolve_company_name(ticker: str, company_name: str) -> str:
    """Return a clean company name for query building and relevance scoring."""
    if company_name:
        name = company_name
    else:
        try:
            from app.tools._yf_client import get_ticker
            info = get_ticker(ticker).info
            name = info.get("longName") or info.get("shortName") or ""
        except Exception:
            name = ""

    for suffix in (", Inc.", " Inc.", ", Corp.", " Corp.", ", Ltd.", " Ltd.",
                   ", LLC", " LLC", " Holdings", " Group", " Corporation"):
        name = name.replace(suffix, "")
    return name.strip()


def _build_query(company_name: str, ticker: str) -> str:
    """Build an exact-phrase NewsAPI query that avoids ambiguous ticker matches."""
    search_term = company_name if company_name else ticker.upper()
    financial_terms = "(stock OR shares OR earnings OR revenue OR investor OR quarterly OR NYSE OR NASDAQ OR SEC OR market)"
    return f'"{search_term}" AND {financial_terms}'


def _relevance_score(title: str, description: str, ticker: str, company_name: str) -> int:
    """
    Score 0–10: how specifically an article is about the given company.
    Checks title and description only — body-only mentions are off-topic noise.
    Avoids false positives for short ambiguous tickers (A, IT, NOW, WELL).
    """
    t = title.lower()
    d = (description or "").lower()
    tk = ticker.lower()
    co_words = [w for w in company_name.lower().split() if len(w) > 2]

    score = 0
    if len(tk) >= 4 and tk in t:
        score += 5
    if co_words and any(w in t for w in co_words):
        score += 4
    if len(tk) >= 4 and tk in d:
        score += 2
    if co_words and any(w in d for w in co_words):
        score += 1
    return score


_CATALYST_RULES: list[tuple[str, list[str]]] = [
    ("Earnings Beat/Miss",   ["beat", "miss", "earnings", "eps", "quarterly results", "revenue beat", "revenue miss"]),
    ("Analyst Upgrade",      ["upgrade", "outperform", "overweight", "buy rating", "price target raised", "target raised"]),
    ("Analyst Downgrade",    ["downgrade", "underperform", "underweight", "sell rating", "price target cut", "target cut"]),
    ("FDA / Regulatory",     ["fda", "approval", "approved", "cleared", "rejected", "clinical trial", "drug"]),
    ("Contract / Deal",      ["contract", "deal", "partnership", "agreement", "awarded", "signed"]),
    ("Product Launch",       ["launch", "unveiled", "announced", "new product", "release"]),
    ("Insider Buy",          ["insider buy", "insider purchase", "executive buy", "ceo buy"]),
    ("Legal / Regulatory",   ["lawsuit", "investigation", "probe", "antitrust", "fine", "penalty", "fraud", "sec"]),
    ("Macro Headwind",       ["tariff", "fed", "interest rate", "inflation", "recession", "gdp", "jobs report"]),
    ("Layoffs / Restructure",["layoff", "restructur", "job cut", "workforce reduction", "downsiz"]),
    ("M&A",                  ["acqui", "merger", "takeover", "buyout", "bid for"]),
    ("Earnings Warning",     ["warning", "guidance cut", "lowered guidance", "below expectations", "profit warning"]),
]

_STRENGTH_HIGH = ["beat", "raised", "upgrade", "approval", "contract", "merger", "acqui", "record", "fda approved"]
_STRENGTH_LOW  = ["watch", "consider", "analyst note", "report says", "could", "may"]


def _classify_catalyst(headline: str) -> str:
    h = headline.lower()
    for label, keywords in _CATALYST_RULES:
        if any(k in h for k in keywords):
            return label
    return "General News"


def _catalyst_strength(headline: str) -> str:
    h = headline.lower()
    if any(k in h for k in _STRENGTH_HIGH):
        return "HIGH"
    if any(k in h for k in _STRENGTH_LOW):
        return "LOW"
    return "MEDIUM"


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
                "catalyst_type": _classify_catalyst(title),
                "catalyst_strength": _catalyst_strength(title),
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
