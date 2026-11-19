from datetime import date, datetime

import pandas as pd
import pytest

from market_view.config import IST, get_settings
from market_view.market_context.regime import prepare_market
from market_view.research.lab import ResearchLab, TrendAdxResearch, market_context, numeric_checks
from market_view.strategies.trend import TrendPullbackV1
from tests.conftest import random_walk


def test_adx_hypothesis_only_filters_baseline_and_is_causal():
    data = random_walk(420)
    baseline = TrendPullbackV1().prepare(data, None)
    # Supply a known completed-bar market filter, without changing the stock series.
    market = pd.DataFrame({"m_above50": True}, index=data.index)
    baseline = TrendPullbackV1().prepare(data, market)
    candidate = TrendAdxResearch().prepare(data, market)
    assert not (candidate.entry & ~baseline.entry).any()
    assert candidate.loc[candidate.entry, "adx"].ge(20).all()
    changed = data.copy()
    changed.iloc[300:, changed.columns.get_indexer(["open", "high", "low", "close"])] *= 2
    before = TrendAdxResearch().prepare(changed, market)
    pd.testing.assert_frame_equal(candidate.iloc[:300], before.iloc[:300])
    assert TrendAdxResearch().id != TrendPullbackV1().id


def test_bad_or_missing_data_records_blocked_report_without_backtesting(tmp_path):
    lab = ResearchLab(tmp_path)
    bad = random_walk(400)
    bad.iloc[250, bad.columns.get_loc("high")] = 1
    report = lab.run_cycle({"TCS": bad}, None)
    assert report["status"] == "blocked"
    assert report["runs"] == []
    assert report["blockers"]
    assert len(lab.history()) == 1
    assert (tmp_path / report["id"] / "manifest.json").exists()


def test_locked_period_overlap_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings().backtest.periods["validate"], "end", "2024-12-31")
    with pytest.raises(ValueError, match="locked"):
        ResearchLab(tmp_path).run_cycle({"TCS": random_walk()}, None)


def test_identical_snapshot_reuses_record_instead_of_retesting_validation(tmp_path):
    lab = ResearchLab(tmp_path)
    data = {"TCS": random_walk()}
    first = lab.run_cycle(data, None)
    second = lab.run_cycle(data, None)
    assert first["id"] == second["id"]
    assert second["reused"] is True
    assert len(lab.history()) == 1


def test_numeric_screen_cannot_establish_full_gate_approval():
    metrics = {"profit_factor": 1.5, "trades": 120, "max_drawdown_pct": -10,
               "sharpe": 1.2, "benchmark_sharpe": .7, "total_return_pct": 12}
    checks = numeric_checks(metrics, metrics, [metrics, metrics], [metrics, metrics, metrics], metrics)
    assert all(checks.values())
    metrics["profit_factor"] = float("nan")
    assert not numeric_checks(metrics, metrics, [metrics], [metrics], metrics)["validation_profit_factor"]


def test_weekly_scheduler_defaults_off_and_submits_once_per_week(tmp_path):
    lab = ResearchLab(tmp_path)
    submitted = []
    sunday = datetime(2026, 11, 22, 10, 1, tzinfo=IST)
    lab.tick(sunday, lambda: submitted.append(1))
    assert submitted == []
    lab.control(True)
    lab.tick(sunday, lambda: submitted.append(1))
    lab.tick(sunday, lambda: submitted.append(1))
    assert submitted == [1]
    assert ResearchLab(tmp_path).status()["enabled"] is True


def test_market_context_excludes_today_before_close():
    data = random_walk(400, start="2025-05-01")
    last = data.index[-1]
    market = market_context(data, None, datetime.combine(last.date(), datetime.min.time(), IST).replace(hour=11))
    assert date.fromisoformat(market["as_of"][:10]) < last.date()
    assert market["news_available"] is False


def test_actual_cycle_pins_inputs_records_trials_and_never_selects_on_holdout(tmp_path):
    data = random_walk(3700, start="2009-01-01")
    data["volume"] *= 20
    market = prepare_market(data, None)
    lab = ResearchLab(tmp_path)
    enabled_before = get_settings().strategies.model_dump()
    risk_before = get_settings().risk.model_dump()
    report = lab.run_cycle({"TCS": data}, market)
    assert report["runs"], report["blockers"]
    assert len(report["runs"]) <= 18
    assert report["promotion_allowed"] is False
    assert all(date.fromisoformat(r["end"]) < date(2023, 1, 1) for r in report["runs"])
    pinned = pd.read_parquet(tmp_path / report["id"] / "inputs" / "TCS.parquet")
    assert pinned.index[-1].year == 2022
    changed = data.copy()
    changed.loc[changed.index.year >= 2023, "close"] *= 100
    # A different holdout price must not change this experiment or consume validation again.
    assert lab.run_cycle({"TCS": changed}, market)["id"] == report["id"]
    assert get_settings().strategies.model_dump() == enabled_before
    assert get_settings().risk.model_dump() == risk_before


def test_promising_cycle_runs_bounded_robustness_without_promoting_or_mutating_risk(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import market_view.research.lab as module

    initial_risk = get_settings().risk.risk_per_trade_pct
    monkeypatch.setattr(get_settings().risk, "risk_per_trade_pct", initial_risk)
    calls = []

    class FakeEngine:
        def __init__(self, strategies, data, start, end, capital, **kwargs):
            self.strategy = strategies[0]
            calls.append({"start": start, "end": end, "risk": kwargs["risk"].cfg.risk_per_trade_pct,
                          "slippage": kwargs["costs"].slippage, "operational": kwargs["enforce_breakers"]})

        def run(self):
            get_settings().risk.risk_per_trade_pct = .4  # outside changes must not alter this frozen run
            return SimpleNamespace(equity=pd.Series([500000., 510000.], index=pd.date_range("2020-01-01", periods=2)),
                trades=[self.strategy.id], benchmark=None, trades_df=lambda: pd.DataFrame())

    monkeypatch.setattr(module, "Backtester", FakeEngine)
    monkeypatch.setattr(module, "compute", lambda eq, trades, benchmark: {
        "profit_factor": 1.5, "trades": 120, "max_drawdown_pct": -10, "sharpe": 1.2,
        "benchmark_sharpe": .7, "total_return_pct": 12, "expectancy_r": .2 if trades[0].startswith("research") else .1})
    data = random_walk(3700, start="2009-01-01")
    report = ResearchLab(tmp_path).run_cycle({"TCS": data}, prepare_market(data, None))
    assert len(calls) == 18
    assert report["status"] == "needs_evidence" and not report["promotion_allowed"]
    assert all(call["risk"] == initial_risk for call in calls)
    assert sum(call["operational"] for call in calls) == 1
    assert sum(call["slippage"] == 2*calls[0]["slippage"] for call in calls) == 1
    assert all(call["end"] < date(2023, 1, 1) for call in calls)


def test_interrupted_attempt_is_visible_and_not_silently_retested(tmp_path):
    lab = ResearchLab(tmp_path)
    data = {"TCS": random_walk()}
    report = lab.run_cycle(data, None)
    (tmp_path / report["id"] / "report.json").unlink()  # simulate interrupted final reporting
    assert lab.history()[0]["status"] == "interrupted"
    assert lab.run_cycle(data, None)["reused"] is True


def test_scheduler_failure_is_visible_and_disables_scheduling(tmp_path, monkeypatch):
    import time

    lab = ResearchLab(tmp_path)
    lab.control(True)

    def fail(*args):
        raise OSError("simulated scheduler storage failure")

    monkeypatch.setattr(lab, "tick", fail)
    lab.start_worker(lambda: None)
    try:
        deadline = time.monotonic()+2
        while not lab.status()["last_error"] and time.monotonic() < deadline:
            time.sleep(.01)
        assert lab.status()["worker_running"]
        assert not lab.status()["enabled"]
        assert "storage failure" in lab.status()["last_error"]
        assert ResearchLab(tmp_path).status()["enabled"] is False
    finally:
        lab.close()
