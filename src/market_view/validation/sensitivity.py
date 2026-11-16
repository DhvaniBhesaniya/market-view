"""Parameter sensitivity: nudge each numeric parameter +/-10% and +/-20%.

A real edge shows a PLATEAU (neighbours also work). A curve-fit shows a SPIKE (only the exact
value works). Gate 3 requires neighbours within +/-20% to stay profitable.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from market_view.backtest import runner
from market_view.backtest.metrics import compute
from market_view.strategies import get_class, make

FACTORS = (0.8, 0.9, 1.0, 1.1, 1.2)


def nudged_values(base: int | float) -> list[tuple[float, int | float]]:
    """(factor, value) pairs around `base`. Floats: +/-10% and +/-20%. Integers: the same, but if rounding
    collapses them (e.g. 2 * 0.9 -> 2) use base-2..base+2 instead, so the parameter really moves."""
    if isinstance(base, int):
        vals = [max(1, round(base * f)) for f in FACTORS]
        if len(set(vals)) < len(FACTORS):
            vals = [max(1, base + d) for d in (-2, -1, 0, 1, 2)]
        uniq = list(dict.fromkeys(vals))
        return [(round(v / base, 3), v) for v in uniq]
    return [(f, round(base * f, 4)) for f in FACTORS]


def sensitivity(strategy_id: str, start: date, end: date, params: list[str] | None = None,
                symbols: list[str] | None = None) -> pd.DataFrame:
    defaults = get_class(strategy_id).defaults
    params = params or [k for k, v in defaults.items() if isinstance(v, int | float) and not isinstance(v, bool)]
    data, market = runner.load_inputs(start, end, symbols)
    rows = []
    for name in params:
        base = defaults[name]
        for f, val in nudged_values(base):
            try:
                strat = make(strategy_id, **{name: val})
            except ValueError:  # outside the allowed range (rule strategies validate their params)
                continue
            r = runner.run([strat], start, end, data=data, market=market)
            m = compute(r.equity, r.trades, r.benchmark)
            rows.append({"param": name, "factor": f, "value": val, "trades": m["trades"],
                         "return_pct": round(m["total_return_pct"], 2), "max_dd_pct": round(m["max_drawdown_pct"], 2),
                         "profit_factor": round(m["profit_factor"], 2), "expectancy_r": round(m["expectancy_r"], 3)})
    return pd.DataFrame(rows)


def plateau_check(df: pd.DataFrame) -> pd.DataFrame:
    """Per parameter: are ALL tested neighbours profitable (expectancy > 0)?"""
    return df.groupby("param").agg(
        all_profitable=("expectancy_r", lambda s: bool((s > 0).all())),
        min_expectancy_r=("expectancy_r", "min"), max_expectancy_r=("expectancy_r", "max"),
    ).reset_index()
