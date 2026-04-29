from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Literal, Any
import asyncio
import numpy as np
import logging

from app.auth import verify_api_key

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
async def tier1(request: Tier1Request, _: str = Depends(verify_api_key)):
    sym = request.ticker.upper().strip()
    if not sym:
        raise HTTPException(status_code=400, detail="Ticker is required")

    def _run_all():
        price = get_price.invoke({"ticker": sym})
        # Pass company_name so news tool skips its own yfinance lookup
        company_name = price.get("company_name", "") if isinstance(price, dict) else ""
        technicals = get_technicals.invoke({"ticker": sym})
        analyst = get_analyst_consensus.invoke({"ticker": sym})
        earnings = get_earnings.invoke({"ticker": sym})
        fundamentals = get_fundamentals.invoke({"ticker": sym})
        short_interest = get_short_interest.invoke({"ticker": sym})
        congressional = get_congressional_trades.invoke({"ticker": sym})
        news = get_news_impact.invoke({"ticker": sym, "company_name": company_name})
        macro = get_macro_environment.invoke({})
        sectors = get_sector_heatmap.invoke({})
        return price, technicals, analyst, earnings, fundamentals, short_interest, congressional, news, macro, sectors

    try:
        results = await asyncio.to_thread(_run_all)
        price, technicals, analyst, earnings, fundamentals, short_interest, congressional, news, macro, sectors = results
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
            "cached": False,
            "exec_mode": request.exec_mode,
        })
    except Exception as e:
        logger.exception("tier1 failed for %s", sym)
        raise HTTPException(status_code=500, detail=f"Tier1 fetch failed: {str(e)}")


@router.post("/tier2")
async def tier2(request: Tier2Request, _: str = Depends(verify_api_key)):
    sym = request.ticker.upper().strip()
    tool_fn = _TIER2_TOOLS.get(request.tool)
    if not tool_fn:
        raise HTTPException(status_code=400, detail=f"Unknown tier2 tool: {request.tool}")

    invoke_params = {"ticker": sym, **request.params}
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(tool_fn.invoke, invoke_params),
            timeout=25.0,
        )
        return _sanitize({
            "ticker": sym,
            "tool": request.tool,
            "result": result,
            "tokens_used": _TOKEN_ESTIMATES.get(request.tool, 500),
            "cached": False,
            "exec_mode": request.exec_mode,
        })
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail=f"{request.tool} timed out — try again")
    except Exception as e:
        logger.exception("tier2 %s failed for %s", request.tool, sym)
        raise HTTPException(status_code=500, detail=f"Tier2 tool failed: {str(e)}")


@router.post("/tier3")
async def tier3(request: Tier3Request, _: str = Depends(verify_api_key)):
    sym = request.ticker.upper().strip()
    tool_fn = _TIER3_TOOLS.get(request.tool)
    if not tool_fn:
        raise HTTPException(status_code=400, detail=f"Unknown tier3 tool: {request.tool}")

    invoke_params = {"ticker": sym, **request.params}
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(tool_fn.invoke, invoke_params),
            timeout=90.0,
        )
        return _sanitize({
            "ticker": sym,
            "tool": request.tool,
            "result": result,
            "tokens_used": _TOKEN_ESTIMATES.get(request.tool, 1000),
            "cached": False,
        })
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail=f"{request.tool} timed out — LLM or data fetch took too long")
    except Exception as e:
        logger.exception("tier3 %s failed for %s", request.tool, sym)
        raise HTTPException(status_code=500, detail=f"Tier3 tool failed: {str(e)}")


@router.get("/tier3/estimate")
async def tier3_estimate(
    tool: str = Query(...),
    ticker: str = Query(""),
    _: str = Depends(verify_api_key),
):
    estimated = _TOKEN_ESTIMATES.get(tool, 1000)
    cost = round(estimated / 1_000_000 * 0.60, 6)
    return {
        "tool": tool,
        "estimated_tokens": estimated,
        "estimated_cost_usd": cost,
        "cached": False,
    }
