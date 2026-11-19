"""One web-owned paper worker. No broker trading API is imported here.

Pausing disables entries; scheduled exits and monitoring continue for an existing account.
The application must remain awake/running: simulated stops cannot execute while it is down.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from market_view import calendar as cal
from market_view.config import DATA_DIR, get_settings
from market_view.paper.trader import PaperTrader


def _fingerprint() -> str:
    s = get_settings()
    code = hashlib.sha256()
    for path in sorted(Path(__file__).parents[1].rglob("*.py")):
        code.update(path.name.encode())
        code.update(path.read_bytes())
    payload = [s.paper.model_dump(), s.risk.model_dump(), s.strategies.model_dump(), s.calendar.model_dump(),
               s.universe.model_dump(), code.hexdigest()]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


class PaperAutomation:
    def __init__(self, root: Path | None = None, factory: Callable[[], PaperTrader] | None = None):
        self.root = root or DATA_DIR / "paper"
        self.path = self.root / "automation.json"
        self.factory = factory or (lambda: PaperTrader(root=self.root))
        self._account: PaperTrader | None = None
        self._state_lock = threading.RLock()
        self._job_lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._ownership = None
        self._retry_after = 0.0
        self._last_demand: datetime | None = None
        self._paper: dict = {"started": False, "how": "Start the research paper trial using the web controls."}
        self._state = {"entries_enabled": False, "heartbeat": None, "last_error": None,
                       "busy": None, "last_job": None, "fingerprint": None}
        if self.path.exists():
            saved = json.loads(self.path.read_text(encoding="utf-8"))
            self._state.update({k: saved[k] for k in ("entries_enabled", "fingerprint", "last_error") if k in saved})
            if self._state["entries_enabled"] and self._state["fingerprint"] != _fingerprint():
                self._state.update(entries_enabled=False, last_error="Configuration changed; review before restarting the paper trial.")

    def _persist(self):
        self.root.mkdir(parents=True, exist_ok=True)
        pending = self.path.with_suffix(".tmp")
        pending.write_text(json.dumps({k: self._state[k] for k in ("entries_enabled", "fingerprint", "last_error")}), encoding="utf-8")
        pending.replace(self.path)

    def _trader(self) -> PaperTrader:
        if self._account is None:
            self._account = self.factory()
        return self._account

    def entries_allowed(self) -> bool:
        with self._state_lock:
            return self._state["entries_enabled"] and not self._stop.is_set()

    def status(self) -> dict:
        with self._state_lock:
            return {**self._state, "worker_running": bool(self._thread and self._thread.is_alive()),
                    "mode": "paper", "research_only": True,
                    "schedule": get_settings().paper.schedule.model_dump(),
                    "calendar_through_year": max(d.year for d in cal.holidays()),
                    "limitation": "Keep this application and computer running. Simulated stops stop during downtime."}

    def paper_status(self) -> dict:
        # A GET never creates an account, and does not wait behind a slow history request.
        if not self._paper["started"] and (self.root / "trader.json").exists():
            with self._job_lock:
                self._refresh()
        with self._state_lock:
            return json.loads(json.dumps(self._paper, default=str))

    def _refresh(self):
        t = self._trader()
        with self._state_lock:
            self._paper = {"started": True, **t.status(), "initial_capital": t.cfg.initial_capital}

    def control(self, enabled: bool, acknowledge_research: bool = False) -> dict:
        if enabled and not acknowledge_research:
            raise ValueError("Acknowledge that this is research paper trading with unvalidated strategies.")
        if enabled:
            with self._job_lock:
                t = self._trader()
                if t.reconcile():
                    raise ValueError("Reconciliation failed; entries remain paused. Review the kill switch.")
                if t.killswitch.active:
                    raise ValueError("Kill switch is active. Review it before enabling paper entries.")
                self._refresh()
        with self._state_lock:
            self._state.update(entries_enabled=enabled, fingerprint=_fingerprint())
            if enabled:
                self._state["last_error"] = None
            self._persist()
        return self.status()

    def tick(self, now: datetime | None = None):
        now = now or cal.now_ist()
        with self._state_lock:
            self._state["heartbeat"] = now.isoformat()
        if self._stop.is_set() or time.monotonic() < self._retry_after:
            return
        if not self.entries_allowed() and not (self.root / "trader.json").exists():
            return
        with self._job_lock:
            t = self._trader()
            try:
                calendar_known = now.year <= max(d.year for d in cal.holidays())
                if not calendar_known:
                    self.control(False)
                    with self._state_lock:
                        self._state["last_error"] = "NSE holiday calendar is not verified for this year; update the calendar before entries. Position monitoring continues with fresh quotes."
                        self._persist()
                if not cal.is_trading_day(now.date()):
                    return
                if self.entries_allowed() and "09:00" <= now.strftime("%H:%M") < "09:15" and (self._last_demand is None or now-self._last_demand >= timedelta(seconds=30)):
                    from market_view.api.market_demand import capture

                    self._run("demand-observation", lambda: capture(now=now))
                    self._last_demand = now
                schedule = t.cfg.schedule
                opening = datetime.combine(now.date(), cal.parse_hhmm(schedule.open_job), now.tzinfo)
                # Never buy at noon merely because the app missed the opening schedule.
                if opening <= now < opening + timedelta(minutes=10) and t.st["last_open"] != now.date().isoformat():
                    self._run("open", lambda: t.open_job(now, entry_permission=self.entries_allowed))
                last = t.st.get("last_monitor")
                due = last is None or now - datetime.fromisoformat(last) >= timedelta(minutes=schedule.monitor_every_minutes)
                if cal.is_market_open(now) and due:
                    self._run("monitor", lambda: t.monitor(now))
                if calendar_known and now.time() >= cal.parse_hhmm(schedule.eod_job) and t.st["last_eod"] != now.date().isoformat():
                    self._run("eod", lambda: t.eod(now.date()))
                    t.reconcile()
                self._refresh()
            except Exception as exc:
                self._retry_after = time.monotonic() + 60
                message = f"{type(exc).__name__}: {exc}"
                t.killswitch.trigger("paper automation failed; inspect the application error", "automation")
                self.control(False)
                with self._state_lock:
                    self._state["last_error"] = message
                    self._persist()
                t.journal.event("ERROR", f"paper automation: {message}")
            finally:
                with self._state_lock:
                    self._state["busy"] = None

    def _run(self, kind: str, fn: Callable):
        with self._state_lock:
            self._state["busy"] = kind
        result = fn()
        with self._state_lock:
            self._state["last_job"] = {"kind": kind, "finished_at": cal.now_ist().isoformat(), "result": result}

    def start_worker(self):
        if self._thread and self._thread.is_alive():
            return
        self.root.mkdir(parents=True, exist_ok=True)
        handle = (self.root / "automation.lock").open("a+b")
        handle.seek(0)
        handle.write(b"0")
        handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            raise RuntimeError("Paper automation is owned by another application process.") from None
        self._ownership = handle
        self._stop.clear()

        def loop():
            while not self._stop.is_set():
                try:
                    self.tick()
                except Exception:
                    # Even corrupted account files must produce visible failure, not a dead worker.
                    with self._state_lock:
                        self._state.update(entries_enabled=False, last_error="Paper account could not be loaded. Inspect the application log before restarting.")
                        self._persist()
                    import logging

                    logging.exception("Paper worker failed")
                self._stop.wait(15)

        self._thread = threading.Thread(target=loop, name="paper-automation", daemon=True)
        self._thread.start()

    def close(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        # Keep the process lock if an in-flight request has not stopped yet.
        if self._ownership and not (self._thread and self._thread.is_alive()):
            self._ownership.close()
            self._ownership = None
