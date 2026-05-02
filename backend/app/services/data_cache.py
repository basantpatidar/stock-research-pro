"""
Cache helpers for yfinance data (StockDataCache) and LLM results (ResearchCache).

All TTL values are read from app.config.Settings so they can be overridden via .env:
  CACHE_TTL_EARNINGS_FALLBACK_DAYS, CACHE_TTL_FUNDAMENTALS_DAYS,
  CACHE_TTL_ANALYST_DAYS, CACHE_TTL_SHORT_INTEREST_DAYS,
  CACHE_TTL_NEWS_HOURS, CACHE_TTL_CONGRESSIONAL_HOURS,
  CACHE_TTL_LLM_TIER2_HOURS, CACHE_TTL_LLM_TIER3_HOURS,
  CACHE_TTL_LLM_BACKTEST_HOURS
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import get_settings
from app.db.models import ResearchCache, StockDataCache


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stock_data_ttl_days(data_type: str) -> float:
    s = get_settings()
    return {
        "fundamentals": s.cache_ttl_fundamentals_days,
        "analyst": s.cache_ttl_analyst_days,
        "short_interest": s.cache_ttl_short_interest_days,
        "news": s.cache_ttl_news_hours / 24,
        "congressional": s.cache_ttl_congressional_hours / 24,
    }.get(data_type, 1)


def _llm_ttl_hours(tool_name: str) -> float:
    s = get_settings()
    short = s.cache_ttl_llm_short_hours   # 0.5h — intraday signals that move with price
    tier2 = s.cache_ttl_llm_tier2_hours   # 2h  — general tier2 fallback
    tier3 = s.cache_ttl_llm_tier3_hours   # 24h — daily analysis
    return {
        # 30-min window — recalculate as price/news changes throughout the day
        "get_convergence_score": short,
        "get_risk_reward": short,
        "get_sentiment": short,
        "get_options_intelligence": short,
        "get_mtf_confluence": short,
        # 1h — active paper trades need semi-fresh coaching
        "analyze_paper_trade": 1.0,
        # 2h — general tier2 fallback covers news, etc.
        "get_news_impact": tier2,
        # 24h — one reassessment per trading day is sufficient
        "get_price_forecast": tier3,
        "get_cascade_impact": tier3,
        "bull_bear_debate": tier3,
        "get_congressional_trades": tier3,
        # Quarterly — pure math on quarterly financials; expires with earnings cycle
        "get_earnings_quality": float(s.cache_ttl_earnings_quality_days * 24),
        # 7 days — expensive T3; thesis/backtest results change slowly
        "investor_personas": float(s.cache_ttl_llm_personas_hours),
        "run_backtest": float(s.cache_ttl_llm_backtest_hours),
        # Dynamic TTL — tier3 endpoint overrides expires_at to next_earnings_date
        "analyze_earnings_transcript": tier3,
    }.get(tool_name, tier2)


def earnings_expiry(result: dict) -> datetime:
    """Expire 2 days after next_earnings_date, or fall back to the configured day count."""
    ned = result.get("next_earnings_date") if isinstance(result, dict) else None
    if ned:
        try:
            dt = datetime.fromisoformat(str(ned)[:10])
            return dt.replace(tzinfo=timezone.utc) + timedelta(days=2)
        except (ValueError, TypeError):
            pass
    return _now() + timedelta(days=get_settings().cache_ttl_earnings_fallback_days)


def stock_data_expiry(data_type: str) -> datetime:
    return _now() + timedelta(days=_stock_data_ttl_days(data_type))


# ── StockDataCache ────────────────────────────────────────────────────────────

async def get_stock_cache(db: AsyncSession | None, ticker: str, data_type: str) -> dict | None:
    if db is None:
        return None
    result = await db.execute(
        select(StockDataCache).where(
            StockDataCache.ticker == ticker,
            StockDataCache.data_type == data_type,
            StockDataCache.expires_at > _now(),
        )
    )
    row = result.scalar_one_or_none()
    return row.data if row else None


async def get_earnings_cache(db: AsyncSession | None, ticker: str) -> dict | None:
    """Fetch cached earnings, but treat the cache as stale if next_earnings_date has passed.

    Prevents serving pre-earnings estimates after the actual report drops, regardless
    of what expires_at says — including when CACHE_TTL_EARNINGS_FALLBACK_DAYS is long.
    """
    if db is None:
        return None
    result = await db.execute(
        select(StockDataCache).where(
            StockDataCache.ticker == ticker,
            StockDataCache.data_type == "earnings",
            StockDataCache.expires_at > _now(),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None

    data = row.data
    ned = data.get("next_earnings_date") if isinstance(data, dict) else None
    if ned:
        try:
            earnings_dt = datetime.fromisoformat(str(ned)[:10]).replace(tzinfo=timezone.utc)
            if earnings_dt < _now():
                # Earnings have occurred — cached pre-earnings data is stale
                return None
        except (ValueError, TypeError):
            pass

    return data


async def set_stock_cache(
    db: AsyncSession | None,
    ticker: str,
    data_type: str,
    data: dict,
    expires_at: datetime,
) -> None:
    if db is None:
        return
    now = _now()
    stmt = (
        pg_insert(StockDataCache)
        .values(
            ticker=ticker,
            data_type=data_type,
            data=data,
            fetched_at=now,
            expires_at=expires_at,
        )
        .on_conflict_do_update(
            constraint="uq_stock_data_cache_ticker_type",
            set_={"data": data, "fetched_at": now, "expires_at": expires_at},
        )
    )
    await db.execute(stmt)
    await db.commit()


# ── ResearchCache (LLM results) ───────────────────────────────────────────────

async def get_llm_cache(db: AsyncSession | None, ticker: str, tool_name: str) -> dict | None:
    if db is None:
        return None
    result = await db.execute(
        select(ResearchCache).where(
            ResearchCache.ticker == ticker,
            ResearchCache.mode == tool_name,
            ResearchCache.expires_at > _now(),
        )
    )
    row = result.scalar_one_or_none()
    return row.result if row else None


async def set_llm_cache(
    db: AsyncSession | None,
    ticker: str,
    tool_name: str,
    data: dict,
    expires_at: datetime | None = None,
) -> None:
    if db is None:
        return
    now = _now()
    if expires_at is None:
        expires_at = now + timedelta(hours=_llm_ttl_hours(tool_name))
    stmt = (
        pg_insert(ResearchCache)
        .values(
            ticker=ticker,
            mode=tool_name,
            result=data,
            cached_at=now,
            expires_at=expires_at,
        )
        .on_conflict_do_update(
            constraint="uq_research_cache_ticker_mode",
            set_={"result": data, "cached_at": now, "expires_at": expires_at},
        )
    )
    await db.execute(stmt)
    await db.commit()
