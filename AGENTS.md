# Working on market-view

Personal NSE trading research and paper-trading software. The owner is learning trading;
explain the market reason for a design as well as the implementation.

## Start with the actual state

- Read `CLAUDE.md` for project context and `docs/04-roadmap.md` for evidence gates.
- Inspect the relevant code before relying on phase labels or test counts in old documentation.
- Python engine: `src/market_view/`; configuration: `config/`; tests: `tests/`.
- Web API: `src/market_view/api/`; inspect `frontend/package.json` for the current UI stack.
- Preserve existing user changes. Research requests do not authorize changing enabled strategies,
  risk limits, credentials, or running paper/live trading jobs.

## Trading invariants

- Paper is the default. Keep the live broker methods locked; AI research never gets broker tools.
- Strategies emit signals; the risk engine sizes/vetoes entries; execution owns order submission.
- A close-based signal can execute only after the close is known. Include costs and adverse fills.
- Preserve raw data snapshots and immutable experiment/strategy versions.
- Do not use the locked test period for idea selection. Follow the existing validation gates.
- Risk examples use the repository's limits, not third-party skills' US-market or Kelly defaults.
- Distinguish a researched hypothesis, an implemented strategy, and a validated strategy.
  A skill, paper, or chart pattern does not establish an edge in this account.

## Codex skills

Project skills are in `.agents/skills/`. Select the narrow workflow needed for the task.

| Work | Skill |
| --- | --- |
| Compare cash/F&O, swing/intraday, or specify a new trading idea | `market-view-strategy-research` |
| Backtests, robustness, parameter searches, promotion evidence | `market-view-backtest-validation` |
| Candles, corporate actions, pre-open data, feeds, calendars | `market-view-market-data` |
| Stops, sizing, order state, reconciliation, kill switch | `market-view-risk-execution` |
| Journal review, losing trades, paper/backtest drift | `market-view-trade-review` |
| Python/FastAPI, React/TypeScript/charts, implementation | `market-view-app-development` |
| LLM research, news tagging, ML ranking | `market-view-ai-research` |
| Browser interaction and visual checks when a running UI exists | `playwright` |
| Requested `.ipynb` experiments or tutorials | `jupyter-notebook` |
| Requested secure coding review or threat model | `security-best-practices`, `security-threat-model` |

The existing `.claude/skills/` library remains useful reference material. Its instructions
are not automatically Codex installations. The project skills link to relevant references
and explain adaptations; read only the part needed. See `docs/13-codex-skills.md`.

Third-party tool names, `${CLAUDE_SKILL_DIR}`, global installation paths, and Bash examples
must be resolved to the actual installed files and PowerShell environment. Do not execute a
bundled script without checking its behavior, dependencies, credentials, and output paths.
Do not add dependencies or infrastructure merely because an example uses them. Skills do
not grant permission to place trades, contact people, or change external accounts.

## Verification

Use `uv run pytest` for relevant engine changes and the configured frontend scripts for UI
changes. Risk, cost, execution, and backtest fixes need meaningful regression coverage.
For documentation/skill-only work, validate skill manifests and local links rather than
rerunning the trading engine. Report which checks actually ran.
