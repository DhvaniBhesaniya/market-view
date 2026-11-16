"""Background jobs for slow work (backtests, walk-forward, sensitivity, Monte Carlo).

The UI submits a job, gets an id back immediately, and polls `/api/jobs/{id}`. Two worker threads:
enough to run a quick backtest while a long sensitivity sweep is busy, without overloading a laptop.
Jobs live in memory; their RESULTS are persisted by the code they run (experiment log, validations log).
"""

from __future__ import annotations

import threading
import traceback
import uuid
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from market_view.config import IST

MAX_KEPT = 200


class JobManager:
    def __init__(self, workers: int = 2) -> None:
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="mv-job")
        self._jobs: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def _now() -> str:
        return datetime.now(IST).isoformat(timespec="seconds")

    def submit(self, kind: str, params: dict[str, Any], fn: Callable[[], Any]) -> dict[str, Any]:
        job = {"id": uuid.uuid4().hex[:12], "kind": kind, "params": params, "status": "queued",
               "created_at": self._now(), "started_at": None, "finished_at": None, "result": None, "error": None}
        with self._lock:
            self._jobs[job["id"]] = job
            while len(self._jobs) > MAX_KEPT:
                self._jobs.popitem(last=False)
        self._pool.submit(self._run, job["id"], fn)
        return self.get(job["id"])  # type: ignore[return-value]

    def _run(self, job_id: str, fn: Callable[[], Any]) -> None:
        self._update(job_id, status="running", started_at=self._now())
        try:
            result = fn()
            self._update(job_id, status="done", result=result, finished_at=self._now())
        except Exception as e:  # report every failure to the UI instead of losing it in a thread
            self._update(job_id, status="error", error=f"{type(e).__name__}: {e}",
                         trace=traceback.format_exc(limit=5), finished_at=self._now())

    def _update(self, job_id: str, **fields: Any) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(fields)

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def list(self, include_results: bool = False) -> list[dict[str, Any]]:
        with self._lock:
            jobs = [dict(j) for j in reversed(self._jobs.values())]
        if not include_results:
            for j in jobs:
                j.pop("result", None)
                j.pop("trace", None)
        return jobs

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
