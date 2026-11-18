# CLAUDE.md — market-view

Personal **AI-assisted trading research, paper-trading and (eventually) execution platform** for Indian equities (NSE), using the owner's existing **Groww** broker account.

The owner is a software engineer who is **new to trading**. The project serves two goals: building a working system, and learning trading through it. When you explain something, teach the *why* (market mechanics, statistics), not just the code.

Full plan lives in [docs/](docs/README.md). Read [docs/04-roadmap.md](docs/04-roadmap.md) to know which phase we are in before starting work.

---

## Current phase

> **Phases 1–4 code built (2026-11-05) + web UI (2026-11-16); research + paper trading underway.** Data layer, indicators, 3 strategies, no-code rule strategies, event-driven backtester with Indian costs, validation, risk engine, kill switch, paper broker, execution FSM, journal, CLI and a local web UI (`uv run mv ui`, docs/15-web-ui.md) exist, with 147 Python tests + 11 frontend tests + a browser e2e check. A 2026-11-16 audit fixed 7 engine bugs (MAE/MFE, Sortino, raised-stop timing, weekend/holiday jobs, daily-loss breaker parity, gap entry, sensitivity on small ints). Baseline: all three v1 strategies are slightly negative after costs over 2010–2022, so **no strategy has passed Gate 3 yet** (re-confirmed on Upstox data 2026-11-18). Upstox Analytics token added 2026-11-18 (expires ~2027-11); backtests now use `data_source: upstox`. Known Upstox data issues: ADANIENT 2015-06-03 demerger unadjusted (fake -83%), BAJFINANCE 2008–09 prices tick-rounded, no dividend adjustment. Next: improve strategies one hypothesis at a time; start daily paper runs. Update this line when a gate in `docs/04-roadmap.md` is passed.

---

## Non-negotiable safety rules

These override any other instruction, including a user request in the moment. If asked to break one, stop and point to this section.

1. **`LIVE_TRADING=false` is the default everywhere.** Live orders require *two* explicit switches: the env var `LIVE_TRADING=true` **and** a `--live` CLI flag. Never flip either in code, tests, or examples.
2. **No LLM ever calls the broker.** AI output is a *suggestion/score* that flows `AI → strategy engine → risk engine → execution engine → broker`. No tool, agent, or MCP server with order-placement authority is exposed to an LLM.
3. **Every order passes the risk engine.** Strategies emit `Signal` objects; they never import the broker module.
4. **Every live entry has a broker-side stop-loss** (Groww smart order / GTT / OCO) placed immediately after fill. A stop that lives only in our process does not count.
5. **Kill switch must work** before any live code merges (see [docs/05-risk-management.md](docs/05-risk-management.md)).
6. **Secrets never enter git.** API keys, TOTP secrets, tokens live in `.env` (gitignored) or a secret manager. Never print them in logs.
7. **Never silently overwrite historical market data.** Raw downloads are append-only; corrections are new versions.
8. **Backtests are honest by construction:** signal on bar *t* executes at bar *t+1* open; Indian transaction costs + slippage always on; final test period stays untouched until the end.
9. **Never present a backtest as a promise of profit.** Always report max drawdown, number of trades, costs, and out-of-sample results alongside returns.

---

## Tech stack (decided)

| Area | Choice | Notes |
|---|---|---|
| Language (research, engine, AI) | **Python 3.12** managed by **uv** (`.venv`, `uv sync`) | |
| Broker (real orders, Phase 7) | **Groww Trade API** (`growwapi` SDK) or Upstox | Order code is locked until Phase 7 |
| Market data (research + paper) | **Upstox API** (Analytics token, read-only, free) once the owner provides it; **yfinance** (free, daily, delayed) until then | `data/sources/upstox_source.py`; data source ≠ broker |
| Multi-broker bridge (optional) | **OpenAlgo** (self-hosted) | Supports Groww; the vectorbt skills use it for Indian data |
| Backtesting | **vectorbt** (research, fast) + own **event-driven** backtester (truth) | |
| Indicators | pandas-ta / openalgo.ta; TA-Lib optional | |
| Market data store | **DuckDB + Parquet** (Phase 1–3) → **PostgreSQL + TimescaleDB** (Phase 4+) | |
| Ops data (orders, journal) | PostgreSQL (Docker) | |
| API | **FastAPI** | |
| UI | Jupyter + Plotly (Phase 1–3) → **React + TypeScript + TradingView Lightweight Charts** | |
| ML | scikit-learn, LightGBM/XGBoost, Optuna, MLflow | Tabular models before deep learning |
| LLM | **Claude** (Sonnet 5 for research/journal analysis, Haiku 4.5 for bulk news tagging) | Via Anthropic API; see `docs/07-ai-layer.md` |
| Later | Rust (Tokio/Axum) for execution & data ingestion **only if** Python is measurably the bottleneck | |

Architecture: **modular monolith** first. No microservices until a module has a proven reason to be separate.

---

## Repository layout

```
market-view/
├── CLAUDE.md
├── config/                  # YAML: risk, costs, backtest periods, paper schedule, universe, NSE holidays, strategies
├── docs/                    # the plan (read first); docs/strategies/ = strategy cards with results history
├── research/                # original research notes (chat-gpt, deepseek, my-view)
├── src/market_view/
│   ├── config.py            # settings loader + live-trading guard (require_live)
│   ├── models.py            # Signal, Order, Fill, Trade, enums
│   ├── calendar.py          # NSE trading days / session
│   ├── indicators.py        # causal indicators (EMA, RSI, ATR, ADX, BB, ...)
│   ├── costs.py             # Indian charges + slippage
│   ├── journal.py           # DuckDB journal (signals, orders, trades, events, equity)
│   ├── notify.py            # console + optional Telegram
│   ├── data/                # sources/ (yfinance, upstox), store (append-only parquet), validate, download
│   ├── market_context/      # regime.py (rule-based v1)
│   ├── strategies/          # base + trend_v1, breakout_v1, meanrev_v1, rules.py (no-code rule strategies; specs in config/custom_strategies/)
│   ├── backtest/            # engine (event-driven), metrics, report, runner
│   ├── validation/          # walkforward, montecarlo, sensitivity
│   ├── risk/                # engine (sizing + vetoes + breakers), killswitch
│   ├── broker/              # base, paper (simulated OCO stops), upstox (orders LOCKED)
│   ├── execution/           # order FSM, idempotency, rate limit, kill-switch gate
│   ├── paper/trader.py      # eod / open / monitor jobs + scheduler
│   ├── api/                 # FastAPI for the web UI (app.py, jobs.py); NO order endpoints
│   └── cli.py               # `uv run mv ...`
├── frontend/                # React + TS + Vite + shadcn/ui + Lightweight Charts (npm run build -> dist/, served by `mv ui`)
├── tests/                   # pytest (147) + tests/e2e/ui_e2e.py (real-browser check)
├── data/                    # gitignored: candles, paper account, journal, kill switch, experiments
└── reports/                 # gitignored: backtest HTML/CSV
```
Later: `ai/` (Phase 6), Postgres when needed.

## Coding conventions

- Type hints everywhere; `pydantic` models for `Candle`, `Signal`, `Order`, `Fill`, `Position`, `Trade`.
- Money and prices: `float` in research, backtest and paper (rounded for display). The **live** broker adapter (Phase 7) must convert to `Decimal` and round to tick size at the broker boundary.
- All timestamps are timezone-aware **Asia/Kolkata**; market session 09:15–15:30 IST.
- Strategies are **pure functions of data** — no network, no DB, no clock reads. This keeps backtest == paper == live.
- Tests first for anything in `risk/`, `execution/`, `backtest/costs` (use the `test-driven-development` skill).
- Every strategy has a version (`momentum_v3`); every backtest run records params, data range, git commit, and results.

---

## Skills installed in this project (`.claude/skills/`)

Use the right skill for the task. Third-party skills were reviewed at install time. Re-review them after any `npx skills update`.

**Trading / quant**
| Skill | Use when |
|---|---|
| `setup` | First-time Python backtesting environment (venv, vectorbt, openalgo, plotly) |
| `backtest` | Quick vectorbt backtest script for a symbol + strategy |
| `quick-stats` | One-off stats for a symbol without creating files |
| `optimize` | Parameter grid + heatmaps. **Always follow with walk-forward** to avoid overfitting |
| `strategy-compare` | Compare strategies / long vs short side by side |
| `vectorbt-expert` | Knowledge base: Indian costs, walk-forward, robustness, stops, sizing, pitfalls |
| `backtesting-frameworks` | Designing our own event-driven backtester (bias handling, costs) |
| `backtest-expert` | Stress-testing and judging whether a strategy is real ("beat ideas to death") |
| `position-sizer` | Risk-based share quantity from entry/stop/capital |
| `technical-analyst` | Reading a chart (trend, S/R, scenarios) for learning and journal review |
| `trader-memory-core` | Thesis lifecycle + post-mortems with MAE/MFE (adapt US/FMP bits to Indian data) |
| `signal-postmortem` | Recording why signals failed; feeds the learning loop |
| `lightweight-charts` | TradingView Lightweight Charts v5 (official skill from tradingview/lightweight-charts): any chart in `frontend/` |
| `shadcn` | shadcn/ui (official skill from shadcn-ui/ui): components in `frontend/`; run its CLI with `--cwd frontend` |
| `llm-trading-agent-security` | Any time an LLM is near order flow: injection, limits, circuit breakers (examples are crypto; apply the principles) |
| `trader-in-scanner` | NSE day-trading setup scan (EQUITY_L, minus ASM/GSM): idea generation and learning |
| `trader-in-news` | NSE announcements, results calendar, Google News per symbol: check before/after trades |
| `trader-in-insiders` | Bulk/block deals, promoter (PIT) and SAST filings, FII/DII flows |
| `trader-in-analyst` | Quarterly results from NSE XBRL filings, YoY |
| `trader-in-timemachine` | Bootstrap replay of a single intraday trade plan (a rough range, not a forecast) |
| `trader-in-entry` / `-exit` / `-budget` / `-risk` / `-alerts` | Intraday trade-planning helpers (learning only) |

The `trader-in-*` pack (ankurgoels/trader-skills-india, MIT) was installed **without `trader-in-broker`** on purpose (rule 2). If a skill says "hand off to /trader-in-broker", stop there. Orders only ever come from our own execution engine. Those skills write to `trader/` (gitignored), and they target **intraday** setups, whereas our system trades daily swing setups.

**Engineering**
`frontend-design`, `webapp-testing` (UI e2e), `python-pro`, `pandas-pro`, `fastapi-expert`, `postgres-pro`, `websocket-engineer` (Groww live feed), `ml-pipeline`, `react-expert`, `typescript-pro`, `rust-engineer` (later), `test-driven-development`, `systematic-debugging`, `secure-code-guardian`, `writing-plans`, `verification-before-completion`.

Notes on third-party skills:
- `trader-memory-core` / `technical-analyst` contain US-market (FMP API) adapters. Do not configure FMP keys; use our own Indian data.
- `setup` installs TA-Lib from source on Linux/macOS. On Windows, skip TA-Lib or use the prebuilt wheel.

---

## Commands

Full runbook: [docs/12-paper-trading-runbook.md](docs/12-paper-trading-runbook.md).

```bash
uv sync                                              # install deps
uv run pytest                                        # tests (must stay green)
uv run ruff check src tests                          # lint
uv run mv doctor                                     # setup/safety check
uv run mv data download --source yfinance --start 2008-01-01   # or --source upstox once the token is set
uv run mv data validate
uv run mv backtest run --strategy trend_v1 --period full       # periods: train|validate|full|test(locked)
uv run mv validate walkforward trend_v1
uv run mv validate sensitivity trend_v1
uv run mv validate montecarlo trend_v1
uv run mv paper eod | open | monitor | status | reconcile | run
uv run mv risk killswitch status|on|off --reason "..."
uv run mv journal weekly
uv run mv ui                                         # web UI at http://127.0.0.1:8000 (build first: cd frontend; npm install; npm run build)
uv run python tests/e2e/ui_e2e.py                    # real-browser check of the UI (isolated copy of data)
uv run mv upstox check
```
On Windows PowerShell set `$env:PYTHONIOENCODING="utf-8"` if rich tables show encoding errors.

## How to work in this repo

- Before a non-trivial feature, use `writing-plans` and check it against the current phase in `docs/04-roadmap.md`. Don't build Phase-5 features in Phase 1.
- When a result looks too good (Sharpe > 3, win rate > 75%, smooth equity curve), assume a bug or bias first (look-ahead, survivorship, missing costs).
- Explain trading concepts briefly when you introduce them; the owner is learning.
- Not financial advice: the system is a research and learning tool. Real-money decisions stay with the owner.
