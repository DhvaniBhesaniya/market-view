"""Technical indicators, written out so they can be read and learned from.

Every function is CAUSAL: the value at bar t uses only bars <= t. (tests/test_lookahead.py checks it.)
Wilder smoothing (RSI, ATR, ADX) = EMA with alpha = 1/period.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    """Simple moving average: plain mean of the last n closes."""
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    """Exponential moving average: recent bars weigh more. Reacts faster than SMA."""
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def _wilder(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """Relative Strength Index (0-100): average gain vs average loss.
    > 70 often called overbought, < 30 oversold. In strong trends RSI stays 50-70."""
    delta = close.diff()
    gain = _wilder(delta.clip(lower=0), n)
    loss = _wilder(-delta.clip(upper=0), n)
    rs = gain / loss.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.where(loss != 0, 100.0).where(gain.notna())


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    return pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Average True Range: the typical size of a bar in rupees, including gaps.
    Used for volatility-based stops: a 2xATR stop is 'two normal days' away."""
    return _wilder(true_range(df), n)


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Middle = SMA(n); bands = middle +/- k standard deviations."""
    mid = sma(close, n)
    sd = close.rolling(n, min_periods=n).std(ddof=0)
    return mid - k * sd, mid, mid + k * sd


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Average Directional Index (0-100): trend STRENGTH, not direction.
    < 20 weak/no trend (range), > 25 trending."""
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    tr = _wilder(true_range(df), n)
    plus_di = 100 * _wilder(plus_dm, n) / tr
    minus_di = 100 * _wilder(minus_dm, n) / tr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return _wilder(dx, n)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD = EMA(fast) - EMA(slow): momentum. Signal = EMA(signal) of MACD. Histogram = MACD - signal.
    MACD crossing above its signal line = momentum turning up."""
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return line, sig, line - sig


def highest(s: pd.Series, n: int, exclude_current: bool = True) -> pd.Series:
    """Highest value of the previous n bars (excluding today by default, for breakouts)."""
    base = s.shift(1) if exclude_current else s
    return base.rolling(n, min_periods=n).max()


def lowest(s: pd.Series, n: int, exclude_current: bool = False) -> pd.Series:
    base = s.shift(1) if exclude_current else s
    return base.rolling(n, min_periods=n).min()


def volume_ratio(volume: pd.Series, n: int = 20) -> pd.Series:
    """Today's volume / average of the PREVIOUS n days. 1.5 = 50% above normal."""
    return volume / volume.shift(1).rolling(n, min_periods=n).mean()


def slope(s: pd.Series, n: int = 10) -> pd.Series:
    """Percent change over n bars: positive = rising."""
    return s.pct_change(n) * 100


def close_location(df: pd.DataFrame) -> pd.Series:
    """Where the close sits in the day's range: 1 = at the high, 0 = at the low."""
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    return ((df["close"] - df["low"]) / rng).fillna(0.5)


def rolling_percentile(s: pd.Series, n: int = 252) -> pd.Series:
    """Percentile rank (0-1) of today's value within the last n values."""
    return s.rolling(n, min_periods=max(20, n // 4)).apply(lambda w: (w[:-1] < w[-1]).mean(), raw=True)


def avg_turnover_cr(df: pd.DataFrame, n: int = 20) -> pd.Series:
    """Average daily traded value in crore rupees (1 crore = 1e7)."""
    return (df["close"] * df["volume"]).rolling(n, min_periods=n).mean() / 1e7


def vwap(df: pd.DataFrame) -> pd.Series:
    """Intraday VWAP, reset each day. (Meaningful only on intraday bars.)"""
    tp = (df["high"] + df["low"] + df["close"]) / 3
    day = df.index.date
    pv = (tp * df["volume"]).groupby(day).cumsum()
    v = df["volume"].groupby(day).cumsum().replace(0, np.nan)
    return pv / v
