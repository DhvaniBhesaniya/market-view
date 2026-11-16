"""Execution engine: the ONLY path from an approved decision to a broker.

  * order state machine with illegal-transition protection
  * idempotent client_order_id; an UNKNOWN submit is reconciled before any retry (no duplicates)
  * kill switch blocks new ENTRIES (exits and protective stops are always allowed)
  * order-rate limiter far below the SEBI 10 orders/sec threshold
  * a live broker additionally requires the double live switch
"""

from __future__ import annotations

import time
from collections import deque
from datetime import datetime

from market_view.broker.base import Broker
from market_view.config import IST, get_settings, require_live
from market_view.journal import Journal
from market_view.models import Order, OrderStatus
from market_view.risk.killswitch import KillSwitch

ALLOWED: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.NEW: {OrderStatus.SUBMITTING, OrderStatus.REJECTED_RISK},
    OrderStatus.SUBMITTING: {OrderStatus.OPEN, OrderStatus.COMPLETE, OrderStatus.REJECTED_BROKER, OrderStatus.UNKNOWN},
    OrderStatus.OPEN: {OrderStatus.PARTIAL, OrderStatus.COMPLETE, OrderStatus.CANCEL_REQUESTED, OrderStatus.REJECTED_BROKER},
    OrderStatus.PARTIAL: {OrderStatus.PARTIAL, OrderStatus.COMPLETE, OrderStatus.CANCEL_REQUESTED},
    OrderStatus.CANCEL_REQUESTED: {OrderStatus.CANCELLED, OrderStatus.COMPLETE, OrderStatus.PARTIAL},
    OrderStatus.UNKNOWN: {OrderStatus.OPEN, OrderStatus.COMPLETE, OrderStatus.REJECTED_BROKER, OrderStatus.CANCELLED,
                          OrderStatus.PARTIAL},
    OrderStatus.COMPLETE: set(),
    OrderStatus.CANCELLED: set(),
    OrderStatus.REJECTED_BROKER: set(),
    OrderStatus.REJECTED_RISK: set(),
}


class IllegalTransition(RuntimeError):
    pass


class EntryBlocked(RuntimeError):
    pass


def transition(order: Order, new: OrderStatus) -> Order:
    if new not in ALLOWED[order.status]:
        raise IllegalTransition(f"{order.client_order_id}: {order.status} -> {new} not allowed")
    order.status = new
    return order


class RateLimiter:
    def __init__(self, per_second: int) -> None:
        self.per_second = per_second
        self.times: deque[float] = deque()

    def wait(self) -> None:
        now = time.monotonic()
        while self.times and now - self.times[0] > 1.0:
            self.times.popleft()
        if len(self.times) >= self.per_second:
            time.sleep(max(0.0, 1.0 - (now - self.times[0])))
        self.times.append(time.monotonic())


class ExecutionEngine:
    def __init__(self, broker: Broker, journal: Journal | None = None, killswitch: KillSwitch | None = None,
                 live_flag: bool = False) -> None:
        if broker.is_live:
            require_live(live_flag)
        self.broker = broker
        self.journal = journal or Journal()
        self.killswitch = killswitch or KillSwitch()
        self.limiter = RateLimiter(get_settings().risk.max_orders_per_second)

    def submit(self, order: Order) -> Order:
        if order.tag == "entry" and self.killswitch.active:
            transition(order, OrderStatus.REJECTED_RISK)
            self.journal.order(order, note="kill switch active")
            raise EntryBlocked("kill switch active: new entries blocked")
        order.created_at = order.created_at or datetime.now(IST)
        transition(order, OrderStatus.SUBMITTING)
        self.limiter.wait()
        try:
            order.broker_order_id = self.broker.place_order(order)
        except Exception as e:  # network/timeout: we do not know whether it reached the broker
            transition(order, OrderStatus.UNKNOWN)
            self.journal.event("ERROR", f"submit {order.client_order_id} failed: {e}; reconciling")
            order.broker_order_id = self.broker.find_by_client_id(order.client_order_id)
            if order.broker_order_id is None:
                order.status = OrderStatus.REJECTED_BROKER
                self.journal.order(order, note=f"not found at broker after error: {e}")
                return order
        status = self.broker.order_status(order.broker_order_id)
        if status != order.status:
            transition(order, status)
        note = getattr(self.broker, "order_reason", lambda _: None)(order.broker_order_id)
        self.journal.order(order, note=note)
        return order
