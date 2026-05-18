import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import verify_api_key
from app.db.database import get_db
from app.db.models import ScreenerPreset
from app.tools.remaining_tools import run_screener

router = APIRouter(prefix="/screener", tags=["screener"])


class ScreenerFilters(BaseModel):
    min_market_cap_b: float = 100.0
    min_volume: int = 1_000_000
    min_price_drop_pct: float = 10.0
    sector: str = "all"
    max_pe: float = 0.0
    universe: str = "sp500"  # sp500 | nasdaq100 | etfs | mega | legacy
    limit: int = 50  # max tickers to fetch (hard-capped at 150)


class SavePresetRequest(BaseModel):
    name: str
    filters: ScreenerFilters
    auto_monitor: bool = False


@router.post("/run")
async def run_screener_now(
    filters: ScreenerFilters,
    _: str = Depends(verify_api_key),
):
    """Run the screener immediately with given filters. Returns matching stocks."""
    try:
        result = await asyncio.to_thread(
            run_screener.invoke,
            {
                "min_market_cap_b": filters.min_market_cap_b,
                "min_volume": filters.min_volume,
                "min_price_drop_pct": filters.min_price_drop_pct,
                "sector": filters.sector,
                "max_pe": filters.max_pe,
                "universe": filters.universe,
                "limit": filters.limit,
            },
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Screener failed: {str(e)}")


@router.post("/presets")
async def save_preset(
    request: SavePresetRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Save a screener preset for reuse and optional auto-monitoring."""
    preset = ScreenerPreset(
        name=request.name,
        filters=request.filters.model_dump(),
        auto_monitor=request.auto_monitor,
    )
    db.add(preset)
    await db.commit()
    return {"message": f"Preset '{request.name}' saved", "id": preset.id}


@router.get("/presets")
async def get_presets(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Get all saved screener presets."""
    result = await db.execute(select(ScreenerPreset).order_by(ScreenerPreset.created_at.desc()))
    presets = result.scalars().all()
    return {
        "presets": [
            {
                "id": p.id,
                "name": p.name,
                "filters": p.filters,
                "auto_monitor": p.auto_monitor,
                "last_run": p.last_run.isoformat() if p.last_run else None,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in presets
        ]
    }


@router.post("/presets/{preset_id}/run")
async def run_preset(
    preset_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Run a saved preset by ID."""
    result = await db.execute(select(ScreenerPreset).where(ScreenerPreset.id == preset_id))
    preset = result.scalar_one_or_none()
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")

    filters = preset.filters
    try:
        screener_result = await asyncio.to_thread(run_screener.invoke, filters)
        preset.last_run = datetime.now(timezone.utc)
        await db.commit()
        return screener_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Screener failed: {str(e)}")


@router.patch("/presets/{preset_id}/toggle-monitor")
async def toggle_auto_monitor(
    preset_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Toggle background auto-monitoring for a preset."""
    result = await db.execute(select(ScreenerPreset).where(ScreenerPreset.id == preset_id))
    preset = result.scalar_one_or_none()
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")

    preset.auto_monitor = not preset.auto_monitor
    await db.commit()
    status = "enabled" if preset.auto_monitor else "disabled"
    return {"message": f"Auto-monitor {status} for '{preset.name}'"}
