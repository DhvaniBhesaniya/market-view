"""Market regime (rule-based v1). Phase 6 replaces/compares this with an ML classifier.

Regimes:
  TREND_UP    NIFTY above a rising 50 EMA and ADX >= 20
  TREND_DOWN  NIFTY below a falling 50 EMA and ADX >= 20
  HIGH_VOL    India VIX in the top 20% of its last year (overrides the above)
  RANGE       everything else
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from market_view import indicators as ta

REGIMES = ("TREND_UP", "TREND_DOWN", "RANGE", "HIGH_VOL")


def prepare_market(nifty: pd.DataFrame, vix: pd.DataFrame | None = None) -> pd.DataFrame:
    m = pd.DataFrame(index=nifty.index)
    m["m_close"] = nifty["close"]
    m["m_ema50"] = ta.ema(nifty["close"], 50)
    m["m_ema200"] = ta.ema(nifty["close"], 200)
    m["m_slope50"] = ta.slope(m["m_ema50"], 10)
    m["m_adx"] = ta.adx(nifty, 14)
    m["m_above50"] = m["m_close"] > m["m_ema50"]
    if vix is not None and not vix.empty:
        v = vix["close"].reindex(m.index, method="ffill")
        m["vix"] = v
        m["vix_pct"] = ta.rolling_percentile(v, 252)
    else:
        m["vix"] = np.nan
        m["vix_pct"] = np.nan

    up = m["m_above50"] & (m["m_slope50"] > 0) & (m["m_adx"] >= 20)
    down = (~m["m_above50"]) & (m["m_slope50"] < 0) & (m["m_adx"] >= 20)
    regime = np.where(up, "TREND_UP", np.where(down, "TREND_DOWN", "RANGE"))
    regime = np.where(m["vix_pct"].fillna(0) >= 0.8, "HIGH_VOL", regime)
    m["regime"] = pd.Series(regime, index=m.index).where(m["m_ema50"].notna(), "UNKNOWN")
    return m


def align(market: pd.DataFrame | None, index: pd.DatetimeIndex) -> pd.DataFrame | None:
    """Align market context to a symbol's bars using only past/current values (ffill, no bfill)."""
    if market is None:
        return None
    return market.reindex(market.index.union(index)).ffill().reindex(index)
