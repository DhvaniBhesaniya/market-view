import numpy as np
import pandas as pd

from market_view import indicators as ta
from tests.conftest import random_walk


def test_sma_ema_basic():
    s = pd.Series([1.0, 2, 3, 4, 5])
    assert ta.sma(s, 3).iloc[-1] == 4.0
    assert np.isnan(ta.sma(s, 3).iloc[1])
    e = ta.ema(s, 3)
    assert 4.0 < e.iloc[-1] < 5.0  # EMA leans toward recent values


def test_rsi_bounds_and_extremes():
    up = pd.Series(np.arange(1, 50, dtype=float))
    assert ta.rsi(up, 14).iloc[-1] == 100.0
    down = pd.Series(np.arange(50, 1, -1, dtype=float))
    assert ta.rsi(down, 14).iloc[-1] < 1
    r = ta.rsi(random_walk()["close"], 14).dropna()
    assert ((r >= 0) & (r <= 100)).all()


def test_atr_positive_and_adx_range():
    df = random_walk()
    assert (ta.atr(df).dropna() > 0).all()
    a = ta.adx(df).dropna()
    assert ((a >= 0) & (a <= 100)).all()


def test_highest_excludes_current_bar():
    s = pd.Series([1.0, 2, 3, 10])
    # previous 3 bars' high at the last bar is 3, not 10 (no peeking at today)
    assert ta.highest(s, 3).iloc[-1] == 3.0


def test_volume_ratio_uses_previous_days():
    v = pd.Series([100.0] * 20 + [300.0])
    assert ta.volume_ratio(v, 20).iloc[-1] == 3.0
