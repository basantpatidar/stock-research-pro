from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Literal, Any
from langchain_core.messages import HumanMessage
import json
import asyncio
import logging
import numpy as np

from app.agent.graph import get_agent
from app.auth import verify_api_key
from app.tools.price import get_price
from app.tools.technicals import get_technicals
from app.tools.analyst import get_analyst_consensus
from app.tools.earnings import get_earnings
from app.tools.news import get_news_impact

logger = logging.getLogger(__name__)


def _sanitize(obj: Any) -> Any:
    """Recursively convert numpy scalars to JSON-serializable Python types."""
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

router = APIRouter(prefix="/research", tags=["research"])


class ResearchRequest(BaseModel):
    ticker: str
    mode: Literal["day_trade", "long_term", "both"] = "both"
    depth: Literal["quick", "deep"] = "quick"
    question: str = ""


@router.post("/")
async def run_research(
    request: ResearchRequest,
    _: str = Depends(verify_api_key),
):
    """
    Run full agent research on a ticker. Returns structured JSON result.
    For streaming reasoning steps use GET /research/stream instead.
    """
    ticker = request.ticker.upper().strip()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker is required")

    question = request.question or f"Give me a full research brief on {ticker}. Mode: {request.mode}."

    try:
        agent = get_agent()
        result = await asyncio.to_thread(
            agent.invoke,
            {
                "messages": [HumanMessage(content=question)],
                "ticker": ticker,
                "mode": request.mode,
                "research_depth": request.depth,
            }
        )

        messages = result.get("messages", [])
        final_message = messages[-1].content if messages else "No result"

        return {
            "ticker": ticker,
            "mode": request.mode,
            "result": final_message,
            "tool_calls": len([m for m in messages if hasattr(m, "tool_calls") and m.tool_calls]),
        }
    except Exception as e:
        msg = str(e).lower()
        if "quota" in msg or "rate" in msg or "429" in msg or "exhausted" in msg:
            raise HTTPException(status_code=429, detail="LLM quota exhausted — all providers failed. Try again later.")
        raise HTTPException(status_code=500, detail=f"Research failed: {str(e)}")


@router.get("/data")
async def get_research_data(
    ticker: str = Query(..., description="Stock ticker symbol"),
    _: str = Depends(verify_api_key),
):
    """
    Fetch structured stock data directly from tools — no LLM, no agent, fast.
    Returns price, technicals, analyst consensus, earnings, and news.
    """
    sym = ticker.upper().strip()
    if not sym:
        raise HTTPException(status_code=400, detail="Ticker is required")

    def _call_tools():
        price = get_price.invoke({"ticker": sym})
        technicals = get_technicals.invoke({"ticker": sym})
        analyst = get_analyst_consensus.invoke({"ticker": sym})
        earnings = get_earnings.invoke({"ticker": sym})
        news = get_news_impact.invoke({"ticker": sym})
        return price, technicals, analyst, earnings, news

    try:
        price, technicals, analyst, earnings, news = await asyncio.to_thread(_call_tools)

        logger.info(
            "research/data %s — price_ok=%s technicals_ok=%s analyst_ok=%s earnings_ok=%s news_ok=%s",
            sym,
            "error" not in price,
            "error" not in technicals,
            "error" not in analyst,
            "error" not in earnings,
            "error" not in news,
        )
        if "error" in price:
            logger.warning("price error for %s: %s", sym, price["error"])
        if "error" in technicals:
            logger.warning("technicals error for %s: %s", sym, technicals["error"])
        if "error" in analyst:
            logger.warning("analyst error for %s: %s", sym, analyst["error"])
        if "error" in earnings:
            logger.warning("earnings error for %s: %s", sym, earnings["error"])
        if "error" in news:
            logger.warning("news error for %s: %s", sym, news["error"])

        return _sanitize({
            "ticker": sym,
            "price": price,
            "technicals": technicals,
            "analyst": analyst,
            "earnings": earnings,
            "news": news,
        })
    except Exception as e:
        logger.exception("research/data failed for %s", sym)
        raise HTTPException(status_code=500, detail=f"Data fetch failed: {str(e)}")


@router.get("/stream")
async def stream_research(
    ticker: str,
    mode: str = "both",
    depth: str = "quick",
    _: str = Depends(verify_api_key),
):
    """
    Stream agent reasoning steps via SSE.
    Each event shows the agent thinking, tool calls, and tool results in real time.
    """
    ticker = ticker.upper().strip()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker is required")

    async def event_generator():
        try:
            question = f"Give me a full research brief on {ticker}. Mode: {mode}. Depth: {depth}."

            yield f"data: {json.dumps({'type': 'start', 'ticker': ticker, 'mode': mode})}\n\n"

            events = await asyncio.to_thread(
                lambda: list(
                    get_agent().stream(
                        {
                            "messages": [HumanMessage(content=question)],
                            "ticker": ticker,
                            "mode": mode,
                            "research_depth": depth,
                        }
                    )
                )
            )

            for event in events:
                messages = event.get("messages", [])
                if not messages:
                    continue

                last = messages[-1]

                # Tool call — agent is fetching data
                if hasattr(last, "tool_calls") and last.tool_calls:
                    for tc in last.tool_calls:
                        payload = {
                            "type": "tool_call",
                            "tool": tc["name"],
                            "args": tc["args"],
                        }
                        yield f"data: {json.dumps(payload)}\n\n"
                        await asyncio.sleep(0)

                # Tool result — data came back
                elif hasattr(last, "name") and last.name:
                    content = last.content
                    if isinstance(content, str):
                        try:
                            content = json.loads(content)
                        except Exception:
                            pass
                    payload = {
                        "type": "tool_result",
                        "tool": last.name,
                        "result": content,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                    await asyncio.sleep(0)

                # Agent reasoning / final answer
                elif hasattr(last, "content") and last.content:
                    payload = {
                        "type": "reasoning",
                        "content": last.content,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                    await asyncio.sleep(0)

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
