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
| **Chart** | Separate candle-interval and history controls; custom minute/hour/day/week/month bars, IST candle times, source/freshness, explicit market-data downloads, indicators and daily strategy signals |
| **Strategies** | Built-in (code) and your rule strategies, with latest train / validate / full results and Gate 3 status |
| **Build a strategy** | No-code rule builder: templates, conditions (indicator vs indicator/number, crosses), stop/target/time/trailing exits, market filter, regimes, live plain-English validation and live signal preview. **Save = new immutable version** after a look-ahead self-check |
| **Backtests** | Run one strategy or a portfolio on train / validate / full / forward; experiment log; compare up to 4 equity curves. The locked 2023-2025 test period is CLI-only |
| **Backtest report** | Honesty box (costs, too-few-trades, open positions, breaker events), metrics, equity vs NIFTY + drawdown, trades (click one for its chart), year by year, exit and rejection reasons, per symbol, exact parameters |
| **Validation** | Gate 3 checklist + walk-forward, sensitivity (plateau vs spike heat-strip) and Monte Carlo (cone of outcomes, R histogram). Results are saved to `data/validations.jsonl` |
| **Paper trading** | Paper account, positions, journal (trades / signals / orders / events), kill switch on/off (off needs a written note), daily routine |
| **Data** | Coverage per symbol, data-quality issues to review for Gate 1, Upstox setup steps |

**Explain layer:** every dotted-underlined term (Sharpe, drawdown, R, ATR, walk-forward…) shows a plain-language
definition and how to read it on hover/focus. Definitions live in `frontend/src/lib/glossary.ts`.

## Candle intervals, source and time

On **Chart**, the **Candle interval** row controls one candle: `1m`, `5m`, `15m`, `30m`, `1h`,
`1d`, `1w`, or `1M` (month). **Custom** accepts whole minute/hour/day/week/month intervals,
such as `7m` or `3M`. **History** separately controls how much data to display. These are
different controls; the old 6M/1Y/3Y buttons were history ranges, not candle intervals.

If an interval has no saved data, click **Download / update candles**. That single-symbol
background job uses the chosen Yahoo Finance or Upstox data adapter and the existing raw
snapshot/revision store. It does not place any order. Provider history limits apply: Yahoo
minute history is recent, and the chart downloader bounds one-minute requests to a recent
week and other intraday requests to a conservative recent window. Upstox needs its token.
Long bulk imports still use the CLI. The completed job shows the actual dates downloaded.
Yahoo daily updates refresh the existing daily span together, so a newly adjusted visible
slice is not deliberately merged into an older split/dividend adjustment basis.

Custom intraday bars combine compatible smaller candles with OHLCV aggregation anchored to
09:15 IST independently for each session. Weekly bars use Monday-based calendar groups;
months use calendar groups; custom multi-day bars use fixed calendar-day groups. Calendar
bars are labelled with their first observed trading session. Missing bars are not filled
with invented prices. A period still in progress can have an incomplete final candle.

**Seconds are unavailable with the current historical adapters.** The custom control explains
that a recorded tick-data feed is needed. Minute or daily OHLCV cannot reconstruct seconds.
[Upstox historical interval documentation](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/).

Hover a candle to see **date, hour, minute, second and IST** in the legend and crosshair time
label. Intraday instants retain their timezone and are formatted in Asia/Kolkata even when
the browser uses another timezone. A daily candle's 09:15 timestamp is a **session-start
label**, not the time of a particular transaction; multi-day candles show **period start**.

Indicators use the selected candle interval and the existing Python indicator functions.
Strategy previews remain daily: select `1d` for their signals. Changing the chart interval
does not change a strategy, its backtest timeframe or paper-trading behavior.

The provenance line distinguishes **stored history** from a live feed, identifies the
provider/adjustment policy and shows the latest underlying observation. TradingView
Lightweight Charts renders the supplied prices; it is not a TradingView market-data feed.
Yahoo prices are split/dividend adjusted and can differ from a broker's unadjusted chart.
Changing an interval/source does not display the preceding selection's candles while loading.

## Rule strategies (no code)

- Saved as YAML in `config/custom_strategies/<name>_v<N>.yaml` (tracked in git: they are research artefacts).
- Compiled into a normal `Strategy` subclass (`src/market_view/strategies/rules.py`), so they run through the same
  backtester, risk engine and paper trader as hand-written strategies. Enable one for paper trading by adding its
  id to `config/strategies.yaml` (only after Gate 3).
- Numeric knobs are flattened (`entry1_left_n`, `stop_value`, ...) so walk-forward grids and sensitivity work.
- Every indicator in the catalogue is causal and tested for it; saving re-checks look-ahead on synthetic data.

## How to check everything (before trusting a change)

```powershell
uv run pytest                          # engine, rules, API, chart intervals and safety properties
uv run ruff check src tests
cd frontend; npm run check; cd ..      # typecheck + lint + unit tests + production build
uv run python tests/e2e/ui_e2e.py      # real browser: every page + main flows, on an ISOLATED copy of your data
uv run python tests/e2e/ui_e2e.py --chart-only   # focused interval/hover check
```

The browser check exists because a production build once crashed on every page while type-check, lint, unit
tests and the build all passed. It never writes to your real `data/`, `reports/` or `config/`.
Screenshots are written to `output/playwright/ui-e2e/` (gitignored). Intraday browser fixtures
are synthetic and isolated; screenshots of those fixtures do not represent market observations.

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
