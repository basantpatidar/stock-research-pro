import asyncio
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.auth import verify_api_key
from app.tools.gap_scanner import scan_gaps

router = APIRouter(prefix="/gap-scanner", tags=["gap-scanner"])


class ScanRequest(BaseModel):
    tickers: list[str]
    threshold_pct: float = 2.0


@router.post("/")
async def run_gap_scan(
    request: ScanRequest,
    _: str = Depends(verify_api_key),
):
    tickers = [t.upper().strip() for t in request.tickers if t.strip()][:50]
    result = await asyncio.to_thread(scan_gaps, tickers, request.threshold_pct)
    return result
