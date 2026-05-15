"""Broker factory — mirrors backend/app/llm/factory.py shape.

`get_broker(settings)` is the only call site the rest of the app uses. To add
a new broker, add a branch here and a module beside this file. See
docs/trading.md SEC:ARCH for the design.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from app.brokers.base import BaseBroker
from app.brokers.errors import BrokerError

if TYPE_CHECKING:
    from app.config import Settings


def get_broker(settings: "Settings") -> BaseBroker:
    """Return the configured broker. Raises BrokerError on misconfiguration."""
    provider = (settings.broker or "alpaca").lower()
    mode = (settings.broker_mode or "paper").lower()
    if mode not in ("paper", "live"):
        raise BrokerError(f"BROKER_MODE must be 'paper' or 'live', got '{mode}'")

    if provider == "alpaca":
        from app.brokers.alpaca import AlpacaBroker
        return AlpacaBroker(
            api_key=settings.alpaca_api_key,
            api_secret=settings.alpaca_api_secret,
            mode=mode,
            base_url=settings.alpaca_base_url or None,
        )

    raise BrokerError(
        f"Unknown BROKER '{provider}'. Supported: alpaca. "
        "Add a new provider under backend/app/brokers/ and wire it in factory.py."
    )


@lru_cache(maxsize=1)
def get_broker_cached() -> BaseBroker:
    """Per-process cached broker instance. Use this from request handlers.

    Cache key is implicit (no args) — settings is read fresh inside get_broker.
    Restart the backend after rotating ALPACA_* keys or changing BROKER_MODE.
    """
    from app.config import get_settings
    return get_broker(get_settings())
