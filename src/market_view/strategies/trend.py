"""trend_v1 - buy pullbacks to the 20 EMA inside an established uptrend.

Thesis: trends persist; buying a pullback gives a closer stop (better R) than chasing highs.
Card: docs/strategies/trend_v1.md
"""

from __future__ import annotations

import pandas as pd

from market_view import indicators as ta
from market_view.strategies.base import Manage, PositionView, Strategy


class TrendPullbackV1(Strategy):
    name = "trend"
    version = 1
    description = "20/50 EMA uptrend, pullback to 20 EMA, RSI 50-70, volume confirmation"
    defaults = {
        "fast": 20, "slow": 50, "slope_bars": 10, "pullback_lookback": 3, "pullback_atr": 1.0,
        "rsi_min": 50.0, "rsi_max": 70.0, "vol_min": 1.2, "stop_atr": 2.0, "swing_low_bars": 5,
        "time_stop_bars": 15,
    }
    scale_out_r = 1.5
    scale_out_fraction = 0.5

    def prepare(self, df: pd.DataFrame, market: pd.DataFrame | None) -> pd.DataFrame:
        p = self.p
        out = self._join_market(self._common(df), market)
        out["ema_fast"] = ta.ema(df["close"], p["fast"])
        out["ema_slow"] = ta.ema(df["close"], p["slow"])
        out["ema_slow_slope"] = ta.slope(out["ema_slow"], p["slope_bars"])
        out["rsi"] = ta.rsi(df["close"], 14)
        touched = ta.lowest(df["low"], p["pullback_lookback"]) <= out["ema_fast"] + p["pullback_atr"] * out["atr"]
        out["entry"] = (
            out["m_above50"].eq(True)
            & (out["ema_fast"] > out["ema_slow"])
            & (out["ema_slow_slope"] > 0)
            & touched
            & (df["close"] > out["ema_fast"])
            & out["rsi"].between(p["rsi_min"], p["rsi_max"])
            & (out["vol_ratio"] >= p["vol_min"])
        ).fillna(False)
        swing_low = ta.lowest(df["low"], p["swing_low_bars"])
        out["stop"] = pd.concat([swing_low, df["close"] - p["stop_atr"] * out["atr"]], axis=1).min(axis=1)
        out["target"] = float("nan")  # managed by scale-out + trailing
        out["confidence"] = (out["vol_ratio"].clip(0, 3) / 3 * 0.5 + (out["rsi"] - 50) / 40).clip(0, 1)
        return out

    def reasons(self, row: pd.Series) -> list[str]:
        return [
            f"EMA{self.p['fast']}>EMA{self.p['slow']} (slope {row['ema_slow_slope']:.2f}%)",
            "pullback to fast EMA, closed back above",
            f"RSI {row['rsi']:.0f}",
            f"volume {row['vol_ratio']:.1f}x avg",
            f"NIFTY above 50 EMA, regime {row.get('regime', '?')}",
        ]

    def manage(self, pos: PositionView, row: pd.Series) -> Manage:
        if pos.scaled_out and row["close"] < row["ema_fast"]:
            return Manage(exit_next_open=True, reason="close below 20 EMA after scale-out")
        if not pos.scaled_out and pos.bars_held >= self.p["time_stop_bars"]:
            return Manage(exit_next_open=True, reason=f"time stop {self.p['time_stop_bars']} bars")
        return Manage()
