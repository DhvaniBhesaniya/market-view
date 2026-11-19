"""Read-only demand observations. Regular quote depth is NOT verified opening-auction data."""

from __future__ import annotations

import json
import math
import threading
import uuid
from datetime import datetime, time
from pathlib import Path

from market_view import calendar as cal
from market_view.config import DATA_DIR, IST, get_settings
from market_view.data.sources.upstox_source import UpstoxSource, instrument_key

_lock = threading.Lock()
ROOT = DATA_DIR / "demand_snapshots"
LIMITATION = ("Displayed bid/ask quantities are observations, not executed buying or a forecast. "
              "Orders may change or cancel. This endpoint's closing-auction fields are not verified "
              "for the opening auction; no auction strategy or order is generated.")


def _number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) and number >= 0 else None
    except (TypeError, ValueError):
        return None


def latest(root: Path = ROOT) -> dict:
    paths = sorted(root.glob("*/*.json")) if root.exists() else []
    if not paths:
        return {"snapshot_id": None, "rows": [], "auction_verified": False, "limitation": LIMITATION}
    body = json.loads(paths[-1].read_text(encoding="utf-8"))
    body.pop("raw", None)
    return body


def capture(root: Path = ROOT, now: datetime | None = None, source=None) -> dict:
    with _lock:
        now = (now or datetime.now(IST)).astimezone(IST)
        keys = {instrument_key(s): s for s in get_settings().universe.symbols}
        raw = (source or UpstoxSource())._get("/v3/market-quote/quotes", {"instrument_key": ",".join(keys)})
        if not raw:
            raise RuntimeError("No demand observations returned by Upstox.")
        rows = []
        for item in raw.values():
            symbol = keys.get(item.get("instrument_token"))
            if not symbol:
                continue
            buy, sell = _number(item.get("total_buy_quantity")), _number(item.get("total_sell_quantity"))
            imbalance = 100*(buy-sell)/(buy+sell) if buy is not None and sell is not None and buy+sell > 0 else None
            rows.append({"symbol": symbol, "buy_quantity": buy, "sell_quantity": sell,
                         "imbalance_pct": round(imbalance, 2) if imbalance is not None else None,
                         "last_price": _number(item.get("last_price")), "response_time": item.get("timestamp"),
                         "last_trade_time": item.get("last_trade_time")})
        rows.sort(key=lambda r: (r["imbalance_pct"] is None, -(r["imbalance_pct"] or 0), r["symbol"]))
        snapshot_id = now.strftime("%H%M%S%f") + "-" + uuid.uuid4().hex[:8]
        body = {"snapshot_id": snapshot_id, "captured_at": now.isoformat(), "provider": "upstox-v3-full-quotes",
                "session": "pre_open" if cal.is_trading_day(now.date()) and time(9) <= now.time() < time(9, 15) else "continuous" if cal.is_market_open(now) else "closed",
                "auction_verified": False, "limitation": LIMITATION, "rows": rows, "raw": raw}
        directory = root / now.date().isoformat()
        directory.mkdir(parents=True, exist_ok=True)
        # Exclusive creation: observations are never overwritten or reconstructed from OHLCV.
        pending = directory / f"{snapshot_id}.tmp"
        final = directory / f"{snapshot_id}.json"
        with pending.open("x", encoding="utf-8") as f:
            json.dump(body, f, indent=2)
        if final.exists():
            raise RuntimeError("Snapshot id collision; existing observation was preserved.")
        pending.rename(final)  # readers only see complete snapshots
        body.pop("raw")
        return body
