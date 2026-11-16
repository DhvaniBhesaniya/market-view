"""meanrev_v1 — buy short-term oversold dips in long-term uptrends.

Thesis: sharp 2-3 day sell-offs in strong stocks tend to bounce. Works in RANGE / mild uptrends,
fails in crashes (hence the 200 SMA filter and a hard stop). Card: docs/strategies/meanrev_v1.md
"""

from __future__ import annotations

import pandas as pd

from market_view import indicators as ta
from market_view.strategies.base import Manage, PositionView, Strategy


class MeanReversionV1(Strategy):
    name = "meanrev"
    version = 1
    description = "Close > 200 SMA, RSI(2) < 10, close below lower Bollinger band"
    defaults = {
        "trend_sma": 200, "rsi_len": 2, "rsi_entry": 10.0, "rsi_exit": 70.0, "bb_len": 20, "bb_k": 2.0,
        "exit_sma": 5, "stop_atr": 2.5, "target_r": 2.0, "time_stop_bars": 7,
    }
    allowed_regimes = ("TREND_UP", "RANGE", "UNKNOWN")

    def prepare(self, df: pd.DataFrame, market: pd.DataFrame | None) -> pd.DataFrame:
        p = self.p
        out = self._join_market(self._common(df), market)
        out["sma_trend"] = ta.sma(df["close"], p["trend_sma"])
        out["rsi"] = ta.rsi(df["close"], p["rsi_len"])
        out["bb_lower"], _, _ = ta.bollinger(df["close"], p["bb_len"], p["bb_k"])
        out["sma_exit"] = ta.sma(df["close"], p["exit_sma"])
        out["entry"] = (
            (df["close"] > out["sma_trend"])
            & (out["rsi"] < p["rsi_entry"])
            & (df["close"] < out["bb_lower"])
        ).fillna(False)
        out["stop"] = df["close"] - p["stop_atr"] * out["atr"]
        out["target"] = df["close"] + p["target_r"] * (df["close"] - out["stop"])
        out["confidence"] = ((p["rsi_entry"] - out["rsi"]) / p["rsi_entry"]).clip(0, 1)
        return out

    def reasons(self, row: pd.Series) -> list[str]:
        return [
            f"above {self.p['trend_sma']} SMA (long-term uptrend)",
            f"RSI({self.p['rsi_len']}) {row['rsi']:.1f} < {self.p['rsi_entry']}",
            "close below lower Bollinger band",
            f"regime {row.get('regime', '?')}",
        ]

    def manage(self, pos: PositionView, row: pd.Series) -> Manage:
        if row["close"] > row["sma_exit"] or row["rsi"] > self.p["rsi_exit"]:
            return Manage(exit_next_open=True, reason="mean reverted (close > 5 SMA or RSI2 > 70)")
        if pos.bars_held >= self.p["time_stop_bars"]:
            return Manage(exit_next_open=True, reason=f"time stop {self.p['time_stop_bars']} bars")
        return Manage()
