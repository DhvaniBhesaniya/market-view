"""Rule-based strategies: build a strategy from indicator conditions, without writing code (UI builder).

A `RuleSpec` is plain data, saved as YAML in config/custom_strategies/<name>_v<version>.yaml. It compiles
into an ordinary `Strategy` subclass, so it runs through the SAME backtester, risk engine and paper
trader as the hand-written strategies and obeys the same honesty rules:

  * every indicator in the catalogue is causal (bar t uses bars <= t only)
  * a signal on bar t's close is filled at bar t+1's open (the engine does this, not the strategy)
  * versions are immutable: saving an edited strategy creates a NEW version, never overwrites one
  * before a spec is saved it must pass a look-ahead self-check on synthetic data

Numeric knobs are flattened into `defaults` (e.g. `entry1_left_n`, `stop_value`) so walk-forward grids
and the +/-20% sensitivity test work on custom strategies too.
"""

from __future__ import annotations

import copy
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, Literal

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from market_view import indicators as ta
from market_view.config import CONFIG_DIR, IST
from market_view.strategies.base import Manage, PositionView, Strategy

# ============================================================================ indicator catalogue


@dataclass(frozen=True)
class Param:
    name: str
    default: float
    min: float
    max: float
    integer: bool = True
    label: str = ""


@dataclass(frozen=True)
class IndicatorDef:
    id: str
    label: str            # short name shown in the UI, e.g. "EMA"
    group: str            # Price | Trend | Momentum | Volatility | Volume
    placement: str        # "price": drawn over the candles | "pane": own pane below
    params: tuple[Param, ...]
    outputs: tuple[str, ...]
    explain: str          # one-paragraph teaching note shown in the UI
    compute: Callable[[pd.DataFrame, dict[str, Any]], dict[str, pd.Series]]
    levels: tuple[float, ...] = ()       # guide lines, e.g. RSI 30 / 70
    value_range: tuple[float, float] | None = None

    def defaults(self) -> dict[str, Any]:
        return {p.name: (int(p.default) if p.integer else float(p.default)) for p in self.params}


def _one(s: pd.Series) -> dict[str, pd.Series]:
    return {"value": s}


def _bb(df: pd.DataFrame, p: dict[str, Any]) -> dict[str, pd.Series]:
    lower, mid, upper = ta.bollinger(df["close"], p["n"], p["k"])
    return {"upper": upper, "mid": mid, "lower": lower}


def _donchian(df: pd.DataFrame, p: dict[str, Any]) -> dict[str, pd.Series]:
    return {"upper": ta.highest(df["high"], p["n"], exclude_current=True),
            "lower": ta.lowest(df["low"], p["n"], exclude_current=True)}


def _macd(df: pd.DataFrame, p: dict[str, Any]) -> dict[str, pd.Series]:
    line, sig, hist = ta.macd(df["close"], p["fast"], p["slow"], p["signal"])
    return {"macd": line, "signal": sig, "hist": hist}


_N = lambda d, lo=2, hi=400: Param("n", d, lo, hi, True, "period")  # noqa: E731

INDICATORS: dict[str, IndicatorDef] = {d.id: d for d in [
    IndicatorDef("close", "Close", "Price", "price", (), ("value",),
                 "The day's closing price. Signals are judged on the close and filled at the NEXT open.",
                 lambda df, p: _one(df["close"])),
    IndicatorDef("open", "Open", "Price", "price", (), ("value",), "The day's opening price.",
                 lambda df, p: _one(df["open"])),
    IndicatorDef("high", "High", "Price", "price", (), ("value",), "The day's highest traded price.",
                 lambda df, p: _one(df["high"])),
    IndicatorDef("low", "Low", "Price", "price", (), ("value",), "The day's lowest traded price.",
                 lambda df, p: _one(df["low"])),
    IndicatorDef("sma", "SMA", "Trend", "price", (_N(20),), ("value",),
                 "Simple moving average: the plain average of the last N closes. Price above a rising "
                 "SMA(200) is the classic definition of a long-term uptrend.",
                 lambda df, p: _one(ta.sma(df["close"], p["n"]))),
    IndicatorDef("ema", "EMA", "Trend", "price", (_N(20),), ("value",),
                 "Exponential moving average: like the SMA but recent days weigh more, so it turns "
                 "faster. EMA(20) above EMA(50) = short-term trend stronger than medium-term.",
                 lambda df, p: _one(ta.ema(df["close"], p["n"]))),
    IndicatorDef("bb", "Bollinger", "Volatility", "price",
                 (_N(20, 5, 200), Param("k", 2.0, 0.5, 4.0, False, "std devs")), ("upper", "mid", "lower"),
                 "Bollinger Bands: SMA(N) +/- k standard deviations. About 95% of closes fall inside "
                 "2-sigma bands, so a close below the lower band is statistically stretched.",
                 _bb),
    IndicatorDef("donchian", "Donchian", "Trend", "price", (_N(20, 2, 250),), ("upper", "lower"),
                 "Donchian channel: highest high / lowest low of the PREVIOUS N days (today excluded). "
                 "Close above the upper line = a fresh N-day breakout.",
                 _donchian),
    IndicatorDef("rsi", "RSI", "Momentum", "pane", (_N(14, 2, 100),), ("value",),
                 "Relative Strength Index (0-100): average gains vs average losses. Below 30 is often "
                 "called oversold, above 70 overbought. In strong uptrends RSI tends to stay 40-80.",
                 lambda df, p: _one(ta.rsi(df["close"], p["n"])), (30.0, 70.0), (0.0, 100.0)),
    IndicatorDef("macd", "MACD", "Momentum", "pane",
                 (Param("fast", 12, 2, 100, True), Param("slow", 26, 3, 200, True), Param("signal", 9, 2, 50, True)),
                 ("macd", "signal", "hist"),
                 "MACD = EMA(fast) - EMA(slow). It crossing above its signal line means momentum is "
                 "turning up; the histogram is the gap between them.",
                 _macd, (0.0,)),
    IndicatorDef("roc", "ROC %", "Momentum", "pane", (_N(10, 1, 250),), ("value",),
                 "Rate of change: % change of the close over N days. Positive = price higher than N days ago.",
                 lambda df, p: _one(ta.slope(df["close"], p["n"])), (0.0,)),
    IndicatorDef("ema_slope", "EMA slope %", "Trend", "pane",
                 (_N(50), Param("bars", 10, 1, 100, True, "over bars")), ("value",),
                 "% change of EMA(N) over the last `bars` days. Above 0 = the average itself is rising.",
                 lambda df, p: _one(ta.slope(ta.ema(df["close"], p["n"]), p["bars"])), (0.0,)),
    IndicatorDef("adx", "ADX", "Trend", "pane", (_N(14, 2, 100),), ("value",),
                 "Average Directional Index (0-100): trend STRENGTH, not direction. Below 20 = no trend "
                 "(range), above 25 = trending.",
                 lambda df, p: _one(ta.adx(df, p["n"])), (20.0, 25.0), (0.0, 100.0)),
    IndicatorDef("atr", "ATR", "Volatility", "pane", (_N(14, 2, 100),), ("value",),
                 "Average True Range: the typical size of one day's move in rupees, including gaps. "
                 "A 2xATR stop is 'two normal days' away from the entry.",
                 lambda df, p: _one(ta.atr(df, p["n"]))),
    IndicatorDef("atr_pct", "ATR %", "Volatility", "pane", (_N(14, 2, 100),), ("value",),
                 "ATR as % of the close, so volatility can be compared across stocks (Rs 100 vs Rs 5,000).",
                 lambda df, p: _one(ta.atr(df, p["n"]) / df["close"] * 100)),
    IndicatorDef("volume", "Volume", "Volume", "pane", (), ("value",), "Shares traded that day.",
                 lambda df, p: _one(df["volume"].astype(float))),
    IndicatorDef("volume_ratio", "Volume ratio", "Volume", "pane", (_N(20, 2, 250),), ("value",),
                 "Today's volume / average of the previous N days. 1.5 = 50% above normal: big players "
                 "are active, which makes breakouts more trustworthy.",
                 lambda df, p: _one(ta.volume_ratio(df["volume"], p["n"])), (1.0,)),
    IndicatorDef("close_location", "Close location", "Price", "pane", (), ("value",),
                 "Where the close sits in the day's range: 1 = closed at the high (buyers won the day), "
                 "0 = at the low.",
                 lambda df, p: _one(ta.close_location(df)), (0.5,), (0.0, 1.0)),
    IndicatorDef("turnover_cr", "Turnover Rs cr", "Volume", "pane", (_N(20, 2, 250),), ("value",),
                 "Average daily traded value in Rs crore. Liquidity: the risk engine rejects stocks "
                 "below the configured minimum.",
                 lambda df, p: _one(ta.avg_turnover_cr(df, p["n"]))),
]}


def compute_indicator(df: pd.DataFrame, ind: str, params: dict[str, Any] | None = None) -> dict[str, pd.Series]:
    """Compute one catalogue indicator with validated params (used by the chart API and strategies)."""
    d = INDICATORS[ind]
    p = _clean_params(d, params or {})
    return d.compute(df, p)


def _clean_params(d: IndicatorDef, params: dict[str, Any]) -> dict[str, Any]:
    unknown = set(params) - {p.name for p in d.params}
    if unknown:
        raise ValueError(f"{d.id}: unknown params {sorted(unknown)}")
    out: dict[str, Any] = {}
    for p in d.params:
        v = params.get(p.name, p.default)
        try:
            v = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"{d.id}.{p.name} must be a number, got {v!r}") from None
        if p.integer:
            if v != int(v):
                raise ValueError(f"{d.id}.{p.name} must be a whole number, got {v}")
            v = int(v)
        if not (p.min <= v <= p.max):
            raise ValueError(f"{d.id}.{p.name}={v} outside allowed range {p.min}..{p.max}")
        out[p.name] = v
    if d.id == "macd" and out["fast"] >= out["slow"]:
        raise ValueError("macd: fast period must be smaller than slow period")
    return out


# ============================================================================ spec models

Op = Literal[">", "<", ">=", "<=", "crosses_above", "crosses_below"]
OP_TEXT = {">": ">", "<": "<", ">=": ">=", "<=": "<=", "crosses_above": "crosses above",
           "crosses_below": "crosses below"}
BUILTIN_NAMES = {"trend", "breakout", "meanrev"}
NAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,30}$")


class Operand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["indicator", "value"]
    ind: str | None = None
    params: dict[str, float] = Field(default_factory=dict)
    output: str | None = None
    value: float | None = None

    @model_validator(mode="after")
    def _check(self) -> Operand:
        if self.kind == "value":
            if self.value is None or not np.isfinite(self.value):
                raise ValueError("a number operand needs a finite `value`")
            self.ind, self.params, self.output = None, {}, None
            return self
        if self.ind not in INDICATORS:
            raise ValueError(f"unknown indicator {self.ind!r}; known: {sorted(INDICATORS)}")
        d = INDICATORS[self.ind]
        self.params = _clean_params(d, self.params)
        self.output = self.output or d.outputs[0]
        if self.output not in d.outputs:
            raise ValueError(f"{d.id} has outputs {list(d.outputs)}, not {self.output!r}")
        self.value = None
        return self

    def label(self) -> str:
        if self.kind == "value":
            return f"{self.value:g}"
        d = INDICATORS[self.ind]  # type: ignore[index]
        args = ",".join(f"{v:g}" for v in self.params.values())
        base = f"{d.label}({args})" if args else d.label
        return base if len(d.outputs) == 1 else f"{base} {self.output}"


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    left: Operand
    op: Op
    right: Operand

    @model_validator(mode="after")
    def _check(self) -> Condition:
        if self.left.kind == "value":
            raise ValueError("the left side of a condition must be an indicator")
        return self

    def label(self) -> str:
        return f"{self.left.label()} {OP_TEXT[self.op]} {self.right.label()}"


class StopRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["atr", "percent", "swing_low"] = "atr"
    value: float = 2.0

    @model_validator(mode="after")
    def _check(self) -> StopRule:
        lo, hi = {"atr": (0.5, 6.0), "percent": (0.5, 25.0), "swing_low": (2, 60)}[self.type]
        if not lo <= self.value <= hi:
            raise ValueError(f"stop {self.type} value {self.value} outside {lo}..{hi}")
        if self.type == "swing_low":
            if self.value != int(self.value):
                raise ValueError("swing_low stop needs a whole number of bars")
            self.value = int(self.value)
        return self

    def label(self) -> str:
        return {"atr": f"{self.value:g} x ATR(14) below entry", "percent": f"{self.value:g}% below entry",
                "swing_low": f"lowest low of last {self.value:g} days"}[self.type]


class TargetRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["none", "r_multiple", "percent"] = "none"
    value: float | None = None

    @model_validator(mode="after")
    def _check(self) -> TargetRule:
        if self.type == "none":
            self.value = None
            return self
        lo, hi = {"r_multiple": (0.5, 10.0), "percent": (0.5, 100.0)}[self.type]
        if self.value is None or not lo <= self.value <= hi:
            raise ValueError(f"target {self.type} value {self.value} outside {lo}..{hi}")
        return self

    def label(self) -> str:
        return {"none": "none (exit by rules / trailing stop)", "r_multiple": f"{self.value:g}R",
                "percent": f"+{self.value:g}%"}[self.type]


class RuleSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    version: int = 1
    description: str = ""
    hypothesis: str = ""   # WHY should this work? (a testable belief, docs/06)
    entry: list[Condition] = Field(min_length=1, max_length=8)
    exit: list[Condition] = Field(default_factory=list, max_length=8)
    stop: StopRule = Field(default_factory=StopRule)
    target: TargetRule = Field(default_factory=TargetRule)
    time_stop_bars: int | None = Field(default=None, ge=1, le=250)
    trail_atr_mult: float | None = Field(default=None, ge=0.5, le=8.0)
    market_filter: bool = True    # only buy when NIFTY 50 is above its 50 EMA
    allowed_regimes: list[Literal["TREND_UP", "TREND_DOWN", "RANGE", "HIGH_VOL"]] | None = None
    created_at: str | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip().lower()
        if not NAME_RE.match(v):
            raise ValueError("use 3-31 lowercase letters, digits or _, starting with a letter")
        if re.search(r"_v\d+$", v):
            raise ValueError("must not end in _v<number>; the version is added automatically")
        if v in BUILTIN_NAMES:
            raise ValueError(f"{v!r} is a built-in strategy name")
        return v

    @property
    def id(self) -> str:
        return f"{self.name}_v{self.version}"

    def describe(self) -> str:
        parts = ["BUY when " + " AND ".join(c.label() for c in self.entry)]
        if self.market_filter:
            parts.append("only while NIFTY 50 is above its 50 EMA")
        if self.allowed_regimes:
            parts.append("regimes: " + ", ".join(self.allowed_regimes))
        parts.append("stop " + self.stop.label())
        if self.target.type != "none":
            parts.append("target " + self.target.label())
        if self.exit:
            parts.append("SELL when " + " OR ".join(c.label() for c in self.exit))
        if self.trail_atr_mult:
            parts.append(f"trail stop {self.trail_atr_mult:g} x ATR below the highest high")
        if self.time_stop_bars:
            parts.append(f"time stop {self.time_stop_bars} days")
        return "; ".join(parts)


# ============================================================================ flatten / apply params


def flatten(spec: RuleSpec) -> dict[str, Any]:
    """Numeric knobs as a flat dict: entry1_left_n, entry1_right_value, stop_value, ..."""
    out: dict[str, Any] = {}
    for group in ("entry", "exit"):
        for i, c in enumerate(getattr(spec, group), start=1):
            for side in ("left", "right"):
                o: Operand = getattr(c, side)
                if o.kind == "value":
                    out[f"{group}{i}_{side}_value"] = float(o.value)  # type: ignore[arg-type]
                else:
                    for k, v in o.params.items():
                        out[f"{group}{i}_{side}_{k}"] = v
    out["stop_value"] = spec.stop.value
    if spec.target.type != "none":
        out["target_value"] = float(spec.target.value)  # type: ignore[arg-type]
    if spec.time_stop_bars:
        out["time_stop_bars"] = int(spec.time_stop_bars)
    if spec.trail_atr_mult:
        out["trail_atr_mult"] = float(spec.trail_atr_mult)
    return out


_KEY_RE = re.compile(r"^(entry|exit)(\d+)_(left|right)_(\w+)$")


def apply_params(spec: RuleSpec, params: dict[str, Any]) -> RuleSpec:
    """Return a re-validated copy of `spec` with flattened params applied."""
    d = copy.deepcopy(spec.model_dump())
    for key, val in params.items():
        m = _KEY_RE.match(key)
        if m:
            group, idx, side, name = m.group(1), int(m.group(2)) - 1, m.group(3), m.group(4)
            operand = d[group][idx][side]
            if name == "value":
                operand["value"] = val
            else:
                operand["params"][name] = val
        elif key == "stop_value":
            d["stop"]["value"] = val
        elif key == "target_value":
            d["target"]["value"] = val
        elif key in ("time_stop_bars", "trail_atr_mult"):
            d[key] = val
        else:
            raise ValueError(f"unknown param {key!r}")
    return RuleSpec(**d)


# ============================================================================ the strategy


def _cross(a: pd.Series, b: pd.Series, up: bool) -> pd.Series:
    if up:
        return (a > b) & (a.shift(1) <= b.shift(1))
    return (a < b) & (a.shift(1) >= b.shift(1))


_OPS: dict[str, Callable[[pd.Series, pd.Series], pd.Series]] = {
    ">": lambda a, b: a > b, "<": lambda a, b: a < b, ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b,
    "crosses_above": lambda a, b: _cross(a, b, True), "crosses_below": lambda a, b: _cross(a, b, False),
}


class RuleStrategy(Strategy):
    """Base for compiled rule specs. Use `compile_spec(spec)` to get a concrete class."""

    base_spec: ClassVar[RuleSpec]

    def __init__(self, **overrides: Any) -> None:
        super().__init__(**overrides)
        self.spec = apply_params(self.base_spec, self.p) if overrides else self.base_spec

    def spec_dict(self) -> dict[str, Any]:
        return self.spec.model_dump(mode="json")

    def prepare(self, df: pd.DataFrame, market: pd.DataFrame | None) -> pd.DataFrame:
        out = self._join_market(self._common(df), market)
        cache: dict[tuple, dict[str, pd.Series]] = {}

        def series(o: Operand) -> pd.Series:
            if o.kind == "value":
                return pd.Series(float(o.value), index=df.index)  # type: ignore[arg-type]
            key = (o.ind, tuple(sorted(o.params.items())))
            if key not in cache:
                cache[key] = INDICATORS[o.ind].compute(df, dict(o.params))  # type: ignore[index]
            return cache[key][o.output]  # type: ignore[index]

        def masks(group: str) -> pd.Series:
            conds: list[Condition] = getattr(self.spec, group)
            combined = pd.Series(group == "entry", index=df.index)
            for i, c in enumerate(conds, start=1):
                a, b = series(c.left), series(c.right)
                out[f"{group}{i}_l"], out[f"{group}{i}_r"] = a, b
                m = _OPS[c.op](a, b).fillna(False).astype(bool)
                out[f"{group}{i}"] = m
                combined = (combined & m) if group == "entry" else (combined | m)
            return combined

        entry = masks("entry")
        if self.spec.market_filter:
            entry &= out["m_above50"].eq(True)
        out["entry"] = entry.fillna(False).astype(bool)
        out["exit_signal"] = masks("exit").astype(bool) if self.spec.exit else False

        close, s = df["close"], self.spec.stop
        if s.type == "atr":
            out["stop"] = close - s.value * out["atr"]
        elif s.type == "percent":
            out["stop"] = close * (1 - s.value / 100)
        else:
            out["stop"] = ta.lowest(df["low"], int(s.value))
        t = self.spec.target
        if t.type == "r_multiple":
            out["target"] = close + t.value * (close - out["stop"])  # type: ignore[operator]
        elif t.type == "percent":
            out["target"] = close * (1 + t.value / 100)  # type: ignore[operator]
        else:
            out["target"] = float("nan")
        out["confidence"] = 0.5
        return out

    def reasons(self, row: pd.Series) -> list[str]:
        def fmt(v: Any) -> str:
            return f"{float(v):,.2f}" if pd.notna(v) else "n/a"

        return [f"{c.label()}  ({fmt(row.get(f'entry{i}_l'))} vs {fmt(row.get(f'entry{i}_r'))})"
                for i, c in enumerate(self.spec.entry, start=1)]

    def manage(self, pos: PositionView, row: pd.Series) -> Manage:
        new_stop = None
        if self.spec.trail_atr_mult and pd.notna(row.get("atr")):
            new_stop = pos.highest_high - self.spec.trail_atr_mult * float(row["atr"])
        if self.spec.exit and bool(row.get("exit_signal", False)):
            hit = [c.label() for i, c in enumerate(self.spec.exit, start=1) if bool(row.get(f"exit{i}", False))]
            return Manage(new_stop=new_stop, exit_next_open=True, reason="exit rule: " + " / ".join(hit))
        if self.spec.time_stop_bars and pos.bars_held >= self.spec.time_stop_bars:
            return Manage(new_stop=new_stop, exit_next_open=True, reason=f"time stop {self.spec.time_stop_bars} bars")
        return Manage(new_stop=new_stop)


def _max_period(spec: RuleSpec) -> int:
    periods = [int(v) for c in spec.entry + spec.exit for o in (c.left, c.right) if o.kind == "indicator"
               for k, v in o.params.items() if k in ("n", "slow")]
    return max(periods, default=20)


def compile_spec(spec: RuleSpec) -> type[RuleStrategy]:
    return type(f"Rule_{spec.id}", (RuleStrategy,), {
        "name": spec.name, "version": spec.version, "description": spec.description or spec.describe(),
        "defaults": flatten(spec), "base_spec": spec, "warmup_bars": max(60, 2 * _max_period(spec)),
        "allowed_regimes": tuple(spec.allowed_regimes) if spec.allowed_regimes else None,
    })


# ============================================================================ look-ahead self-check


def _synthetic(n: int, seed: int, start_price: float) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = start_price * np.exp(np.cumsum(rng.normal(0.0004, 0.015, n)))
    open_ = np.r_[start_price, close[:-1]] * (1 + rng.normal(0, 0.003, n))
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.01, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.01, n))
    idx = pd.DatetimeIndex([pd.Timestamp(d.date(), tz=IST) + pd.Timedelta(hours=9, minutes=15)
                            for d in pd.bdate_range("2015-01-01", periods=n)], name="ts")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                         "volume": rng.integers(500_000, 3_000_000, n).astype(float)}, index=idx)


def lookahead_check(strategy: Strategy, n: int = 700) -> list[str]:
    """Values at bar t must not change when future bars are appended. Returns problems (empty = OK)."""
    from market_view.market_context.regime import prepare_market

    df, nifty, vix = _synthetic(n, 7, 1000.0), _synthetic(n, 3, 10_000.0), _synthetic(n, 5, 15.0)
    full = strategy.prepare(df, prepare_market(nifty, vix))
    cols = [c for c in ("entry", "stop", "target", "exit_signal") if c in full]
    problems = []
    for cut in (n // 2, int(n * 0.7), n - 30):
        part = strategy.prepare(df.iloc[:cut], prepare_market(nifty.iloc[:cut], vix.iloc[:cut]))
        for col in cols:
            a, b = full[col].iloc[cut - 1], part[col].iloc[-1]
            if pd.isna(a) and pd.isna(b):
                continue
            if isinstance(a, bool | np.bool_) or isinstance(b, bool | np.bool_):
                same = bool(a) == bool(b)
            else:
                same = bool(np.isclose(float(a), float(b), rtol=1e-9, equal_nan=True))
            if not same:
                problems.append(f"{col} at bar {cut - 1} changed when future bars were added ({b} -> {a})")
    return problems


# ============================================================================ storage (append-only versions)


def custom_dir() -> Path:
    return Path(os.environ.get("MARKET_VIEW_CUSTOM_STRATEGIES", CONFIG_DIR / "custom_strategies"))


def list_specs() -> list[RuleSpec]:
    d = custom_dir()
    if not d.exists():
        return []
    specs = []
    for path in sorted(d.glob("*.yaml")):
        with path.open(encoding="utf-8") as f:
            specs.append(RuleSpec(**yaml.safe_load(f)))
    return sorted(specs, key=lambda s: (s.name, s.version))


def custom_classes() -> dict[str, type[Strategy]]:
    return {s.id: compile_spec(s) for s in list_specs()}


def next_version(name: str) -> int:
    return max((s.version for s in list_specs() if s.name == name), default=0) + 1


def save_spec(spec: RuleSpec) -> RuleSpec:
    """Validate, self-test for look-ahead, then write a NEW immutable version. Never overwrites."""
    spec = RuleSpec(**{**spec.model_dump(), "version": next_version(spec.name),
                       "created_at": datetime.now(IST).isoformat(timespec="seconds")})
    problems = lookahead_check(compile_spec(spec)())
    if problems:
        raise ValueError("look-ahead self-check failed: " + "; ".join(problems))
    d = custom_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{spec.id}.yaml"
    header = (f"# Custom rule strategy {spec.id} (created {spec.created_at}). Versions are immutable:\n"
              f"# edit in the UI to create {spec.name}_v{spec.version + 1}. {spec.describe()}\n")
    with path.open("x", encoding="utf-8") as f:   # "x" = fail if the file exists
        f.write(header)
        yaml.safe_dump(spec.model_dump(mode="json"), f, sort_keys=False, allow_unicode=True)
    return spec
