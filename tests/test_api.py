"""Web API: contract, safety properties, and end-to-end research flows on synthetic data (no network)."""

import time

import pytest
from fastapi.testclient import TestClient

from market_view import indicators as ta
from market_view.api.app import create_app
from market_view.data import store
from tests.conftest import random_walk

SYMS = {"RELIANCE": 11, "INFY": 12, "TCS": 13, "SBIN": 14}


@pytest.fixture(scope="module")
def client():
    # ~4.2 years of synthetic daily bars covering the 2020-2022 'validate' period, plus warm-up
    for i, (sym, seed) in enumerate(SYMS.items()):
        df = random_walk(1100, seed=seed, start_price=500 + 300 * i, start="2018-09-03")
        df["volume"] = df["volume"] * 20  # liquid enough for the risk engine's turnover filter
        store.save(df, "yfinance", "1d", sym)
    store.save(random_walk(1100, seed=3, start_price=11_000, start="2018-09-03"), "yfinance", "1d", "NIFTY50")
    store.save(random_walk(1100, seed=5, start_price=15, start="2018-09-03"), "yfinance", "1d", "INDIAVIX")
    with TestClient(create_app()) as c:
        yield c


def wait(client, job, timeout=180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = client.get(f"/api/jobs/{job['id']}").json()
        if j["status"] in ("done", "error"):
            return j
        time.sleep(0.2)
    raise AssertionError(f"job {job['id']} did not finish")


RULE = {"name": "api_dip", "hypothesis": "short dips in an uptrend recover",
        "entry": [{"left": {"kind": "indicator", "ind": "rsi", "params": {"n": 14}}, "op": "<",
                   "right": {"kind": "value", "value": 40}},
                  {"left": {"kind": "indicator", "ind": "close"}, "op": ">",
                   "right": {"kind": "indicator", "ind": "sma", "params": {"n": 100}}}],
        "exit": [{"left": {"kind": "indicator", "ind": "rsi", "params": {"n": 14}}, "op": ">",
                  "right": {"kind": "value", "value": 60}}],
        "stop": {"type": "atr", "value": 2}, "time_stop_bars": 15, "market_filter": False}


# ---------------------------------------------------------------- safety


def test_no_order_endpoints_exist(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/status" in paths  # the schema really lists our routes
    assert not [p for p in paths if "order" in p.lower() or "place" in p.lower() or "broker" in p.lower()]
    writes = sorted(p for p, ops in paths.items() if set(ops) & {"post", "put", "patch", "delete"})
    # the complete list of state-changing endpoints; adding one must be a conscious decision
    assert writes == ["/api/backtests", "/api/indicators/compute", "/api/killswitch", "/api/strategies",
                      "/api/strategies/preview", "/api/strategies/validate", "/api/validations/{kind}"]


def test_foreign_host_header_rejected(client):
    """DNS-rebinding protection: a web page on evil.example cannot talk to the local API."""
    assert client.get("/api/status", headers={"host": "evil.example"}).status_code == 400


def test_status_reports_paper_mode_and_never_leaks_secrets(client, monkeypatch):
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "SECRET-TOKEN-123")
    r = client.get("/api/status")
    assert r.status_code == 200
    body = r.json()
    assert body["live_trading"] is False and body["mode"] == "paper"
    assert body["upstox_token_set"] is True
    assert "SECRET-TOKEN-123" not in r.text
    assert body["periods"]["test"]["locked"] is True


def test_locked_test_period_refused(client):
    r = client.post("/api/backtests", json={"strategies": ["trend_v1"], "period": "test"})
    assert r.status_code == 403 and "LOCKED" in r.json()["detail"]
    r = client.post("/api/validations/sensitivity", json={"strategy": "trend_v1", "period": "test"})
    assert r.status_code == 422


def test_killswitch_on_off_requires_note(client):
    assert client.post("/api/killswitch", json={"action": "on", "reason": "ui test"}).json()["active"] is True
    r = client.post("/api/killswitch", json={"action": "off", "reason": "ok"})
    assert r.status_code == 422  # too short
    r = client.post("/api/killswitch", json={"action": "off", "reason": "short note"})
    assert r.status_code == 200 and r.json()["active"] is False  # exactly 10 chars is accepted
    assert r.json()["history"][0]["action"] == "OFF"


def test_backtest_run_id_path_traversal_blocked(client):
    for bad in ("..%2F..%2Fpyproject.toml", "nope"):
        assert client.get(f"/api/backtests/{bad}").status_code in (400, 404)


# ---------------------------------------------------------------- market data + indicators


def test_symbols_and_candles(client):
    rows = {r["symbol"]: r for r in client.get("/api/symbols").json()}
    assert rows["RELIANCE"]["bars"] == 1100 and rows["NIFTY50"]["kind"] == "index"
    assert rows["HDFCBANK"]["bars"] == 0  # in the universe, no data stored
    bars = client.get("/api/candles/INFY", params={"start": "2020-01-01", "end": "2020-12-31"}).json()["bars"]
    times = [b["time"] for b in bars]
    assert times == sorted(set(times)) and times[0] >= "2020-01-01" and times[-1] <= "2020-12-31"
    assert all(b["low"] <= min(b["open"], b["close"]) and b["high"] >= max(b["open"], b["close"]) for b in bars)
    assert client.get("/api/candles/NOPE").status_code == 404
    assert client.get("/api/candles/INFY", params={"start": "2020-13-01"}).status_code == 422


def test_indicators_match_engine_and_are_warmed_up(client):
    cat = {d["id"]: d for d in client.get("/api/indicators").json()}
    assert {"ema", "rsi", "bb", "macd", "atr"} <= set(cat) and cat["rsi"]["levels"] == [30.0, 70.0]
    r = client.post("/api/indicators/compute", json={"symbol": "TCS", "start": "2021-01-01", "items": [
        {"key": "e", "ind": "ema", "params": {"n": 200}}, {"key": "b", "ind": "bb", "params": {"n": 20, "k": 2}}]})
    assert r.status_code == 200
    body = r.json()
    ema = body["e"]["value"]
    assert ema[0]["time"] >= "2021-01-01"  # cut to the window, yet present from day one (warmed up earlier)
    expected = ta.ema(store.load("TCS")["close"], 200).iloc[-1]
    assert ema[-1]["value"] == pytest.approx(expected, rel=1e-6)
    assert set(body["b"]) == {"upper", "mid", "lower"}
    bad = client.post("/api/indicators/compute", json={"symbol": "TCS", "items": [{"key": "x", "ind": "rsi", "params": {"n": 1}}]})
    assert bad.status_code == 422 and "outside" in bad.json()["detail"]


# ---------------------------------------------------------------- strategies


def test_builtin_strategies_listed_with_cards(client):
    rows = {r["id"]: r for r in client.get("/api/strategies").json()}
    assert {"trend_v1", "breakout_v1", "meanrev_v1"} <= set(rows)
    one = client.get("/api/strategies/trend_v1").json()
    assert one["kind"] == "builtin" and one["card_md"] and "fast" in one["defaults"]
    assert client.get("/api/strategies/nope_v1").status_code == 404


def test_builder_validate_create_version_and_preview(client):
    bad = client.post("/api/strategies/validate", json={**RULE, "name": "Trend"}).json()
    assert not bad["ok"] and any("built-in" in e for e in bad["errors"])
    ok = client.post("/api/strategies/validate", json=RULE).json()
    assert ok["ok"] and "RSI(14) < 40" in ok["describe"] and ok["next_version"] == 1

    r1 = client.post("/api/strategies", json=RULE)
    assert r1.status_code == 201 and r1.json()["id"] == "api_dip_v1"
    r2 = client.post("/api/strategies", json={**RULE, "version": 99, "stop": {"type": "atr", "value": 3}})
    assert r2.json()["id"] == "api_dip_v2"  # client cannot pick/overwrite a version
    assert client.get("/api/strategies/api_dip_v1").json()["spec"]["stop"]["value"] == 2.0
    assert client.post("/api/strategies", json={**RULE, "entry": []}).status_code == 422

    p = client.post("/api/strategies/preview", json={"strategy_id": "api_dip_v1", "symbol": "RELIANCE"}).json()
    assert p["signals"] and p["condition_stats"][0]["true_bars"] >= p["all_conditions_bars"] >= len(p["signals"])
    s0 = p["signals"][0]
    assert s0["stop"] < s0["close"] and s0["reasons"]
    unsaved = client.post("/api/strategies/preview", json={"spec": RULE, "symbol": "RELIANCE"}).json()
    assert len(unsaved["signals"]) == len(p["signals"])
    builtin = client.post("/api/strategies/preview", json={"strategy_id": "meanrev_v1", "symbol": "SBIN"})
    assert builtin.status_code == 200 and "condition_stats" not in builtin.json()


# ---------------------------------------------------------------- backtests + validations (end to end)


def test_backtest_job_and_report(client):
    client.post("/api/strategies", json={**RULE, "name": "api_bt"})
    job = client.post("/api/backtests", json={"strategies": ["api_bt_v1"], "period": "validate",
                                               "symbols": list(SYMS)}).json()
    assert job["status"] in ("queued", "running")
    done = wait(client, job)
    assert done["status"] == "done", done.get("error")
    run_id = done["result"]["run_id"]

    rows = client.get("/api/backtests", params={"strategy": "api_bt_v1"}).json()
    assert rows[0]["run_id"] == run_id and rows[0]["metrics"]["trades"] == done["result"]["metrics"]["trades"]

    d = client.get(f"/api/backtests/{run_id}").json()
    assert d["equity"] and d["benchmark"] and d["drawdown"] and d["yearly"]
    assert d["equity"][0]["time"] >= "2020-01-01" and d["equity"][-1]["time"] <= "2022-12-31"
    assert len(d["trades"]) == d["metrics"]["trades"]
    assert all(dd["value"] <= 0 for dd in d["drawdown"])
    assert d["params"]["specs"]["api_bt_v1"]["name"] == "api_bt"  # reproducible from the log
    assert d["signals"]["total"] >= d["signals"].get("approved", 0)
    if d["trades"]:
        sym = d["trades"][0]["symbol"]
        sigs = client.get(f"/api/backtests/{run_id}/signals", params={"symbol": sym}).json()
        assert sigs and all(s["symbol"] == sym for s in sigs)


def test_unknown_strategy_backtest_404(client):
    assert client.post("/api/backtests", json={"strategies": ["ghost_v1"], "period": "full"}).status_code == 404


def test_montecarlo_validation_job_is_logged(client):
    client.post("/api/strategies", json={**RULE, "name": "api_mc"})
    job = client.post("/api/validations/montecarlo", json={"strategy": "api_mc_v1", "period": "validate"}).json()
    done = wait(client, job)
    assert done["status"] == "done", done.get("error")
    res = done["result"]
    assert res["kind"] == "montecarlo" and "summary" in res and "fan" in res
    if "error" not in res["fan"]:
        f = res["fan"]
        assert all(a <= b <= c for a, b, c in zip(f["p5"], f["p50"], f["p95"], strict=True))
    logged = client.get("/api/validations", params={"strategy": "api_mc_v1"}).json()
    assert logged and logged[0]["id"] == res["id"]


def test_failed_job_reports_error_instead_of_vanishing(client, monkeypatch):
    from market_view.backtest import runner

    def boom(*a, **k):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(runner, "run", boom)
    job = client.post("/api/backtests", json={"strategies": ["trend_v1"], "period": "validate"}).json()
    done = wait(client, job)
    assert done["status"] == "error" and "synthetic failure" in done["error"]


# ---------------------------------------------------------------- paper + journal (read-only)


def test_paper_not_started_and_journal_read_only(client):
    assert client.get("/api/paper").json()["started"] is False
    assert client.get("/api/journal/trades").json() == []
    assert client.get("/api/journal/users").status_code == 404
    assert client.get("/api/journal/trades", params={"limit": 0}).status_code == 422


def test_data_quality(client):
    q = client.get("/api/data/quality").json()
    assert q["source"] == "yfinance" and isinstance(q["by_kind"], dict)
