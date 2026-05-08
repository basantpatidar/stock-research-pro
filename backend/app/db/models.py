from datetime import datetime
from typing import Any
import uuid

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
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


class ScannerAlert(Base):
    """Records every dip-buy alert fired (live or backtest) and its price outcome."""

    __tablename__ = "scanner_alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    target_price: Mapped[float] = mapped_column(Float, nullable=False)
    stop_price: Mapped[float] = mapped_column(Float, nullable=False)
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    signals: Mapped[Any] = mapped_column(JSONB, nullable=True)
    session_window: Mapped[str | None] = mapped_column(String(30), nullable=True)
    vix_at_entry: Mapped[float | None] = mapped_column(Float, nullable=True)
    capital_used: Mapped[float] = mapped_column(Float, default=1000.0)
    source: Mapped[str] = mapped_column(String(20), default="live")   # "live" | "backtest"
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)  # open / win / loss / expired
    outcome_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_pnl_dollar: Mapped[float | None] = mapped_column(Float, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(30), nullable=True)  # target_hit / stop_hit / eod_close


class StockDataCache(Base):
    """Caches slow-changing yfinance data keyed by (ticker, data_type).

    data_type values and their TTLs (override via .env CACHE_TTL_* vars):
      earnings        — until next_earnings_date + 2 days (quarterly; dynamic)
      fundamentals    — 30 days  (quarterly: P/E, margins, FCF)
      analyst         — 1 day    (price targets shift weekly)
      short_interest  — 7 days   (FINRA bi-weekly)
      news            — 30 min   (stale news causes bad signals)
      congressional   — 24 hours (sporadic STOCK Act filings)
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
