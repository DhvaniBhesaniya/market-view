"""Backtest reports (HTML + JSON) and the experiment log (never overwritten)."""

from __future__ import annotations

import json
import subprocess
import threading
from datetime import datetime
from pathlib import Path

import pandas as pd

from market_view.backtest.engine import BacktestResult
from market_view.backtest.metrics import compute, drawdown_series
from market_view.config import DATA_DIR, IST, REPORTS_DIR, ROOT

_LOG_LOCK = threading.Lock()


def git_sha() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                             text=True, timeout=5)
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "src", "config"], cwd=ROOT,
                               capture_output=True, text=True, timeout=5).stdout.strip()
        return (out.stdout.strip() or "nogit") + ("-dirty" if dirty else "")
    except Exception:
        return "nogit"


def save(result: BacktestResult, label: str, period: str) -> tuple[str, dict, Path]:
    metrics = compute(result.equity, result.trades, result.benchmark)
    metrics["breaker_events"] = len(result.events)
    base_id = f"{datetime.now(IST):%Y%m%d-%H%M%S}-{label}-{period}"
    (REPORTS_DIR / "backtests").mkdir(parents=True, exist_ok=True)
    with _LOG_LOCK:  # never reuse a run directory (two UI jobs can finish in the same second)
        run_id, n = base_id, 1
        while (REPORTS_DIR / "backtests" / run_id).exists():
            n += 1
            run_id = f"{base_id}-{n}"
        out = REPORTS_DIR / "backtests" / run_id
        out.mkdir()

    record = {"run_id": run_id, "label": label, "period": period, "git": git_sha(),
              "params": result.params, "metrics": metrics, "events": result.events}
    (out / "result.json").write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    result.trades_df().to_csv(out / "trades.csv", index=False)
    result.equity.to_csv(out / "equity.csv")
    if result.benchmark is not None:
        result.benchmark.to_csv(out / "benchmark.csv")
    if not result.signals.empty:
        result.signals.to_csv(out / "signals.csv", index=False)
    _html(result, metrics, out / "report.html", run_id)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _LOG_LOCK, (DATA_DIR / "experiments.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({k: v for k, v in record.items() if k != "events"}, default=str) + "\n")
    return run_id, metrics, out


def _html(result: BacktestResult, m: dict, path: Path, title: str) -> None:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.04,
                        subplot_titles=("Equity vs NIFTY 50 buy-and-hold", "Drawdown %"))
    fig.add_trace(go.Scatter(x=result.equity.index, y=result.equity, name="Strategy"), row=1, col=1)
    if result.benchmark is not None:
        fig.add_trace(go.Scatter(x=result.benchmark.index, y=result.benchmark, name="NIFTY 50",
                                 line={"dash": "dot"}), row=1, col=1)
    fig.add_trace(go.Scatter(x=result.equity.index, y=drawdown_series(result.equity), name="Drawdown",
                             fill="tozeroy", line={"color": "#c0392b"}), row=2, col=1)
    fig.update_layout(height=700, title=title, template="plotly_white")

    rows = "".join(
        f"<tr><td>{k}</td><td>{v:,.2f}</td></tr>" if isinstance(v, float) else f"<tr><td>{k}</td><td>{v}</td></tr>"
        for k, v in m.items() if k not in ("warnings", "exit_reasons")
    )
    warn = "".join(f"<li>{w}</li>" for w in m["warnings"]) or "<li>none</li>"
    trades = result.trades_df().drop(columns=["reasons", "context"], errors="ignore")
    num = trades.select_dtypes("number").columns
    trades[num] = trades[num].round(2)
    trades_html = trades.to_html(index=False) if not trades.empty else "<p>No trades.</p>"
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>{title}</title>
<style>body{{font-family:system-ui,sans-serif;margin:24px;max-width:1200px}}table{{border-collapse:collapse;font-size:13px}}
td,th{{border:1px solid #ddd;padding:4px 8px}}.warn{{background:#fff4e5;padding:8px 16px;border-left:4px solid #e67e22}}</style></head>
<body><h2>{title}</h2>
<p><b>Not a promise of profit.</b> Simulated results, including Indian charges and slippage. Past performance does not predict the future.</p>
<div class="warn"><b>Sanity warnings</b><ul>{warn}</ul></div>
{fig.to_html(full_html=False, include_plotlyjs="cdn")}
<h3>Metrics</h3><table>{rows}</table>
<h3>Exit reasons</h3><pre>{json.dumps(m['exit_reasons'], indent=1)}</pre>
<h3>Events</h3><pre>{chr(10).join(result.events) or 'none'}</pre>
<h3>Trades</h3>{trades_html}</body></html>"""
    path.write_text(html, encoding="utf-8")


def load_experiments() -> pd.DataFrame:
    path = DATA_DIR / "experiments.jsonl"
    if not path.exists():
        return pd.DataFrame()
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    flat = [{"run_id": r["run_id"], "label": r["label"], "period": r["period"], "git": r["git"], **{
        k: r["metrics"].get(k) for k in ("trades", "cagr_pct", "max_drawdown_pct", "sharpe", "profit_factor",
                                          "expectancy_r", "win_rate_pct", "benchmark_cagr_pct")}} for r in rows]
    return pd.DataFrame(flat)
