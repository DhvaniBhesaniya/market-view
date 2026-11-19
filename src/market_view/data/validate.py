"""Data quality checks. Bad data silently produces fake backtest results."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class Issue:
    symbol: str
    kind: str
    ts: str
    detail: str


def validate(df: pd.DataFrame, symbol: str, jump_pct: float = 20.0, max_gap_days: int = 7) -> list[Issue]:
    issues: list[Issue] = []
    if df.empty:
        return [Issue(symbol, "empty", "", "no data")]

    def add(kind: str, mask: pd.Series, detail: str) -> None:
        for ts in df.index[mask.to_numpy()]:
            issues.append(Issue(symbol, kind, ts.isoformat(), detail))

    add("ohlc_inconsistent", (df["high"] < df[["open", "close", "low"]].max(axis=1)) |
        (df["low"] > df[["open", "close", "high"]].min(axis=1)), "high/low do not bound open/close")
    add("non_positive_price", (df[["open", "high", "low", "close"]] <= 0).any(axis=1), "price <= 0")
    add("zero_volume", df["volume"] <= 0, "volume is zero (holiday bar or bad data)")
    ret = df["close"].pct_change().abs() * 100
    add("price_jump", ret > jump_pct, f"close moved > {jump_pct}% in one bar (split/bonus not adjusted?)")
    if df.index.duplicated().any():
        add("duplicate_ts", pd.Series(df.index.duplicated(), index=df.index), "duplicate timestamp")
    gaps = df.index.to_series().diff().dt.days
    add("gap", gaps > max_gap_days, f"more than {max_gap_days} calendar days between bars")
    return issues
