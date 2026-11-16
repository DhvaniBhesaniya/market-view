"""Regression tests for bugs found in the 2026-11-16 engine audit. Each test failed before its fix."""

from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from market_view.backtest.engine import Backtester
from market_view.backtest.metrics import sortino
from market_view.broker.paper import PaperBroker
from market_view.config import IST, RiskConfig
from market_view.costs import CostModel
from market_view.data.sources.base import Quote
from market_view.journal import Journal
from market_view.models import Side, Signal
from market_view.paper.trader import PaperTrader
from market_view.risk.engine import RiskEngine
from market_view.risk.killswitch import KillSwitch
from market_view.strategies.base import Manage, Strategy
from market_view.validation.sensitivity import nudged_values
from tests.conftest import make_df


class Shots(Strategy):
    """Entry signals on the bar indexes in `at`, stop = close - stop_dist, optional target."""

    name = "shots"
    version = 1
    defaults = {"at": (25,), "stop_dist": 10.0, "target_dist": 0.0}
    warmup_bars = 0

    def prepare(self, df, market):
        out = df.copy()
        out["entry"] = False
        for i in self.p["at"]:
            out.iloc[i, out.columns.get_loc("entry")] = True
        out["stop"] = out["close"] - self.p["stop_dist"]
        out["target"] = out["close"] + self.p["target_dist"] if self.p["target_dist"] else float("nan")
        out["confidence"] = 0.5
        return out

    def reasons(self, row):
        return ["test"]

    def manage(self, pos, row):
        return Manage()


def flat(n=40, p=100.0):
    return [(p, p + 1, p - 1, p)] * n


def backtest(bars, enforce=False, **params):
    df = make_df(bars)
    risk = RiskEngine(cfg=RiskConfig(min_price=1, min_edge_to_cost_ratio=0), sectors={}, initial_capital=500_000)
    return Backtester([Shots(**params)], {"TEST": df}, df.index[0].date(), df.index[-1].date(), 500_000,
                      risk=risk, costs=CostModel(), enforce_breakers=enforce).run()


# ---------------------------------------------------------------- backtest engine


def test_mae_includes_gap_exit_price():
    bars = flat()
    bars[28] = (70.0, 72, 69, 71)  # opens through the 90 stop
    t = backtest(bars).trades[0]
    assert t.exit_reason == "gap through stop"
    assert t.mae_pct == pytest.approx((70 / t.entry_price - 1) * 100)


def test_mfe_includes_target_exit_price():
    bars = flat()
    bars[30] = (100.0, 125, 99, 120)
    t = backtest(bars, target_dist=20.0).trades[0]
    assert t.exit_reason == "target"
    assert t.mfe_pct >= (120 / t.entry_price - 1) * 100 - 1e-9


def test_entry_skipped_when_raw_open_below_stop():
    bars = flat()
    bars[26] = (89.97, 90.5, 89.5, 90.2)  # stop 90; open below it, slippage pushes the fill above it
    res = backtest(bars)
    row = res.signals.iloc[0]
    assert not row["approved"] and "gapped" in row["reasons"]
    assert not res.trades


def test_daily_loss_breaker_recorded_and_enforced_like_paper():
    bars = flat(60)
    bars[30] = (50.0, 51, 49, 50)  # gap far through the stop: ~-1.25% of equity in one day
    research = backtest(bars, at=(25, 40))
    assert any("WOULD KILL SWITCH: daily loss" in e for e in research.events)
    # research mode resumes after the recorded event: the 2nd signal is taken (still open at the end)
    assert research.signals["approved"].tolist() == [True, True]
    assert research.params["open_positions_at_end"] == ["TEST"]

    live_like = backtest(bars, enforce=True, at=(25, 40))
    assert any(e.endswith("hit cap") and "KILL SWITCH" in e and "WOULD" not in e for e in live_like.events)
    # 2nd entry blocked, exactly as the latched paper kill switch would
    assert live_like.signals["approved"].tolist() == [True, False]
    assert "kill switch" in live_like.signals["reasons"].iloc[1].lower()
    assert live_like.params["open_positions_at_end"] == []


def test_sortino_uses_downside_deviation():
    eq = pd.Series(np.cumprod([1, 0.99, 1.02, 0.99, 1.02, 0.99, 1.02]) * 100,
                   index=pd.date_range("2024-01-01", periods=7))
    r = eq.pct_change().dropna()
    expected = r.mean() / np.sqrt((np.minimum(r, 0) ** 2).mean()) * np.sqrt(252)
    assert sortino(eq) == pytest.approx(expected)
    assert sortino(pd.Series([100.0, 101, 102, 103], index=pd.date_range("2024-01-01", periods=4))) == 0.0


# ---------------------------------------------------------------- costs (Groww minimum brokerage)


def test_groww_minimum_brokerage():
    c = CostModel()
    assert c.breakdown(Side.BUY, 2_000).brokerage == pytest.approx(5)    # 0.1% = 2 -> min Rs 5
    assert c.breakdown(Side.BUY, 100).brokerage == pytest.approx(2.5)    # min(5, 2.5% of 100)
    assert c.breakdown(Side.BUY, 100_000).brokerage == pytest.approx(20)


# ---------------------------------------------------------------- sensitivity


@pytest.mark.parametrize("base", [2, 3, 5, 14, 200])
def test_sensitivity_really_moves_integer_params(base):
    vals = [v for _, v in nudged_values(base)]
    assert len(set(vals)) >= 4, vals
    assert base in vals and all(isinstance(v, int) and v >= 1 for v in vals)


def test_sensitivity_float_params_use_factors():
    assert [v for _, v in nudged_values(2.0)] == [1.6, 1.8, 2.0, 2.2, 2.4]


# ---------------------------------------------------------------- paper trader


def _trader(tmp_path):
    return PaperTrader(root=tmp_path, broker=PaperBroker(tmp_path / "broker.json", 500_000),
                       journal=Journal(tmp_path / "j.duckdb"), killswitch=KillSwitch(tmp_path / "ks.json"))


def _q(sym, ltp, now, low=None, high=None, open_=None):
    return Quote(symbol=sym, ltp=ltp, low=low or ltp, high=high or ltp, open=open_ or ltp, time=now)


def _queue(t, sym="TCS", price=1000.0, stop=970.0, target=None, strategy="trend_v1"):
    s = Signal(strategy_id=strategy, symbol=sym, ref_price=price, stop=stop, target=target,
               bar_time=datetime(2026, 11, 4, 9, 15, tzinfo=IST), context={"turnover_cr": 500.0, "adv20": 1e7})
    t.st["pending_entries"] = [s.model_dump(mode="json")]
    t._save()


def test_raised_stop_ignores_lows_from_before_it_was_raised(tmp_path):
    t = _trader(tmp_path)
    d1 = datetime(2026, 11, 5, 9, 20, tzinfo=IST)
    _queue(t)
    t.open_job(d1, {"TCS": _q("TCS", 1000, d1)})
    entry = t.positions["TCS"]["entry_price"]
    for p in t.broker.s["protective"].values():
        p["placed_date"] = "2026-11-04"  # rested overnight, the normal case
    d2 = datetime(2026, 11, 6, 10, 0, tzinfo=IST)
    level = entry + 1.5 * (entry - 970)
    t.monitor(d2, {"TCS": _q("TCS", level + 1, d2, low=990, high=level + 1, open_=1000)})  # dip to 990, then rally
    assert t.positions["TCS"]["scaled_out"]
    later = d2 + timedelta(minutes=5)
    out = t.monitor(later, {"TCS": _q("TCS", level + 2, later, low=990, high=level + 2, open_=1000)})
    assert not out["fills"], "price never went back to breakeven after the stop was raised"
    assert "TCS" in t.positions
    # ...but a real drop to breakeven after the raise must still stop it out
    later2 = later + timedelta(minutes=5)
    out = t.monitor(later2, {"TCS": _q("TCS", entry - 1, later2, low=990, high=level + 2, open_=1000)})
    assert out["fills"] and "TCS" not in t.positions


def test_open_job_refuses_non_trading_day_and_keeps_signals(tmp_path):
    t = _trader(tmp_path)
    sat = datetime(2026, 11, 7, 9, 20, tzinfo=IST)
    _queue(t, strategy="meanrev_v1", target=1060.0)
    out = t.open_job(sat, {"TCS": _q("TCS", 1000, sat - timedelta(days=1))})
    assert not out["entries"] and "not a trading day" in out["skipped"][0]
    assert len(t.st["pending_entries"]) == 1  # kept for the next real session


def test_open_job_refuses_outside_market_hours(tmp_path):
    t = _trader(tmp_path)
    early = datetime(2026, 11, 6, 8, 30, tzinfo=IST)
    _queue(t, strategy="meanrev_v1", target=1060.0)
    out = t.open_job(early, {"TCS": _q("TCS", 1000, early)})
    assert not out["entries"] and "market closed" in out["skipped"][0]


def test_eod_on_holiday_keeps_pending_entries(tmp_path):
    t = _trader(tmp_path)
    _queue(t, strategy="meanrev_v1", target=1060.0)
    out = t.eod(today=date(2026, 11, 10), update_data=False, data={}, market=None)  # Diwali-Balipratipada
    assert "not a trading day" in out["warnings"][0]
    assert len(t.st["pending_entries"]) == 1
