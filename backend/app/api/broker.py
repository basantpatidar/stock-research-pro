"""Broker / order execution routes.

Phase 1 ships GET /broker/account only — proof that the broker layer is
wired end-to-end before any UI gets built against it. See docs/api.md
SEC:BROKER_ROUTES for the full route plan and docs/trading.md SEC:PHASES
for the rollout.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response

from app.auth import verify_api_key
from app.brokers import AccountInfo, BrokerError, BrokerUnreachable, get_broker
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/broker", tags=["broker"])


@router.get("/account", response_model=AccountInfo, dependencies=[Depends(verify_api_key)])
def get_broker_account(response: Response) -> AccountInfo:
    """Smoke test for broker connectivity. Returns broker name, mode, and
    account snapshot. Use this to verify ALPACA_API_KEY / ALPACA_API_SECRET
    are valid before building UI against the broker layer.

    Returns 503 with X-Broker-Status: unreachable when the broker API is
    down or credentials are missing — the frontend uses that header to
    show a connectivity banner instead of a blank page.
    """
    settings = get_settings()
    try:
        broker = get_broker(settings)
        return broker.get_account()
    except BrokerUnreachable as exc:
        logger.warning("broker unreachable: %s", exc)
        response.headers["X-Broker-Status"] = "unreachable"
        raise HTTPException(status_code=503, detail=str(exc))
    except BrokerError as exc:
        # Misconfiguration (missing keys, unknown provider) — distinct from
        # transient failure. Surface as 503 so the UI shows the same banner
        # but log loudly for ops.
        logger.error("broker misconfigured: %s", exc)
        response.headers["X-Broker-Status"] = "misconfigured"
        raise HTTPException(status_code=503, detail=str(exc))
