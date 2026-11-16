"""Turn pandas objects into JSON the charts understand.

Lightweight Charts wants `{time, value}` points with STRICTLY ascending unique times. Daily bars are
sent as 'YYYY-MM-DD' business-day strings (our bars are stamped 09:15 IST; the date is what matters).
NaN is not valid JSON: NaN points are dropped (a line simply starts once the indicator has warmed up).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


def day(ts: Any) -> str:
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


def clean(v: Any) -> Any:
    """Make a scalar JSON-safe: NaN/inf -> None, numpy -> python, timestamps -> ISO strings."""
    if v is None:
        return None
    if isinstance(v, np.bool_ | bool):
        return bool(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, float | np.floating):
        f = float(v)
        return f if math.isfinite(f) else None
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    return v


def deep_clean(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): deep_clean(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [deep_clean(v) for v in obj]
    return clean(obj)


def line(s: pd.Series, digits: int = 4) -> list[dict[str, Any]]:
    s = s.replace([np.inf, -np.inf], np.nan).dropna()
    out: dict[str, float] = {}
    for ts, v in s.items():
        out[day(ts)] = round(float(v), digits)  # duplicate days: last one wins (keeps times unique)
    return [{"time": t, "value": v} for t, v in out.items()]


def candles(df: pd.DataFrame) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for ts, r in df[["open", "high", "low", "close", "volume"]].iterrows():
        if any(pd.isna(r[c]) for c in ("open", "high", "low", "close")):
            continue
        rows[day(ts)] = {"time": day(ts), "open": round(float(r["open"]), 4), "high": round(float(r["high"]), 4),
                         "low": round(float(r["low"]), 4), "close": round(float(r["close"]), 4),
                         "volume": float(r["volume"]) if pd.notna(r["volume"]) else 0.0}
    return list(rows.values())


def records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    return [deep_clean(r) for r in df.to_dict("records")]
