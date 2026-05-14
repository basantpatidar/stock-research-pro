"""Alpaca implementation of BaseBroker.

Paper and live both speak the same REST API at different base URLs. The
SDK ([alpaca-py](https://github.com/alpacahq/alpaca-py)) picks the right one
from the `paper=True/False` flag we pass at client construction.
"""

from __future__ import annotations

import logging
from typing import Literal

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

logger = logging.getLogger(__name__)


# Map our DTO enums onto alpaca-py's enums. Kept inline so a future SDK
# version bump that renames their enums is one edit, not a hunt.
_OUR_TO_ALPACA_SIDE = {
    OrderSide.BUY:  "buy",
    OrderSide.SELL: "sell",
}
_OUR_TO_ALPACA_TYPE = {
    OrderType.MARKET:     "market",
    OrderType.LIMIT:      "limit",
    OrderType.STOP:       "stop",
    OrderType.STOP_LIMIT: "stop_limit",
}
_OUR_TO_ALPACA_TIF = {
    TimeInForce.DAY: "day",
    TimeInForce.GTC: "gtc",
    TimeInForce.IOC: "ioc",
    TimeInForce.FOK: "fok",
}
_ALPACA_TO_OUR_STATUS = {
    "new":               OrderStatus.NEW,
    "accepted":          OrderStatus.ACCEPTED,
    "pending_new":       OrderStatus.NEW,
    "accepted_for_bidding": OrderStatus.ACCEPTED,
    "partially_filled":  OrderStatus.PARTIALLY_FILLED,
    "filled":            OrderStatus.FILLED,
    "canceled":          OrderStatus.CANCELED,
    "rejected":          OrderStatus.REJECTED,
    "expired":           OrderStatus.EXPIRED,
}


class AlpacaBroker(BaseBroker):
    name = "alpaca"

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        mode: Literal["paper", "live"] = "paper",
        base_url: str | None = None,
    ) -> None:
        if not api_key or not api_secret:
            # Surface as configuration error, not a runtime crash later
            raise BrokerError(
                "Alpaca client requires ALPACA_API_KEY and ALPACA_API_SECRET. "
                "Paper and live use different keys — check BROKER_MODE matches your key."
            )

        try:
            from alpaca.trading.client import TradingClient  # type: ignore
        except ImportError as exc:
            raise BrokerError(
                "alpaca-py is not installed. Run `pip install alpaca-py` or rebuild the "
                "backend image so the brokers layer can talk to Alpaca."
            ) from exc

        self.mode = mode
        self._client = TradingClient(
            api_key=api_key,
            secret_key=api_secret,
            paper=(mode == "paper"),
            url_override=base_url or None,
        )

    # ── Account ──────────────────────────────────────────────────────────────

    def get_account(self) -> AccountInfo:
        try:
            acct = self._client.get_account()
        except Exception as exc:
            raise BrokerUnreachable(f"alpaca get_account failed: {exc}") from exc
        last_equity = getattr(acct, "last_equity", None)
        return AccountInfo(
            broker=self.name,
            mode=self.mode,
            cash=float(acct.cash),
            buying_power=float(acct.buying_power),
            equity=float(acct.equity),
            last_equity=float(last_equity) if last_equity is not None else None,
            daytrade_count=int(getattr(acct, "daytrade_count", 0) or 0),
        )

    # ── Positions ────────────────────────────────────────────────────────────

    def get_positions(self) -> list[Position]:
        try:
            raw = self._client.get_all_positions()
        except Exception as exc:
            raise BrokerUnreachable(f"alpaca get_all_positions failed: {exc}") from exc
        return [self._to_position(p) for p in raw]

    @staticmethod
    def _to_position(p) -> Position:
        return Position(
            symbol=p.symbol,
            qty=float(p.qty),
            avg_entry_price=float(p.avg_entry_price),
            current_price=float(p.current_price or 0.0),
            market_value=float(p.market_value or 0.0),
            unrealized_pl=float(p.unrealized_pl or 0.0),
            unrealized_pl_pct=float(p.unrealized_plpc or 0.0) * 100.0,
        )

    # ── Orders ───────────────────────────────────────────────────────────────

    def get_orders(self, status: str = "open", limit: int = 50) -> list[Order]:
        try:
            from alpaca.trading.requests import GetOrdersRequest  # type: ignore
            from alpaca.trading.enums import QueryOrderStatus  # type: ignore
            status_map = {
                "open":   QueryOrderStatus.OPEN,
                "closed": QueryOrderStatus.CLOSED,
                "all":    QueryOrderStatus.ALL,
            }
            req = GetOrdersRequest(status=status_map.get(status, QueryOrderStatus.OPEN), limit=limit)
            raw = self._client.get_orders(filter=req)
        except Exception as exc:
            raise BrokerUnreachable(f"alpaca get_orders failed: {exc}") from exc
        return [self._to_order(o) for o in raw]

    def get_order(self, broker_order_id: str) -> Order:
        try:
            raw = self._client.get_order_by_id(broker_order_id)
        except Exception as exc:
            raise BrokerError(f"alpaca get_order_by_id failed: {exc}") from exc
        return self._to_order(raw)

    def place_order(self, req: PlaceOrderRequest) -> Order:
        try:
            from alpaca.trading.requests import (  # type: ignore
                LimitOrderRequest,
                MarketOrderRequest,
                StopOrderRequest,
                StopLimitOrderRequest,
                TakeProfitRequest,
                StopLossRequest,
            )
            from alpaca.trading.enums import (  # type: ignore
                OrderSide as APSide,
                TimeInForce as APTIF,
                OrderClass as APClass,
            )

            side = APSide.BUY if req.side == OrderSide.BUY else APSide.SELL
            tif = {
                TimeInForce.DAY: APTIF.DAY,
                TimeInForce.GTC: APTIF.GTC,
                TimeInForce.IOC: APTIF.IOC,
                TimeInForce.FOK: APTIF.FOK,
            }[req.time_in_force]

            bracket_kwargs: dict = {}
            if req.stop_price is not None or req.take_profit_price is not None:
                bracket_kwargs["order_class"] = APClass.BRACKET
                if req.take_profit_price is not None:
                    bracket_kwargs["take_profit"] = TakeProfitRequest(limit_price=req.take_profit_price)
                if req.stop_price is not None:
                    bracket_kwargs["stop_loss"] = StopLossRequest(stop_price=req.stop_price)

            common = dict(
                symbol=req.symbol,
                qty=req.qty,
                side=side,
                time_in_force=tif,
                client_order_id=req.client_order_id,
                **bracket_kwargs,
            )
            if req.order_type == OrderType.MARKET:
                ap_req = MarketOrderRequest(**common)
            elif req.order_type == OrderType.LIMIT:
                ap_req = LimitOrderRequest(limit_price=req.limit_price, **common)
            elif req.order_type == OrderType.STOP:
                ap_req = StopOrderRequest(stop_price=req.stop_price, **common)
            else:  # STOP_LIMIT
                ap_req = StopLimitOrderRequest(
                    stop_price=req.stop_price, limit_price=req.limit_price, **common
                )

            raw = self._client.submit_order(order_data=ap_req)
        except BrokerError:
            raise
        except Exception as exc:
            msg = str(exc).lower()
            # Alpaca surfaces buying-power / position errors as 4xx — distinguish
            # those from network/5xx so the API layer can return 422 vs 503.
            if any(t in msg for t in ("insufficient", "forbidden", "not allowed", "rejected", "422", "403")):
                raise BrokerRejected(f"alpaca rejected order: {exc}") from exc
            raise BrokerUnreachable(f"alpaca submit_order failed: {exc}") from exc
        return self._to_order(raw)

    def cancel_order(self, broker_order_id: str) -> None:
        try:
            self._client.cancel_order_by_id(broker_order_id)
        except Exception as exc:
            # Already-filled / already-canceled is fine; surface as no-op
            if "not allowed" in str(exc).lower() or "already" in str(exc).lower():
                logger.info("alpaca cancel no-op for %s: %s", broker_order_id, exc)
                return
            raise BrokerUnreachable(f"alpaca cancel_order failed: {exc}") from exc

    def is_market_open(self) -> bool:
        try:
            clock = self._client.get_clock()
        except Exception as exc:
            raise BrokerUnreachable(f"alpaca get_clock failed: {exc}") from exc
        return bool(clock.is_open)

    # ── Conversion helpers ───────────────────────────────────────────────────

    @staticmethod
    def _to_order(o) -> Order:
        ap_status = str(getattr(o, "status", "") or "").lower()
        return Order(
            broker_order_id=str(o.id),
            client_order_id=getattr(o, "client_order_id", None),
            symbol=o.symbol,
            side=OrderSide(str(o.side).lower()),
            qty=float(o.qty),
            order_type=OrderType(str(o.order_type).lower()),
            limit_price=float(o.limit_price) if getattr(o, "limit_price", None) else None,
            stop_price=float(o.stop_price) if getattr(o, "stop_price", None) else None,
            take_profit_price=None,  # bracket leg lives on a child order in Alpaca
            time_in_force=TimeInForce(str(o.time_in_force).lower()),
            status=_ALPACA_TO_OUR_STATUS.get(ap_status, OrderStatus.NEW),
            filled_qty=float(getattr(o, "filled_qty", 0) or 0),
            filled_avg_price=float(o.filled_avg_price) if getattr(o, "filled_avg_price", None) else None,
            submitted_at=o.submitted_at,
            filled_at=getattr(o, "filled_at", None),
            canceled_at=getattr(o, "canceled_at", None),
            rejected_reason=getattr(o, "failed_at", None) and str(getattr(o, "reject_reason", "") or ""),
        )
