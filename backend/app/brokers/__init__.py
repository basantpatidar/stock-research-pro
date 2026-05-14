"""Broker abstraction — paper trading first, live trading after sign-off.

Swap providers via the `BROKER` env var; swap paper/live via `BROKER_MODE`.
See docs/trading.md SEC:ARCH for the full design.
"""

from app.brokers.base import (
    AccountInfo,
    BaseBroker,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    PlaceOrderRequest,
    Position,
    TimeInForce,
)
from app.brokers.errors import BrokerError, BrokerRejected, BrokerUnreachable
from app.brokers.factory import get_broker

__all__ = [
    "AccountInfo",
    "BaseBroker",
    "BrokerError",
    "BrokerRejected",
    "BrokerUnreachable",
    "Order",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "PlaceOrderRequest",
    "Position",
    "TimeInForce",
    "get_broker",
]
