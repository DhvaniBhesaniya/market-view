# CLAUDE.md — market-view

Personal **AI-assisted trading research, paper-trading and (eventually) execution platform** for Indian equities (NSE), using the owner's existing **Groww** broker account.

The owner is a software engineer who is **new to trading**. The project serves two goals: building a working system, and learning trading through it. When you explain something, teach the *why* (market mechanics, statistics), not just the code.

Full plan lives in [docs/](docs/README.md). Read [docs/04-roadmap.md](docs/04-roadmap.md) to know which phase we are in before starting work.

---

## Current phase

> **Phase 0 — Setup & learning.** No application code exists yet. Update this line when a phase gate in `docs/04-roadmap.md` is passed.

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
| Language (research, engine, AI) | **Python 3.12** managed by **uv** | Python is *not yet installed* on this machine — see `docs/10-tech-stack-and-setup.md` |
| Broker | **Groww Trade API** (`growwapi` SDK) | ₹499+GST/month subscription; static IP needed only for order placement |
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

## Repository layout (target)

```
market-view/
├── CLAUDE.md
├── docs/                    # the plan (read first)
├── research/                # original research notes (chat-gpt, deepseek, my-view)
├── src/market_view/
│   ├── data/                # downloaders, normalizers, storage (DuckDB/Postgres)
│   ├── indicators/
│   ├── strategies/          # Strategy base class + implementations (pure, no I/O)
│   ├── backtest/            # event-driven engine, cost model, metrics
│   ├── validation/          # walk-forward, Monte Carlo, sensitivity
│   ├── risk/                # risk engine, position sizing, kill switch
│   ├── broker/              # Broker interface, PaperBroker, GrowwBroker
│   ├── execution/           # order state machine, reconciliation
│   ├── journal/             # trade journal, MAE/MFE, post-mortems
│   ├── market_context/      # regime, macro, FII/DII, news, sentiment
│   ├── ai/                  # LLM research assistant, ML models (advisory only)
│   └── api/                 # FastAPI app
├── notebooks/               # exploration only; logic graduates into src/
├── backtesting/             # vectorbt scripts produced by the /backtest skills
├── tests/
├── data/                    # gitignored: raw/, parquet/, duckdb files
└── frontend/                # later
```

## Coding conventions

- Type hints everywhere; `pydantic` models for `Candle`, `Signal`, `Order`, `Fill`, `Position`, `Trade`.
- Money and prices: use `Decimal` in the risk/execution/accounting path; `float`/numpy is fine in research and vectorized backtests.
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
| `llm-trading-agent-security` | Any time an LLM is near order flow: injection, limits, circuit breakers (examples are crypto; apply the principles) |

**Engineering**
`python-pro`, `pandas-pro`, `fastapi-expert`, `postgres-pro`, `websocket-engineer` (Groww live feed), `ml-pipeline`, `react-expert`, `typescript-pro`, `rust-engineer` (later), `test-driven-development`, `systematic-debugging`, `secure-code-guardian`, `writing-plans`, `verification-before-completion`.

Notes on third-party skills:
- `trader-memory-core` / `technical-analyst` contain US-market (FMP API) adapters. Do not configure FMP keys; use our own Indian data.
- `setup` installs TA-Lib from source on Linux/macOS. On Windows, skip TA-Lib or use the prebuilt wheel.

---

## Commands

_To be filled in as they exist._ Expected:

```bash
uv sync                          # install deps
uv run pytest                    # tests
uv run python -m market_view.data.download --universe nifty50 --interval 1d
uv run python -m market_view.backtest run --strategy trend_v1
uv run python -m market_view.paper run            # paper trading (default mode)
```

## How to work in this repo

- Before a non-trivial feature, use `writing-plans` and check it against the current phase in `docs/04-roadmap.md`. Don't build Phase-5 features in Phase 1.
- When a result looks too good (Sharpe > 3, win rate > 75%, smooth equity curve), assume a bug or bias first (look-ahead, survivorship, missing costs).
- Explain trading concepts briefly when you introduce them; the owner is learning.
- Not financial advice: the system is a research and learning tool. Real-money decisions stay with the owner.
