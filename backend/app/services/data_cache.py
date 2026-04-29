"""
Cache helpers for yfinance data (StockDataCache) and LLM results (ResearchCache).

StockDataCache — keyed by (ticker, data_type), TTL varies by data_type:
  earnings       → until next_earnings_date + 2 days  (quarterly data)
  fundamentals   → 7 days
  analyst        → 7 days
  short_interest → 14 days
  news           → 2 hours
  congressional  → 2 hours

ResearchCache — keyed by (ticker, tool_name), TTL varies by tool:
  Tier 2 tools   → 2 hours
  Tier 3 tools   → 4 hours
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models import ResearchCache, StockDataCache

_STOCK_DATA_TTL_DAYS: dict[str, float] = {
    "fundamentals": 7,
    "analyst": 7,
    "short_interest": 14,
    "news": 2 / 24,        # 2 hours
    "congressional": 2 / 24,
}

_LLM_CACHE_TTL_HOURS: dict[str, float] = {
    "get_news_impact": 2,
    "get_sentiment": 2,
    "get_convergence_score": 2,
    "get_price_forecast": 2,
    "get_risk_reward": 2,
    "investor_personas": 4,
    "bull_bear_debate": 4,
    "analyze_earnings_transcript": 4,
    "run_backtest": 24,
    "get_congressional_trades": 2,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def earnings_expiry(result: dict) -> datetime:
    """Set expiry to 2 days after the next earnings date, or 7 days if unknown."""
    ned = result.get("next_earnings_date") if isinstance(result, dict) else None
    if ned:
        try:
            dt = datetime.fromisoformat(str(ned)[:10])
            return dt.replace(tzinfo=timezone.utc) + timedelta(days=2)
        except (ValueError, TypeError):
            pass
    return _now() + timedelta(days=7)


def stock_data_expiry(data_type: str) -> datetime:
    days = _STOCK_DATA_TTL_DAYS.get(data_type, 1)
    return _now() + timedelta(days=days)


# ── StockDataCache ────────────────────────────────────────────────────────────

async def get_stock_cache(db: AsyncSession, ticker: str, data_type: str) -> dict | None:
    result = await db.execute(
        select(StockDataCache).where(
            StockDataCache.ticker == ticker,
            StockDataCache.data_type == data_type,
            StockDataCache.expires_at > _now(),
        )
    )
    row = result.scalar_one_or_none()
    return row.data if row else None


async def set_stock_cache(
    db: AsyncSession,
    ticker: str,
    data_type: str,
    data: dict,
    expires_at: datetime,
) -> None:
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

async def get_llm_cache(db: AsyncSession, ticker: str, tool_name: str) -> dict | None:
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
    db: AsyncSession,
    ticker: str,
    tool_name: str,
    data: dict,
) -> None:
    ttl_hours = _LLM_CACHE_TTL_HOURS.get(tool_name, 2.0)
    now = _now()
    expires_at = now + timedelta(hours=ttl_hours)
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
