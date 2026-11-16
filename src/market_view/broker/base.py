"""Broker interface. PaperBroker now; UpstoxBroker/GrowwBroker for live (Phase 7).

Nothing outside `execution/` may call these methods (CLAUDE.md rules 2 and 3).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel

from market_view.models import Fill, Order, OrderStatus


class BrokerPosition(BaseModel):
    symbol: str
    qty: int
    avg_price: float


class Funds(BaseModel):
    cash: float


class Broker(ABC):
    name: str = "base"
    is_live: bool = False

    @abstractmethod
    def place_order(self, order: Order) -> str:
        """Submit an order; returns the broker order id. Never assume it filled."""

    @abstractmethod
    def cancel_order(self, broker_order_id: str) -> None: ...

    @abstractmethod
    def order_status(self, broker_order_id: str) -> OrderStatus: ...

    @abstractmethod
    def find_by_client_id(self, client_order_id: str) -> str | None:
        """Reconciliation after an UNKNOWN submit: did this order reach the broker?"""

    @abstractmethod
    def place_protective(self, symbol: str, qty: int, stop: float, target: float | None) -> str:
        """Broker-side stop-loss (+ optional target) as OCO / GTT (CLAUDE.md rule 4)."""

    @abstractmethod
    def modify_protective(self, protective_id: str, stop: float | None = None, qty: int | None = None,
                          target: float | None = None, at: datetime | None = None) -> None: ...

    @abstractmethod
    def cancel_protective(self, protective_id: str) -> None: ...

    @abstractmethod
    def positions(self) -> list[BrokerPosition]: ...

    @abstractmethod
    def funds(self) -> Funds: ...

    @abstractmethod
    def fills(self) -> list[Fill]: ...
