from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime

import pandas as pd
from pydantic import BaseModel

from market_view.config import IST
from market_view.models import OHLCV


class Quote(BaseModel):
    symbol: str
    ltp: float
    open: float | None = None
    high: float | None = None
    low: float | None = None
    prev_close: float | None = None
    time: datetime  # time the quote was observed / last bar time (IST)


class DataSource(ABC):
    """Normalized market data access.

    `history` returns a DataFrame indexed by tz-aware (Asia/Kolkata) bar-open timestamps named `ts`,
    with float columns open, high, low, close and int volume, sorted ascending, no duplicates.
    """

    name: str = "base"
    adjusted: bool = False  # True if prices are split/dividend adjusted

    @abstractmethod
    def history(self, symbol: str, interval: str, start: date, end: date) -> pd.DataFrame: ...

    @abstractmethod
    def quotes(self, symbols: list[str]) -> dict[str, Quote]: ...


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce a raw frame into the canonical OHLCV shape."""
    if df.empty:
        return pd.DataFrame(columns=OHLCV, index=pd.DatetimeIndex([], tz=IST, name="ts"))
    out = df.copy()
    out.columns = [str(c).lower() for c in out.columns]
    out = out[OHLCV]
    idx = pd.DatetimeIndex(out.index)
    idx = idx.tz_localize(IST) if idx.tz is None else idx.tz_convert(IST)
    out.index = idx.rename("ts")
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out = out.dropna(subset=["open", "high", "low", "close"])
    out[["open", "high", "low", "close"]] = out[["open", "high", "low", "close"]].astype(float)
    out["volume"] = out["volume"].fillna(0).astype("int64")
    return out
