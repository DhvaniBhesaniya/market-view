"""breakout_v1 - 20-day high breakout on strong volume, trailed with a chandelier stop.

Thesis: a volatility expansion on high volume often continues. False breakouts are the main
enemy - every one is journaled for the learning loop. Card: docs/strategies/breakout_v1.md
"""

from __future__ import annotations

import pandas as pd

from market_view import indicators as ta
from market_view.strategies.base import Manage, PositionView, Strategy


class BreakoutV1(Strategy):
    name = "breakout"
    version = 1
    description = "Close above prior 20-day high, volume >= 1.5x, ADX > 20, strong close"
    defaults = {
        "lookback": 20, "vol_min": 1.5, "adx_min": 20.0, "close_loc_min": 0.75,
        "vix_pct_max": 0.8, "stop_atr": 2.0, "trail_atr": 3.0, "time_stop_bars": 20,
    }

    def prepare(self, df: pd.DataFrame, market: pd.DataFrame | None) -> pd.DataFrame:
        p = self.p
        out = self._join_market(self._common(df), market)
        out["hh"] = ta.highest(df["high"], p["lookback"], exclude_current=True)
        out["adx"] = ta.adx(df, 14)
        out["close_loc"] = ta.close_location(df)
        vix_ok = out["vix_pct"].isna() | (out["vix_pct"] < p["vix_pct_max"])
        out["entry"] = (
            out["m_above50"].eq(True)
            & vix_ok
            & (df["close"] > out["hh"])
            & (out["vol_ratio"] >= p["vol_min"])
            & (out["adx"] > p["adx_min"])
            & (out["close_loc"] >= p["close_loc_min"])
        ).fillna(False)
        out["stop"] = df["close"] - p["stop_atr"] * out["atr"]
        out["target"] = float("nan")
        out["confidence"] = ((out["vol_ratio"] - 1).clip(0, 3) / 3 * 0.6 + (out["adx"] / 50).clip(0, 0.4)).clip(0, 1)
        return out

    def reasons(self, row: pd.Series) -> list[str]:
        return [
            f"close above {self.p['lookback']}-day high {row['hh']:.2f}",
            f"volume {row['vol_ratio']:.1f}x avg",
            f"ADX {row['adx']:.0f}",
            f"closed in top {100 - row['close_loc'] * 100:.0f}% of range",
            f"regime {row.get('regime', '?')}",
        ]

    def manage(self, pos: PositionView, row: pd.Series) -> Manage:
        chandelier = pos.highest_high - self.p["trail_atr"] * row["atr"]
        new_stop = chandelier if chandelier > pos.stop else None
        if pos.bars_held >= self.p["time_stop_bars"]:
            return Manage(new_stop=new_stop, exit_next_open=True, reason=f"time stop {self.p['time_stop_bars']} bars")
        return Manage(new_stop=new_stop, reason="chandelier trail" if new_stop else "")
