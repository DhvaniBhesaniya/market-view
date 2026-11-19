from datetime import date, datetime, timedelta

from market_view.config import IST
from market_view.journal import Journal
from market_view.models import Trade
from market_view.paper.review import annotate_trade, save_plan, update_action, weekly_review


def insert(journal, pnl, day=4, mode="paper"):
    journal.mode = mode
    when = datetime(2026, 11, day, 11, 0, tzinfo=IST)
    journal.trade(Trade(strategy_id="test_v1", symbol="TCS", entry_time=when-timedelta(days=1),
                        exit_time=when, entry_price=1000, exit_price=1000+pnl/10, qty=10,
                        initial_stop=970, target=1060, gross_pnl=pnl+10, charges=10,
                        net_pnl=pnl, r_multiple=pnl/300, bars_held=1, mae_pct=-1, mfe_pct=1, exit_reason="stop"))


def test_empty_review_is_honest_and_has_three_priorities(tmp_path):
    report = weekly_review(tmp_path / "missing.duckdb", date(2026, 11, 5))
    assert report["summary"]["trades"] == 0
    assert report["summary"]["win_rate_pct"] is None
    assert report["rating"]["score"] is None
    assert len(report["actions"]) == 3
    assert not (tmp_path / "missing.duckdb").exists()


def test_report_uses_only_paper_exits_in_ist_week(tmp_path):
    j = Journal(tmp_path / "j.duckdb")
    insert(j, 100)
    insert(j, -50, day=5)
    insert(j, 999, day=12)
    insert(j, 800, mode="live")
    r = weekly_review(j.path, date(2026, 11, 5))
    assert r["summary"]["net_pnl"] == 50
    assert r["summary"]["trades"] == 2
    assert r["summary"]["win_rate_pct"] == 50
    assert r["summary"]["biggest_win"] == 100
    assert r["summary"]["biggest_loss"] == -50
    assert r["rating"]["score"] is None


def test_profitable_rule_breaks_score_worse_than_disciplined_losses(tmp_path):
    j = Journal(tmp_path / "j.duckdb")
    insert(j, 100)
    insert(j, -50, day=12)
    ids = j.query("SELECT rowid AS id FROM trades ORDER BY exit_time")["id"].tolist()
    annotate_trade(j.path, ids[0], False, False, False, False, "Risk and plan were both ignored.")
    annotate_trade(j.path, ids[1], True, True, True, True, "Followed the signal, sizing, and exit rules.")
    bad = weekly_review(j.path, date(2026, 11, 5))
    good = weekly_review(j.path, date(2026, 11, 12))
    assert bad["rating"]["score"] == 0
    assert good["rating"]["score"] == 10
    assert good["previous"]["summary"]["net_pnl"] == 100
    assert good["rating"]["basis"] == "Recorded process evidence; profit does not raise this score."


def test_review_cannot_annotate_nonpaper_trade(tmp_path):
    import pytest

    j = Journal(tmp_path / "j.duckdb")
    insert(j, 100, mode="live")
    with pytest.raises(ValueError, match="Paper"):
        annotate_trade(j.path, 0, True, True, True, True, "A review must never modify a live journal row.")


def test_next_week_can_track_a_saved_prior_plan(tmp_path):
    j = Journal(tmp_path / "j.duckdb")
    insert(j, 100)
    save_plan(j.path, date(2026, 11, 5))
    update_action(j.path, date(2026, 11, 5), 0, True, "Compared every fill with the approved signal and stop.")
    report = weekly_review(j.path, date(2026, 11, 12))
    prior_actions = report["previous"]["actions"]
    assert len(prior_actions) == 3
    assert prior_actions[0]["completed"] is True
    assert "approved signal" in prior_actions[0]["note"]
    assert prior_actions[1]["completed"] is False


def test_saved_plan_is_not_rewritten_after_new_annotations(tmp_path):
    j = Journal(tmp_path / "j.duckdb")
    insert(j, 100)
    save_plan(j.path, date(2026, 11, 5))
    before = weekly_review(j.path, date(2026, 11, 5))["actions"]
    annotate_trade(j.path, 0, False, False, False, False, "A new review revealed risk and plan violations.")
    save_plan(j.path, date(2026, 11, 5))
    assert weekly_review(j.path, date(2026, 11, 5))["actions"] == before
