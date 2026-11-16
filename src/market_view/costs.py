"""Indian transaction cost model (NSE equity). See docs/09 and config/costs.yaml.

Why it matters: delivery STT is 0.1% on BOTH buy and sell. A round trip costs ~0.25-0.3% before
slippage. A strategy aiming for 1% moves gives away a quarter of every win to costs.
"""

from __future__ import annotations

from dataclasses import dataclass

from market_view.config import CostConfig, SegmentCosts, get_settings
from market_view.models import Side


@dataclass
class ChargeBreakdown:
    brokerage: float
    stt: float
    exchange: float
    sebi: float
    stamp: float
    gst: float
    dp: float

    @property
    def total(self) -> float:
        return self.brokerage + self.stt + self.exchange + self.sebi + self.stamp + self.gst + self.dp


class CostModel:
    def __init__(self, cfg: CostConfig | None = None) -> None:
        self.cfg = cfg or get_settings().costs

    def _seg(self, product: str) -> SegmentCosts:
        return self.cfg.intraday if product.upper() == "MIS" else self.cfg.delivery

    def breakdown(self, side: Side, value: float, product: str = "CNC") -> ChargeBreakdown:
        """Charges for ONE executed order of `value` rupees."""
        c = self._seg(product)
        if value <= 0:
            return ChargeBreakdown(0, 0, 0, 0, 0, 0, 0)
        floor = c.brokerage_min
        if c.brokerage_min_pct is not None:  # Groww: min Rs 5, but never more than 2.5% of a tiny order
            floor = min(floor, value * c.brokerage_min_pct / 100)
        brokerage = max(floor, min(c.brokerage_flat, value * c.brokerage_pct / 100))
        stt = value * (c.stt_buy_pct if side == Side.BUY else c.stt_sell_pct) / 100
        exchange = value * c.exchange_txn_pct / 100
        sebi = value * c.sebi_pct / 100
        stamp = value * c.stamp_buy_pct / 100 if side == Side.BUY else 0.0
        gst = (brokerage + exchange + sebi) * c.gst_pct / 100
        dp = c.dp_charge_per_sell if side == Side.SELL else 0.0
        return ChargeBreakdown(brokerage, stt, exchange, sebi, stamp, gst, dp)

    def charges(self, side: Side, value: float, product: str = "CNC") -> float:
        return self.breakdown(side, value, product).total

    def round_trip(self, entry: float, exit_: float, qty: int, product: str = "CNC") -> float:
        return self.charges(Side.BUY, entry * qty, product) + self.charges(Side.SELL, exit_ * qty, product)

    @property
    def slippage(self) -> float:
        return self.cfg.slippage_bps / 10_000

    def fill_price(self, side: Side, price: float) -> float:
        """Apply slippage: you always get a slightly worse price than you saw."""
        return price * (1 + self.slippage) if side == Side.BUY else price * (1 - self.slippage)
