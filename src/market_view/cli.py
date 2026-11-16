"""market-view command line.  Run `uv run mv --help`."""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta

import typer
from rich.console import Console
from rich.table import Table

from market_view.config import env, get_settings

app = typer.Typer(help="market-view: NSE research, backtesting and paper trading. Paper mode by default.",
                  no_args_is_help=True)
data_app = typer.Typer(help="Download / validate market data", no_args_is_help=True)
universe_app = typer.Typer(help="Trading universe", no_args_is_help=True)
bt_app = typer.Typer(help="Backtests", no_args_is_help=True)
val_app = typer.Typer(help="Validation: walk-forward, Monte Carlo, sensitivity", no_args_is_help=True)
paper_app = typer.Typer(help="Paper trading", no_args_is_help=True)
risk_app = typer.Typer(help="Risk & kill switch", no_args_is_help=True)
upstox_app = typer.Typer(help="Upstox API connection (market data)", no_args_is_help=True)
journal_app = typer.Typer(help="Trade journal", no_args_is_help=True)
for name, sub in [("data", data_app), ("universe", universe_app), ("backtest", bt_app), ("validate", val_app),
                  ("paper", paper_app), ("risk", risk_app), ("upstox", upstox_app), ("journal", journal_app)]:
    app.add_typer(sub, name=name)

console = Console()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _table(rows: list[dict], title: str = "") -> None:
    if not rows:
        console.print(f"[dim]{title}: nothing[/dim]")
        return
    t = Table(title=title)
    for k in rows[0]:
        t.add_column(str(k))
    for r in rows:
        t.add_row(*[f"{v:,.2f}" if isinstance(v, float) else str(v) for v in r.values()])
    console.print(t)


def _parse_symbols(symbols: str | None) -> list[str] | None:
    return [s.strip().upper() for s in symbols.split(",")] if symbols else None


# ---------------------------------------------------------------- data
@data_app.command("download")
def data_download(
    start: str = typer.Option("2008-01-01", help="YYYY-MM-DD"),
    end: str = typer.Option(None, help="YYYY-MM-DD (default today)"),
    interval: str = typer.Option("1d"),
    source: str = typer.Option("auto", help="auto | yfinance | upstox"),
    symbols: str = typer.Option(None, help="comma list; default = universe + indices"),
):
    """Download history into data/ (append-only)."""
    from market_view.data.download import default_symbols, download

    syms = _parse_symbols(symbols) or default_symbols()
    end_d = date.fromisoformat(end) if end else date.today()
    console.print(f"Downloading {len(syms)} symbols {interval} {start}..{end_d} via {source}")
    counts = download(syms, interval, date.fromisoformat(start), end_d, source,
                      progress=lambda s, msg: console.print(f"  {s:12s} {msg}"))
    failed = [s for s, n in counts.items() if n < 0]
    console.print(f"[green]done[/green]: {sum(1 for n in counts.values() if n > 0)} ok, {len(failed)} failed {failed or ''}")


@data_app.command("validate")
def data_validate(source: str = "yfinance", interval: str = "1d"):
    """Check stored data for gaps, bad OHLC, unadjusted splits, duplicates."""
    from market_view.data import store
    from market_view.data.validate import validate

    indices = set(get_settings().universe.indices)
    all_issues = []
    for sym in store.available(source, interval):
        issues = validate(store.load(sym, interval, source), sym)
        if sym in indices:  # indices have no volume and VIX jumps 20%+ routinely
            issues = [i for i in issues if i.kind not in ("zero_volume", "price_jump")]
        all_issues += issues
    by_kind: dict[str, int] = {}
    for i in all_issues:
        by_kind[i.kind] = by_kind.get(i.kind, 0) + 1
    _table([{"kind": k, "count": v} for k, v in sorted(by_kind.items())], "Data issues")
    _table([i.__dict__ for i in all_issues if i.kind in ("price_jump", "ohlc_inconsistent", "duplicate_ts")][:40],
           "Issues needing review (first 40)")


@data_app.command("list")
def data_list(source: str = "yfinance", interval: str = "1d"):
    from market_view.data import store

    rows = []
    for sym in store.available(source, interval):
        df = store.load(sym, interval, source)
        rows.append({"symbol": sym, "bars": len(df), "from": df.index[0].date(), "to": df.index[-1].date()})
    _table(rows, f"Stored data ({source}, {interval})")


# ---------------------------------------------------------------- universe
@universe_app.command("show")
def universe_show():
    u = get_settings().universe
    _table([{"symbol": s, "sector": i.sector, "isin": i.isin} for s, i in u.symbols.items()], f"{u.name} ({u.fetched})")


@universe_app.command("refresh")
def universe_refresh():
    """Update config/universe.yaml from NSE's official NIFTY 50 list."""
    from market_view.data.download import refresh_nifty50

    added, removed = refresh_nifty50()
    console.print(f"added: {added or 'none'}  removed (moved to former_members): {removed or 'none'}")


# ---------------------------------------------------------------- backtest
@bt_app.command("run")
def backtest_run(
    strategy: str = typer.Option("all", help="strategy id (trend_v1, breakout_v1, meanrev_v1) or 'all' (portfolio)"),
    period: str = typer.Option("validate", help="train | validate | full | test | forward"),
    symbols: str = typer.Option(None, help="comma list; default = universe"),
    unlock_test: bool = typer.Option(False, "--unlock-test", help="allow the LOCKED test period (once per version)"),
    enforce_breakers: bool = typer.Option(False, "--enforce-breakers",
                                          help="halt strategies exactly like live (default: record 'WOULD' events)"),
):
    """Run an event-driven backtest with Indian costs. Writes reports/backtests/<run_id>/report.html."""
    from market_view.backtest import report, runner
    from market_view.strategies import enabled, make

    strats = enabled() if strategy == "all" else [make(strategy)]
    ids = [s.id for s in strats]
    if period == "test":
        prior = {i: runner.test_runs_for(i) for i in ids}
        if any(prior.values()):
            console.print(f"[bold red]WARNING[/bold red]: test period already run for {prior}. Re-running and "
                          "re-tuning on it turns it into training data.")
    start, end = runner.resolve_period(period, unlock_test, ids)
    console.print(f"Backtesting {ids} on {period} {start}..{end}")
    result = runner.run(strats, start, end, _parse_symbols(symbols), enforce_breakers=enforce_breakers)
    run_id, m, out = report.save(result, "+".join(ids), period)
    _print_metrics(m)
    console.print(f"Report: [link]{out / 'report.html'}[/link]")


def _print_metrics(m: dict) -> None:
    keys = ["trades", "total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "sortino", "mar", "win_rate_pct",
            "profit_factor", "expectancy_r", "avg_win", "avg_loss", "max_consecutive_losses", "total_charges",
            "charges_pct_of_gross_profit", "exposure_pct", "breaker_events", "benchmark_return_pct",
            "benchmark_cagr_pct", "benchmark_max_drawdown_pct"]
    _table([{"metric": k, "value": m.get(k)} for k in keys if k in m], f"{m.get('start')} .. {m.get('end')}")
    for w in m.get("warnings", []):
        console.print(f"[yellow]! {w}[/yellow]")


@bt_app.command("experiments")
def backtest_experiments(last: int = 20):
    """List past backtest runs (the experiment log)."""
    from market_view.backtest.report import load_experiments

    df = load_experiments()
    _table(df.tail(last).round(3).to_dict("records") if not df.empty else [], "Experiments")


# ---------------------------------------------------------------- validation
@val_app.command("walkforward")
def validate_walkforward(strategy: str, grid: str = typer.Option(None, help='JSON e.g. {"stop_atr":[1.5,2,2.5]}'),
                         symbols: str = None):
    """Year-by-year out-of-sample test windows (never touches the locked test period)."""
    from market_view.validation.walkforward import summarize, walk_forward

    df = walk_forward(strategy, json.loads(grid) if grid else None, _parse_symbols(symbols))
    _table(df.astype(str).to_dict("records"), f"Walk-forward {strategy}")
    console.print(summarize(df))


@val_app.command("montecarlo")
def validate_montecarlo(strategy: str, period: str = "full", risk_pct: float = None, symbols: str = None):
    """Shuffle/bootstraps trade outcomes to show the RANGE of drawdowns to expect."""
    from market_view.backtest import runner
    from market_view.validation.montecarlo import simulate

    s = get_settings()
    start, end = runner.resolve_period(period)
    result = runner.run([strategy], start, end, _parse_symbols(symbols))
    mc = s.backtest.montecarlo
    console.print_json(data=simulate(result.trades, risk_pct or s.risk.risk_per_trade_pct, mc.runs, seed=mc.seed))


@val_app.command("sensitivity")
def validate_sensitivity(strategy: str, period: str = "full", params: str = None, symbols: str = None):
    """Nudge each parameter +/-10/20%: looking for a plateau, not a spike."""
    from market_view.backtest import runner
    from market_view.validation.sensitivity import plateau_check, sensitivity

    start, end = runner.resolve_period(period)
    df = sensitivity(strategy, start, end, params.split(",") if params else None, _parse_symbols(symbols))
    _table(df.astype(str).to_dict("records"), f"Sensitivity {strategy}")
    _table(plateau_check(df).astype(str).to_dict("records"), "Plateau check")


# ---------------------------------------------------------------- paper
def _trader():
    from market_view.paper.trader import PaperTrader

    return PaperTrader()


@paper_app.command("eod")
def paper_eod(no_update: bool = typer.Option(False, "--no-update", help="skip data download")):
    """After close: update data, manage positions, create tomorrow's signals."""
    console.print_json(data=_trader().eod(update_data=not no_update))


@paper_app.command("open")
def paper_open():
    """At open: execute pending exits, then entries (with broker-side stops)."""
    console.print_json(data=_trader().open_job())


@paper_app.command("monitor")
def paper_monitor():
    """During session: check stops/targets, scale-outs, kill-switch conditions."""
    console.print_json(data=_trader().monitor())


@paper_app.command("run")
def paper_run():
    """Run the scheduler loop (open / monitor / eod at configured IST times). Ctrl+C to stop."""
    _trader().run_forever()


@paper_app.command("status")
def paper_status():
    st = _trader().status()
    positions = st.pop("positions")
    console.print_json(data=st)
    _table([{"symbol": s, **p} for s, p in positions.items()], "Open positions")


@paper_app.command("reconcile")
def paper_reconcile():
    issues = _trader().reconcile()
    console.print("[green]reconciled: OK[/green]" if not issues else f"[red]{issues}[/red]")


@paper_app.command("reset")
def paper_reset(confirm: bool = typer.Option(False, "--yes", help="really delete paper account state")):
    """Start a fresh paper account (journal history is kept)."""
    from market_view.config import DATA_DIR

    if not confirm:
        console.print("Add --yes to delete data/paper/broker.json and trader.json (journal is kept).")
        raise typer.Exit(1)
    for f in ("broker.json", "trader.json"):
        (DATA_DIR / "paper" / f).unlink(missing_ok=True)
    console.print("paper account reset")


# ---------------------------------------------------------------- risk
@risk_app.command("killswitch")
def risk_killswitch(action: str = typer.Argument("status", help="status | on | off"),
                    reason: str = typer.Option("manual", help="reason (on) or note (off, >= 10 chars)")):
    from market_view.risk.killswitch import KillSwitch

    ks = KillSwitch()
    if action == "on":
        ks.trigger(reason, "manual")
    elif action == "off":
        ks.reset(reason)
    console.print_json(data={k: v for k, v in ks.status().items() if k != "history"})


@risk_app.command("size")
def risk_size(entry: float, stop: float, equity: float = None, risk_pct: float = None):
    """Position size calculator: how many shares for this entry/stop?"""
    from market_view.costs import CostModel
    from market_view.risk.engine import position_size

    s = get_settings()
    equity = equity or s.paper.initial_capital
    risk_pct = risk_pct or s.risk.risk_per_trade_pct
    qty = position_size(equity, risk_pct, entry, stop)
    cost = CostModel().round_trip(entry, entry + 2 * (entry - stop), qty)
    console.print(f"risk Rs {equity * risk_pct / 100:,.0f} / {entry - stop:.2f} per share = [bold]{qty} shares[/bold] "
                  f"(Rs {qty * entry:,.0f}, {qty * entry / equity * 100:.1f}% of equity). "
                  f"Round-trip charges at a 2R exit ~ Rs {cost:,.0f}")


# ---------------------------------------------------------------- upstox
@upstox_app.command("check")
def upstox_check():
    """Verify UPSTOX_ACCESS_TOKEN works (fetches NIFTY 50 LTP)."""
    from market_view.data.sources.upstox_source import UpstoxSource

    console.print_json(data=UpstoxSource().check())


@upstox_app.command("login-url")
def upstox_login_url():
    """Daily OAuth flow step 1 (not needed with an Analytics token)."""
    from market_view.data.sources.upstox_source import login_url

    console.print(login_url())


@upstox_app.command("exchange-code")
def upstox_exchange_code(code: str):
    """Daily OAuth flow step 2: paste the ?code= value; prints a token to put in .env (valid until 03:30 IST)."""
    from market_view.data.sources.upstox_source import exchange_code

    token = exchange_code(code)
    console.print("Put this in .env as UPSTOX_ACCESS_TOKEN (never commit it):")
    console.print(token)


# ---------------------------------------------------------------- journal
@journal_app.command("trades")
def journal_trades(last: int = 30):
    from market_view.journal import Journal

    df = Journal().query(f"SELECT symbol, strategy_id, entry_time, exit_time, qty, round(net_pnl,0) pnl, "
                         f"round(r_multiple,2) r, exit_reason FROM trades ORDER BY exit_time DESC LIMIT {int(last)}")
    _table(df.astype(str).to_dict("records"), "Closed trades")


@journal_app.command("signals")
def journal_signals(last: int = 30):
    from market_view.journal import Journal

    df = Journal().query(f"SELECT ts, stage, strategy_id, symbol, approved, qty, reasons FROM signals "
                         f"ORDER BY ts DESC LIMIT {int(last)}")
    _table(df.astype(str).to_dict("records"), "Signals & risk decisions")


@journal_app.command("weekly")
def journal_weekly():
    """Weekly review numbers (docs/05 section 7)."""
    from market_view.journal import Journal

    j = Journal()
    since = (date.today() - timedelta(days=7)).isoformat()
    df = j.query(f"SELECT strategy_id, count(*) trades, round(sum(net_pnl),0) pnl, round(avg(r_multiple),2) avg_r, "
                 f"round(100.0*avg(CASE WHEN net_pnl>0 THEN 1 ELSE 0 END),1) win_pct, round(avg(mae_pct),2) avg_mae, "
                 f"round(avg(mfe_pct),2) avg_mfe FROM trades WHERE exit_time >= '{since}' GROUP BY 1")
    _table(df.astype(str).to_dict("records"), f"Week since {since}")
    rej = j.query(f"SELECT reasons, count(*) n FROM signals WHERE approved = false AND ts >= '{since}' "
                  f"GROUP BY 1 ORDER BY n DESC LIMIT 10")
    _table(rej.astype(str).to_dict("records"), "Top rejection reasons")


# ---------------------------------------------------------------- ui
@app.command()
def ui(port: int = typer.Option(8000, help="local port"),
       open_browser: bool = typer.Option(True, "--open/--no-open", help="open the browser"),
       reload: bool = typer.Option(False, "--reload", help="auto-reload on code changes (development)")):
    """Start the web UI at http://127.0.0.1:<port> (localhost only; it has no order endpoints)."""
    import threading
    import webbrowser

    import uvicorn

    from market_view.api.app import STATIC_DIR

    url = f"http://127.0.0.1:{port}"
    if not STATIC_DIR.exists():
        console.print("[yellow]UI not built yet[/yellow]: run `cd frontend; npm install; npm run build` "
                      f"(the API alone is at {url}/docs)")
    console.print(f"market-view UI: [link]{url}[/link]   (Ctrl+C to stop)")
    if open_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run("market_view.api.app:app", host="127.0.0.1", port=port, reload=reload, log_level="warning")


# ---------------------------------------------------------------- doctor
@app.command()
def doctor():
    """Check setup: config, data, tokens, safety switches."""
    from market_view.data import store
    from market_view.risk.killswitch import KillSwitch

    s = get_settings()
    rows = [
        {"check": "LIVE_TRADING", "value": env("LIVE_TRADING", "false"),
         "ok": env("LIVE_TRADING", "false").lower() != "true"},
        {"check": "risk per trade %", "value": s.risk.risk_per_trade_pct, "ok": s.risk.risk_per_trade_pct <= 0.5},
        {"check": "universe symbols", "value": len(s.universe.symbols), "ok": len(s.universe.symbols) > 0},
        {"check": "yfinance daily data stored", "value": len(store.available("yfinance", "1d")),
         "ok": len(store.available("yfinance", "1d")) > 0},
        {"check": "upstox daily data stored", "value": len(store.available("upstox", "1d")), "ok": True},
        {"check": "UPSTOX_ACCESS_TOKEN set", "value": bool(env("UPSTOX_ACCESS_TOKEN")), "ok": True},
        {"check": "kill switch active", "value": KillSwitch().active, "ok": not KillSwitch().active},
    ]
    _table(rows, "market-view doctor")


if __name__ == "__main__":
    app()
