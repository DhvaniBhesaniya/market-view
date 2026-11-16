"""Chart intervals must preserve observed prices, session anchors and real timestamps."""

import time
from datetime import datetime, timedelta
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from market_view.api import app as webapp
from market_view.api.jobs import JobManager
from market_view.config import IST
from market_view.data import store


@pytest.fixture
def chart_client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(webapp, "jobs", JobManager())
    daily = pd.DataFrame(
        {"open": [100, 110, 120, 130], "high": [106, 116, 126, 136],
         "low": [98, 108, 118, 128], "close": [104, 114, 124, 134], "volume": [10, 20, 30, 40]},
        index=pd.DatetimeIndex(["2026-01-30 09:15", "2026-02-02 09:15", "2026-02-03 09:15", "2026-02-04 09:15"], tz=IST),
    )
    store.save(daily, "yfinance", "1d", "RELIANCE")
    with TestClient(webapp.create_app()) as client:
        yield client


def minute_data():
    index = pd.date_range("2026-02-02 09:15", periods=14, freq="min", tz=IST).append(
        pd.date_range("2026-02-03 09:15", periods=14, freq="min", tz=IST))
    prices = pd.Series(range(100, 128), index=index, dtype=float)
    return pd.DataFrame({"open": prices, "high": prices + 1, "low": prices - 1,
                         "close": prices + 0.5, "volume": 10}, index=index)


def test_intraday_chart_preserves_same_day_candles_and_ist(chart_client):
    store.save(minute_data(), "yfinance", "1m", "RELIANCE")
    body = chart_client.get("/api/candles/RELIANCE?interval=1m").json()
    assert len(body["bars"]) == 28
    assert body["bars"][0]["time"] == "2026-02-02T09:15:00+05:30"
    assert body["bars"][1]["time"] == "2026-02-02T09:16:00+05:30"
    assert body["timezone"] == "Asia/Kolkata" and body["source_interval"] == "1m"


def test_five_minute_ohlcv_is_anchored_to_each_session(chart_client):
    store.save(minute_data(), "yfinance", "1m", "RELIANCE")
    body = chart_client.get("/api/candles/RELIANCE?interval=5m").json()
    bars = body["bars"]
    assert len(bars) == 6
    assert bars[0] == {"time": "2026-02-02T09:15:00+05:30", "timestamp": "2026-02-02T09:15:00+05:30",
                       "open": 100, "high": 105, "low": 99, "close": 104.5, "volume": 50}
    assert bars[3]["time"] == "2026-02-03T09:15:00+05:30"
    assert body["aggregated"] is True


def test_custom_seven_minute_buckets_do_not_drift_across_days(chart_client):
    store.save(minute_data(), "yfinance", "1m", "RELIANCE")
    bars = chart_client.get("/api/candles/RELIANCE?interval=7m").json()["bars"]
    assert len(bars) == 4 and [b["volume"] for b in bars] == [70] * 4
    assert bars[1]["time"] == "2026-02-02T09:22:00+05:30"
    assert bars[2]["time"] == "2026-02-03T09:15:00+05:30"


def test_months_aggregate_daily_prices_without_losing_last_day(chart_client):
    body = chart_client.get("/api/candles/RELIANCE?interval=1M").json()
    bars = body["bars"]
    assert len(bars) == 2
    assert bars[1]["open"] == 110 and bars[1]["high"] == 136
    assert bars[1]["low"] == 108 and bars[1]["close"] == 134 and bars[1]["volume"] == 90
    assert body["source_interval"] == "1d"


def test_daily_source_and_freshness_are_explicit(chart_client):
    body = chart_client.get("/api/candles/RELIANCE").json()
    assert body["source"] == "yfinance" and body["adjusted"] is True
    assert body["interval"] == "1d" and body["live"] is False
    assert body["last_observation"] == "2026-02-04T09:15:00+05:30"
    assert body["bars"][0]["time"] == "2026-01-30"


def test_daily_prices_are_never_split_into_intraday_candles(chart_client):
    response = chart_client.get("/api/candles/RELIANCE?interval=5m")
    assert response.status_code == 200
    body = response.json()
    assert body["bars"] == [] and body["needs_download"] is True
    assert "minute" in body["message"].lower()


@pytest.mark.parametrize("interval", ["1s", "30s", "0m", "-5m", "1.5m", "99999M", "bad"])
def test_unsupported_intervals_are_explained(chart_client, interval):
    response = chart_client.get("/api/candles/RELIANCE", params={"interval": interval})
    assert response.status_code == 422
    if interval.endswith("s"):
        assert "tick" in response.json()["detail"].lower()


def test_indicators_use_selected_candles_and_keep_intraday_times(chart_client):
    store.save(minute_data(), "yfinance", "1m", "RELIANCE")
    response = chart_client.post("/api/indicators/compute", json={"symbol": "RELIANCE", "interval": "5m",
        "items": [{"key": "s", "ind": "sma", "params": {"n": 2}}]})
    assert response.status_code == 200
    points = response.json()["s"]["value"]
    assert points[0]["time"] == "2026-02-02T09:20:00+05:30"
    assert points[0]["value"] == pytest.approx((104.5 + 109.5) / 2)


def test_invalid_source_and_symbol_cannot_be_used_as_paths(chart_client):
    assert chart_client.get("/api/candles/RELIANCE?source=../escape").status_code == 422
    assert chart_client.post("/api/chart/download", json={"symbol": "NOPE", "interval": "5m"}).status_code == 422


def test_monthly_freshness_uses_last_daily_observation_not_month_start(chart_client):
    body = chart_client.get("/api/candles/RELIANCE?interval=1M").json()
    assert body["last_observation"] == "2026-02-04T09:15:00+05:30"


def test_download_job_uses_real_finer_adapter_and_append_only_store(chart_client, monkeypatch):
    from market_view.api import chart_data

    calls = []
    today = datetime.now(IST).date()

    def history(symbol, interval, start, end):
        calls.append((symbol, interval, start, end))
        frame = minute_data().iloc[:14].copy()
        frame.index = pd.date_range(f"{today} 09:15", periods=14, freq="min", tz=IST)
        return frame

    monkeypatch.setattr(chart_data, "get_source", lambda _: SimpleNamespace(history=history))
    response = chart_client.post("/api/chart/download", json={"symbol": "RELIANCE", "interval": "7m",
        "source": "yfinance", "start": "2008-01-01"})
    assert response.status_code == 202
    job_id = response.json()["id"]
    for _ in range(250):
        job = chart_client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in {"done", "error"}:
            break
        time.sleep(0.02)
    assert job["status"] == "done", job.get("error")
    assert calls == [("RELIANCE", "1m", today - timedelta(days=6), today)]
    assert len(store.load("RELIANCE", "1m", "yfinance")) == 14
    assert len(list(store.raw_dir("yfinance", "1m", "RELIANCE").glob("*.parquet"))) == 1
    bars = chart_client.get("/api/candles/RELIANCE?interval=7m").json()["bars"]
    assert len(bars) == 2 and bars[0]["volume"] == 70


def test_download_refuses_missing_upstox_token_and_reversed_dates(chart_client):
    assert chart_client.post("/api/chart/download", json={"symbol": "RELIANCE", "interval": "5m",
        "source": "upstox"}).status_code == 422
    assert chart_client.post("/api/chart/download", json={"symbol": "RELIANCE", "start": "2026-02-04",
        "end": "2026-01-30"}).status_code == 422


def test_adjusted_daily_refresh_preserves_one_adjustment_basis(chart_client, monkeypatch):
    from market_view.api import chart_data

    calls = []
    existing = store.load("RELIANCE")

    def history(symbol, interval, start, end):
        calls.append(start)
        return existing

    monkeypatch.setattr(chart_data, "get_source", lambda _: SimpleNamespace(history=history))
    chart_data.download("RELIANCE", chart_data.Interval.parse("1d"), "yfinance",
                        datetime(2026, 2, 2).date(), datetime(2026, 2, 4).date())
    # Yahoo's adjustment basis can change after a dividend/split. Refresh all saved daily
    # observations together, not just the visible slice mixed with old adjusted prices.
    assert calls == [datetime(2026, 1, 30).date()]
