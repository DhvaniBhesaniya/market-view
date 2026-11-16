"""Strategy interface. Strategies are PURE: no network, no database, no clock.

The same object runs in backtest, paper and live:
  prepare(df, market) -> adds indicator columns + `entry` (bool), `stop`, `target`, `confidence`
                         computed causally (bar t uses bars <= t only)
  manage(position, row) -> per-bar exit management (trail stop up / exit next open)

Execution rule (CLAUDE.md #8): a signal on bar t's close is filled at bar t+1's open.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar

import pandas as pd

from market_view.models import Signal


@dataclass
class PositionView:
    symbol: str
    qty: int
    entry_price: float
    entry_time: datetime
    initial_stop: float
    stop: float
    target: float | None
    bars_held: int
    highest_high: float
    scaled_out: bool

    @property
    def r_per_share(self) -> float:
        return self.entry_price - self.initial_stop


@dataclass
class Manage:
    new_stop: float | None = None      # only ever raised, never lowered
    exit_next_open: bool = False
    reason: str = ""


class Strategy(ABC):
    name: ClassVar[str]
    version: ClassVar[int]
    description: ClassVar[str] = ""
    defaults: ClassVar[dict[str, Any]] = {}
    warmup_bars: ClassVar[int] = 210
    timeframe: ClassVar[str] = "1d"
    allowed_regimes: ClassVar[tuple[str, ...] | None] = None  # None = trade in any regime

    # profit booking: sell `scale_out_fraction` at `scale_out_r` R, then stop -> breakeven
    scale_out_r: ClassVar[float | None] = None
    scale_out_fraction: ClassVar[float] = 0.5

    def __init__(self, **overrides: Any) -> None:
        unknown = set(overrides) - set(self.defaults)
        if unknown:
            raise ValueError(f"{self.id}: unknown params {sorted(unknown)}")
        self.p: dict[str, Any] = {**self.defaults, **overrides}

    @property
    def id(self) -> str:
        return f"{self.name}_v{self.version}"

    @abstractmethod
    def prepare(self, df: pd.DataFrame, market: pd.DataFrame | None) -> pd.DataFrame: ...

    @abstractmethod
    def reasons(self, row: pd.Series) -> list[str]: ...

    @abstractmethod
    def manage(self, pos: PositionView, row: pd.Series) -> Manage: ...

    def regime_ok(self, row: pd.Series) -> bool:
        if self.allowed_regimes is None or "regime" not in row:
            return True
        return row["regime"] in self.allowed_regimes

    def signal_at(self, prepared: pd.DataFrame, ts: pd.Timestamp, symbol: str) -> Signal | None:
        """Build a Signal if `entry` fired on bar ts."""
        if ts not in prepared.index:
            return None
        row = prepared.loc[ts]
        if not bool(row.get("entry", False)) or not self.regime_ok(row):
            return None
        stop, close = float(row["stop"]), float(row["close"])
        if not stop < close:
            return None
        target = row.get("target")
        context = {
            k: (float(row[k]) if isinstance(row[k], int | float) else str(row[k]))
            for k in ("atr", "rsi", "adx", "vol_ratio", "turnover_cr", "adv20", "regime", "vix", "m_above50")
            if k in row and pd.notna(row[k])
        }
        return Signal(
            strategy_id=self.id,
            symbol=symbol,
            ref_price=close,
            stop=stop,
            target=float(target) if target is not None and pd.notna(target) else None,
            confidence=float(row.get("confidence", 0.5)),
            reasons=self.reasons(row),
            bar_time=ts.to_pydatetime(),
            context=context,
        )

    @staticmethod
    def _common(df: pd.DataFrame) -> pd.DataFrame:
        """Indicators most strategies and the risk engine need."""
        from market_view import indicators as ta

        out = df.copy()
        out["atr"] = ta.atr(df, 14)
        out["vol_ratio"] = ta.volume_ratio(df["volume"], 20)
        out["turnover_cr"] = ta.avg_turnover_cr(df, 20)
        out["adv20"] = df["volume"].rolling(20, min_periods=20).mean()
        return out

    @staticmethod
    def _join_market(out: pd.DataFrame, market: pd.DataFrame | None) -> pd.DataFrame:
        from market_view.market_context.regime import align

        m = align(market, out.index)
        if m is None:
            out["m_above50"] = True
            out["regime"] = "UNKNOWN"
            out["vix_pct"] = float("nan")
            return out
        return out.join(m)
