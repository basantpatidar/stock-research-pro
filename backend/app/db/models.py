from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_signal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_evaluated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ScreenerPreset(Base):
    __tablename__ = "screener_presets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    filters: Mapped[Any] = mapped_column(JSONB, nullable=False, default=dict)
    auto_monitor: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_run: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AlertHistory(Base):
    __tablename__ = "alert_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False)


class ResearchCache(Base):
    __tablename__ = "research_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    # tool name, e.g. "get_convergence_score" — widened from 20 to support all tool names
    mode: Mapped[str] = mapped_column(String(100), nullable=False)
    result: Mapped[Any] = mapped_column(JSONB, nullable=False)
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("ticker", "mode", name="uq_research_cache_ticker_mode"),
    )


class StockDataCache(Base):
    """Caches slow-changing yfinance data keyed by (ticker, data_type).

    data_type values and their TTLs:
      earnings        — until next_earnings_date + 2 days (quarterly)
      fundamentals    — 7 days
      analyst         — 7 days
      short_interest  — 14 days
      news            — 2 hours
      congressional   — 2 hours
    """

    __tablename__ = "stock_data_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    data_type: Mapped[str] = mapped_column(String(30), nullable=False)
    data: Mapped[Any] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("ticker", "data_type", name="uq_stock_data_cache_ticker_type"),
    )
