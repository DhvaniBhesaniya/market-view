"""Desktop entry point: local application, browser, logs; no command-line trading interface."""

from __future__ import annotations

import logging
import threading
import urllib.request
import webbrowser

import uvicorn

from market_view.config import DATA_DIR, ROOT

URL = "http://127.0.0.1:8000"


def main():
    # Reopening the launcher opens the existing application, not another paper worker.
    try:
        with urllib.request.urlopen(URL + "/api/status", timeout=2) as response:
            if response.status == 200 and response.headers.get("content-type", "").startswith("application/json"):
                webbrowser.open(URL)
                return
    except OSError:
        pass
    if not (ROOT / "frontend/dist/index.html").exists():
        raise RuntimeError("The frontend production build is missing. Complete the developer setup first.")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=DATA_DIR / "application.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    def open_when_ready():
        import time

        for _ in range(60):
            try:
                with urllib.request.urlopen(URL + "/api/status", timeout=1) as response:
                    if response.status == 200:
                        webbrowser.open(URL)
                        return
            except OSError:
                time.sleep(.5)

    threading.Thread(target=open_when_ready, daemon=True).start()
    # pythonw has no console stream; the application log receives server errors.
    uvicorn.run("market_view.api.app:app", host="127.0.0.1", port=8000, workers=1, log_config=None)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logging.exception("Application startup failed")
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, f"Market View could not start: {exc}", "Market View", 16)
