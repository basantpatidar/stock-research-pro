from fastapi import APIRouter, Depends
from app.auth import verify_api_key
from app.tools.remaining_tools import get_macro_environment, get_sector_heatmap
from app.tools.geopolitical import get_geopolitical_events
import asyncio

router = APIRouter(prefix="/macro", tags=["macro"])


@router.get("/environment")
async def macro_environment(_: str = Depends(verify_api_key)):
    """Fetch current macro market environment — VIX, S&P, oil, yields, risk status."""
    result = await asyncio.to_thread(get_macro_environment.invoke, {})
    return result


@router.get("/sectors")
async def sector_heatmap(_: str = Depends(verify_api_key)):
    """Fetch sector performance heatmap for the last 5 days."""
    result = await asyncio.to_thread(get_sector_heatmap.invoke, {})
    return result


@router.get("/geopolitical")
async def geopolitical_events(_: str = Depends(verify_api_key)):
    """Fetch active geopolitical events and their market impact."""
    result = await asyncio.to_thread(
        get_geopolitical_events.invoke,
        {"query": "geopolitical market risk war sanctions trade"}
    )
    return result


@router.get("/all")
async def all_macro(_: str = Depends(verify_api_key)):
    """Fetch all macro data in one call — environment, sectors, and geopolitical events."""
    env, sectors, geo = await asyncio.gather(
        asyncio.to_thread(get_macro_environment.invoke, {}),
        asyncio.to_thread(get_sector_heatmap.invoke, {}),
        asyncio.to_thread(
            get_geopolitical_events.invoke,
            {"query": "geopolitical market risk"}
        ),
    )
    return {
        "environment": env,
        "sectors": sectors,
        "geopolitical": geo,
    }
