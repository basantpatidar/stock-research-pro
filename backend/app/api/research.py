from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Literal
from langchain_core.messages import HumanMessage
import json
import asyncio

from app.agent.graph import get_agent
from app.auth import verify_api_key

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
