"""Rule-based (no-code) strategies: validation, exact behaviour on known bars, look-ahead, versioning."""

import pandas as pd
import pytest
from pydantic import ValidationError

from market_view import indicators as ta
from market_view.backtest.engine import Backtester
from market_view.config import RiskConfig
from market_view.costs import CostModel
from market_view.market_context.regime import prepare_market
from market_view.risk.engine import RiskEngine
from market_view.strategies import get_class, make
from market_view.strategies.base import PositionView
from market_view.strategies.rules import (
    INDICATORS,
    RuleSpec,
    apply_params,
    compile_spec,
    compute_indicator,
    custom_dir,
    flatten,
    list_specs,
    lookahead_check,
    save_spec,
)
from tests.conftest import make_df, random_walk


def ind(name, output=None, **params):
    return {"kind": "indicator", "ind": name, "params": params, **({"output": output} if output else {})}


def num(v):
    return {"kind": "value", "value": v}


def spec(**kw) -> RuleSpec:
    base = {"name": "test_rule", "entry": [{"left": ind("rsi", n=14), "op": "<", "right": num(30)}],
            "market_filter": False}
    return RuleSpec(**{**base, **kw})


# ---------------------------------------------------------------- catalogue


@pytest.mark.parametrize("ind_id", sorted(INDICATORS))
def test_every_indicator_is_causal(ind_id):
    """Appending future bars must not change any past indicator value."""
    df = random_walk(400, seed=21)
    full = compute_indicator(df, ind_id)
    part = compute_indicator(df.iloc[:250], ind_id)
    for out in INDICATORS[ind_id].outputs:
        a, b = full[out].iloc[:250], part[out]
        assert len(b) == 250
        pd.testing.assert_series_equal(a, b, check_names=False, rtol=1e-9)


def test_macd_matches_definition():
    df = random_walk(300, seed=4)
    line, sig, hist = ta.macd(df["close"], 12, 26, 9)
    expected = df["close"].ewm(span=12, adjust=False, min_periods=12).mean() - \
        df["close"].ewm(span=26, adjust=False, min_periods=26).mean()
    pd.testing.assert_series_equal(line, expected, check_names=False)
    pd.testing.assert_series_equal(hist, line - sig, check_names=False)


def test_indicator_params_are_validated():
    df = random_walk(100)
    with pytest.raises(ValueError, match="outside"):
        compute_indicator(df, "rsi", {"n": 1})
    with pytest.raises(ValueError, match="whole number"):
        compute_indicator(df, "ema", {"n": 20.5})
    with pytest.raises(ValueError, match="unknown params"):
        compute_indicator(df, "sma", {"length": 20})
    with pytest.raises(ValueError, match="fast period"):
        compute_indicator(df, "macd", {"fast": 30, "slow": 26})


# ---------------------------------------------------------------- spec validation


@pytest.mark.parametrize("bad, msg", [
    ({"name": "Trend"}, "built-in"),
    ({"name": "x"}, "3-31 lowercase"),
    ({"name": "my_strat_v2"}, "_v<number>"),
    ({"entry": []}, "at least 1"),
    ({"entry": [{"left": num(5), "op": ">", "right": num(3)}]}, "left side"),
    ({"entry": [{"left": ind("nope"), "op": ">", "right": num(3)}]}, "unknown indicator"),
    ({"entry": [{"left": ind("bb", output="top"), "op": ">", "right": num(3)}]}, "outputs"),
    ({"entry": [{"left": ind("rsi", n=14), "op": "=>", "right": num(3)}]}, "op"),
    ({"stop": {"type": "atr", "value": 20}}, "outside"),
    ({"target": {"type": "r_multiple"}}, "outside"),
    ({"time_stop_bars": 0}, "greater than or equal"),
    ({"allowed_regimes": ["BULL"]}, "allowed_regimes"),
])
def test_invalid_specs_are_rejected(bad, msg):
    with pytest.raises(ValidationError, match=msg):
        spec(**bad)


def test_defaults_are_filled_and_described():
    s = spec(entry=[{"left": ind("ema", n=20), "op": "crosses_above", "right": ind("ema", n=50)},
                    {"left": ind("bb", output="lower"), "op": "<", "right": ind("close")}],
             target={"type": "r_multiple", "value": 2}, time_stop_bars=10)
    assert s.entry[1].left.params == {"n": 20, "k": 2.0}
    assert isinstance(s.entry[0].left.params["n"], int)
    text = s.describe()
    assert "EMA(20) crosses above EMA(50)" in text and "Bollinger(20,2) lower < Close" in text
    assert "target 2R" in text and "time stop 10 days" in text


# ---------------------------------------------------------------- exact behaviour on known bars


def rising(n=40, start=100.0, step=1.0):
    return make_df([(start + i * step,) * 4 for i in range(n)])


def test_crosses_above_fires_only_on_the_cross_bar():
    df = rising()  # close = 100, 101, ... 139
    s = spec(entry=[{"left": ind("close"), "op": "crosses_above", "right": num(110.5)}],
             stop={"type": "percent", "value": 5})
    out = compile_spec(s)().prepare(df, None)
    fired = out.index[out["entry"]]
    assert list(fired) == [df.index[11]]  # 110 -> 111 is the only cross
    gt = compile_spec(spec(entry=[{"left": ind("close"), "op": ">", "right": num(110.5)}]))().prepare(df, None)
    assert gt["entry"].sum() == 40 - 11  # '>' is true on every bar after


def test_stops_and_targets_are_exact():
    df = random_walk(300, seed=9)
    atr = ta.atr(df, 14)
    out = compile_spec(spec(stop={"type": "atr", "value": 2.5}, target={"type": "r_multiple", "value": 3}))().prepare(df, None)
    pd.testing.assert_series_equal(out["stop"], df["close"] - 2.5 * atr, check_names=False)
    pd.testing.assert_series_equal(out["target"] - df["close"], 3 * (df["close"] - out["stop"]), check_names=False)

    out = compile_spec(spec(stop={"type": "percent", "value": 4}, target={"type": "percent", "value": 10}))().prepare(df, None)
    assert out["stop"].iloc[-1] == pytest.approx(df["close"].iloc[-1] * 0.96)
    assert out["target"].iloc[-1] == pytest.approx(df["close"].iloc[-1] * 1.10)

    out = compile_spec(spec(stop={"type": "swing_low", "value": 7}))().prepare(df, None)
    assert out["stop"].iloc[-1] == pytest.approx(df["low"].iloc[-7:].min())
    assert out["target"].isna().all()


def test_market_filter_blocks_entries_when_nifty_below_50ema():
    df = rising(300)
    falling_nifty = make_df([(20000 - i * 10,) * 4 for i in range(300)])
    s = spec(entry=[{"left": ind("close"), "op": ">", "right": num(0)}], market_filter=True)
    out = compile_spec(s)().prepare(df, prepare_market(falling_nifty))
    assert not out["entry"].any()
    out = compile_spec(s.model_copy(update={"market_filter": False}))().prepare(df, prepare_market(falling_nifty))
    assert out["entry"].iloc[-1]


def test_manage_exit_rule_time_stop_and_trailing():
    s = spec(exit=[{"left": ind("rsi", n=14), "op": ">", "right": num(70)}], time_stop_bars=5, trail_atr_mult=2)
    st = compile_spec(s)()
    pos = PositionView("X", 10, 100, pd.Timestamp("2024-01-01").to_pydatetime(), 95, 95, None, 2, 120, False)
    m = st.manage(pos, pd.Series({"exit_signal": True, "exit1": True, "atr": 3.0}))
    assert m.exit_next_open and "RSI(14) > 70" in m.reason and m.new_stop == pytest.approx(114)
    m = st.manage(pos, pd.Series({"exit_signal": False, "exit1": False, "atr": 3.0}))
    assert not m.exit_next_open
    pos.bars_held = 5
    assert st.manage(pos, pd.Series({"exit_signal": False, "atr": 3.0})).exit_next_open


# ---------------------------------------------------------------- params for walk-forward / sensitivity


def test_flatten_and_apply_params_round_trip():
    s = spec(entry=[{"left": ind("rsi", n=14), "op": "<", "right": num(30)},
                    {"left": ind("close"), "op": ">", "right": ind("sma", n=200)}],
             target={"type": "r_multiple", "value": 2})
    flat = flatten(s)
    assert flat == {"entry1_left_n": 14, "entry1_right_value": 30.0, "entry2_right_n": 200,
                    "stop_value": 2.0, "target_value": 2.0}
    s2 = apply_params(s, {"entry1_left_n": 10, "entry1_right_value": 25.0, "stop_value": 3.0})
    assert s2.entry[0].left.params["n"] == 10 and s2.entry[0].right.value == 25 and s2.stop.value == 3
    with pytest.raises(ValueError, match="unknown param"):
        apply_params(s, {"bogus": 1})
    with pytest.raises(ValidationError, match="outside"):
        apply_params(s, {"entry1_left_n": 1})


def test_overrides_change_behaviour():
    df = random_walk(500, seed=2)
    cls = compile_spec(spec())
    a = cls().prepare(df, None)["entry"].sum()
    b = cls(entry1_right_value=45.0).prepare(df, None)["entry"].sum()
    assert b > a
    with pytest.raises(ValueError, match="unknown params"):
        cls(nope=1)


# ---------------------------------------------------------------- look-ahead


@pytest.mark.parametrize("ind_id", sorted(INDICATORS))
def test_lookahead_check_passes_for_every_indicator(ind_id):
    d = INDICATORS[ind_id]
    for out in d.outputs:
        s = spec(entry=[{"left": ind(ind_id, output=out), "op": "crosses_above", "right": ind("sma", n=10)}],
                 exit=[{"left": ind(ind_id, output=out), "op": "<", "right": num(0)}], market_filter=True,
                 target={"type": "r_multiple", "value": 2})
        assert lookahead_check(compile_spec(s)()) == []


def test_lookahead_check_catches_a_leak():
    """The checker must FAIL a strategy that peeks at tomorrow; otherwise it proves nothing."""
    base = compile_spec(spec())

    class Leaky(base):  # type: ignore[valid-type, misc]
        def prepare(self, df, market):
            out = super().prepare(df, market)
            out["entry"] = (df["close"].shift(-1) > df["close"]).fillna(False)  # tomorrow's close!
            return out

    assert lookahead_check(Leaky())


# ---------------------------------------------------------------- storage + registry


def test_save_creates_immutable_versions_and_registers():
    for f in custom_dir().glob("versioned_*.yaml"):
        f.unlink()
    v1 = save_spec(spec(name="versioned_one"))
    v2 = save_spec(spec(name="versioned_one", stop={"type": "atr", "value": 3}))
    assert (v1.version, v2.version) == (1, 2)
    assert (custom_dir() / "versioned_one_v1.yaml").exists() and (custom_dir() / "versioned_one_v2.yaml").exists()
    reloaded = {s.id: s for s in list_specs()}
    assert reloaded["versioned_one_v1"].stop.value == 2.0  # v1 untouched by saving v2
    assert reloaded["versioned_one_v2"].stop.value == 3.0
    assert get_class("versioned_one_v2").version == 2
    assert make("versioned_one_v1").spec.id == "versioned_one_v1"
    with pytest.raises(KeyError, match="unknown strategy"):
        make("versioned_one_v9")


# ---------------------------------------------------------------- through the real backtester


def test_rule_strategy_backtest_obeys_next_open_rule():
    df = random_walk(600, seed=33)
    s = spec(entry=[{"left": ind("rsi", n=14), "op": "<", "right": num(40)}],
             exit=[{"left": ind("rsi", n=14), "op": ">", "right": num(55)}],
             stop={"type": "atr", "value": 2}, time_stop_bars=10)
    strat = compile_spec(s)()
    risk = RiskEngine(cfg=RiskConfig(min_price=1, min_avg_turnover_cr=0, min_edge_to_cost_ratio=0),
                      sectors={}, initial_capital=500_000)
    bt = Backtester([strat], {"TEST": df}, df.index[60].date(), df.index[-1].date(), 500_000, risk=risk,
                    costs=CostModel())
    res = bt.run()
    assert len(res.trades) >= 5
    prepared = strat.prepare(df, None)
    for t in res.trades:
        i = df.index.get_loc(pd.Timestamp(t.entry_time))
        assert prepared["entry"].iloc[i - 1], "entry must follow a signal on the PREVIOUS bar"
        assert t.entry_price != df["close"].iloc[i - 1] or df["open"].iloc[i] == df["close"].iloc[i - 1]
        assert t.charges > 0
    assert res.params["specs"]["test_rule_v1"]["entry"][0]["right"]["value"] == 40
