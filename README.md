# market-view

A personal market view and strategy platform: AI-assisted trading **research, backtesting and paper trading** for Indian equities (NSE). Upstox provides market data; real orders (much later) will go through Groww or Upstox.

**Status:** the Phase 1–4 engine is built (data → strategies → honest backtests → risk engine → paper trading), with 53 tests. No strategy has passed validation yet. See [docs/04-roadmap.md](docs/04-roadmap.md).

```powershell
uv sync
uv run pytest
uv run mv doctor
uv run mv data download --source yfinance --start 2008-01-01
uv run mv backtest run --strategy all --period validate
uv run mv paper status
uv run mv ui        # web UI (first: cd frontend; npm install; npm run build) - see docs/15-web-ui.md
```

- ▶️ How to run it: [docs/12-paper-trading-runbook.md](docs/12-paper-trading-runbook.md)
- 📘 Plan & docs: [docs/README.md](docs/README.md)
- 🤖 Claude Code guidance: [CLAUDE.md](CLAUDE.md)
- 🔬 Original research notes: [research/](research/)

> Educational project. Not financial advice. Paper trading only. Live order code is locked behind `LIVE_TRADING=true` **and** `--live`, and isn't implemented until Phase 7.
