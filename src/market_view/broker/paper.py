"""PaperBroker: a simulated broker with real-world frictions. No money moves.

* market orders fill at the latest quote +/- slippage, paying full Indian charges
* protective orders (stop + target, OCO) rest "at the broker" and trigger on quotes, like a GTT/OCO:
  a gap below the stop fills at the (worse) open/last price, never at the stop
* state persists to JSON so the scheduler, CLI and dashboard share one account
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from market_view.broker.base import Broker, BrokerPosition, Funds
from market_view.config import DATA_DIR, IST
from market_view.costs import CostModel
from market_view.data.sources.base import Quote
from market_view.models import Fill, Order, OrderStatus, OrderType, Side


class PaperBrokerError(RuntimeError):
    pass


class PaperBroker(Broker):
    name = "paper"
    is_live = False

    def __init__(self, path: Path | None = None, initial_cash: float = 500_000, costs: CostModel | None = None,
                 product: str = "CNC") -> None:
        self.path = path or DATA_DIR / "paper" / "broker.json"
        self.costs = costs or CostModel()
        self.product = product
        self.quotes: dict[str, Quote] = {}
        if self.path.exists():
            self.s = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.s = {"cash": initial_cash, "positions": {}, "orders": {}, "protective": {}, "fills": []}
            self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.s, indent=2, default=str), encoding="utf-8")

    def set_quotes(self, quotes: dict[str, Quote]) -> None:
        self.quotes.update(quotes)

    # ------------------------------------------------------------------ orders
    def _fill(self, client_id: str, symbol: str, side: Side, qty: int, price: float, tag: str) -> Fill:
        px = self.costs.fill_price(side, price)
        charges = self.costs.charges(side, px * qty, self.product)
        pos = self.s["positions"].get(symbol, {"qty": 0, "avg_price": 0.0})
        if side == Side.BUY:
            cost = px * qty + charges
            if cost > self.s["cash"]:
                raise PaperBrokerError(f"insufficient funds: need {cost:.2f}, have {self.s['cash']:.2f}")
            new_qty = pos["qty"] + qty
            pos["avg_price"] = (pos["avg_price"] * pos["qty"] + px * qty) / new_qty
            pos["qty"] = new_qty
            self.s["cash"] -= cost
        else:
            if qty > pos["qty"]:
                raise PaperBrokerError(f"cannot sell {qty} {symbol}: holding {pos['qty']} (no short selling)")
            pos["qty"] -= qty
            self.s["cash"] += px * qty - charges
        if pos["qty"] == 0:
            self.s["positions"].pop(symbol, None)
        else:
            self.s["positions"][symbol] = pos
        fill = Fill(client_order_id=client_id, symbol=symbol, side=side, qty=qty, price=px, charges=charges,
                    time=datetime.now(IST))
        self.s["fills"].append({**fill.model_dump(mode="json"), "tag": tag})
        return fill

    def place_order(self, order: Order) -> str:
        if order.order_type != OrderType.MARKET:
            raise PaperBrokerError("PaperBroker supports MARKET orders; use place_protective for stops")
        q = self.quotes.get(order.symbol)
        if q is None:
            raise PaperBrokerError(f"no quote for {order.symbol}")
        broker_id = "P" + uuid.uuid4().hex[:10]
        rec = {"client_order_id": order.client_order_id, "symbol": order.symbol, "side": order.side,
               "qty": order.qty, "status": OrderStatus.OPEN, "tag": order.tag}
        try:
            self._fill(order.client_order_id, order.symbol, order.side, order.qty, q.ltp, order.tag)
            rec["status"] = OrderStatus.COMPLETE
        except PaperBrokerError as e:
            rec["status"] = OrderStatus.REJECTED_BROKER
            rec["reason"] = str(e)
        self.s["orders"][broker_id] = rec
        self._save()
        return broker_id

    def cancel_order(self, broker_order_id: str) -> None:
        rec = self.s["orders"].get(broker_order_id)
        if rec and rec["status"] == OrderStatus.OPEN:
            rec["status"] = OrderStatus.CANCELLED
            self._save()

    def order_status(self, broker_order_id: str) -> OrderStatus:
        rec = self.s["orders"].get(broker_order_id)
        return OrderStatus(rec["status"]) if rec else OrderStatus.UNKNOWN

    def order_reason(self, broker_order_id: str) -> str | None:
        return (self.s["orders"].get(broker_order_id) or {}).get("reason")

    def find_by_client_id(self, client_order_id: str) -> str | None:
        for bid, rec in self.s["orders"].items():
            if rec["client_order_id"] == client_order_id:
                return bid
        return None

    # ------------------------------------------------------------------ protective (OCO)
    def place_protective(self, symbol: str, qty: int, stop: float, target: float | None) -> str:
        pid = "OCO" + uuid.uuid4().hex[:8]
        self.s["protective"][pid] = {"symbol": symbol, "qty": qty, "stop": stop, "target": target,
                                     "placed_date": datetime.now(IST).date().isoformat()}
        self._save()
        return pid

    def modify_protective(self, protective_id: str, stop: float | None = None, qty: int | None = None,
                          target: float | None = None, at: datetime | None = None) -> None:
        """`at` = when the change happened. A stop raised mid-session must not be triggered by a low that
        was printed BEFORE the raise, so the day's low only counts for stops that rested since the open."""
        p = self.s["protective"].get(protective_id)
        if not p:
            raise PaperBrokerError(f"protective order {protective_id} not found")
        changed_on = (at or datetime.now(IST)).astimezone(IST).date().isoformat()
        if stop is not None and stop != p["stop"]:
            p["stop"] = stop
            p["stop_since"] = changed_on
        if target is not None and target != p.get("target"):
            p["target"] = target
            p["target_since"] = changed_on
        if qty is not None:
            p["qty"] = qty
        self._save()

    def cancel_protective(self, protective_id: str) -> None:
        self.s["protective"].pop(protective_id, None)
        self._save()

    def protective(self) -> dict[str, dict]:
        return dict(self.s["protective"])

    def on_quotes(self, quotes: dict[str, Quote]) -> list[tuple[str, str, Fill]]:
        """Trigger resting protective orders. Returns [(protective_id, 'stop'|'target', fill)].
        Stop checked before target (pessimistic) when both were touched."""
        self.set_quotes(quotes)
        out = []
        for pid, p in list(self.s["protective"].items()):
            q = quotes.get(p["symbol"])
            if q is None:
                continue
            # The day's high/low only count if the order was resting before today's open;
            # for an order placed today, earlier lows happened before it existed -> use LTP only.
            today = q.time.astimezone(IST).date().isoformat()
            placed = p.get("placed_date", "")
            stop_rested = p.get("stop_since", placed) < today
            target_rested = p.get("target_since", placed) < today
            rested_overnight = placed < today
            low = q.low if (stop_rested and q.low is not None) else q.ltp
            high = q.high if (target_rested and q.high is not None) else q.ltp
            held = self.s["positions"].get(p["symbol"], {}).get("qty", 0)
            qty = min(p["qty"], held)
            if qty <= 0:
                self.s["protective"].pop(pid)
                continue
            if low <= p["stop"]:
                gap = stop_rested and rested_overnight and q.open is not None and q.open <= p["stop"]
                price = q.open if gap else min(p["stop"], q.ltp)
                fill = self._fill(f"{pid}-SL", p["symbol"], Side.SELL, qty, price, "stop")
                self.s["protective"].pop(pid)
                out.append((pid, "stop", fill))
            elif p.get("target") and high >= p["target"]:
                fill = self._fill(f"{pid}-TG", p["symbol"], Side.SELL, qty, p["target"], "target")
                self.s["protective"].pop(pid)
                out.append((pid, "target", fill))
        if out:
            self._save()
        return out

    # ------------------------------------------------------------------ account
    def positions(self) -> list[BrokerPosition]:
        return [BrokerPosition(symbol=s, qty=p["qty"], avg_price=p["avg_price"]) for s, p in self.s["positions"].items()]

    def funds(self) -> Funds:
        return Funds(cash=self.s["cash"])

    def fills(self) -> list[Fill]:
        return [Fill(**{k: v for k, v in f.items() if k != "tag"}) for f in self.s["fills"]]
