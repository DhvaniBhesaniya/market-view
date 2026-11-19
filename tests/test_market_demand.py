import json
from datetime import datetime

from market_view.api.market_demand import capture, latest
from market_view.config import IST
from market_view.data.sources.upstox_source import instrument_key


def test_snapshot_is_raw_preserved_and_not_called_an_auction_signal(tmp_path):
    raw = {"NSE_EQ:TCS": {"instrument_token": instrument_key("TCS"), "last_price": 1000,
            "total_buy_quantity": 300, "total_sell_quantity": 100, "timestamp": "2026-11-05T09:03:00+05:30"}}

    class Source:
        def _get(self, path, params):
            assert path == "/v3/market-quote/quotes"
            return raw

    r = capture(tmp_path, datetime(2026, 11, 5, 9, 3, tzinfo=IST), Source())
    assert r["session"] == "pre_open"
    assert r["auction_verified"] is False
    assert r["rows"][0]["imbalance_pct"] == 50
    assert r["rows"][0]["buy_quantity"] == 300
    stored = json.loads(next(tmp_path.rglob("*.json")).read_text())
    assert stored["raw"] == raw
    assert latest(tmp_path)["snapshot_id"] == r["snapshot_id"]


def test_missing_quantity_is_unknown_not_zero(tmp_path):
    class Source:
        def _get(self, *a):
            return {"NSE_EQ:TCS": {"instrument_token": instrument_key("TCS"), "last_price": 1000}}

    r = capture(tmp_path, datetime(2026, 11, 5, 11, 0, tzinfo=IST), Source())
    assert r["session"] == "continuous"
    assert r["rows"][0]["imbalance_pct"] is None
    assert r["rows"][0]["buy_quantity"] is None
