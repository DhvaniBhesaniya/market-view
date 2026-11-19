"""Local web application launcher. Not a trading interface: no orders are placed from here.

Terminal use (recommended):
    uv run market-view start     # runs in this terminal; Ctrl+C or closing the terminal stops it
    uv run market-view status    # is it running? which process?
    uv run market-view stop      # stop a running instance (e.g. from another terminal)

Stopping the app also stops the paper worker (scheduled jobs and stop/target monitoring).
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

import uvicorn

from market_view.config import DATA_DIR, ROOT

HOST, PORT = "127.0.0.1", 8000
URL = f"http://{HOST}:{PORT}"
PID_FILE = DATA_DIR / "server.pid"


def is_running(timeout: float = 2) -> bool:
    try:
        with urllib.request.urlopen(URL + "/api/status", timeout=timeout) as response:
            return response.status == 200 and response.headers.get("content-type", "").startswith("application/json")
    except OSError:
        return False


def _pid_on_port() -> int | None:
    """PID listening on PORT (Windows netstat; lsof elsewhere)."""
    try:
        if os.name == "nt":
            out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True, timeout=10).stdout
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 5 and parts[1].endswith(f":{PORT}") and parts[3].upper() == "LISTENING":
                    return int(parts[4])
        else:
            out = subprocess.run(["lsof", "-ti", f"tcp:{PORT}", "-sTCP:LISTEN"], capture_output=True, text=True, timeout=10).stdout
            return int(out.split()[0]) if out.split() else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return None


def server_pid() -> int | None:
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return _pid_on_port()


def _open_when_ready() -> None:
    for _ in range(60):
        if is_running(timeout=1):
            webbrowser.open(URL)
            return
        time.sleep(0.5)


def start(open_browser: bool = True) -> int:
    if is_running():
        print(f"Market View is already running at {URL} (pid {server_pid()}). Stop it with: uv run market-view stop")
        if open_browser:
            webbrowser.open(URL)
        return 0
    if not (ROOT / "frontend/dist/index.html").exists():
        raise RuntimeError("The frontend build is missing: cd frontend; npm install; npm run build")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [logging.FileHandler(DATA_DIR / "application.log", encoding="utf-8")]
    console = sys.stdout is not None  # pythonw has no console
    if console:
        handlers.append(logging.StreamHandler())
        print(f"Market View starting at {URL}  (Ctrl+C to stop; this also stops paper monitoring)")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=handlers)
    if open_browser:
        threading.Thread(target=_open_when_ready, daemon=True).start()
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    try:
        uvicorn.run("market_view.api.app:app", host=HOST, port=PORT, workers=1, log_config=None)
    finally:
        PID_FILE.unlink(missing_ok=True)
    return 0


def stop() -> int:
    pid = server_pid() if is_running() else None
    if pid is None:
        PID_FILE.unlink(missing_ok=True)
        print("Market View is not running.")
        return 0
    os.kill(pid, signal.SIGTERM)  # Windows: TerminateProcess; account files are written by atomic replace
    for _ in range(20):
        if not is_running(timeout=0.5):
            PID_FILE.unlink(missing_ok=True)
            print(f"Stopped Market View (pid {pid}). Paper monitoring is off until you start it again.")
            return 0
        time.sleep(0.5)
    print(f"Process {pid} did not stop; end it in Task Manager.")
    return 1


def status() -> int:
    if is_running():
        print(f"Running at {URL} (pid {server_pid()}).")
    else:
        print("Not running.")
    return 0


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="market-view", description="Start/stop the local Market View web app.")
    parser.add_argument("command", nargs="?", default="start", choices=["start", "stop", "status"])
    parser.add_argument("--no-browser", action="store_true", help="don't open the browser on start")
    args = parser.parse_args(argv)
    if args.command == "stop":
        return stop()
    if args.command == "status":
        return status()
    return start(open_browser=not args.no_browser)


def main() -> None:
    """Entry for `python -m market_view.server`."""
    try:
        sys.exit(cli())
    except Exception as exc:
        logging.exception("Application startup failed")
        if sys.stdout is None and os.name == "nt":
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, f"Market View could not start: {exc}", "Market View", 16)
        else:
            raise


if __name__ == "__main__":
    main()
