"""Load data for a period (with indicator warm-up) and run the backtester."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

import pandas as pd

from market_view.backtest.engine import Backtester, BacktestResult
from market_view.config import DATA_DIR, IST, get_settings
from market_view.data import store
from market_view.market_context.regime import prepare_market
from market_view.strategies import Strategy, make


class TestPeriodLocked(RuntimeError):
    pass


def resolve_period(name: str, unlock_test: bool = False, strategy_ids: list[str] | None = None) -> tuple[date, date]:
    periods = get_settings().backtest.periods
    if name not in periods:
        raise KeyError(f"unknown period {name!r}; known: {sorted(periods)}")
    if name == "test":
        if not unlock_test:
            raise TestPeriodLocked(
                "The 2023-2025 test period is LOCKED. Run it once per strategy version, only after the "
                "Gate 3 checks pass on train/validate/walk-forward. Pass --unlock-test to proceed."
            )
        log = DATA_DIR / "test_period_log.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"at": datetime.now(IST).isoformat(), "strategies": strategy_ids}) + "\n")
    p = periods[name]
    end = date.fromisoformat(p.end) if p.end else datetime.now(IST).date()
    return date.fromisoformat(p.start), end


def test_runs_for(strategy_id: str) -> int:
    log = DATA_DIR / "test_period_log.jsonl"
    if not log.exists():
        return 0
    return sum(1 for line in log.read_text(encoding="utf-8").splitlines()
               if line.strip() and strategy_id in (json.loads(line).get("strategies") or []))


def load_inputs(start: date, end: date, symbols: list[str] | None = None, source: str | None = None,
                interval: str | None = None) -> tuple[dict[str, pd.DataFrame], pd.DataFrame | None]:
    s = get_settings()
    source = source or s.backtest.data_source
    interval = interval or s.backtest.interval
    warm_start = start - timedelta(days=int(s.backtest.warmup_days * 1.5))
    symbols = symbols or s.universe.all_symbols()
    data = store.load_many(symbols, interval, source, warm_start, end)
    nifty = store.load(s.backtest.benchmark, interval, source, warm_start, end)
    vix = store.load(s.backtest.volatility_index, interval, source, warm_start, end)
    market = prepare_market(nifty, vix) if not nifty.empty else None
    return data, market


def run(strategies: list[Strategy] | list[str], start: date, end: date, symbols: list[str] | None = None,
        capital: float | None = None, data: dict[str, pd.DataFrame] | None = None,
        market: pd.DataFrame | None = None, enforce_breakers: bool = False) -> BacktestResult:
    strats = [make(x) if isinstance(x, str) else x for x in strategies]
    if data is None:
        data, market = load_inputs(start, end, symbols)
    if not data:
        raise RuntimeError("No market data in the store. Run: uv run mv data download")
    bt = Backtester(strats, data, start, end, capital or get_settings().backtest.initial_capital, market=market,
                    enforce_breakers=enforce_breakers)
    return bt.run()
