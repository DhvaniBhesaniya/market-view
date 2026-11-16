"""Look-ahead guard: a strategy's values at bar t must not change when future bars are added.

If this fails, the strategy is peeking at the future and every backtest of it is fake.
"""

import pandas as pd
import pytest

from market_view.market_context.regime import prepare_market
from market_view.strategies import REGISTRY
from tests.conftest import random_walk

COLS = ["entry", "stop", "target", "confidence"]


@pytest.mark.parametrize("strategy_id", sorted(REGISTRY))
def test_no_lookahead(strategy_id):
    df = random_walk(700, seed=7)
    nifty = random_walk(700, seed=3, start_price=10_000)
    vix = random_walk(700, seed=5, start_price=15)
    strat = REGISTRY[strategy_id]()
    full = strat.prepare(df, prepare_market(nifty, vix))
    for cut in (300, 450, 650):
        part = strat.prepare(df.iloc[:cut], prepare_market(nifty.iloc[:cut], vix.iloc[:cut]))
        a = full[COLS].iloc[cut - 1]
        b = part[COLS].iloc[-1]
        for col in COLS:
            if pd.isna(a[col]) and pd.isna(b[col]):
                continue
            assert a[col] == pytest.approx(b[col], rel=1e-9), f"{strategy_id}.{col} changed at bar {cut}: future leak"


@pytest.mark.parametrize("strategy_id", sorted(REGISTRY))
def test_strategy_produces_signals_and_valid_stops(strategy_id):
    df = random_walk(1500, seed=11)
    nifty = random_walk(1500, seed=12, start_price=10_000)
    strat = REGISTRY[strategy_id]()
    p = strat.prepare(df, prepare_market(nifty))
    entries = p[p["entry"]]
    assert (entries["stop"] < entries["close"]).all()
