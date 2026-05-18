import asyncio

from fastapi import APIRouter, Depends

from app.auth import verify_api_key
from app.tools.economic_calendar import get_economic_calendar
from app.tools.fear_greed import get_fear_greed
from app.tools.fred_macro import get_fred_macro
from app.tools.geopolitical import get_geopolitical_events
from app.tools.market_breadth import get_market_breadth
from app.tools.remaining_tools import get_macro_environment, get_sector_heatmap

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
        get_geopolitical_events.invoke, {"query": "geopolitical market risk war sanctions trade"}
    )
    return result


@router.get("/fred")
async def fred_macro(_: str = Depends(verify_api_key)):
    """Fetch FRED credit, rates, liquidity, and cross-asset signals."""
    result = await asyncio.to_thread(get_fred_macro.invoke, {})
    return result


@router.get("/fear-greed")
async def fear_greed_index(_: str = Depends(verify_api_key)):
    """Fetch CNN Fear & Greed Index from Alternative.me (no API key required)."""
    result = await asyncio.to_thread(get_fear_greed)
    return result


@router.get("/calendar")
async def economic_calendar(_: str = Depends(verify_api_key)):
    """Fetch upcoming high-impact economic events from FRED release schedule."""
    result = await asyncio.to_thread(get_economic_calendar)
    return result


@router.get("/breadth")
async def market_breadth_endpoint(_: str = Depends(verify_api_key)):
    """Fetch market breadth indicators — % above 50d/200d MA, advance/decline, 52w H/L."""
    result = await asyncio.to_thread(get_market_breadth)
    return result


@router.get("/all")
async def all_macro(_: str = Depends(verify_api_key)):
    """Fetch all macro data in one call — environment, sectors, geopolitical, FRED, fear/greed, calendar, breadth."""
    env, sectors, geo, fred, fear_greed, calendar, breadth = await asyncio.gather(
        asyncio.to_thread(get_macro_environment.invoke, {}),
        asyncio.to_thread(get_sector_heatmap.invoke, {}),
        asyncio.to_thread(get_geopolitical_events.invoke, {"query": "geopolitical market risk"}),
        asyncio.to_thread(get_fred_macro.invoke, {}),
        asyncio.to_thread(get_fear_greed),
        asyncio.to_thread(get_economic_calendar),
        asyncio.to_thread(get_market_breadth),
    )
    return {
        "environment": env,
        "sectors": sectors,
        "geopolitical": geo,
        "fred": fred,
        "fear_greed": fear_greed,
        "calendar": calendar,
        "breadth": breadth,
    }
