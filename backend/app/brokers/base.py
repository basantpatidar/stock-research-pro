"""BaseBroker interface + Pydantic DTOs.

Every provider implementation converts its native types to the DTOs below
so the API layer and the frontend never care which broker is configured.
See docs/trading.md SEC:ARCH for the full design.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class TimeInForce(str, Enum):
    DAY = "day"
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"


class OrderStatus(str, Enum):
    NEW = "new"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class AccountInfo(BaseModel):
    broker: str
    mode: Literal["paper", "live"]
    cash: float
    buying_power: float
    equity: float
    # Previous trading day's close equity — used by the daily-loss cap to
    # compute today's P&L (`equity - last_equity`). Optional because not
    # every broker exposes it; cap falls back to "skip" when None.
    last_equity: float | None = None
    daytrade_count: int


class Position(BaseModel):
    symbol: str
    qty: float
    avg_entry_price: float
    current_price: float
    market_value: float
    unrealized_pl: float
    unrealized_pl_pct: float


class Order(BaseModel):
    broker_order_id: str
    client_order_id: str | None = None
    symbol: str
    side: OrderSide
    qty: float
    order_type: OrderType
    limit_price: float | None = None
    stop_price: float | None = None
    take_profit_price: float | None = None
    time_in_force: TimeInForce
    status: OrderStatus
    filled_qty: float = 0.0
    filled_avg_price: float | None = None
    submitted_at: datetime
    filled_at: datetime | None = None
    canceled_at: datetime | None = None
    rejected_reason: str | None = None


class PlaceOrderRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=10)
    side: OrderSide
    qty: float = Field(..., gt=0)
    order_type: OrderType
    limit_price: float | None = Field(default=None, gt=0)
    stop_price: float | None = Field(default=None, gt=0)
    take_profit_price: float | None = Field(default=None, gt=0)
    time_in_force: TimeInForce = TimeInForce.DAY
    client_order_id: str | None = Field(default=None, max_length=64)


class BaseBroker(ABC):
    """Provider-agnostic interface. See docs/trading.md SEC:ARCH."""

    name: str  # set by subclass — e.g. "alpaca"
    mode: Literal["paper", "live"]  # set by subclass from BROKER_MODE

    @abstractmethod
    def get_account(self) -> AccountInfo:
        """Buying power, cash, equity, daytrade_count. Raises BrokerUnreachable."""

    @abstractmethod
    def get_positions(self) -> list[Position]:
        """Open positions. Returns [] when flat. Raises BrokerUnreachable."""

    @abstractmethod
    def get_orders(self, status: str = "open", limit: int = 50) -> list[Order]:
        """status ∈ {open, all, closed}. Raises BrokerUnreachable."""

    @abstractmethod
    def get_order(self, broker_order_id: str) -> Order:
        """Single order lookup. Raises BrokerError if not found."""

    @abstractmethod
    def place_order(self, req: PlaceOrderRequest) -> Order:
        """Submit an order. Risk caps are enforced UPSTREAM in the API layer —
        the broker is the last-mile, not the gatekeeper. Raises BrokerRejected
        on broker-side refusal, BrokerUnreachable on transient failure."""

    @abstractmethod
    def cancel_order(self, broker_order_id: str) -> None:
        """Best-effort cancel. Silently succeeds if already filled or canceled."""

    @abstractmethod
    def is_market_open(self) -> bool:
        """The broker's clock — don't compute locally to avoid TZ drift."""
