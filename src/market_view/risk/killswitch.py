"""Kill switch: a persistent STOP ALL NEW TRADING flag. See docs/05-risk-management.md section 5.

State lives in data/killswitch.json so every process (scheduler, CLI, dashboard) sees it.
Turning it OFF requires a written note — restarting after a halt is a deliberate decision.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from market_view.config import DATA_DIR, IST


class KillSwitch:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DATA_DIR / "killswitch.json"

    def _read(self) -> dict:
        if not self.path.exists():
            return {"active": False, "history": []}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @property
    def active(self) -> bool:
        return bool(self._read().get("active"))

    def status(self) -> dict:
        return self._read()

    def trigger(self, reason: str, source: str = "auto") -> None:
        data = self._read()
        if data.get("active"):
            return
        now = datetime.now(IST).isoformat()
        data.update(active=True, reason=reason, since=now, source=source)
        data.setdefault("history", []).append({"at": now, "action": "ON", "reason": reason, "source": source})
        self._write(data)

    def reset(self, note: str) -> None:
        if not note or len(note.strip()) < 10:
            raise ValueError("Resetting the kill switch needs a note (>= 10 chars) explaining why it is safe")
        data = self._read()
        now = datetime.now(IST).isoformat()
        data.update(active=False, reason=None, since=None)
        data.setdefault("history", []).append({"at": now, "action": "OFF", "note": note})
        self._write(data)
