"""Core data contracts shared by backtest, paper and (later) live modes.

Prices are floats in research/backtest/paper. The live execution path (Phase 7) must convert to
Decimal at the broker boundary.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

OHLCV = ["open", "high", "low", "close", "volume"]


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"
    SL_M = "SL-M"


class OrderStatus(StrEnum):
    NEW = "NEW"
    REJECTED_RISK = "REJECTED_RISK"
    SUBMITTING = "SUBMITTING"
    OPEN = "OPEN"
    PARTIAL = "PARTIAL"
    COMPLETE = "COMPLETE"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    REJECTED_BROKER = "REJECTED_BROKER"
    UNKNOWN = "UNKNOWN"


class Signal(BaseModel):
    """A strategy's proposal. It is never an order: the risk engine decides."""

    strategy_id: str
    symbol: str
    side: Side = Side.BUY
    ref_price: float  # close of the signal bar
    stop: float
    target: float | None = None
    confidence: float = 0.5
    reasons: list[str] = Field(default_factory=list)
    bar_time: datetime
    context: dict[str, Any] = Field(default_factory=dict)
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])

    @property
    def risk_per_share(self) -> float:
        return self.ref_price - self.stop


class RiskDecision(BaseModel):
    approved: bool
    qty: int = 0
    reasons: list[str] = Field(default_factory=list)
    risk_amount: float = 0.0


class Order(BaseModel):
    client_order_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    broker_order_id: str | None = None
    symbol: str
    side: Side
    qty: int
    order_type: OrderType = OrderType.MARKET
    price: float | None = None
    trigger: float | None = None
    product: str = "CNC"
    status: OrderStatus = OrderStatus.NEW
    strategy_id: str | None = None
    signal_id: str | None = None
    tag: str = ""  # entry | exit | stop | target
    created_at: datetime | None = None


class Fill(BaseModel):
    client_order_id: str
    symbol: str
    side: Side
    qty: int
    price: float
    charges: float
    time: datetime


class Trade(BaseModel):
    """A closed round trip (possibly with partial exits)."""

    strategy_id: str
    symbol: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float  # quantity-weighted average exit
    qty: int
    initial_stop: float
    target: float | None
    gross_pnl: float
    charges: float
    net_pnl: float
    r_multiple: float
    bars_held: int
    mae_pct: float  # max adverse excursion, % from entry (negative)
    mfe_pct: float  # max favourable excursion, % from entry
    exit_reason: str
    reasons: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
