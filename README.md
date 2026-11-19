# market-view

A local web application for NSE strategy research, backtesting and simulated trading. Upstox supplies read-only market data. Live broker orders remain locked.

**No strategy has passed Gate 3.** A paper trial gathers operational and research evidence; it does not establish a profitable strategy. See [the validation gates](docs/04-roadmap.md).

Start it with `uv run market-view start` (it runs in that terminal; **Ctrl+C** or `uv run market-view stop` stops it, `uv run market-view status` checks it). Use **Data** to check Upstox and download history, then **Paper trading → Start research paper trial**. There is no trading CLI. Keep the application and computer running for scheduled monitoring and simulated stops.

The Paper page includes entry pause/resume, kill switch, saved stock-demand observations and a weekly mentor with actual closed-trade metrics, process reviews and three tracked priorities. Displayed demand is not a prediction or a verified opening-auction signal.

[Current operating guide and remaining work](docs/17-web-paper-automation.md).

**Research lab** runs a bounded baseline/candidate experiment and records data vetoes, failed trials
and validation evidence without an AI key. Optional weekly scheduling and market context are in
[the independent research guide](docs/18-independent-research.md). It cannot promote strategies.

Developer setup and verification:

```powershell
uv sync
uv run pytest
cd frontend
npm ci
npm run check
```

- ▶️ How to run it: [web paper guide](docs/17-web-paper-automation.md)
- 📘 Plan & docs: [docs/README.md](docs/README.md)
- 🤖 Claude Code guidance: [CLAUDE.md](CLAUDE.md)
- 🔬 Original research notes: [research/](research/)

Paper fills are simulations. Fees, gaps, quote sampling and outages can change outcomes; none of the software promises daily profits.
