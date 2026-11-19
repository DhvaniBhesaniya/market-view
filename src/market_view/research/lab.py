"""One preregistered research hypothesis, exact snapshots, bounded trials, no promotion.

Routine computation requires no LLM. Failed data and strategies are recorded, not optimized away.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import platform
import threading
import uuid
from collections.abc import Callable
from datetime import date, datetime, timedelta
from importlib.metadata import version
from pathlib import Path

import pandas as pd

from market_view import indicators as ta
from market_view.api.serialize import deep_clean
from market_view.backtest.engine import Backtester
from market_view.backtest.metrics import compute
from market_view.config import DATA_DIR, IST, get_settings
from market_view.costs import CostModel
from market_view.data import store
from market_view.data.validate import validate
from market_view.market_context.regime import prepare_market
from market_view.models import Side
from market_view.risk.engine import RiskEngine
from market_view.strategies.trend import TrendPullbackV1

PROTOCOL = "trend-adx-research-v1"
MAX_RUNS = 18


class TrendAdxResearch(TrendPullbackV1):
    """A1 from docs/14: only add completed-bar stock ADX >= 20 to the unchanged baseline."""

    name = "research_trend_adx"
    defaults = {**TrendPullbackV1.defaults, "adx_min": 20.0}

    def prepare(self, df, market):
        out = super().prepare(df, market)
        out["adx"] = ta.adx(df, 14)
        out["entry"] &= out["adx"].ge(self.p["adx_min"]).fillna(False)
        return out


class DoubleFriction(CostModel):
    """Stress assumption, not a replacement tax schedule."""

    def charges(self, side: Side, value: float, product: str = "CNC") -> float:
        return 2 * super().charges(side, value, product)

    @property
    def slippage(self) -> float:
        return 2 * super().slippage


def market_context(nifty: pd.DataFrame, vix: pd.DataFrame | None, now: datetime | None = None) -> dict:
    now = (now or datetime.now(IST)).astimezone(IST)
    # Daily bars can be updated during a session: only use completed daily observations.
    cutoff = now.date() if now.hour * 60 + now.minute >= 15 * 60 + 30 else now.date()-timedelta(days=1)
    nifty = nifty[nifty.index.date <= cutoff] if not nifty.empty else nifty
    vix = vix[vix.index.date <= cutoff] if vix is not None and not vix.empty else None
    if nifty.empty:
        return {"available": False, "as_of": None, "regime": "UNKNOWN", "news_available": False}
    m = prepare_market(nifty, vix)
    row = m.iloc[-1]
    age_days = (now.date()-m.index[-1].date()).days
    return deep_clean({"available": True, "as_of": m.index[-1].isoformat(), "regime": row.regime,
                       "source": get_settings().backtest.data_source, "calendar_age_days": age_days,
                       "close": row.m_close, "ema50": row.m_ema50, "ema200": row.m_ema200,
                       "adx": row.m_adx, "vix": row.vix, "news_available": False,
                       "meaning": "Rule-based description of the latest completed stored bar; not a forecast. Check its age before use."})


def _finite(value) -> bool:
    return isinstance(value, int | float) and math.isfinite(value)


def numeric_checks(validation: dict, full: dict, neighbours: list[dict], windows: list[dict], stress: dict) -> dict:
    pf = validation.get("profit_factor")
    return {
        "validation_profit_factor": _finite(pf) and pf >= 1.3,
        "sample_size": full.get("trades", 0) >= 100 and validation.get("trades", 0) >= 30,
        "drawdown": _finite(full.get("max_drawdown_pct")) and abs(full["max_drawdown_pct"]) <= 15,
        "yearly_robustness": bool(windows) and sum(m.get("total_return_pct", 0) > 0 for m in windows)/len(windows) >= .6,
        "training_neighbours": len(neighbours) == 2 and all(m.get("trades", 0) > 0 and m.get("total_return_pct", 0) > 0 for m in neighbours),
        "double_friction": stress.get("trades", 0) > 0 and stress.get("total_return_pct", 0) > 0,
        "benchmark_sharpe": _finite(validation.get("sharpe")) and _finite(validation.get("benchmark_sharpe")) and validation["sharpe"] > validation["benchmark_sharpe"],
    }


class ResearchLab:
    def __init__(self, root: Path | None = None):
        self.root = root or DATA_DIR / "research_runs"
        self._lock = threading.Lock()
        self._state_lock = threading.RLock()
        self._busy = False
        self._stage = None
        self._active_id = None
        self._heartbeat = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._settings_path = self.root / "schedule.json"
        self._schedule = {"enabled": False, "last_attempt_week": None, "last_error": None}
        if self._settings_path.exists():
            self._schedule.update(json.loads(self._settings_path.read_text(encoding="utf-8")))

    def status(self):
        with self._state_lock:
            return {**self._schedule, "busy": self._busy, "stage": self._stage,
                    "heartbeat": self._heartbeat, "worker_running": bool(self._thread and self._thread.is_alive()),
                    "schedule": "Sunday 10:00 IST, while application is running", "protocol": PROTOCOL,
                    "max_backtests": MAX_RUNS, "llm_required": False, "automatic_promotion": False}

    def _save_schedule(self):
        self.root.mkdir(parents=True, exist_ok=True)
        pending = self._settings_path.with_suffix(".tmp")
        pending.write_text(json.dumps(self._schedule), encoding="utf-8")
        pending.replace(self._settings_path)

    def control(self, enabled: bool):
        with self._state_lock:
            self._schedule["enabled"] = enabled
            self._save_schedule()
        return self.status()

    def tick(self, now: datetime, submit):
        week = f"{now.isocalendar().year}-{now.isocalendar().week}"
        with self._state_lock:
            self._heartbeat = now.isoformat()
            if not self._schedule["enabled"] or now.weekday() != 6 or now.hour < 10 or self._busy or self._schedule["last_attempt_week"] == week:
                return
            self._schedule["last_attempt_week"] = week
            self._save_schedule()  # persist before queuing: restarts cannot loop through validation
        try:
            submit()
        except Exception as exc:
            with self._state_lock:
                self._schedule["last_error"] = f"Research submission failed: {exc}"
                self._save_schedule()

    def history(self, limit: int | None = 20):
        reports = []
        manifests = sorted(self.root.glob("*/manifest.json"), reverse=True)
        for manifest in manifests[:limit] if limit else manifests:
            complete = manifest.parent / "report.json"
            if complete.exists():
                reports.append(json.loads(complete.read_text(encoding="utf-8")))
                continue
            progress = manifest.parent / "progress.json"
            if progress.exists():
                record = json.loads(progress.read_text(encoding="utf-8"))
                record["status"] = "running" if record["id"] == self._active_id else "interrupted"
                if record["status"] == "interrupted":
                    record["blockers"] = ["Application stopped before this report completed; evidence is incomplete. Identical inputs will not silently consume validation again."]
                reports.append(record)
        return reports

    def start_worker(self, submit: Callable):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()

        def loop():
            while not self._stop.is_set():
                try:
                    self.tick(datetime.now(IST), submit)
                except Exception as exc:
                    with self._state_lock:
                        self._schedule.update(enabled=False, last_error=f"Research scheduler failed: {exc}")
                        try:
                            self._save_schedule()
                        except OSError:
                            logging.exception("Could not persist research scheduler error")
                    logging.exception("Research scheduler failed; scheduling disabled")
                self._stop.wait(30)

        self._thread = threading.Thread(target=loop, name="research-scheduler", daemon=True)
        self._thread.start()

    def close(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    @staticmethod
    def _periods():
        s = get_settings().backtest
        if s.interval != "1d":
            raise ValueError("This protocol supports daily cash-equity research only.")
        p = s.periods
        train = (date.fromisoformat(p["train"].start), date.fromisoformat(p["train"].end))
        val = (date.fromisoformat(p["validate"].start), date.fromisoformat(p["validate"].end))
        if not train[0] < train[1] < val[0] <= val[1] < date.fromisoformat(p["test"].start):
            raise ValueError("Research periods must be chronological and end before the locked test window.")
        return train, val

    def run_cycle(self, data: dict[str, pd.DataFrame] | None = None, market: pd.DataFrame | None = None):
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("A research cycle is already running.")
        with self._state_lock:
            self._busy, self._stage = True, "Pinning stored data and checking quality"
        try:
            return self._cycle(data, market)
        finally:
            with self._state_lock:
                self._busy, self._stage = False, None
                self._active_id = None
            self._lock.release()

    def _cycle(self, data, market):
        train, val = self._periods()
        s = get_settings().model_copy(deep=True)
        start = train[0]-timedelta(days=int(s.backtest.warmup_days*1.5))
        missing = []
        raw_indices = {}
        if data is None:
            symbols = s.universe.all_symbols()
            data = store.load_many(symbols, "1d", s.backtest.data_source, start, val[1])
            missing = [sym for sym in symbols if sym not in data or data[sym].empty]
            nifty = store.load(s.backtest.benchmark, "1d", s.backtest.data_source, start, val[1])
            vix = store.load(s.backtest.volatility_index, "1d", s.backtest.data_source, start, val[1])
            raw_indices = {"_benchmark_raw": nifty, "_vix_raw": vix}
            market = prepare_market(nifty, vix) if not nifty.empty else None
        # Copies and date cuts happen before hashing/indicators. Holdout and forward rows are excluded.
        data = {sym: df[(df.index.date >= start) & (df.index.date <= val[1])].copy(deep=True) for sym, df in data.items()}
        market = market[(market.index.date >= start) & (market.index.date <= val[1])].copy(deep=True) if market is not None else None
        config = {"backtest": s.backtest.model_dump(), "risk": s.risk.model_dump(), "costs": s.costs.model_dump(), "universe": s.universe.model_dump()}
        baseline_params = {**TrendPullbackV1.defaults, **s.strategies.params.get("trend_v1", {})}
        spec = {"protocol": PROTOCOL, "baseline": baseline_params, "candidate": {**baseline_params, "adx_min": 20},
                "training_neighbours": [16, 24], "config": config, "train": list(map(str, train)), "validation": list(map(str, val)),
                "excluded": ["locked test", "forward paper history"], "max_backtests": MAX_RUNS,
                "dependencies": {"python": platform.python_version(), **{p: version(p) for p in ("numpy", "pandas", "pyarrow", "pydantic")}}}
        code_files = sorted(Path(__file__).parents[1].rglob("*.py"))
        code_blobs = {p.relative_to(Path(__file__).parents[1]): p.read_bytes() for p in code_files}
        code_digest = hashlib.sha256()
        for relative, blob in code_blobs.items():
            code_digest.update(str(relative).encode()+b"\0"+blob)
        code_hash = code_digest.hexdigest()
        fingerprint = hashlib.sha256(json.dumps(spec, sort_keys=True, default=str).encode()+code_hash.encode())
        frames = {**data, **raw_indices, "_market": market} if market is not None else {**data, **raw_indices}
        for key, frame in sorted(frames.items()):
            fingerprint.update(key.encode())
            fingerprint.update(str(list(frame.dtypes.astype(str))).encode())
            fingerprint.update(pd.util.hash_pandas_object(frame, index=True).values.tobytes())
        digest = fingerprint.hexdigest()
        for old in self.history(limit=None):
            if old["fingerprint"] == digest:
                return {**old, "reused": True}
        run_id = datetime.now(IST).strftime("%Y%m%d-%H%M%S")+"-"+uuid.uuid4().hex[:8]
        self._active_id = run_id
        directory = self.root / run_id
        directory.mkdir(parents=True)
        snapshot = directory / "inputs"
        snapshot.mkdir()
        hashes = {}
        for key, frame in frames.items():
            path = snapshot / f"{key}.parquet"
            frame.to_parquet(path)
            hashes[key] = hashlib.sha256(path.read_bytes()).hexdigest()
        code_dir = directory / "code"
        for relative, blob in code_blobs.items():
            target = code_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(blob)
        manifest = {**spec, "fingerprint": digest, "code_sha256": code_hash, "input_sha256": hashes,
                    "trial_policy": "One fixed hypothesis; neighbours are training diagnostics, not a validation parameter search."}
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
        report = {"id": run_id, "created_at": datetime.now(IST).isoformat(), "fingerprint": digest,
                  "status": "blocked", "protocol": PROTOCOL, "runs": [], "blockers": [], "checks": {},
                  "promotion_allowed": False, "reused": False,
                  "remaining_evidence": ["Verified historical membership/corporate actions", "Contract-note cost and benchmark reconciliation", "Independent holdout protocol and forward paper evidence"],
                  "input_symbols": len(data), "llm_used": False}
        self._checkpoint(directory, report)
        blockers = report["blockers"]
        blockers.extend(f"Missing history: {symbol}" for symbol in missing)
        if market is None or market.empty:
            blockers.append("Missing benchmark market context")
        elif market.index[-1].date() < val[1]-timedelta(days=7):
            blockers.append("Benchmark history does not cover the validation period")
        if not data:
            blockers.append("No stored stock history")
        for sym, frame in data.items():
            if frame.empty:
                blockers.append(f"{sym}: empty history")
                continue
            values = frame[["open", "high", "low", "close", "volume"]]
            if values.isna().any().any() or values.isin([float("inf"), -float("inf")]).any().any():
                blockers.append(f"{sym}: missing/non-finite OHLCV values")
            issues = validate(frame, sym)
            blockers.extend(f"{sym} {i.ts[:10]}: {i.kind}" for i in issues[:20])
        for name, frame in raw_indices.items():
            if frame.empty:
                blockers.append(f"Missing {name} history")
            else:
                blockers.extend(f"{name} {i.ts[:10]}: {i.kind}" for i in validate(frame, name)
                                if i.kind not in ("zero_volume", "price_jump"))
        try:
            if not blockers:
                self._experiment(report, directory, data, market, train, val, baseline_params, s)
        except Exception as exc:
            report["status"] = "failed"
            blockers.append(f"Research failed: {type(exc).__name__}: {exc}")
        report = deep_clean(report)
        pending = directory / "report.tmp"
        pending.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        pending.rename(directory / "report.json")
        return report

    @staticmethod
    def _checkpoint(directory, report):
        pending = directory / "progress.tmp"
        pending.write_text(json.dumps(deep_clean(report), allow_nan=False), encoding="utf-8")
        pending.replace(directory / "progress.json")

    def _experiment(self, report, directory, data, market, train, val, params, settings):
        def evaluate(label, strategy, period, *, stress=False, operational=False):
            if len(report["runs"]) >= MAX_RUNS:
                raise RuntimeError("Bounded research budget exhausted")
            with self._state_lock:
                self._stage = label
            trial = {"label": label, "strategy": strategy.id, "params": strategy.p,
                     "start": str(period[0]), "end": str(period[1]), "double_friction": stress,
                     "operational_breakers": operational, "status": "running"}
            report["runs"].append(trial)
            self._checkpoint(directory, report)
            try:
                costs = DoubleFriction(settings.costs) if stress else CostModel(settings.costs)
                sectors = {sym: settings.universe.info(sym).sector for sym in settings.universe.all_symbols()}
                risk = RiskEngine(settings.risk.model_copy(deep=True), costs, sectors, settings.backtest.initial_capital)
                result = Backtester([strategy], data, *period, settings.backtest.initial_capital,
                                    market=market, costs=costs, risk=risk,
                                    enforce_breakers=operational).run()
            except Exception as exc:
                trial.update(status="failed", error=str(exc))
                self._checkpoint(directory, report)
                raise
            metrics = compute(result.equity, result.trades, result.benchmark)
            trial.update(status="complete", metrics=metrics)
            self._checkpoint(directory, report)
            result.equity.to_frame("equity").to_parquet(directory / f"{label}-equity.parquet")
            result.trades_df().to_json(directory / f"{label}-trades.json", orient="records", date_format="iso")
            return metrics

        evaluate("baseline-train", TrendPullbackV1(**params), train)
        evaluate("candidate-train", TrendAdxResearch(**params), train)
        neighbours = [evaluate(f"neighbour-{n}-train", TrendAdxResearch(**params, adx_min=n), train) for n in (16, 24)]
        baseline = evaluate("baseline-validation", TrendPullbackV1(**params), val)
        candidate = evaluate("candidate-validation", TrendAdxResearch(**params), val)
        if not (_finite(candidate.get("profit_factor")) and candidate["profit_factor"] >= 1.3 and candidate["trades"] >= 30):
            report.update(status="rejected", blockers=["Fixed candidate failed validation profit factor/sample precheck; further tests skipped."])
            return
        full = evaluate("candidate-full-research", TrendAdxResearch(**params), (train[0], val[1]))
        stress = evaluate("candidate-double-friction", TrendAdxResearch(**params), val, stress=True)
        operational = evaluate("candidate-operational", TrendAdxResearch(**params), val, operational=True)
        wf = settings.backtest.walkforward
        years = list(range(wf.first_test_year, wf.last_test_year+1, wf.test_years))
        if len(years) > 9 or any(date(y, 1, 1) < train[0] or date(y+wf.test_years-1, 12, 31) > val[1] for y in years):
            raise ValueError("Configured yearly windows exceed this protocol's research bounds")
        windows = [evaluate(f"candidate-year-{y}", TrendAdxResearch(**params), (date(y, 1, 1), date(y+wf.test_years-1, 12, 31))) for y in years]
        checks = numeric_checks(candidate, full, neighbours, windows, stress)
        checks["beats_baseline_expectancy"] = candidate["expectancy_r"] > baseline["expectancy_r"]
        checks["operational_after_cost_profit"] = operational["total_return_pct"] > 0
        report.update(status="needs_evidence" if all(checks.values()) else "rejected", checks=checks)
        report["blockers"] = [key.replace("_", " ") for key, passed in checks.items() if not passed]
        if all(checks.values()):
            report["blockers"] = ["Numeric screen passed; full promotion evidence is incomplete. Active trading is unchanged."]
