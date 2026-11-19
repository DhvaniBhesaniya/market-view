from datetime import datetime

from market_view.config import IST
from market_view.data.sources.upstox_source import UpstoxSource, instrument_key


def test_quotes_use_exchange_trade_time_and_batch_requests(monkeypatch):
    source = UpstoxSource(token="test")
    when = datetime(2026, 11, 5, 9, 19, tzinfo=IST)
    calls = []

    def get(path, params=None):
        calls.append(path)
        return {"NSE_EQ:TCS": {"instrument_token": instrument_key("TCS"), "last_price": 1000,
                "last_trade_time": str(int(when.timestamp() * 1000)), "ohlc": {"open": 995, "high": 1001, "low": 994}}}

    monkeypatch.setattr(source, "_get", get)
    quotes = source.quotes(["TCS", "INFY"])
    assert quotes["TCS"].time == when
    assert "INFY" not in quotes
    assert calls == ["/v3/market-quote/quotes"]


def test_missing_exchange_timestamp_is_not_fabricated(monkeypatch):
    source = UpstoxSource(token="test")
    monkeypatch.setattr(source, "_get", lambda *a: {"NSE_EQ:TCS": {
        "instrument_token": instrument_key("TCS"), "last_price": 1000, "timestamp": datetime.now(IST).isoformat()}})
    assert source.quotes(["TCS"]) == {}
