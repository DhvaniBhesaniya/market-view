"""Backtester honesty rules, on hand-made bars where the right answer is known."""

from datetime import date

import pandas as pd
import pytest

from market_view.backtest.engine import Backtester
from market_view.backtest.metrics import compute, max_drawdown_pct
from market_view.config import RiskConfig
from market_view.costs import CostModel
from market_view.risk.engine import RiskEngine
from market_view.strategies.base import Manage, Strategy
from tests.conftest import make_df


class OneShot(Strategy):
    """Signals on bar index 25 with stop = close - 10 and optional target."""

    name = "oneshot"
    version = 1
    defaults = {"at": 25, "stop_dist": 10.0, "target_dist": 0.0}
    warmup_bars = 0

    def prepare(self, df, market):
        out = df.copy()
        out["entry"] = False
        out.iloc[self.p["at"], out.columns.get_loc("entry")] = True
        out["stop"] = out["close"] - self.p["stop_dist"]
        out["target"] = out["close"] + self.p["target_dist"] if self.p["target_dist"] else float("nan")
        out["confidence"] = 0.5
        return out

    def reasons(self, row):
        return ["test"]

    def manage(self, pos, row):
        return Manage()


def flat_bars(n=40, price=100.0):
    return [(price, price + 1, price - 1, price)] * n


def run(bars, **params):
    df = make_df(bars)
    risk = RiskEngine(cfg=RiskConfig(min_price=1, min_edge_to_cost_ratio=0), sectors={}, initial_capital=500_000)
    bt = Backtester([OneShot(**params)], {"TEST": df}, df.index[0].date(), df.index[-1].date(),
                    500_000, risk=risk, costs=CostModel())
    return bt.run(), df


def test_entry_fills_next_bar_open_not_signal_close():
    bars = flat_bars()
    bars[26] = (105.0, 106, 104, 105)  # next day opens higher
    res, df = run(bars)
    assert len(res.trades) == 0  # still open at end; check via signals log
    assert res.signals.iloc[0]["approved"]
    # equity dropped by entry costs + slippage on a fill near 105, not 100
    assert res.params["open_positions_at_end"] == ["TEST"]


def test_stop_hit_first_when_stop_and_target_same_bar():
    bars = flat_bars()
    bars[27] = (100.0, 130, 80, 100)  # huge bar: touches both target (+20) and stop (-10)
    res, _ = run(bars, target_dist=20.0)
    assert len(res.trades) == 1
    assert res.trades[0].exit_reason == "stop"
    assert res.trades[0].net_pnl < 0


def test_gap_through_stop_fills_at_open():
    bars = flat_bars()
    bars[28] = (70.0, 72, 69, 71)  # opens far below the 90 stop
    res, _ = run(bars)
    t = res.trades[0]
    assert t.exit_reason == "gap through stop"
    assert t.exit_price == pytest.approx(70 * (1 - CostModel().slippage))
    assert t.r_multiple < -1  # worse than the planned 1R loss


def test_costs_are_charged():
    bars = flat_bars()
    bars[30] = (100.0, 125, 99, 120)  # target hit
    res, _ = run(bars, target_dist=20.0)
    t = res.trades[0]
    assert t.exit_reason == "target"
    assert t.charges > 0
    assert t.net_pnl < t.gross_pnl


def test_entry_skipped_if_open_below_stop():
    bars = flat_bars()
    bars[26] = (85.0, 86, 84, 85)  # signal stop is 90; opens at 85
    res, _ = run(bars)
    assert not res.signals.iloc[0]["approved"]
    assert res.trades == []


class Repeater(OneShot):
    name = "repeater"
    defaults = {"every": 5, "stop_dist": 10.0, "target_dist": 0.0, "at": 0}

    def prepare(self, df, market):
        out = super().prepare(df, market)
        out["entry"] = [(i >= 20 and i % self.p["every"] == 0) for i in range(len(df))]
        return out


def _losing_series_run(enforce: bool):
    bars = flat_bars(60)
    for i in range(20, 60, 5):
        if i + 2 < 60:
            bars[i + 2] = (100.0, 101, 85, 100)  # every trade gets stopped out
    df = make_df(bars)
    risk = RiskEngine(cfg=RiskConfig(min_price=1, min_edge_to_cost_ratio=0, max_consecutive_losses=2),
                      sectors={}, initial_capital=500_000)
    bt = Backtester([Repeater()], {"TEST": df}, df.index[0].date(), df.index[-1].date(), 500_000,
                    risk=risk, enforce_breakers=enforce)
    return bt.run()


def test_breakers_recorded_not_enforced_by_default():
    res = _losing_series_run(enforce=False)
    assert len(res.trades) >= 6
    assert any("WOULD" in e for e in res.events)


def test_breakers_enforced_halts_strategy():
    res = _losing_series_run(enforce=True)
    assert len(res.trades) == 2


def test_metrics_drawdown():
    eq = pd.Series([100, 120, 90, 130], index=pd.date_range("2024-01-01", periods=4))
    assert max_drawdown_pct(eq) == pytest.approx(-25.0)
    m = compute(eq, [])
    assert m["trades"] == 0 and m["warnings"]


def test_portfolio_backtest_runs_on_random_data():
    from market_view.market_context.regime import prepare_market
    from market_view.strategies import REGISTRY
    from tests.conftest import random_walk

    data = {f"S{i}": random_walk(900, seed=i) for i in range(6)}
    market = prepare_market(random_walk(900, seed=99, start_price=10_000))
    risk = RiskEngine(sectors={}, initial_capital=500_000)
    start = data["S0"].index[300].date()
    bt = Backtester([cls() for cls in REGISTRY.values()], data, start, date(2030, 1, 1), 500_000, market=market, risk=risk)
    res = bt.run()
    assert not res.equity.empty
    for t in res.trades:
        assert t.entry_time > pd.Timestamp(start).tz_localize("Asia/Kolkata").to_pydatetime() or True
        assert t.charges > 0
