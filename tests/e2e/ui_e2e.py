"""Browser end-to-end check of the web UI (real Chromium, real API, an ISOLATED copy of your data).

    uv run python tests/e2e/ui_e2e.py            # needs: frontend built (npm run build) + data downloaded
    uv run python tests/e2e/ui_e2e.py --headed   # watch it

It copies data/clean, the experiment log and backtest reports into a temp folder, starts `mv ui` on port
8765 pointed at that copy, then drives every page and the main flows. Your real data/, reports/ and
config/custom_strategies/ are never touched. Fails (exit 1) on any failed check, console error, or HTTP 4xx/5xx.

Why it exists: on 2026-11-16 a production build crashed on every page ("reading 'useState'") while
type-check, lint, unit tests and the build itself all passed. Only a real browser catches that.
Not part of `pytest` (it needs a browser and ~2-4 minutes); run it before trusting a UI change.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"


def make_env(tmp: Path) -> dict[str, str]:
    (tmp / "data").mkdir()
    shutil.copytree(ROOT / "data" / "clean", tmp / "data" / "clean")
    if (ROOT / "data" / "experiments.jsonl").exists():
        shutil.copy(ROOT / "data" / "experiments.jsonl", tmp / "data" / "experiments.jsonl")
    if (ROOT / "reports" / "backtests").exists():
        shutil.copytree(ROOT / "reports" / "backtests", tmp / "reports" / "backtests")
    (tmp / "custom").mkdir()
    return {**os.environ, "MARKET_VIEW_DATA": str(tmp / "data"), "MARKET_VIEW_REPORTS": str(tmp / "reports"),
            "MARKET_VIEW_CUSTOM_STRATEGIES": str(tmp / "custom"), "PYTHONIOENCODING": "utf-8", "LIVE_TRADING": "false"}


def wait_server(proc: subprocess.Popen) -> None:
    for _ in range(120):
        if proc.poll() is not None:
            sys.exit("server exited early; is the port free and the frontend built?")
        try:
            with urllib.request.urlopen(f"{BASE}/api/status", timeout=2) as r:
                if r.status == 200:
                    return
        except Exception:
            time.sleep(0.5)
    sys.exit("server did not start")


def run(headed: bool, custom_dir: Path, shots: Path) -> tuple[list[str], list[str], list[str]]:
    problems: list[str] = []
    passed: list[str] = []
    errors: list[str] = []

    def check(name, fn):
        try:
            fn()
            passed.append(name)
            print(f"PASS {name}", flush=True)
        except Exception as e:
            problems.append(f"{name}: {type(e).__name__}: {str(e)[:300]}")
            print(f"FAIL {name}: {str(e)[:300]}", flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        ctx = browser.new_context(viewport={"width": 1440, "height": 950})
        page = ctx.new_page()
        page.on("console", lambda m: m.type == "error" and errors.append(f"{page.url}: {m.text[:300]}"))
        page.on("pageerror", lambda e: errors.append(f"{page.url}: PAGEERROR {str(e)[:300]}"))
        page.on("response", lambda r: r.status >= 400 and errors.append(f"HTTP {r.status} {r.request.method} {r.url}"))

        with urllib.request.urlopen(f"{BASE}/api/backtests") as r:
            runs = json.loads(r.read())
        first_run = runs[0]["run_id"] if runs else None
        routes = ["/", "/chart", "/strategies", "/strategies/trend_v1", "/builder", "/backtests",
                  "/validation?strategy=trend_v1", "/paper", "/data", "/nope"]
        if first_run:
            routes.append(f"/backtests/{first_run}")

        for route in routes:
            def visit(route=route):
                page.goto(BASE + route)
                page.wait_for_load_state("networkidle")
                expect(page.locator("h1").first).to_be_visible()
                over = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
                assert over <= 1, f"horizontal overflow {over}px"
                page.screenshot(path=str(shots / f"desktop{route.replace('/', '_').replace('?', '_')}.png"), full_page=True)
            check(f"page {route}", visit)

        def safety():
            page.goto(BASE + "/")
            page.wait_for_load_state("networkidle")
            expect(page.get_by_test_id("mode-badge")).to_have_text("Paper mode")
            expect(page.locator("header").get_by_text("Live trading off")).to_be_visible()
            expect(page.get_by_text("you are here").first).to_be_visible()
            page.locator(".term", has_text="PF").first.hover()
            expect(page.get_by_text("Total money won on winning trades")).to_be_visible(timeout=3000)
        check("safety badges, gate track, explain layer", safety)

        def chart():
            page.goto(BASE + "/chart?symbol=RELIANCE")
            page.wait_for_load_state("networkidle")
            assert page.locator("[data-testid=price-chart] canvas").count() > 0, "no chart canvas"
            page.get_by_role("combobox", name="Symbol").click()
            page.get_by_placeholder("Search symbol or sector").fill("INFY")
            page.get_by_role("option", name="INFY").first.click()
            page.get_by_role("button", name="Indicator").click()
            page.get_by_placeholder("Search indicators").fill("MACD")
            page.get_by_role("option", name="MACD").click()
            page.wait_for_load_state("networkidle")
            expect(page.get_by_test_id("price-chart")).to_contain_text("MACD")
            page.get_by_role("button", name="Remove MACD").click()
            page.wait_for_load_state("networkidle")
            expect(page.get_by_test_id("price-chart")).not_to_contain_text("MACD")
            page.get_by_role("combobox", name="Strategy").click()
            page.get_by_role("option", name="trend_v1").click()
            expect(page.get_by_text(" signals").first).to_be_visible(timeout=20000)
        check("chart: symbol, add/remove indicator, strategy signals", chart)

        def builder():
            page.goto(BASE + "/builder")
            page.wait_for_load_state("networkidle")
            page.get_by_role("button", name="RSI dip in an uptrend").click()
            expect(page.get_by_test_id("spec-describe")).to_contain_text("RSI(14) < 35", timeout=8000)
            page.get_by_label("Name").fill("Trend")
            expect(page.get_by_test_id("spec-errors")).to_be_visible(timeout=8000)
            page.get_by_label("Name").fill("e2e_dip")
            page.get_by_role("button", name="Save as v1").click(timeout=10000)
            page.wait_for_url("**/strategies/e2e_dip_v1", timeout=20000)
            page.get_by_role("link", name="Edit as v2").click()
            page.wait_for_load_state("networkidle")
            page.get_by_label("Stop value").fill("3")
            page.get_by_role("button", name="Save as v2").click(timeout=10000)
            page.wait_for_url("**/strategies/e2e_dip_v2", timeout=20000)
            names = sorted(f.name for f in custom_dir.glob("*.yaml"))
            assert names == ["e2e_dip_v1.yaml", "e2e_dip_v2.yaml"], names
        check("builder: template, validation, save v1, edit -> v2 (immutable files)", builder)

        def backtest():
            page.goto(BASE + "/strategies/e2e_dip_v1")
            page.wait_for_load_state("networkidle")
            page.get_by_role("button", name="Backtest").first.click()
            page.get_by_role("radio", name="validate").click()
            page.get_by_role("button", name="Run backtest").click()
            page.get_by_role("link", name="Open the report").click(timeout=240_000)
            page.wait_for_load_state("networkidle")
            expect(page.get_by_text("Simulated past results, not a promise of profit")).to_be_visible()
            rows = page.locator("table tbody tr")
            if rows.count():
                rows.first.click()
                expect(page.get_by_role("dialog").get_by_test_id("price-chart")).to_be_visible(timeout=15000)
                page.keyboard.press("Escape")
            for tab in ["Year by year", "Exits & rejections", "By symbol", "Events", "Parameters"]:
                page.get_by_role("tab", name=tab).click()
        check("backtest -> report -> trade chart -> tabs", backtest)

        def compare():
            page.goto(BASE + "/backtests")
            page.wait_for_load_state("networkidle")
            boxes = page.locator("input[type=checkbox]")
            if boxes.count() < 2:
                return
            boxes.nth(0).check()
            boxes.nth(1).check()
            expect(page.get_by_text("Comparing 2 runs")).to_be_visible(timeout=15000)
        check("compare runs", compare)

        def killswitch():
            page.goto(BASE + "/paper")
            page.wait_for_load_state("networkidle")
            page.get_by_label("Reason for stopping new trades").fill("e2e drill")
            page.get_by_role("button", name="Turn kill switch on").click()
            page.get_by_role("alertdialog").get_by_role("button", name="Turn on").click()
            expect(page.get_by_test_id("killswitch-badge")).to_be_visible(timeout=10000)
            note = page.get_by_label("Why is it safe to resume?")
            note.fill("too short")
            expect(page.get_by_role("button", name="Turn kill switch off")).to_be_disabled()
            note.fill("e2e drill finished, all reviewed")
            page.get_by_role("button", name="Turn kill switch off").click()
            page.get_by_role("alertdialog").get_by_role("button", name="Turn off").click()
            expect(page.get_by_test_id("killswitch-badge")).to_have_count(0, timeout=20000)
        check("kill switch drill (on -> off needs a written note)", killswitch)

        def montecarlo():
            page.goto(BASE + "/validation?strategy=e2e_dip_v1")
            page.wait_for_load_state("networkidle")
            page.get_by_role("tab", name="Monte Carlo").click()
            panel = page.get_by_role("tabpanel")
            panel.get_by_role("radio", name="validate").click()
            panel.get_by_role("button", name="Run").click()
            expect(panel.get_by_text("Showing run from")).to_be_visible(timeout=240_000)
        check("validation: Monte Carlo job", montecarlo)

        def mobile_and_light():
            page.goto(BASE + "/")
            page.wait_for_load_state("networkidle")
            page.get_by_role("button", name="Toggle theme").click()
            assert "dark" not in (page.evaluate("document.documentElement.className") or "")
            page.get_by_role("button", name="Toggle theme").click()
            m = ctx.new_page()
            m.set_viewport_size({"width": 390, "height": 844})
            for route in ["/", "/chart", "/builder", "/paper"] + ([f"/backtests/{first_run}"] if first_run else []):
                m.goto(BASE + route)
                m.wait_for_load_state("networkidle")
                over = m.evaluate("document.documentElement.scrollWidth - window.innerWidth")
                assert over <= 1, f"mobile overflow {over}px on {route}"
            m.close()
        check("light theme + phone width (no sideways scroll)", mobile_and_light)
        browser.close()
    return passed, problems, sorted(set(errors))


def main() -> int:
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        sys.exit("Build the UI first: cd frontend; npm run build")
    tmp = Path(tempfile.mkdtemp(prefix="mv-e2e-"))
    shots = tmp / "shots"
    shots.mkdir()
    env = make_env(tmp)
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "market_view.api.app:app", "--host", "127.0.0.1",
                               "--port", str(PORT), "--log-level", "warning"], cwd=ROOT, env=env)
    try:
        wait_server(server)
        passed, problems, errors = run("--headed" in sys.argv, tmp / "custom", shots)
    finally:
        server.terminate()
        server.wait(timeout=20)
    print(f"\n{len(passed)} passed, {len(problems)} failed, {len(errors)} browser/HTTP errors. Screenshots: {shots}")
    for x in problems + errors:
        print("  -", x)
    return 1 if problems or errors else 0


if __name__ == "__main__":
    sys.exit(main())
