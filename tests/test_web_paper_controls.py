from fastapi.testclient import TestClient

from market_view.api.app import create_app
from market_view.paper.automation import PaperAutomation
from tests.test_paper_trader import trader


def test_web_enable_pause_and_live_guard(tmp_path, monkeypatch):
    monkeypatch.setattr("market_view.data.sources.upstox_source.UpstoxSource.check", lambda self: {"benchmark": {"last_price": 1}})
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "fake-test-token")
    controller = PaperAutomation(tmp_path, lambda: trader(tmp_path))
    with TestClient(create_app(paper=controller)) as c:
        assert c.get("/api/paper").json()["started"] is False
        assert c.post("/api/paper/automation", json={"action": "start"}).status_code == 422
        monkeypatch.setenv("LIVE_TRADING", "true")
        assert c.post("/api/paper/automation", json={"action": "start", "acknowledge_research": True}).status_code == 409
        monkeypatch.setenv("LIVE_TRADING", "false")
        r = c.post("/api/paper/automation", json={"action": "start", "acknowledge_research": True})
        assert r.status_code == 200 and r.json()["entries_enabled"] is True
        assert c.get("/api/paper").json()["started"] is True
        assert c.post("/api/paper/automation", json={"action": "pause"}).json()["entries_enabled"] is False
        assert controller._trader().broker.positions() == []


def test_web_trial_refuses_a_failed_connection(tmp_path, monkeypatch):
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "fake-test-token")
    monkeypatch.setattr("market_view.data.sources.upstox_source.UpstoxSource.check", lambda self: {})
    controller = PaperAutomation(tmp_path, lambda: trader(tmp_path))
    with TestClient(create_app(paper=controller)) as c:
        assert c.post("/api/paper/automation", json={"action": "start", "acknowledge_research": True}).status_code == 409
        assert not controller.status()["entries_enabled"]
        assert not (tmp_path / "trader.json").exists()


def test_weekly_api_rejects_invalid_dates_and_fake_annotations():
    with TestClient(create_app()) as c:
        assert c.get("/api/mentor/weekly?day=wrong").status_code == 422
        result = c.get("/api/mentor/weekly?day=2026-11-05").json()
        assert len(result["actions"]) == 3
        assert result["rating"]["score"] is None
        assert c.post("/api/mentor/trades/999999", json={"risk_ok": True, "plan_ok": True,
            "selection_ok": True, "execution_ok": True, "note": "Checked the actual journal evidence."}).status_code == 404
