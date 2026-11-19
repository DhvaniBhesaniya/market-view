from datetime import datetime

import pytest

from market_view.config import IST, get_settings
from market_view.paper.automation import PaperAutomation
from tests.test_paper_trader import trader


def service(tmp_path):
    return PaperAutomation(root=tmp_path, factory=lambda: trader(tmp_path))


def test_default_is_off_and_status_does_not_create_account(tmp_path):
    app = service(tmp_path)
    assert not app.status()["entries_enabled"]
    assert not app.paper_status()["started"]
    assert not (tmp_path / "trader.json").exists()


def test_enable_requires_research_acknowledgement_and_persists(tmp_path):
    app = service(tmp_path)
    with pytest.raises(ValueError, match="research"):
        app.control(True, False)
    app.control(True, True)
    assert service(tmp_path).status()["entries_enabled"]
    app.control(False)
    assert not service(tmp_path).status()["entries_enabled"]


def test_restart_does_not_catch_up_missed_open(tmp_path, monkeypatch):
    app = service(tmp_path)
    app.control(True, True)
    now = datetime(2026, 11, 5, 12, 0, tzinfo=IST)
    t = app._trader()
    calls = []
    monkeypatch.setattr(t, "open_job", lambda *a, **k: calls.append("open"))
    monkeypatch.setattr(t, "monitor", lambda *a, **k: calls.append("monitor"))
    app.tick(now)
    assert calls == ["monitor"]


def test_pause_keeps_monitoring_existing_account(tmp_path, monkeypatch):
    app = service(tmp_path)
    app.control(True, True)
    app.control(False)
    calls = []
    monkeypatch.setattr(app._trader(), "monitor", lambda *a, **k: calls.append("monitor"))
    app.tick(datetime(2026, 11, 5, 11, 0, tzinfo=IST))
    assert calls == ["monitor"]


def test_error_is_visible_and_halts_entries(tmp_path, monkeypatch):
    app = service(tmp_path)
    app.control(True, True)

    def broken(*a, **k):
        raise RuntimeError("feed unavailable")

    monkeypatch.setattr(app._trader(), "monitor", broken)
    app.tick(datetime(2026, 11, 5, 11, 0, tzinfo=IST))
    assert not app.status()["entries_enabled"]
    assert app._trader().killswitch.active
    assert "feed unavailable" in app.status()["last_error"]


def test_unknown_calendar_year_blocks_entries(tmp_path):
    app = service(tmp_path)
    app.control(True, True)
    app.tick(datetime(2027, 1, 4, 9, 20, tzinfo=IST))
    assert not app.status()["entries_enabled"]
    assert "calendar" in app.status()["last_error"]


def test_unknown_calendar_year_preserves_position_monitoring(tmp_path, monkeypatch):
    app = service(tmp_path)
    app.control(True, True)
    calls = []
    monkeypatch.setattr(app._trader(), "monitor", lambda *a, **k: calls.append("monitor"))
    app.tick(datetime(2027, 1, 4, 11, 0, tzinfo=IST))
    assert calls == ["monitor"]


def test_configuration_change_pauses_persisted_permission(tmp_path, monkeypatch):
    app = service(tmp_path)
    app.control(True, True)
    monkeypatch.setattr(get_settings().paper.schedule, "monitor_every_minutes", 2)
    assert not service(tmp_path).status()["entries_enabled"]


def test_worker_process_has_exclusive_ownership(tmp_path):
    one, two = service(tmp_path), service(tmp_path)
    one.start_worker()
    try:
        with pytest.raises(RuntimeError, match="another"):
            two.start_worker()
    finally:
        one.close()
    two.start_worker()
    two.close()


def test_weekend_does_not_run_jobs(tmp_path, monkeypatch):
    app = service(tmp_path)
    app.control(True, True)
    calls = []
    monkeypatch.setattr(app._trader(), "eod", lambda *a, **k: calls.append("eod"))
    app.tick(datetime(2026, 11, 7, 16, 0, tzinfo=IST))
    assert calls == []
