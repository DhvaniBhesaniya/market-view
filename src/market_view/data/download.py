"""Download history for the universe + benchmark indices into the store."""

from __future__ import annotations

import io
from datetime import date

import pandas as pd
import requests
import yaml

from market_view.config import CONFIG_DIR, get_settings
from market_view.data import store
from market_view.data.sources import get_source

NIFTY50_CSV = "https://archives.nseindia.com/content/indices/ind_nifty50list.csv"


def download(symbols: list[str], interval: str, start: date, end: date, source: str = "auto",
             progress=None) -> dict[str, int]:
    src = get_source(source)
    counts: dict[str, int] = {}
    for sym in symbols:
        try:
            df = src.history(sym, interval, start, end)
        except Exception as e:  # keep going; report failures
            counts[sym] = -1
            if progress:
                progress(sym, f"FAILED: {e}")
            continue
        store.save(df, src.name, interval, sym)
        counts[sym] = len(df)
        if progress:
            progress(sym, f"{len(df)} bars")
    return counts


def default_symbols(include_indices: bool = True) -> list[str]:
    s = get_settings()
    syms = s.universe.all_symbols()
    if include_indices:
        syms = list(s.universe.indices) + syms
    return syms


def refresh_nifty50() -> tuple[list[str], list[str]]:
    """Fetch NSE's official constituents CSV and rewrite the `symbols` block of universe.yaml.
    Removed names move to `former_members` (they stay in backtests: fights survivorship bias)."""
    resp = requests.get(NIFTY50_CSV, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    resp.raise_for_status()
    csv = pd.read_csv(io.StringIO(resp.text))
    path = CONFIG_DIR / "universe.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    old = data.get("symbols", {})
    new = {row["Symbol"]: {"isin": row["ISIN Code"], "sector": row["Industry"]}
           for _, row in csv.iterrows()}
    added = [s for s in new if s not in old]
    removed = [s for s in old if s not in new]
    data["former_members"] = {**(data.get("former_members") or {}), **{s: old[s] for s in removed}}
    data["symbols"] = new
    data["fetched"] = date.today().isoformat()
    header = "\n".join(line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("#"))
    path.write_text(header + "\n\n" + yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    get_settings.cache_clear()
    return added, removed
