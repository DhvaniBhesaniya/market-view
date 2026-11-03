# 10 — Tech Stack & Setup (this Windows machine)

## 1. Current machine state (checked 2026-11-03)

| Tool | Status |
|---|---|
| Git | ✅ 2.54 |
| Node.js / npm | ✅ v24 / 11 (used by the `npx skills` installer and the later React UI) |
| **Python** | ❌ **Not installed.** The `python` command is just the Microsoft Store alias |
| Docker Desktop | not checked; needed from Phase 4 |

## 2. Install steps (Phase 0)

Run in PowerShell:

```powershell
# 1. Python 3.12 (real installer, not the Store alias)
winget install -e --id Python.Python.3.12
#    then: Settings → Apps → Advanced app settings → App execution aliases → turn OFF "python.exe" & "python3.exe"

# 2. uv (fast Python package/venv manager)
winget install -e --id astral-sh.uv

# 3. Verify (open a NEW terminal)
python --version     # 3.12.x
uv --version

# 4. VS Code extensions: Python, Pylance, Jupyter, Ruff
# 5. (Phase 4) Docker Desktop
winget install -e --id Docker.DockerDesktop
```

## 3. Project bootstrap

```powershell
cd C:\dhvani-cs\personal\market-view
uv init --lib --name market-view --python 3.12     # creates pyproject.toml + src/market_view
uv add pandas numpy pydantic python-dotenv duckdb pyarrow plotly pandas-ta yfinance tqdm
uv add vectorbt scipy numba
uv add --dev pytest pytest-cov ruff pre-commit ipykernel import-linter
# later phases:
# uv add growwapi pyotp                  # Phase 4 broker
# uv add fastapi uvicorn sqlalchemy psycopg[binary] apscheduler streamlit python-telegram-bot   # Phase 4
# uv add scikit-learn lightgbm optuna mlflow shap anthropic transformers   # Phase 6
```
Alternatively, run the **`/setup`** skill. It creates a venv and installs the vectorbt/openalgo stack. On Windows, answer "no" to TA-Lib (or use `pip install ta-lib` with the prebuilt wheel).

`.env.example` (copy to `.env`, never commit `.env`):
```
LIVE_TRADING=false
GROWW_API_KEY=
GROWW_API_SECRET=
GROWW_TOTP_SECRET=
ANTHROPIC_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
DATABASE_URL=postgresql://market_view:market_view@localhost:5432/market_view
```

## 4. Stack by phase

| Layer | Phase 0–3 | Phase 4–5 | Phase 6+ |
|---|---|---|---|
| Language | Python 3.12 + uv | same | + Rust only if profiling demands it |
| Data store | Parquet + DuckDB | + PostgreSQL/TimescaleDB (Docker) | + Redis (cache/pubsub) if needed |
| Backtesting | vectorbt + own event engine | same | same |
| Scheduling | manual / CLI | APScheduler in the app | same |
| API | — | FastAPI | same |
| UI | Jupyter + Plotly | Streamlit | React + TypeScript + TradingView Lightweight Charts |
| Notifications | — | Telegram bot | + email |
| ML | — | — | scikit-learn, LightGBM, Optuna, MLflow, SHAP |
| LLM | Claude Code (dev) | — | Anthropic SDK (Claude) + FinBERT |
| Deployment | laptop | Docker Compose on a static-IP VPS | + Prometheus/Grafana |
| Quality | ruff, pytest, pre-commit | + import-linter (dependency rules), CI on GitHub Actions | same |

## 5. First week's tasks (concrete)

1. Install Python + uv (above). Create the project with `uv init`. Make the first commit.
2. Create `tests/test_smoke.py` → `uv run pytest` passes.
3. Notebook `notebooks/01_first_look.ipynb`: download `^NSEI` and `RELIANCE.NS` daily since 2015 with yfinance; plot candles + 20/50 EMA + volume.
4. Ask Claude: `/quick-stats RELIANCE` to see a first EMA-crossover result, then ask *why* the numbers look the way they do (costs, drawdown, trade count).
5. Read Varsity Module 1, chapters 1–6.
6. Place one tiny real delivery order in the Groww app and reconcile the contract note by hand.

## 6. Using Claude Code effectively on this project

- Start sessions with: *"Read CLAUDE.md and docs/04-roadmap.md; we're in Phase N; today I want to build X."*
- For features: `writing-plans` → `test-driven-development` → `verification-before-completion`.
- For backtests: `/backtest`, `/optimize`, `/strategy-compare` for exploration, then `backtest-expert` to stress-test.
- For any risk/execution code: ask for a `secure-code-guardian` + `llm-trading-agent-security` review.
- Keep `CLAUDE.md`'s "Current phase" line updated.
- Update skills occasionally: `npx skills update -p`, then **review the diff** (third-party skills run with full permissions).
