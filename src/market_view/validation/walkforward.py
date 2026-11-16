"""Walk-forward analysis: does the strategy keep working as market regimes change?

Mode 1 (fixed params): run each yearly test window separately -> how many windows profitable?
Mode 2 (with a param grid): for each window, pick the best params on the preceding train years,
then trade the next (unseen) year with them. The stitched out-of-sample result is what matters.
"""

from __future__ import annotations

import itertools
from datetime import date

import pandas as pd

from market_view.backtest import runner
from market_view.backtest.metrics import compute
from market_view.config import get_settings
from market_view.strategies import make


def _score(m: dict) -> float:
    # prefer expectancy, require a minimum sample
    return m["expectancy_r"] if m["trades"] >= 15 else -999.0


def walk_forward(strategy_id: str, grid: dict[str, list] | None = None, symbols: list[str] | None = None) -> pd.DataFrame:
    wf = get_settings().backtest.walkforward
    first_train = date(wf.first_test_year - wf.train_years, 1, 1)
    data, market = runner.load_inputs(first_train, date(wf.last_test_year + wf.test_years - 1, 12, 31), symbols)
    rows = []
    for year in range(wf.first_test_year, wf.last_test_year + 1, wf.test_years):
        test_start, test_end = date(year, 1, 1), date(year + wf.test_years - 1, 12, 31)
        params: dict = {}
        if grid:
            train_start, train_end = date(year - wf.train_years, 1, 1), date(year - 1, 12, 31)
            best, best_score = {}, -1e9
            keys = list(grid)
            for combo in itertools.product(*(grid[k] for k in keys)):
                cand = dict(zip(keys, combo, strict=True))
                r = runner.run([make(strategy_id, **cand)], train_start, train_end, data=data, market=market)
                sc = _score(compute(r.equity, r.trades, r.benchmark))
                if sc > best_score:
                    best, best_score = cand, sc
            params = best
        r = runner.run([make(strategy_id, **params)], test_start, test_end, data=data, market=market)
        m = compute(r.equity, r.trades, r.benchmark)
        rows.append({
            "test_window": f"{test_start.year}" + (f"-{test_end.year}" if wf.test_years > 1 else ""),
            "params": params or "default", "trades": m["trades"], "return_pct": round(m["total_return_pct"], 2),
            "max_dd_pct": round(m["max_drawdown_pct"], 2), "profit_factor": round(m["profit_factor"], 2),
            "expectancy_r": round(m["expectancy_r"], 3), "nifty_return_pct": round(m.get("benchmark_return_pct", float("nan")), 2),
        })
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    profitable = float((df["return_pct"] > 0).mean() * 100)
    beat = float((df["return_pct"] > df["nifty_return_pct"]).mean() * 100)
    return {
        "windows": len(df), "profitable_windows_pct": round(profitable, 1),
        "beat_nifty_windows_pct": round(beat, 1), "total_trades": int(df["trades"].sum()),
        "gate_3_walkforward_ok": bool(profitable >= 60),
    }
