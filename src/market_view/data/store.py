"""Append-only market data storage (CLAUDE.md rule 7: never silently overwrite).

Layout:
  data/raw/{source}/{interval}/{symbol}/{fetched_at}.parquet   every download, kept forever
  data/clean/{source}/{interval}/{symbol}.parquet              merged view (latest fetch wins)
  data/revisions.jsonl                                         every value that changed on re-download
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from market_view.config import DATA_DIR, IST
from market_view.data.sources.base import normalize
from market_view.models import OHLCV


def _safe(symbol: str) -> str:
    return symbol.replace("&", "_and_").replace("/", "_").replace("^", "")


def raw_dir(source: str, interval: str, symbol: str) -> Path:
    return DATA_DIR / "raw" / source / interval / _safe(symbol)


def clean_path(source: str, interval: str, symbol: str) -> Path:
    return DATA_DIR / "clean" / source / interval / f"{_safe(symbol)}.parquet"


def save(df: pd.DataFrame, source: str, interval: str, symbol: str) -> Path | None:
    """Store a fresh download: write raw snapshot, merge into clean, log revisions."""
    if df.empty:
        return None
    df = normalize(df)
    fetched = datetime.now(IST).strftime("%Y%m%dT%H%M%S%f")
    rdir = raw_dir(source, interval, symbol)
    rdir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(rdir / f"{fetched}.parquet")

    cpath = clean_path(source, interval, symbol)
    cpath.parent.mkdir(parents=True, exist_ok=True)
    if cpath.exists():
        old = pd.read_parquet(cpath)
        _log_revisions(old, df, source, interval, symbol)
        merged = pd.concat([old[~old.index.isin(df.index)], df]).sort_index()
    else:
        merged = df
    merged.to_parquet(cpath)
    return cpath


def _log_revisions(old: pd.DataFrame, new: pd.DataFrame, source: str, interval: str, symbol: str) -> None:
    common = old.index.intersection(new.index)
    if common.empty:
        return
    a, b = old.loc[common, OHLCV].astype(float), new.loc[common, OHLCV].astype(float)
    changed = ((a - b).abs() > 1e-6 * (a.abs() + 1)).any(axis=1)
    if not changed.any():
        return
    path = DATA_DIR / "revisions.jsonl"
    with path.open("a", encoding="utf-8") as f:
        for ts in common[changed]:
            f.write(json.dumps({
                "logged_at": datetime.now(IST).isoformat(), "source": source, "interval": interval,
                "symbol": symbol, "ts": ts.isoformat(),
                "old": a.loc[ts].to_dict(), "new": b.loc[ts].to_dict(),
            }) + "\n")


def load(symbol: str, interval: str = "1d", source: str = "yfinance",
         start: date | None = None, end: date | None = None) -> pd.DataFrame:
    path = clean_path(source, interval, symbol)
    if not path.exists():
        return normalize(pd.DataFrame())
    df = pd.read_parquet(path)
    if start is not None:
        df = df[df.index.date >= start]
    if end is not None:
        df = df[df.index.date <= end]
    return df


def load_many(symbols: list[str], interval: str = "1d", source: str = "yfinance",
              start: date | None = None, end: date | None = None) -> dict[str, pd.DataFrame]:
    out = {}
    for s in symbols:
        df = load(s, interval, source, start, end)
        if not df.empty:
            out[s] = df
    return out


def available(source: str = "yfinance", interval: str = "1d") -> list[str]:
    d = DATA_DIR / "clean" / source / interval
    return sorted(p.stem.replace("_and_", "&") for p in d.glob("*.parquet")) if d.exists() else []
