import requests
from langchain_core.tools import tool

from app.config import get_settings


@tool
def get_sentiment(ticker: str) -> dict:
    """
    Aggregate market sentiment from Reddit (WSB, r/stocks, r/investing)
    and StockTwits. Returns bullish/bearish/neutral breakdown and trending score.
    """
    results = {}

    # StockTwits — no auth required for public feed
    try:
        url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker.upper()}.json"
        response = requests.get(url, timeout=10)
        data = response.json()

        if "messages" in data:
            messages = data["messages"]
            bull = sum(
                1
                for m in messages
                if m.get("entities", {}).get("sentiment", {}).get("basic") == "Bullish"
            )
            bear = sum(
                1
                for m in messages
                if m.get("entities", {}).get("sentiment", {}).get("basic") == "Bearish"
            )
            total_tagged = bull + bear
            total = len(messages)

            results["stocktwits"] = {
                "total_messages": total,
                "bullish": bull,
                "bearish": bear,
                "bullish_pct": round((bull / total_tagged * 100) if total_tagged > 0 else 50, 1),
                "bearish_pct": round((bear / total_tagged * 100) if total_tagged > 0 else 50, 1),
                "untagged": total - total_tagged,
                "recent_sample": [
                    {
                        "text": m.get("body", "")[:120],
                        "sentiment": m.get("entities", {})
                        .get("sentiment", {})
                        .get("basic", "untagged"),
                        "created": m.get("created_at", "")[:10],
                    }
                    for m in messages[:5]
                ],
            }
        else:
            results["stocktwits"] = {"error": "No StockTwits data available"}
    except Exception as e:
        results["stocktwits"] = {"error": str(e)}

    # Reddit via PRAW
    settings = get_settings()
    if settings.reddit_client_id and settings.reddit_client_secret:
        try:
            import praw

            reddit = praw.Reddit(
                client_id=settings.reddit_client_id,
                client_secret=settings.reddit_client_secret,
                user_agent=settings.reddit_user_agent,
            )

            subreddits = ["wallstreetbets", "stocks", "investing"]
            reddit_posts = []
            mention_count = 0

            for sub in subreddits:
                try:
                    for post in reddit.subreddit(sub).search(
                        f"${ticker.upper()} OR {ticker.upper()} stock",
                        limit=10,
                        time_filter="week",
                        sort="relevance",
                    ):
                        mention_count += 1
                        title_lower = post.title.lower()

                        neg_words = ["bearish", "sell", "short", "drop", "crash", "puts", "down"]
                        pos_words = ["bullish", "buy", "calls", "moon", "long", "up", "squeeze"]

                        sentiment = "neutral"
                        if any(w in title_lower for w in pos_words):
                            sentiment = "bullish"
                        elif any(w in title_lower for w in neg_words):
                            sentiment = "bearish"

                        reddit_posts.append(
                            {
                                "subreddit": sub,
                                "title": post.title[:120],
                                "score": post.score,
                                "comments": post.num_comments,
                                "sentiment": sentiment,
                            }
                        )
                except Exception:
                    continue

            bull_reddit = sum(1 for p in reddit_posts if p["sentiment"] == "bullish")
            bear_reddit = sum(1 for p in reddit_posts if p["sentiment"] == "bearish")

            results["reddit"] = {
                "total_mentions": mention_count,
                "posts_analyzed": len(reddit_posts),
                "bullish": bull_reddit,
                "bearish": bear_reddit,
                "neutral": len(reddit_posts) - bull_reddit - bear_reddit,
                "top_posts": sorted(reddit_posts, key=lambda x: x["score"], reverse=True)[:5],
            }
        except Exception as e:
            results["reddit"] = {"error": f"Reddit fetch failed: {str(e)}"}
    else:
        results["reddit"] = {
            "error": "Reddit credentials not configured (REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET)"
        }

    # Aggregate
    st = results.get("stocktwits", {})
    st_bull = st.get("bullish_pct", 50) if "error" not in st else 50
    overall_sentiment = "Bullish" if st_bull > 60 else "Bearish" if st_bull < 40 else "Neutral"

    return {
        "ticker": ticker.upper(),
        "overall_sentiment": overall_sentiment,
        "stocktwits": results["stocktwits"],
        "reddit": results["reddit"],
    }
