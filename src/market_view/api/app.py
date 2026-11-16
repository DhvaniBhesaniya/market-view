"""market-view local web API (FastAPI). Start with `uv run mv ui`.

SAFETY (CLAUDE.md rules 1-3):
  * There is NO order endpoint here: not live, not paper. The UI can read research and paper state, run
    backtests and validations, save rule strategies, and switch the kill switch ON (or OFF with a written
    note). Orders only ever come from the paper trader's own jobs.
  * It binds to 127.0.0.1 only and rejects foreign Host headers (DNS-rebinding protection), so other
    machines and random web pages cannot drive it.
  * The locked 2023-2025 test period cannot be run from the UI (CLI only, deliberately).
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

import pandas as pd
from fastapi import APIRouter, Body, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from market_view.api import serialize as ser
from market_view.api.jobs import JobManager
from market_view.config import DATA_DIR, IST, REPORTS_DIR, ROOT, env, get_settings

STATIC_DIR = ROOT / "frontend" / "dist"
UI_PERIODS = ("train", "validate", "full", "forward")  # "test" is locked: CLI only
RUN_ID_RE = re.compile(r"^[\w\-+.&]+$")

jobs = JobManager()
api = APIRouter(prefix="/api")


def _source() -> str:
    return get_settings().backtest.data_source


def _bad(msg: str, code: int = status.HTTP_422_UNPROCESSABLE_CONTENT) -> HTTPException:
    return HTTPException(status_code=code, detail=msg)


def _pydantic_errors(e: ValidationError) -> list[str]:
    out = []
    for err in e.errors():
        loc = ".".join(str(x) for x in err.get("loc", ()) if x != "__root__")
        msg = err.get("msg", "").removeprefix("Value error, ")
        out.append(f"{loc}: {msg}" if loc else msg)
    return out


def _parse_day(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise _bad(f"bad date {s!r}, expected YYYY-MM-DD") from None


# ============================================================================ system


@api.get("/status")
def get_status() -> dict[str, Any]:
    from market_view.data import store
    from market_view.risk.killswitch import KillSwitch

    s = get_settings()
    ks = KillSwitch().status()
    live_env = (env("LIVE_TRADING", "false") or "false").lower()
    return ser.deep_clean({
        "live_trading": live_env == "true", "mode": "paper",
        "killswitch": {k: ks.get(k) for k in ("active", "reason", "since", "source")},
        "data": {src: len(store.available(src, "1d")) for src in ("yfinance", "upstox")},
        "data_source": _source(),
        "upstox_token_set": bool(env("UPSTOX_ACCESS_TOKEN")),
        "telegram_set": bool(env("TELEGRAM_BOT_TOKEN") and env("TELEGRAM_CHAT_ID")),
        "risk_per_trade_pct": s.risk.risk_per_trade_pct, "daily_loss_cap_pct": s.risk.daily_loss_cap_pct,
        "initial_capital": s.backtest.initial_capital, "paper_capital": s.paper.initial_capital,
        "enabled_strategies": s.strategies.enabled,
        "periods": {k: {"start": v.start, "end": v.end, "locked": k == "test"} for k, v in s.backtest.periods.items()},
        "paper_started": (DATA_DIR / "paper" / "trader.json").exists(),
        "now": datetime.now(IST).isoformat(timespec="seconds"),
    })


@api.get("/killswitch")
def get_killswitch() -> dict[str, Any]:
    from market_view.risk.killswitch import KillSwitch

    st = KillSwitch().status()
    return {**{k: st.get(k) for k in ("active", "reason", "since", "source")}, "history": st.get("history", [])[-20:][::-1]}


class KillSwitchAction(BaseModel):
    action: Literal["on", "off"]
    reason: str = Field(min_length=3, max_length=500)


@api.post("/killswitch")
def set_killswitch(body: KillSwitchAction) -> dict[str, Any]:
    from market_view.risk.killswitch import KillSwitch

    ks = KillSwitch()
    if body.action == "on":
        ks.trigger(body.reason.strip(), "ui")
    else:
        try:
            ks.reset(body.reason)
        except ValueError as e:
            raise _bad(str(e)) from None
    return get_killswitch()


# ============================================================================ market data


@lru_cache(maxsize=512)
def _coverage(path: str, mtime: float) -> tuple[int, str, str]:
    df = pd.read_parquet(path, columns=["close"])
    return len(df), ser.day(df.index[0]), ser.day(df.index[-1])


@api.get("/symbols")
def get_symbols(source: str | None = None) -> list[dict[str, Any]]:
    from market_view.data import store

    s, src = get_settings(), source or _source()
    rows = []
    entries = ([(sym, "index", "Index") for sym in s.universe.indices]
               + [(sym, "stock", i.sector) for sym, i in s.universe.symbols.items()]
               + [(sym, "former", i.sector) for sym, i in s.universe.former_members.items() if sym not in s.universe.symbols])
    for sym, kind, sector in entries:
        p = store.clean_path(src, "1d", sym)
        row: dict[str, Any] = {"symbol": sym, "kind": kind, "sector": sector, "bars": 0, "first": None, "last": None}
        if p.exists():
            row["bars"], row["first"], row["last"] = _coverage(str(p), p.stat().st_mtime)
        rows.append(row)
    return rows


def _load(symbol: str, source: str | None = None) -> pd.DataFrame:
    from market_view.data import store

    df = store.load(symbol, "1d", source or _source())
    if df.empty:
        raise _bad(f"no stored data for {symbol!r} ({source or _source()}). Run: uv run mv data download", 404)
    return df


def _window(df: pd.DataFrame, start: date | None, end: date | None) -> pd.DataFrame:
    if start:
        df = df[df.index.date >= start]
    if end:
        df = df[df.index.date <= end]
    return df


@api.get("/candles/{symbol}")
def get_candles(symbol: str, start: str | None = None, end: str | None = None, source: str | None = None) -> dict:
    df = _window(_load(symbol, source), _parse_day(start), _parse_day(end))
    return {"symbol": symbol, "source": source or _source(), "bars": ser.candles(df)}


@api.get("/indicators")
def get_indicator_catalog() -> list[dict[str, Any]]:
    from market_view.strategies.rules import INDICATORS

    return [{"id": d.id, "label": d.label, "group": d.group, "placement": d.placement, "outputs": list(d.outputs),
             "explain": d.explain, "levels": list(d.levels), "value_range": list(d.value_range) if d.value_range else None,
             "params": [{"name": p.name, "default": p.default, "min": p.min, "max": p.max, "integer": p.integer,
                         "label": p.label or p.name} for p in d.params]} for d in INDICATORS.values()]


class IndicatorItem(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    ind: str
    params: dict[str, float] = Field(default_factory=dict)


class IndicatorRequest(BaseModel):
    symbol: str
    start: str | None = None
    end: str | None = None
    items: list[IndicatorItem] = Field(max_length=20)


@api.post("/indicators/compute")
def compute_indicators(req: IndicatorRequest) -> dict[str, Any]:
    """Indicators are computed in PYTHON on the full history (so they are warmed up), with the same code the
    strategies use, then cut to the requested window. The chart never re-implements an indicator."""
    from market_view.strategies.rules import INDICATORS, compute_indicator

    df = _load(req.symbol)
    start, end = _parse_day(req.start), _parse_day(req.end)
    out: dict[str, Any] = {}
    for it in req.items:
        if it.ind not in INDICATORS:
            raise _bad(f"unknown indicator {it.ind!r}")
        try:
            series = compute_indicator(df, it.ind, it.params)
        except ValueError as e:
            raise _bad(str(e)) from None
        out[it.key] = {name: ser.line(_window(s.to_frame("v"), start, end)["v"]) for name, s in series.items()}
    return out


# ============================================================================ strategies


def _experiments() -> list[dict[str, Any]]:
    path = DATA_DIR / "experiments.jsonl"
    if not path.exists():
        return []
    rows = []
    keep = ("trades", "total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "sortino", "profit_factor",
            "expectancy_r", "win_rate_pct", "total_charges", "benchmark_return_pct", "benchmark_cagr_pct",
            "exposure_pct", "start", "end", "breaker_events")
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        m = r.get("metrics", {})
        rows.append({"run_id": r["run_id"], "label": r["label"], "period": r["period"], "git": r.get("git"),
                     "strategies": r["label"].split("+"), "has_report": (REPORTS_DIR / "backtests" / r["run_id"]).exists(),
                     "enforce_breakers": (r.get("params") or {}).get("enforce_breakers"),
                     "metrics": {k: m.get(k) for k in keep}})
    return ser.deep_clean(rows[::-1])


def _strategy_info(sid: str, cls: type, experiments: list[dict] | None = None) -> dict[str, Any]:
    from market_view.strategies.rules import RuleStrategy

    s = get_settings()
    is_rule = issubclass(cls, RuleStrategy)
    info: dict[str, Any] = {
        "id": sid, "name": cls.name, "version": cls.version, "kind": "rule" if is_rule else "builtin",
        "description": cls.description, "defaults": ser.deep_clean(dict(cls.defaults)),
        "enabled": sid in s.strategies.enabled, "scale_out_r": cls.scale_out_r,
        "allowed_regimes": list(cls.allowed_regimes) if cls.allowed_regimes else None,
        "has_card": (ROOT / "docs" / "strategies" / f"{sid}.md").exists(),
    }
    if is_rule:
        spec = cls.base_spec
        info.update(spec=spec.model_dump(mode="json"), describe=spec.describe(), hypothesis=spec.hypothesis,
                    created_at=spec.created_at)
    runs = [e for e in (experiments if experiments is not None else _experiments()) if sid in e["strategies"]]
    info["runs"] = len(runs)
    info["latest"] = {p: next((e for e in runs if e["period"] == p and len(e["strategies"]) == 1), None)
                      for p in ("train", "validate", "full")}
    return info


@api.get("/strategies")
def list_strategies() -> list[dict[str, Any]]:
    from market_view.strategies import all_classes

    exps = _experiments()
    return [_strategy_info(sid, cls, exps) for sid, cls in all_classes().items()]


@api.get("/strategies/{sid}")
def get_strategy(sid: str) -> dict[str, Any]:
    from market_view.strategies import get_class

    try:
        cls = get_class(sid)
    except KeyError as e:
        raise _bad(str(e), 404) from None
    info = _strategy_info(sid, cls)
    card = ROOT / "docs" / "strategies" / f"{sid}.md"
    info["card_md"] = card.read_text(encoding="utf-8") if card.exists() else None
    return info


def _spec_from(body: dict[str, Any]):
    from market_view.strategies.rules import RuleSpec

    body = {k: v for k, v in body.items() if k not in ("version", "created_at")}
    return RuleSpec(**body)


@api.post("/strategies/validate")
def validate_strategy(body: Annotated[dict[str, Any], Body()]) -> dict[str, Any]:
    """Live validation for the builder: never saves anything."""
    from market_view.strategies.rules import flatten, next_version

    try:
        spec = _spec_from(body)
    except ValidationError as e:
        return {"ok": False, "errors": _pydantic_errors(e)}
    return {"ok": True, "errors": [], "describe": spec.describe(), "params": flatten(spec),
            "next_version": next_version(spec.name), "normalized": spec.model_dump(mode="json")}


@api.post("/strategies", status_code=status.HTTP_201_CREATED)
def create_strategy(body: Annotated[dict[str, Any], Body()]) -> dict[str, Any]:
    from market_view.strategies import get_class
    from market_view.strategies.rules import save_spec

    try:
        spec = save_spec(_spec_from(body))
    except ValidationError as e:
        return JSONResponse(status_code=422, content={"detail": _pydantic_errors(e)})  # type: ignore[return-value]
    except ValueError as e:
        raise _bad(str(e)) from None
    return _strategy_info(spec.id, get_class(spec.id))


class PreviewRequest(BaseModel):
    strategy_id: str | None = None
    spec: dict[str, Any] | None = None
    symbol: str
    start: str | None = None
    end: str | None = None


def _market() -> pd.DataFrame | None:
    from market_view.data import store
    from market_view.market_context.regime import prepare_market

    s = get_settings()
    nifty = store.load(s.backtest.benchmark, "1d", _source())
    vix = store.load(s.backtest.volatility_index, "1d", _source())
    return prepare_market(nifty, vix) if not nifty.empty else None


@api.post("/strategies/preview")
def preview_strategy(req: PreviewRequest) -> dict[str, Any]:
    """Where would this strategy have signalled on one symbol? (Signals only; P&L needs a backtest.)"""
    from market_view.strategies import make
    from market_view.strategies.rules import RuleStrategy, compile_spec

    if req.spec is not None:
        try:
            strat = compile_spec(_spec_from(req.spec))()
        except ValidationError as e:
            raise _bad("; ".join(_pydantic_errors(e))) from None
    elif req.strategy_id:
        try:
            strat = make(req.strategy_id)
        except KeyError as e:
            raise _bad(str(e), 404) from None
    else:
        raise _bad("give strategy_id or spec")
    df = _load(req.symbol)
    prepared = _window(strat.prepare(df, _market()), _parse_day(req.start), _parse_day(req.end))
    signals = []
    for ts, row in prepared[prepared["entry"].astype(bool)].iterrows():
        if not strat.regime_ok(row) or not (pd.notna(row["stop"]) and row["stop"] < row["close"]):
            continue
        signals.append(ser.deep_clean({"time": ser.day(ts), "close": row["close"], "stop": row["stop"],
                                       "target": row.get("target"), "regime": row.get("regime"),
                                       "reasons": strat.reasons(row)}))
    out: dict[str, Any] = {"strategy_id": strat.id, "symbol": req.symbol, "bars": len(prepared), "signals": signals}
    if isinstance(strat, RuleStrategy):
        spec = strat.spec
        out["exits"] = ([ser.day(ts) for ts in prepared.index[prepared["exit_signal"].astype(bool)]]
                        if spec.exit else [])
        # how restrictive is each condition? (teaches which rule is doing the filtering)
        stats = [{"label": c.label(), "true_bars": int(prepared[f"entry{i}"].sum())}
                 for i, c in enumerate(spec.entry, start=1)]
        all_conds = pd.Series(True, index=prepared.index)
        for i in range(1, len(spec.entry) + 1):
            all_conds &= prepared[f"entry{i}"]
        out["condition_stats"] = stats
        out["all_conditions_bars"] = int(all_conds.sum())
        out["blocked_by_market_filter"] = int((all_conds & ~prepared["entry"].astype(bool)).sum())
    return out


# ============================================================================ backtests


@api.get("/backtests")
def list_backtests(strategy: str | None = None, limit: int = Query(200, ge=1, le=2000)) -> list[dict[str, Any]]:
    rows = _experiments()
    if strategy:
        rows = [r for r in rows if strategy in r["strategies"]]
    return rows[:limit]


def _run_dir(run_id: str) -> Path:
    if not RUN_ID_RE.match(run_id) or ".." in run_id:
        raise _bad("bad run id", 400)
    d = (REPORTS_DIR / "backtests" / run_id).resolve()
    if d.parent != (REPORTS_DIR / "backtests").resolve() or not (d / "result.json").exists():
        raise _bad(f"backtest {run_id!r} not found", 404)
    return d


def _series_csv(path: Path) -> pd.Series | None:
    if not path.exists():
        return None
    df = pd.read_csv(path, index_col=0)
    df.index = pd.to_datetime(df.index, utc=True).tz_convert(IST)
    return df.iloc[:, 0]


def _yearly(equity: pd.Series, bench: pd.Series | None) -> list[dict[str, Any]]:
    rows = []
    for year, s in equity.groupby(equity.index.year):
        prev = equity[equity.index.year < year]
        base = prev.iloc[-1] if not prev.empty else s.iloc[0]
        row = {"year": int(year), "strategy_pct": round((s.iloc[-1] / base - 1) * 100, 2)}
        if bench is not None:
            b = bench[bench.index.year == year]
            bprev = bench[bench.index.year < year]
            if not b.empty:
                bbase = bprev.iloc[-1] if not bprev.empty else b.iloc[0]
                row["nifty_pct"] = round((b.iloc[-1] / bbase - 1) * 100, 2)
        rows.append(row)
    return rows


@api.get("/backtests/{run_id}")
def get_backtest(run_id: str) -> dict[str, Any]:
    from market_view.backtest.metrics import drawdown_series

    d = _run_dir(run_id)
    rec = json.loads((d / "result.json").read_text(encoding="utf-8"))
    equity = _series_csv(d / "equity.csv")
    bench = _series_csv(d / "benchmark.csv")
    if bench is None and equity is not None and not equity.empty:  # older runs: rebuild from stored NIFTY
        from market_view.data import store

        nifty = store.load(get_settings().backtest.benchmark, "1d", _source())
        if not nifty.empty:
            mc = nifty["close"].reindex(nifty.index.union(equity.index)).ffill().reindex(equity.index).dropna()
            if not mc.empty:
                bench = mc / mc.iloc[0] * equity.iloc[0]
    trades = pd.read_csv(d / "trades.csv") if (d / "trades.csv").exists() and (d / "trades.csv").stat().st_size > 2 else pd.DataFrame()
    signals = pd.read_csv(d / "signals.csv") if (d / "signals.csv").exists() else pd.DataFrame()
    sig_summary: dict[str, Any] = {"total": len(signals)}
    if not signals.empty:
        rej = signals[~signals["approved"].astype(bool)]
        sig_summary.update(approved=int(signals["approved"].astype(bool).sum()), rejected=len(rej),
                           # one signal can have several reasons ("max open positions 5; illiquid"): count each.
                           # A column of only blank reasons is read back as float NaN, so force text first.
                           top_rejections=rej["reasons"].astype("string").fillna("(none)").str.split(";").explode()
                           .str.split(":").str[0].str.strip().value_counts().head(10).to_dict())
    per_symbol: list[dict[str, Any]] = []
    if not trades.empty:
        g = trades.groupby("symbol")
        per_symbol = ser.records(pd.DataFrame({
            "trades": g.size(), "net_pnl": g["net_pnl"].sum().round(0), "avg_r": g["r_multiple"].mean().round(2),
            "win_pct": (g["net_pnl"].apply(lambda x: (x > 0).mean() * 100)).round(1)}).reset_index()
            .sort_values("net_pnl"))
    params = rec.get("params", {})
    return ser.deep_clean({
        "run_id": rec["run_id"], "label": rec["label"], "period": rec["period"], "git": rec.get("git"),
        "metrics": rec["metrics"], "events": rec.get("events", []),
        "params": {k: v for k, v in params.items() if k != "symbols"}, "symbols_count": len(params.get("symbols", [])),
        "equity": ser.line(equity, 2) if equity is not None else [],
        "benchmark": ser.line(bench, 2) if bench is not None else [],
        "drawdown": ser.line(drawdown_series(equity), 3) if equity is not None and not equity.empty else [],
        "yearly": _yearly(equity, bench) if equity is not None and not equity.empty else [],
        "trades": ser.records(trades.drop(columns=["context"], errors="ignore")),
        "signals": sig_summary, "per_symbol": per_symbol,
    })


@api.get("/backtests/{run_id}/signals")
def get_backtest_signals(run_id: str, symbol: str) -> list[dict[str, Any]]:
    d = _run_dir(run_id)
    if not (d / "signals.csv").exists():
        return []
    df = pd.read_csv(d / "signals.csv")
    return ser.records(df[df["symbol"] == symbol])


class BacktestRequest(BaseModel):
    strategies: list[str] = Field(min_length=1, max_length=10)
    period: str = "validate"
    symbols: list[str] | None = None
    enforce_breakers: bool = False


@api.post("/backtests", status_code=status.HTTP_202_ACCEPTED)
def run_backtest(req: BacktestRequest) -> dict[str, Any]:
    from market_view.backtest import report, runner
    from market_view.strategies import make

    if req.period == "test":
        raise _bad("The 2023-2025 test period is LOCKED and can only be run from the CLI, once per strategy "
                   "version, after Gate 3 (docs/04-roadmap.md).", 403)
    if req.period not in UI_PERIODS:
        raise _bad(f"period must be one of {UI_PERIODS}")
    try:
        strats = [make(s) for s in req.strategies]
    except (KeyError, ValueError) as e:
        raise _bad(str(e), 404) from None

    def work() -> dict[str, Any]:
        ids = [s.id for s in strats]
        start, end = runner.resolve_period(req.period, False, ids)
        result = runner.run(strats, start, end, req.symbols, enforce_breakers=req.enforce_breakers)
        result.params["enforce_breakers"] = req.enforce_breakers
        run_id, m, _ = report.save(result, "+".join(ids), req.period)
        return {"run_id": run_id, "metrics": ser.deep_clean({k: v for k, v in m.items() if k != "exit_reasons"})}

    return jobs.submit("backtest", req.model_dump(), work)


# ============================================================================ validation


class ValidationRequest(BaseModel):
    strategy: str
    period: str = "full"
    grid: dict[str, list[float]] | None = None
    params: list[str] | None = None


def _save_validation(kind: str, strategy: str, payload: dict[str, Any]) -> dict[str, Any]:
    from market_view.backtest.report import git_sha

    rec = {"id": f"{datetime.now(IST):%Y%m%d-%H%M%S}-{kind}-{strategy}", "kind": kind, "strategy": strategy,
           "created_at": datetime.now(IST).isoformat(timespec="seconds"), "git": git_sha(), **payload}
    rec = ser.deep_clean(rec)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (DATA_DIR / "validations.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, default=str) + "\n")
    return rec


@api.post("/validations/{kind}", status_code=status.HTTP_202_ACCEPTED)
def run_validation(kind: Literal["walkforward", "sensitivity", "montecarlo"], req: ValidationRequest) -> dict[str, Any]:
    from market_view.strategies import get_class

    try:
        get_class(req.strategy)
    except KeyError as e:
        raise _bad(str(e), 404) from None
    if req.period not in UI_PERIODS:
        raise _bad(f"period must be one of {UI_PERIODS} (test is locked)")

    def walkforward() -> dict[str, Any]:
        from market_view.validation.walkforward import summarize, walk_forward

        df = walk_forward(req.strategy, req.grid)
        df["params"] = df["params"].astype(str)
        return _save_validation(kind, req.strategy, {"grid": req.grid, "rows": ser.records(df), "summary": summarize(df)})

    def sensitivity() -> dict[str, Any]:
        from market_view.backtest import runner
        from market_view.validation.sensitivity import plateau_check
        from market_view.validation.sensitivity import sensitivity as sens

        start, end = runner.resolve_period(req.period)
        df = sens(req.strategy, start, end, req.params)
        return _save_validation(kind, req.strategy, {"period": req.period, "rows": ser.records(df),
                                                     "plateau": ser.records(plateau_check(df)) if not df.empty else []})

    def montecarlo() -> dict[str, Any]:
        from market_view.backtest import runner
        from market_view.validation.montecarlo import fan, simulate

        s = get_settings()
        start, end = runner.resolve_period(req.period)
        result = runner.run([req.strategy], start, end)
        mc = s.backtest.montecarlo
        risk = s.risk.risk_per_trade_pct
        return _save_validation(kind, req.strategy, {
            "period": req.period, "summary": simulate(result.trades, risk, mc.runs, seed=mc.seed),
            "fan": fan(result.trades, risk, mc.runs, seed=mc.seed), "trades": len(result.trades)})

    fn = {"walkforward": walkforward, "sensitivity": sensitivity, "montecarlo": montecarlo}[kind]
    return jobs.submit(kind, {"kind": kind, **req.model_dump()}, fn)


@api.get("/validations")
def list_validations(strategy: str | None = None, kind: str | None = None) -> list[dict[str, Any]]:
    path = DATA_DIR / "validations.jsonl"
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [r for r in rows if (not strategy or r["strategy"] == strategy) and (not kind or r["kind"] == kind)]
    return rows[::-1]


# ============================================================================ jobs


@api.get("/jobs")
def list_jobs() -> list[dict[str, Any]]:
    return ser.deep_clean(jobs.list())


@api.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    job = jobs.get(job_id)
    if not job:
        raise _bad("job not found (jobs are kept in memory until the server restarts)", 404)
    return ser.deep_clean(job)


# ============================================================================ paper trading (read-only)


@api.get("/paper")
def get_paper() -> dict[str, Any]:
    if not (DATA_DIR / "paper" / "trader.json").exists():
        return {"started": False, "how": "Run `uv run mv paper eod` after 15:35 IST (or `uv run mv paper run`)."}
    from market_view.paper.trader import PaperTrader

    st = PaperTrader().status()
    return ser.deep_clean({"started": True, **st, "initial_capital": get_settings().paper.initial_capital})


JOURNAL_TABLES = {"trades": "exit_time", "signals": "ts", "events": "ts", "equity": "ts", "orders": "ts"}


@api.get("/journal/{table}")
def get_journal(table: str, limit: int = Query(200, ge=1, le=5000)) -> list[dict[str, Any]]:
    if table not in JOURNAL_TABLES:
        raise _bad(f"table must be one of {sorted(JOURNAL_TABLES)}", 404)
    if not (DATA_DIR / "journal.duckdb").exists():
        return []
    from market_view.journal import Journal

    order = JOURNAL_TABLES[table]  # whitelisted identifiers only; limit is a validated int
    df = Journal().query(f"SELECT * FROM {table} ORDER BY {order} DESC LIMIT {int(limit)}")
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            df[c] = df[c].astype(str)
    return ser.records(df)


# ============================================================================ data quality


@api.get("/data/quality")
def get_data_quality(source: str | None = None) -> dict[str, Any]:
    from market_view.data import store
    from market_view.data.validate import validate

    src = source or _source()
    indices = set(get_settings().universe.indices)
    issues = []
    for sym in store.available(src, "1d"):
        found = validate(store.load(sym, "1d", src), sym)
        if sym in indices:  # indices have no volume and VIX moves 20%+ routinely
            found = [i for i in found if i.kind not in ("zero_volume", "price_jump")]
        issues += found
    by_kind: dict[str, int] = {}
    for i in issues:
        by_kind[i.kind] = by_kind.get(i.kind, 0) + 1
    review = [ser.deep_clean(i.__dict__) for i in issues if i.kind in ("price_jump", "ohlc_inconsistent", "duplicate_ts")]
    return {"source": src, "by_kind": by_kind, "needs_review": review[:300], "total": len(issues)}


# ============================================================================ app


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    jobs.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title="market-view", version="0.1.0", lifespan=_lifespan,
                  description="Local research + paper-trading UI API. No order endpoints exist.")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
    app.include_router(api)

    @app.exception_handler(FileNotFoundError)
    def _missing(_: Request, exc: FileNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(RuntimeError)
    def _runtime(_: Request, exc: RuntimeError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    if STATIC_DIR.exists():  # production build of the React UI (npm run build)
        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            if path.startswith("api/"):
                raise HTTPException(404)
            f = (STATIC_DIR / path).resolve()
            if path and f.is_file() and STATIC_DIR.resolve() in f.parents:
                return FileResponse(f)
            return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
