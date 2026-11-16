"""Chart-only timeframes over observed candles. Never infer fine bars from coarse data."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from market_view.config import IST, env, get_settings
from market_view.data import store
from market_view.data.sources import get_source
from market_view.data.sources.base import normalize

SOURCES = {"yfinance", "upstox"}
NATIVE_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "60m": 60}
MAX_BARS = 20_000


@dataclass(frozen=True)
class Interval:
    count: int
    unit: str

    @classmethod
    def parse(cls, value: str) -> Interval:
        if re.fullmatch(r"\d+s", value):
            raise ValueError("Seconds candles need a recorded tick-data feed. Current history sources start at 1 minute.")
        match = re.fullmatch(r"([1-9]\d{0,3})(m|h|d|w|M)", value)
        if not match:
            raise ValueError("Use a positive whole interval such as 5m, 2h, 1d, 1w or 1M (months).")
        count, unit = int(match[1]), match[2]
        limit = {"m": 390, "h": 6, "d": 365, "w": 52, "M": 120}[unit]
        if count > limit:
            raise ValueError(f"The maximum custom {unit} interval is {limit}.")
        return cls(count, unit)

    @property
    def intraday(self) -> bool:
        return self.unit in {"m", "h"}

    @property
    def minutes(self) -> int:
        return self.count * (60 if self.unit == "h" else 1)

    @property
    def key(self) -> str:
        return f"{self.count}{self.unit}"

    @property
    def download_interval(self) -> str:
        if not self.intraday:
            return "1d"
        return {1: "1m", 5: "5m", 15: "15m", 30: "30m", 60: "1h"}.get(self.minutes, "1m")


def validate_source(source: str | None) -> str:
    source = source or get_settings().backtest.data_source
    if source not in SOURCES:
        raise ValueError("Data source must be yfinance or upstox.")
    return source


def validate_symbol(symbol: str) -> None:
    # Reject separators and unknown instruments before constructing a storage path or request.
    universe = get_settings().universe
    if symbol not in set(universe.all_symbols()) | set(universe.indices):
        raise ValueError(f"Unknown symbol {symbol!r}; select a configured NSE instrument.")


def aggregate(df: pd.DataFrame, interval: Interval, native: str) -> pd.DataFrame:
    if df.empty or (not interval.intraday and interval.key == "1d"):
        return df
    df = df.copy().sort_index()
    idx = df.index.tz_convert(IST)
    if interval.intraday:
        # Anchor to each NSE session, not midnight/UTC or the first observed (possibly late) tick.
        opening = get_settings().calendar.session["open"]
        hour, minute = (int(x) for x in opening.split(":"))
        anchors = idx.normalize() + pd.Timedelta(hours=hour, minutes=minute)
        width = pd.Timedelta(minutes=interval.minutes)
        labels = anchors + ((idx - anchors) // width) * width
    elif interval.unit == "M":
        month_number = idx.year * 12 + idx.month - 1
        labels = month_number // interval.count
    else:
        anchor = pd.Timestamp("1970-01-05" if interval.unit == "w" else "1970-01-01", tz=IST)
        days = interval.count * (7 if interval.unit == "w" else 1)
        labels = (idx.normalize() - anchor).days // days
    df["_observed_at"] = idx
    out = df.groupby(labels, sort=True).agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"),
        close=("close", "last"), volume=("volume", "sum"), _observed_at=("_observed_at", "first"),
    )
    if interval.intraday:
        out.index = pd.DatetimeIndex(out.index, name="ts")
    else:
        # Calendar candles are labelled by their first observed trading session, not a fake tick.
        out.index = pd.DatetimeIndex(out["_observed_at"], name="ts")
    return out.drop(columns="_observed_at")


def load(symbol: str, interval: Interval, source: str) -> tuple[pd.DataFrame, str, Path | None]:
    candidates = ([interval.download_interval] + [name for name, minutes in NATIVE_MINUTES.items()
                    if interval.minutes % minutes == 0]) if interval.intraday else ["1d"]
    for native in dict.fromkeys(candidates):
        path = store.clean_path(source, native, symbol)
        if not path.exists():
            continue
        df = store.load(symbol, native, source)
        if not df.empty:
            out = aggregate(df, interval, native)
            out.attrs["last_observation"] = df.index[-1].isoformat()
            return out, native, path
    return normalize(pd.DataFrame()), interval.download_interval, None


def describe(df: pd.DataFrame, interval: Interval, source: str, native: str, path: Path | None) -> dict:
    return {
        "source": source, "interval": interval.key, "source_interval": native,
        "timezone": "Asia/Kolkata", "adjusted": source == "yfinance", "live": False,
        "aggregated": interval.key != native,
        "last_observation": df.attrs.get("last_observation", df.index[-1].isoformat()) if not df.empty else None,
        "downloaded_at": datetime.fromtimestamp(path.stat().st_mtime, IST).isoformat() if path else None,
        "needs_download": df.empty,
        "message": ("No stored minute candles for this interval. Download market data to load the chart."
                    if interval.intraday else "No stored daily candles. Download market data to load the chart.") if df.empty else None,
    }


def download(symbol: str, interval: Interval, source: str, start: date | None, end: date | None) -> dict:
    """Explicit single-symbol history fetch. No order or account API is used."""
    validate_symbol(symbol)
    source = validate_source(source)
    if source == "upstox" and not env("UPSTOX_ACCESS_TOKEN"):
        raise ValueError("Configure UPSTOX_ACCESS_TOKEN before downloading Upstox candles.")
    today = datetime.now(IST).date()
    end = min(end or today, today)
    native = interval.download_interval
    earliest = date(2000, 1, 1) if source == "upstox" else date(1970, 1, 1)
    if interval.intraday:
        # Conservative Yahoo windows (1m request capped to a recent week); broker history is paged.
        earliest = today - timedelta(days=6 if native == "1m" else 59)
        if source == "upstox":
            earliest = date(2022, 1, 1)
        start = start or end - timedelta(days=5 if native == "1m" else 30)
        # Chart downloads are bounded; longer bulk imports belong in the CLI.
        start = max(start, end - timedelta(days=365), earliest)
    else:
        start = max(start or date(2008, 1, 1), earliest)
        if source == "yfinance":
            existing = store.load(symbol, "1d", source)
            if not existing.empty:
                # Splits/dividends can revise the whole adjusted series. Avoid joining a new
                # visible slice to older prices calculated on a different adjustment basis.
                start = min(start, existing.index[0].date())
                end = min(today, max(end, existing.index[-1].date()))
    if start > end:
        raise ValueError("Requested dates are outside the provider's available history. Choose a recent date range.")
    adapter = get_source(source)
    df = adapter.history(symbol, native, start, end)
    if df.empty:
        raise RuntimeError("The provider returned no candles. Check the symbol, date range and data access, then retry.")
    store.save(df, source, native, symbol)
    return {"symbol": symbol, "source": source, "interval": interval.key, "source_interval": native,
            "bars_downloaded": len(df), "start": start.isoformat(), "end": end.isoformat()}
