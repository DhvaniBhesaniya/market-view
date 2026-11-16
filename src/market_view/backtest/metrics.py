"""Performance metrics. Judge strategies by expectancy, drawdown and sample size — NOT win rate."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from market_view.models import Trade

TRADING_DAYS = 252


def max_drawdown_pct(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    dd = equity / equity.cummax() - 1
    return float(dd.min() * 100)


def drawdown_series(equity: pd.Series) -> pd.Series:
    return (equity / equity.cummax() - 1) * 100


def cagr_pct(equity: pd.Series) -> float:
    if len(equity) < 2 or equity.iloc[0] <= 0:
        return 0.0
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    if years <= 0:
        return 0.0
    return float(((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1) * 100)


def sharpe(equity: pd.Series) -> float:
    r = equity.pct_change().dropna()
    if r.std() == 0 or len(r) < 2:
        return 0.0
    return float(r.mean() / r.std() * math.sqrt(TRADING_DAYS))


def sortino(equity: pd.Series) -> float:
    """Like Sharpe, but only punishes DOWNSIDE volatility: mean / downside deviation, where the
    downside deviation is sqrt(mean(min(r, 0)^2)) over ALL returns (the standard definition)."""
    r = equity.pct_change().dropna()
    if len(r) < 2:
        return 0.0
    dd = math.sqrt(float((r.clip(upper=0) ** 2).mean()))
    if dd == 0:
        return 0.0
    return float(r.mean() / dd * math.sqrt(TRADING_DAYS))


def max_consecutive(values: list[bool]) -> int:
    best = cur = 0
    for v in values:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def compute(equity: pd.Series, trades: list[Trade], benchmark: pd.Series | None = None) -> dict:
    m: dict = {}
    m["start"] = str(equity.index[0].date()) if not equity.empty else None
    m["end"] = str(equity.index[-1].date()) if not equity.empty else None
    m["initial_equity"] = float(equity.iloc[0]) if not equity.empty else 0.0
    m["final_equity"] = float(equity.iloc[-1]) if not equity.empty else 0.0
    m["total_return_pct"] = (m["final_equity"] / m["initial_equity"] - 1) * 100 if m["initial_equity"] else 0.0
    m["cagr_pct"] = cagr_pct(equity)
    m["max_drawdown_pct"] = max_drawdown_pct(equity)
    m["sharpe"] = sharpe(equity)
    m["sortino"] = sortino(equity)
    m["mar"] = m["cagr_pct"] / abs(m["max_drawdown_pct"]) if m["max_drawdown_pct"] else 0.0

    n = len(trades)
    m["trades"] = n
    pnl = np.array([t.net_pnl for t in trades]) if n else np.array([])
    rs = np.array([t.r_multiple for t in trades]) if n else np.array([])
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    m["win_rate_pct"] = float(len(wins) / n * 100) if n else 0.0
    m["avg_win"] = float(wins.mean()) if len(wins) else 0.0
    m["avg_loss"] = float(losses.mean()) if len(losses) else 0.0
    m["profit_factor"] = float(wins.sum() / -losses.sum()) if len(losses) and losses.sum() < 0 else (float("inf") if len(wins) else 0.0)
    m["expectancy_r"] = float(rs.mean()) if n else 0.0
    m["expectancy_rs"] = float(pnl.mean()) if n else 0.0
    m["best_trade"] = float(pnl.max()) if n else 0.0
    m["worst_trade"] = float(pnl.min()) if n else 0.0
    m["max_consecutive_losses"] = max_consecutive([p <= 0 for p in pnl])
    m["avg_bars_held"] = float(np.mean([t.bars_held for t in trades])) if n else 0.0
    m["total_charges"] = float(sum(t.charges for t in trades))
    m["charges_pct_of_gross_profit"] = (
        m["total_charges"] / sum(t.gross_pnl for t in trades if t.gross_pnl > 0) * 100
        if any(t.gross_pnl > 0 for t in trades) else 0.0
    )
    if n and not equity.empty:
        # % of trading days with at least one open position (overlapping trades counted once)
        days = pd.Series(False, index=equity.index.normalize().unique())
        for t in trades:
            days[(days.index >= pd.Timestamp(t.entry_time).normalize())
                 & (days.index <= pd.Timestamp(t.exit_time).normalize())] = True
        m["exposure_pct"] = float(days.mean() * 100)
    else:
        m["exposure_pct"] = 0.0
    m["exit_reasons"] = pd.Series([t.exit_reason for t in trades]).value_counts().to_dict() if n else {}

    if benchmark is not None and not benchmark.empty:
        m["benchmark_return_pct"] = float((benchmark.iloc[-1] / benchmark.iloc[0] - 1) * 100)
        m["benchmark_cagr_pct"] = cagr_pct(benchmark)
        m["benchmark_max_drawdown_pct"] = max_drawdown_pct(benchmark)
        m["benchmark_sharpe"] = sharpe(benchmark)
    m["warnings"] = sanity_warnings(m)
    return m


def sanity_warnings(m: dict) -> list[str]:
    """CLAUDE.md: when results look too good, assume a bug or bias first."""
    w = []
    if m["trades"] < 30:
        w.append(f"only {m['trades']} trades: too few to conclude anything (want >= 100)")
    elif m["trades"] < 100:
        w.append(f"{m['trades']} trades: below the 100-trade gate")
    if m["sharpe"] > 3:
        w.append("Sharpe > 3: suspicious - check look-ahead / costs / survivorship")
    if m["win_rate_pct"] > 75 and m["trades"] >= 30:
        w.append("win rate > 75%: check for look-ahead or tiny-win/huge-loss profile")
    if m["profit_factor"] != float("inf") and m["profit_factor"] > 3 and m["trades"] >= 30:
        w.append("profit factor > 3: suspicious")
    if m.get("benchmark_cagr_pct") is not None and m["cagr_pct"] < m["benchmark_cagr_pct"] and m["mar"] < (
        m["benchmark_cagr_pct"] / abs(m["benchmark_max_drawdown_pct"]) if m.get("benchmark_max_drawdown_pct") else 0
    ):
        w.append("does not beat NIFTY buy-and-hold on return OR risk-adjusted (MAR) basis")
    return w
