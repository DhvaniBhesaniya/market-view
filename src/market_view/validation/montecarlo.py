"""Monte Carlo on trade outcomes ("time machine" for a whole strategy).

The backtest gives ONE order of trades. Reality could deliver the same trades in a different order.
Resampling the R-multiples thousands of times shows the RANGE of drawdowns and returns to expect —
so a 15% drawdown in live trading is recognised as "within the 90th percentile" instead of panic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from market_view.models import Trade


def simulate(trades: list[Trade] | list[float], risk_pct: float = 0.25, runs: int = 1000,
             n_trades: int | None = None, seed: int = 42) -> dict:
    """Bootstrap R-multiples (with replacement) under fixed-fractional sizing."""
    rs = np.array([t.r_multiple if isinstance(t, Trade) else float(t) for t in trades])
    if len(rs) < 10:
        return {"error": f"need >= 10 trades, have {len(rs)}"}
    rng = np.random.default_rng(seed)
    n = n_trades or len(rs)
    samples = rng.choice(rs, size=(runs, n), replace=True)
    growth = 1 + samples * risk_pct / 100
    equity = np.cumprod(growth, axis=1)
    peaks = np.maximum.accumulate(np.concatenate([np.ones((runs, 1)), equity], axis=1), axis=1)[:, 1:]
    max_dd = ((equity / peaks) - 1).min(axis=1) * 100
    final = (equity[:, -1] - 1) * 100
    losing_streak = np.array([_max_streak(row < 0) for row in samples])

    def pct(a: np.ndarray, q: float) -> float:
        return round(float(np.percentile(a, q)), 2)

    return {
        "trades_sampled": n, "runs": runs, "risk_pct_per_trade": risk_pct,
        "final_return_pct": {"p5": pct(final, 5), "p50": pct(final, 50), "p95": pct(final, 95)},
        "max_drawdown_pct": {"p50": pct(max_dd, 50), "p90": pct(max_dd, 10), "p95": pct(max_dd, 5), "worst": pct(max_dd, 0)},
        "longest_losing_streak": {"p50": int(np.percentile(losing_streak, 50)), "p95": int(np.percentile(losing_streak, 95))},
        "prob_loss_pct": round(float((final < 0).mean() * 100), 1),
    }


def fan(trades: list[Trade] | list[float], risk_pct: float = 0.25, runs: int = 1000, seed: int = 42,
        points: int = 60) -> dict:
    """Percentile bands of equity (% return) after each trade: the 'cone' of plausible futures.
    p5..p95 = 90% of reshuffled histories ended inside the band. Same bootstrap as `simulate`."""
    rs = np.array([t.r_multiple if isinstance(t, Trade) else float(t) for t in trades])
    if len(rs) < 10:
        return {"error": f"need >= 10 trades, have {len(rs)}"}
    rng = np.random.default_rng(seed)
    samples = rng.choice(rs, size=(runs, len(rs)), replace=True)
    equity = (np.cumprod(1 + samples * risk_pct / 100, axis=1) - 1) * 100
    idx = np.unique(np.linspace(0, len(rs) - 1, min(points, len(rs))).round().astype(int))
    actual = (np.cumprod(1 + rs * risk_pct / 100) - 1) * 100
    band = {f"p{q}": [round(float(v), 2) for v in np.percentile(equity[:, idx], q, axis=0)] for q in (5, 25, 50, 75, 95)}
    return {"trade_no": [int(i) + 1 for i in idx], **band, "actual": [round(float(actual[i]), 2) for i in idx],
            "r_histogram": _histogram(rs)}


def _histogram(rs: np.ndarray, bins: int = 24) -> list[dict]:
    lo, hi = float(np.floor(rs.min())), float(np.ceil(rs.max()))
    if hi <= lo:
        hi = lo + 1
    counts, edges = np.histogram(rs, bins=bins, range=(lo, hi))
    return [{"from": round(float(edges[i]), 2), "to": round(float(edges[i + 1]), 2), "count": int(c)}
            for i, c in enumerate(counts)]


def _max_streak(mask: np.ndarray) -> int:
    best = cur = 0
    for v in mask:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def setup_history(trades: list[Trade], symbol: str | None = None) -> pd.DataFrame:
    """'Every past time this setup fired' — the honest companion to any single-trade forecast."""
    df = pd.DataFrame([t.model_dump() for t in trades])
    if df.empty:
        return df
    if symbol:
        df = df[df["symbol"] == symbol]
    return df[["symbol", "entry_time", "exit_time", "r_multiple", "net_pnl", "exit_reason", "bars_held"]]
