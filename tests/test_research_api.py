import time

from fastapi.testclient import TestClient

from market_view.api.app import create_app
from market_view.api.jobs import JobManager
from market_view.research.lab import ResearchLab


def test_web_research_is_independent_and_reports_missing_evidence(tmp_path, monkeypatch):
    import market_view.api.app as module

    pool = JobManager()
    monkeypatch.setattr(module, "jobs", pool)
    lab = ResearchLab(tmp_path)
    with TestClient(create_app(research=lab)) as c:
        status = c.get("/api/research").json()
        assert status["status"]["llm_required"] is False
        assert status["status"]["automatic_promotion"] is False
        assert status["status"]["enabled"] is False
        assert c.post("/api/research/control", json={"enabled": True}).json()["enabled"] is True
        assert c.post("/api/research/control", json={"enabled": False}).json()["enabled"] is False
        job = c.post("/api/research/run").json()
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            result = c.get(f"/api/jobs/{job['id']}").json()
            if result["status"] in ("done", "error"):
                break
            time.sleep(.05)
        assert result["status"] == "done", result
        assert result["result"]["status"] == "blocked"
        assert result["result"]["promotion_allowed"] is False
        assert c.get("/api/research").json()["reports"]
