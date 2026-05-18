from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import verify_api_key
from app.db.database import get_db
from app.db.models import WatchlistItem

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchlistAddRequest(BaseModel):
    ticker: str
    company_name: Optional[str] = None
    notes: Optional[str] = None


class WatchlistUpdateRequest(BaseModel):
    notes: Optional[str] = None
    active: Optional[bool] = None


@router.get("/")
async def get_watchlist(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Get all active watchlist items with their latest signals."""
    result = await db.execute(
        select(WatchlistItem)
        .where(WatchlistItem.is_active.is_(True))
        .order_by(WatchlistItem.last_score.desc().nullslast())
    )
    items = result.scalars().all()
    return {
        "count": len(items),
        "items": [
            {
                "id": item.id,
                "ticker": item.ticker,
                "last_signal": item.last_signal,
                "last_score": item.last_score,
                "last_price": item.last_price,
                "last_evaluated": item.last_evaluated.isoformat() if item.last_evaluated else None,
                "added_at": item.added_at.isoformat() if item.added_at else None,
            }
            for item in items
        ],
    }


@router.post("/")
async def add_to_watchlist(
    request: WatchlistAddRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Add a ticker to the watchlist."""
    ticker = request.ticker.upper().strip()

    existing = await db.execute(select(WatchlistItem).where(WatchlistItem.ticker == ticker))
    existing_item = existing.scalar_one_or_none()

    if existing_item:
        if not existing_item.is_active:
            existing_item.is_active = True
            await db.commit()
            return {"message": f"{ticker} re-activated in watchlist", "ticker": ticker}
        raise HTTPException(status_code=409, detail=f"{ticker} already in watchlist")

    item = WatchlistItem(ticker=ticker)
    db.add(item)
    await db.commit()
    return {"message": f"{ticker} added to watchlist", "ticker": ticker}


@router.delete("/{ticker}")
async def remove_from_watchlist(
    ticker: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Remove a ticker from the watchlist (soft delete)."""
    ticker = ticker.upper().strip()
    result = await db.execute(select(WatchlistItem).where(WatchlistItem.ticker == ticker))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail=f"{ticker} not in watchlist")

    item.is_active = False
    await db.commit()
    return {"message": f"{ticker} removed from watchlist"}


@router.get("/signals")
async def get_watchlist_signals(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Get only the tickers with active buy/sell signals.
    Used by the dashboard alert panel.
    """
    result = await db.execute(
        select(WatchlistItem)
        .where(
            WatchlistItem.is_active.is_(True),
            WatchlistItem.last_signal.in_(["Buy now", "Buy — 1 week", "Sell", "Avoid"]),
        )
        .order_by(WatchlistItem.last_score.desc())
    )
    items = result.scalars().all()
    return {
        "signals": [
            {
                "ticker": item.ticker,
                "signal": item.last_signal,
                "score": item.last_score,
                "price": item.last_price,
                "evaluated": item.last_evaluated.isoformat() if item.last_evaluated else None,
            }
            for item in items
        ]
    }
