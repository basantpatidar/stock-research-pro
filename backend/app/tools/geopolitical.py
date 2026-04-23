from langchain_core.tools import tool
import requests
from app.config import get_settings


SECTOR_IMPACT_MAP = {
    "oil": {
        "high_impact": ["Energy", "Airlines", "Shipping", "Transportation"],
        "medium_impact": ["Consumer Goods", "Technology", "Manufacturing"],
        "positive_impact": ["Defense", "Gold/Metals"],
    },
    "semiconductor": {
        "high_impact": ["Technology", "Semiconductors", "Consumer Electronics"],
        "medium_impact": ["Automotive", "Cloud Infrastructure"],
        "positive_impact": [],
    },
    "trade": {
        "high_impact": ["Consumer Goods", "Technology", "Agriculture"],
        "medium_impact": ["Financials", "Manufacturing"],
        "positive_impact": ["Domestic producers"],
    },
    "war": {
        "high_impact": ["Airlines", "Tourism", "Consumer Discretionary"],
        "medium_impact": ["Technology", "Financials"],
        "positive_impact": ["Defense", "Energy", "Gold"],
    },
    "sanctions": {
        "high_impact": ["Energy", "Financials", "Technology"],
        "medium_impact": ["Consumer Goods"],
        "positive_impact": ["Domestic alternatives"],
    },
}


@tool
def get_geopolitical_events(query: str = "geopolitical market risk") -> dict:
    """
    Fetch active geopolitical events and their market impact from news sources.
    Identifies events like wars, sanctions, trade disputes that affect broad market.
    Returns events with severity level and impacted sectors.
    """
    try:
        settings = get_settings()
        events = []

        if settings.newsapi_key:
            geo_queries = [
                "war oil supply stock market",
                "sanctions trade war stock market",
                "geopolitical risk market",
                "Fed interest rates inflation",
                "trade tariffs economy stocks",
            ]

            for q in geo_queries[:2]:
                url = "https://newsapi.org/v2/everything"
                params = {
                    "q": q,
                    "sortBy": "publishedAt",
                    "language": "en",
                    "pageSize": 5,
                    "apiKey": settings.newsapi_key,
                }
                try:
                    r = requests.get(url, params=params, timeout=8)
                    data = r.json()
                    for article in data.get("articles", []):
                        title = article.get("title", "")
                        if not title:
                            continue

                        title_lower = title.lower()
                        severity = "medium"
                        if any(w in title_lower for w in ["war", "attack", "blockade", "invasion", "crisis"]):
                            severity = "critical"
                        elif any(w in title_lower for w in ["sanctions", "ban", "tariff", "probe", "investigation"]):
                            severity = "high"

                        impacted = []
                        if any(w in title_lower for w in ["oil", "energy", "opec", "hormuz"]):
                            impacted = SECTOR_IMPACT_MAP["oil"]["high_impact"]
                        elif any(w in title_lower for w in ["chip", "semiconductor", "tech ban"]):
                            impacted = SECTOR_IMPACT_MAP["semiconductor"]["high_impact"]
                        elif any(w in title_lower for w in ["trade", "tariff", "china"]):
                            impacted = SECTOR_IMPACT_MAP["trade"]["high_impact"]

                        events.append({
                            "title": title,
                            "source": article.get("source", {}).get("name", ""),
                            "published": article.get("publishedAt", "")[:10],
                            "severity": severity,
                            "impacted_sectors": impacted,
                            "url": article.get("url", ""),
                        })
                except Exception:
                    continue

        # Deduplicate by title similarity
        seen = set()
        unique_events = []
        for e in events:
            key = e["title"][:50]
            if key not in seen:
                seen.add(key)
                unique_events.append(e)

        critical = [e for e in unique_events if e["severity"] == "critical"]
        high = [e for e in unique_events if e["severity"] == "high"]

        market_stress = (
            "HIGH — critical geopolitical events active" if critical
            else "ELEVATED — significant events in play" if high
            else "NORMAL"
        )

        return {
            "query": query,
            "events_found": len(unique_events),
            "market_stress_level": market_stress,
            "critical_events": critical,
            "high_severity_events": high,
            "all_events": unique_events[:10],
        }
    except Exception as e:
        return {"error": f"Failed to fetch geopolitical events: {str(e)}"}
