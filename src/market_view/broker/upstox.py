"""UpstoxBroker — read-only account access now; order placement is Phase 7 and LOCKED.

Order placement needs: the Phase 5 gate passed, LIVE_TRADING=true AND --live (config.require_live),
a static IP registered with the broker (SEBI retail algo framework), and broker-side stops.
Until then every order method raises. Do not "temporarily" bypass this.
"""

from __future__ import annotations

from datetime import datetime

from market_view.broker.base import Broker, BrokerPosition, Funds
from market_view.config import require_live
from market_view.models import Fill, Order, OrderStatus


class UpstoxBroker(Broker):
    name = "upstox"
    is_live = True

    def __init__(self, live_flag: bool = False) -> None:
        self.live_flag = live_flag

    def _locked(self) -> None:
        require_live(self.live_flag)
        raise NotImplementedError("Live order placement is implemented in Phase 7 (docs/04-roadmap.md)")

    def place_order(self, order: Order) -> str:
        self._locked()
        raise AssertionError  # unreachable

    def cancel_order(self, broker_order_id: str) -> None:
        self._locked()

    def order_status(self, broker_order_id: str) -> OrderStatus:
        self._locked()
        raise AssertionError

    def find_by_client_id(self, client_order_id: str) -> str | None:
        self._locked()
        raise AssertionError

    def place_protective(self, symbol: str, qty: int, stop: float, target: float | None) -> str:
        self._locked()
        raise AssertionError

    def modify_protective(self, protective_id: str, stop: float | None = None, qty: int | None = None,
                          target: float | None = None, at: datetime | None = None) -> None:
        self._locked()

    def cancel_protective(self, protective_id: str) -> None:
        self._locked()

    # Read-only portfolio endpoints need a static IP at Upstox; wire them in Phase 7 prep.
    def positions(self) -> list[BrokerPosition]:
        raise NotImplementedError("Phase 7 prep: GET /v2/portfolio/short-term-positions")

    def funds(self) -> Funds:
        raise NotImplementedError("Phase 7 prep: GET /v2/user/get-funds-and-margin")

    def fills(self) -> list[Fill]:
        raise NotImplementedError("Phase 7 prep: GET /v2/order/trades/get-trades-for-day")
