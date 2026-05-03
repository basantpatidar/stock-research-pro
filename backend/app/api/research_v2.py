from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Literal, Any
import asyncio
import logging
import time

import numpy as np

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import verify_api_key
from app.db.database import get_db_optional as get_db
from app.services.data_cache import (
    earnings_expiry,
    get_earnings_cache,
    get_llm_cache,
    get_stock_cache,
    set_llm_cache,
    set_stock_cache,
    stock_data_expiry,
)

from app.tools.price import get_price
from app.tools.technicals import get_technicals
from app.tools.analyst import get_analyst_consensus
from app.tools.earnings import get_earnings
from app.tools.fundamentals import get_fundamentals
from app.tools.short_interest import get_short_interest
from app.tools.new.congressional import get_congressional_trades
from app.tools.macro import get_macro_environment
from app.tools.sector import get_sector_heatmap

from app.tools.news import get_news_impact
from app.tools.sentiment import get_sentiment
from app.tools.convergence import get_convergence_score
from app.tools.forecast import get_price_forecast
from app.tools.risk_reward import get_risk_reward
from app.tools.earnings_quality import get_earnings_quality
from app.tools.options_intelligence import get_options_intelligence
from app.tools.technicals_mtf import get_mtf_confluence

from app.tools.pretrade_score import compute_pretrade_score
from app.tools.seasonality import get_seasonality
from app.tools.new.investor_personas import investor_personas
from app.tools.new.bull_bear import bull_bear_debate
from app.tools.new.backtester import run_backtest
from app.tools.new.earnings_transcript import analyze_earnings_transcript
from app.tools.new.paper_trade import analyze_paper_trade

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v2/research", tags=["research-v2"])

_TOKEN_ESTIMATES: dict[str, int] = {
    "get_news_impact": 600,
    "get_sentiment": 500,
    "get_convergence_score": 700,
    "get_price_forecast": 800,
    "get_risk_reward": 500,
    "get_earnings_quality": 0,       # pure math — no LLM tokens
    "get_options_intelligence": 0,   # pure math — no LLM tokens
    "get_mtf_confluence": 0,         # pure math — no LLM tokens
    "get_seasonality": 0,            # pure math — no LLM tokens
    "investor_personas": 5000,
    "bull_bear_debate": 6000,
    "run_backtest": 0,
    "analyze_earnings_transcript": 4000,
    "analyze_paper_trade": 800,
    "get_congressional_trades": 0,
}

_TIER2_TOOLS = {
    "get_news_impact": get_news_impact,
    "get_sentiment": get_sentiment,
    "get_convergence_score": get_convergence_score,
    "get_price_forecast": get_price_forecast,
    "get_risk_reward": get_risk_reward,
    "get_earnings_quality": get_earnings_quality,
    "get_options_intelligence": get_options_intelligence,
    "get_mtf_confluence": get_mtf_confluence,
    "get_seasonality": get_seasonality,
}

_TIER3_TOOLS = {
    "investor_personas": investor_personas,
    "bull_bear_debate": bull_bear_debate,
    "run_backtest": run_backtest,
    "analyze_earnings_transcript": analyze_earnings_transcript,
    "analyze_paper_trade": analyze_paper_trade,
    "get_congressional_trades": get_congressional_trades,
}


def _sanitize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


class Tier1Request(BaseModel):
    ticker: str
    mode: Literal["day_trade", "long_term", "both"] = "both"
    exec_mode: Literal["saver", "normal", "deep"] = "normal"


class Tier2Request(BaseModel):
    ticker: str
    tool: str
    mode: Literal["day_trade", "long_term", "both"] = "both"
    exec_mode: Literal["saver", "normal", "deep"] = "normal"
    params: dict = {}


class Tier3Request(BaseModel):
    ticker: str
    tool: str
    mode: Literal["day_trade", "long_term", "both"] = "both"
    params: dict = {}


@router.post("/tier1")
async def tier1(
    request: Tier1Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    sym = request.ticker.upper().strip()
    if not sym:
        raise HTTPException(status_code=400, detail="Ticker is required")

    t0 = time.perf_counter()

    # 1. Check cache sequentially — AsyncSession does not support concurrent operations
    cached_earnings = await get_earnings_cache(db, sym)
    cached_fundamentals = await get_stock_cache(db, sym, "fundamentals")
    cached_analyst = await get_stock_cache(db, sym, "analyst")
    cached_short_interest = await get_stock_cache(db, sym, "short_interest")
    cached_news = await get_stock_cache(db, sym, "news")
    cached_congressional = await get_stock_cache(db, sym, "congressional")

    needs = {
        "earnings": cached_earnings is None,
        "fundamentals": cached_fundamentals is None,
        "analyst": cached_analyst is None,
        "short_interest": cached_short_interest is None,
        "news": cached_news is None,
        "congressional": cached_congressional is None,
    }

    # 2. Fetch fresh data in a thread — only call yfinance for cache misses.
    #    Price, technicals, macro, sectors are always fresh (intraday data).
    def _run_fresh():
        price = get_price.invoke({"ticker": sym})
        company_name = price.get("company_name", "") if isinstance(price, dict) else ""
        technicals = get_technicals.invoke({"ticker": sym})
        macro = get_macro_environment.invoke({})
        sectors = get_sector_heatmap.invoke({})

        fresh: dict[str, Any] = {}
        if needs["earnings"]:
            fresh["earnings"] = get_earnings.invoke({"ticker": sym})
        if needs["fundamentals"]:
            fresh["fundamentals"] = get_fundamentals.invoke({"ticker": sym})
        if needs["analyst"]:
            fresh["analyst"] = get_analyst_consensus.invoke({"ticker": sym})
        if needs["short_interest"]:
            fresh["short_interest"] = get_short_interest.invoke({"ticker": sym})
        if needs["congressional"]:
            fresh["congressional"] = get_congressional_trades.invoke({"ticker": sym})
        if needs["news"]:
            fresh["news"] = get_news_impact.invoke({"ticker": sym, "company_name": company_name})

        return price, technicals, macro, sectors, fresh

    fresh_keys = [k for k, needed in needs.items() if needed]
    cached_keys = [k for k, needed in needs.items() if not needed]
    logger.info("tier1 %s — cache: %d/6 hits %s, fetching: %s",
                sym, len(cached_keys), cached_keys or "none", fresh_keys or "none")

    try:
        price, technicals, macro, sectors, fresh = await asyncio.to_thread(_run_fresh)
    except Exception as e:
        logger.exception("tier1 failed for %s", sym)
        raise HTTPException(status_code=500, detail=f"Tier1 fetch failed: {str(e)}")

    logger.info("tier1 %s done in %.0fms", sym, (time.perf_counter() - t0) * 1000)

    # 3. Merge cached and fresh results
    earnings = cached_earnings or fresh.get("earnings", {})
    fundamentals = cached_fundamentals or fresh.get("fundamentals", {})
    analyst = cached_analyst or fresh.get("analyst", {})
    short_interest = cached_short_interest or fresh.get("short_interest", {})
    congressional = cached_congressional or fresh.get("congressional", {})
    news = cached_news or fresh.get("news", {})

    # 4. Persist fresh results to cache (fire-and-forget — don't block the response)
    cache_writes = []
    if "earnings" in fresh:
        cache_writes.append(
            set_stock_cache(db, sym, "earnings", fresh["earnings"], earnings_expiry(fresh["earnings"]))
        )
    if "fundamentals" in fresh:
        cache_writes.append(
            set_stock_cache(db, sym, "fundamentals", fresh["fundamentals"], stock_data_expiry("fundamentals"))
        )
    if "analyst" in fresh:
        cache_writes.append(
            set_stock_cache(db, sym, "analyst", fresh["analyst"], stock_data_expiry("analyst"))
        )
    if "short_interest" in fresh:
        cache_writes.append(
            set_stock_cache(db, sym, "short_interest", fresh["short_interest"], stock_data_expiry("short_interest"))
        )
    if "congressional" in fresh:
        cache_writes.append(
            set_stock_cache(db, sym, "congressional", fresh["congressional"], stock_data_expiry("congressional"))
        )
    if "news" in fresh:
        cache_writes.append(
            set_stock_cache(db, sym, "news", fresh["news"], stock_data_expiry("news"))
        )
    for coro in cache_writes:
        try:
            await coro
        except Exception:
            pass

    cache_hits = sum(
        1 for v in [cached_earnings, cached_fundamentals, cached_analyst,
                    cached_short_interest, cached_news, cached_congressional]
        if v is not None
    )

    pretrade_score = compute_pretrade_score(
        price=price if isinstance(price, dict) else {},
        technicals=technicals if isinstance(technicals, dict) else {},
        short_interest=short_interest if isinstance(short_interest, dict) else {},
        news=news if isinstance(news, dict) else {},
        sectors=sectors if isinstance(sectors, dict) else {},
    )

    return _sanitize({
        "ticker": sym,
        "price": price,
        "technicals": technicals,
        "analyst": analyst,
        "earnings": earnings,
        "fundamentals": fundamentals,
        "short_interest": short_interest,
        "congressional": congressional,
        "news": news,
        "macro": macro,
        "sectors": sectors,
        "pretrade_score": pretrade_score,
        "cached": cache_hits > 0,
        "cache_hits": cache_hits,
        "exec_mode": request.exec_mode,
    })


@router.post("/tier2")
async def tier2(
    request: Tier2Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    sym = request.ticker.upper().strip()
    tool_fn = _TIER2_TOOLS.get(request.tool)
    if not tool_fn:
        raise HTTPException(status_code=400, detail=f"Unknown tier2 tool: {request.tool}")

    # Return cached LLM result if available (avoids re-running the same analysis)
    cached = await get_llm_cache(db, sym, request.tool)
    if cached:
        logger.info("tier2 %s %s — cache hit", request.tool, sym)
        return _sanitize({
            "ticker": sym,
            "tool": request.tool,
            "result": cached,
            "tokens_used": 0,
            "cached": True,
            "exec_mode": request.exec_mode,
        })

    t0 = time.perf_counter()
    invoke_params = {"ticker": sym, **request.params}
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(tool_fn.invoke, invoke_params),
            timeout=25.0,
        )
    except asyncio.TimeoutError:
        logger.warning("tier2 %s %s — timed out after 25s", request.tool, sym)
        raise HTTPException(status_code=504, detail=f"{request.tool} timed out — try again")
    except Exception as e:
        logger.exception("tier2 %s failed for %s", request.tool, sym)
        raise HTTPException(status_code=500, detail=f"Tier2 tool failed: {str(e)}")

    logger.info("tier2 %s %s — %.0fms, ~%d tokens",
                request.tool, sym, (time.perf_counter() - t0) * 1000,
                _TOKEN_ESTIMATES.get(request.tool, 500))

    # Persist for next request within the TTL window
    await set_llm_cache(db, sym, request.tool, result)

    return _sanitize({
        "ticker": sym,
        "tool": request.tool,
        "result": result,
        "tokens_used": _TOKEN_ESTIMATES.get(request.tool, 500),
        "cached": False,
        "exec_mode": request.exec_mode,
    })


@router.post("/tier3")
async def tier3(
    request: Tier3Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    sym = request.ticker.upper().strip()
    tool_fn = _TIER3_TOOLS.get(request.tool)
    if not tool_fn:
        raise HTTPException(status_code=400, detail=f"Unknown tier3 tool: {request.tool}")

    # Tier 3 tools are expensive (4k–6k tokens) — always check cache first
    cached = await get_llm_cache(db, sym, request.tool)
    if cached:
        logger.info("tier3 %s %s — cache hit", request.tool, sym)
        return _sanitize({
            "ticker": sym,
            "tool": request.tool,
            "result": cached,
            "tokens_used": 0,
            "cached": True,
        })

    t0 = time.perf_counter()
    invoke_params = {"ticker": sym, **request.params}
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(tool_fn.invoke, invoke_params),
            timeout=90.0,
        )
    except asyncio.TimeoutError:
        logger.warning("tier3 %s %s — timed out after 90s", request.tool, sym)
        raise HTTPException(status_code=504, detail=f"{request.tool} timed out — LLM or data fetch took too long")
    except Exception as e:
        logger.exception("tier3 %s failed for %s", request.tool, sym)
        raise HTTPException(status_code=500, detail=f"Tier3 tool failed: {str(e)}")

    logger.info("tier3 %s %s — %.0fms, ~%d tokens",
                request.tool, sym, (time.perf_counter() - t0) * 1000,
                _TOKEN_ESTIMATES.get(request.tool, 1000))

    # analyze_earnings_transcript is stable for the whole quarter — cache until next earnings date
    if request.tool == "analyze_earnings_transcript":
        await set_llm_cache(db, sym, request.tool, result, expires_at=earnings_expiry(result))
    else:
        await set_llm_cache(db, sym, request.tool, result)

    return _sanitize({
        "ticker": sym,
        "tool": request.tool,
        "result": result,
        "tokens_used": _TOKEN_ESTIMATES.get(request.tool, 1000),
        "cached": False,
    })


@router.get("/tier3/estimate")
async def tier3_estimate(
    tool: str = Query(...),
    ticker: str = Query(""),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    estimated = _TOKEN_ESTIMATES.get(tool, 1000)
    cost = round(estimated / 1_000_000 * 0.60, 6)

    is_cached = False
    if ticker:
        sym = ticker.upper().strip()
        hit = await get_llm_cache(db, sym, tool)
        is_cached = hit is not None

    return {
        "tool": tool,
        "estimated_tokens": 0 if is_cached else estimated,
        "estimated_cost_usd": 0.0 if is_cached else cost,
        "cached": is_cached,
    }
