# 15 — Web UI (how to run it, what each page is for, how to check it)

A local web app over the same Python engine the CLI uses. It **cannot place orders** of any kind:
there is no order endpoint in the API (a test asserts the full list of state-changing endpoints).

## Run it

```powershell
cd C:\dhvani-cs\personal\market-view
uv sync                                   # Python deps (FastAPI, uvicorn included)
cd frontend; npm install; npm run build; cd ..   # build the UI once (and after UI changes)
uv run mv ui                              # opens http://127.0.0.1:8000 (localhost only)
```

UI development (hot reload): run `uv run mv ui --no-open` in one terminal and `cd frontend; npm run dev` in
another, then open http://127.0.0.1:5173 (Vite forwards `/api` to port 8000).

## Pages

| Page | What it is for |
|---|---|
| **Overview** | Safety state (paper mode, live trading off, kill switch), the **gate track** (Gates 0-7 with what each still needs), strategy scoreboard, recent runs |
| **Chart** | Candles + any indicator (editable params) + a strategy's BUY signals; click a signal to see why it fired, its stop and target |
| **Strategies** | Built-in (code) and your rule strategies, with latest train / validate / full results and Gate 3 status |
| **Build a strategy** | No-code rule builder: templates, conditions (indicator vs indicator/number, crosses), stop/target/time/trailing exits, market filter, regimes, live plain-English validation and live signal preview. **Save = new immutable version** after a look-ahead self-check |
| **Backtests** | Run one strategy or a portfolio on train / validate / full / forward; experiment log; compare up to 4 equity curves. The locked 2023-2025 test period is CLI-only |
| **Backtest report** | Honesty box (costs, too-few-trades, open positions, breaker events), metrics, equity vs NIFTY + drawdown, trades (click one for its chart), year by year, exit and rejection reasons, per symbol, exact parameters |
| **Validation** | Gate 3 checklist + walk-forward, sensitivity (plateau vs spike heat-strip) and Monte Carlo (cone of outcomes, R histogram). Results are saved to `data/validations.jsonl` |
| **Paper trading** | Paper account, positions, journal (trades / signals / orders / events), kill switch on/off (off needs a written note), daily routine |
| **Data** | Coverage per symbol, data-quality issues to review for Gate 1, Upstox setup steps |

**Explain layer:** every dotted-underlined term (Sharpe, drawdown, R, ATR, walk-forward…) shows a plain-language
definition and how to read it on hover/focus. Definitions live in `frontend/src/lib/glossary.ts`.

## Rule strategies (no code)

- Saved as YAML in `config/custom_strategies/<name>_v<N>.yaml` (tracked in git: they are research artefacts).
- Compiled into a normal `Strategy` subclass (`src/market_view/strategies/rules.py`), so they run through the same
  backtester, risk engine and paper trader as hand-written strategies. Enable one for paper trading by adding its
  id to `config/strategies.yaml` (only after Gate 3).
- Numeric knobs are flattened (`entry1_left_n`, `stop_value`, ...) so walk-forward grids and sensitivity work.
- Every indicator in the catalogue is causal and tested for it; saving re-checks look-ahead on synthetic data.

## How to check everything (before trusting a change)

```powershell
uv run pytest                          # 147 Python tests (engine, rules, API incl. safety properties)
uv run ruff check src tests
cd frontend; npm run check; cd ..      # typecheck + lint + 11 unit tests + production build
uv run python tests/e2e/ui_e2e.py      # real browser: every page + main flows, on an ISOLATED copy of your data
```

The browser check exists because a production build once crashed on every page while type-check, lint, unit
tests and the build all passed. It never writes to your real `data/`, `reports/` or `config/`.

## Architecture

```
frontend/ (React 19 + TypeScript + Vite, shadcn/ui radix-nova, TradingView Lightweight Charts v5.3,
           TanStack Query, Recharts for non-time charts)
   │  /api (JSON)                         served by FastAPI in production (frontend/dist)
src/market_view/api/ (FastAPI)  ── jobs.py: 2 worker threads for backtests / validations
   │
existing engine: data store, indicators, strategies (+ rules.py), backtester, risk, validation, paper, journal
```

- Indicators shown on charts are computed in **Python** by the same code the strategies use (never re-implemented in JS).
- The server binds to 127.0.0.1 and rejects foreign Host headers (DNS-rebinding protection).
- Skills used to build it: `lightweight-charts` and `shadcn` (official, installed in `.claude/skills/`),
  `fastapi-expert`, `frontend-design`, `webapp-testing`.
