from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
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
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    result: Mapped[Any] = mapped_column(JSONB, nullable=False)
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
