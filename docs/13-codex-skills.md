# 13 — Codex skills for market-view

Prepared 2026-11-16. This is the project skill setup and the reasoning behind it.

## Installed and ready for the next turn

Codex discovers repository skills under `.agents/skills/`; `AGENTS.md` supplies project
context and routing. This is the documented repository location, so no global configuration
or personal skill directory needs changing. Skills are reusable instructions and resources;
they do not train the model or supply a profitable trading edge.
[Official OpenAI skill documentation](https://learn.chatgpt.com/docs/build-skills).

Seven instruction-only skills adapt the workflows to the existing software:

| Skill | Purpose | Example request |
| --- | --- | --- |
| `market-view-strategy-research` | Compare approaches and specify causal, testable rules | “Design an NSE pre-open/ORB experiment.” |
| `market-view-backtest-validation` | Costs, leakage, robustness, walk-forward, promotion evidence | “Try to disprove trend_v2.” |
| `market-view-market-data` | NSE timestamps, history, feeds, auctions, corporate actions | “What data is missing before an intraday backtest?” |
| `market-view-risk-execution` | Sizing, stops, order state, recovery, kill switch | “Review stop handling after partial exits.” |
| `market-view-trade-review` | Journal evidence, losing trades, operational drift | “Explain this month's paper/backtest difference.” |
| `market-view-app-development` | Existing Python/FastAPI and React/TypeScript/chart implementation | “Build a signal explanation panel.” |
| `market-view-ai-research` | Advisory journal/news/ML experiments with baselines | “Design a news filter without giving an LLM broker access.” |

Four official OpenAI skills were installed with Skill Installer from
[`openai/skills`](https://github.com/openai/skills), pinned to revision
`49f948faa9258a0c61caceaf225e179651397431`:

| Skill | Why useful | Dependency/activation boundary |
| --- | --- | --- |
| `playwright` | Inspect real browser flows, screenshots, charts, and errors | Needs Node/npm and a browser runtime when used |
| `jupyter-notebook` | Reproducible requested research/learning notebooks | Notebook execution needs the relevant Python kernel/packages |
| `security-best-practices` | Requested secure coding reviews for Python/TypeScript | Use its stated review triggers |
| `security-threat-model` | Requested analysis of assets, trust boundaries, and abuse paths | Use for an actual threat-model request |

These skills will be available on the next turn. If discovery does not refresh, restart the
Codex session. Mention `$market-view-strategy-research`, for example, or let Codex select a
matching skill. Installation did not install application packages, run trading jobs, connect
accounts, or change broker credentials. Browser/kernel setup can happen when a task needs it.

The official skills contain global-path/Bash examples. In this repository resolve resources
under `.agents/skills/<name>/` and translate shell syntax for PowerShell. For example the
Playwright wrapper invokes `npx --yes --package @playwright/cli playwright-cli`; the installed
notebook helper is `.agents/skills/jupyter-notebook/scripts/new_notebook.py`.

## Existing library: reuse selectively

The project already contains **39** `.claude/skills/*/SKILL.md` files. They remain intact.
The new project workflows route to relevant material rather than installing 39 overlapping
top-level triggers. Inventory, manifests, and selected relevant instructions were reviewed;
this is not a comprehensive security audit of every bundled script or remote dependency.

| Existing skills | Use here | Adaptation or limit |
| --- | --- | --- |
| `backtest-expert`, `backtesting-frameworks` | Hypotheses, biases, causal fills, stress tests | Existing gates take precedence over generic scores/verdicts |
| `vectorbt-expert`, `backtest`, `optimize`, `strategy-compare`, `quick-stats` | Optional rapid research/screening | Current event-driven engine remains truth; native indicators/costs first; do not install OpenAlgo/TA-Lib just for an example |
| `position-sizer` | Fixed-fractional/ATR formula references | Use current 0.25% project risk, 0.5% ceiling, 1.5% heat; whole NSE shares; no imported Kelly/US defaults |
| `technical-analyst` | Explain trends, support/resistance, alternate scenarios | A chart narrative does not establish calibrated probabilities or a tradable edge |
| `signal-postmortem`, `trader-memory-core` | Thesis lifecycle, MAE/MFE, outcome reviews | Local NSE data/DuckDB; no need for their FMP feeds |
| `trader-in-scanner`, `trader-in-news`, `trader-in-analyst`, `trader-in-insiders` | India-specific ideas, filings, events, flows | Check data timestamps, scripts, access terms, and source facts; public disclosures are delayed evidence, not live identity of buyers |
| `trader-in-entry`, `trader-in-exit`, `trader-in-budget`, `trader-in-risk`, `trader-in-alerts`, `trader-in-timemachine` | Learning/reference for intraday plans | Their `trader/` JSON workflow is separate from our engine; no broker handoff; short bootstrap histories do not validate a strategy |
| `python-pro`, `pandas-pro`, `fastapi-expert` | Backend and data implementation | Follow installed versions and existing interfaces, not copied sample code blindly |
| `react-expert`, `typescript-pro`, `lightweight-charts`, `shadcn` | Existing web frontend and financial charts | Inspect current package/component API versions first |
| `systematic-debugging`, `test-driven-development`, `verification-before-completion`, `writing-plans` | Diagnosis, meaningful regressions, verification, planning references | Keep work proportional; do not infer permission for commits, delegation, or extra installation from examples |
| `secure-code-guardian`, `llm-trading-agent-security` | Input/credential boundaries and requested security work | Crypto signing and execution-capable AI examples are outside this application's design |
| `websocket-engineer`, `postgres-pro`, `ml-pipeline`, `rust-engineer`, `setup` | Conditional future infrastructure/reference | No distributed stack, database migration, Rust rewrite, or environment reset without a concrete task need |

The recorded upstream sources for part of the existing library include
[marketcalls/vectorbt-backtesting-skills](https://github.com/marketcalls/vectorbt-backtesting-skills),
[tradermonty/claude-trading-skills](https://github.com/tradermonty/claude-trading-skills),
and [wshobson/agents](https://github.com/wshobson/agents). The India pack was already present;
it was not freshly downloaded or re-executed during this setup.

## Useful material deliberately kept as references

The [official Upstox skill](https://github.com/upstox/upstox-skills/blob/master/skills/upstox/SKILL.md)
includes direct live order placement and account mutation. It was inspected, but not installed
as an execution skill: it conflicts with this project's AI/broker separation. Its read-only
[market-data reference](https://github.com/upstox/upstox-skills/blob/master/skills/upstox/references/market-data.md)
and [streaming reference](https://github.com/upstox/upstox-skills/blob/master/skills/upstox/references/websocket.md)
can inform adapter work after checking current official API documentation. The existing native
adapter remains the integration point.

No `trader-in-broker`, autonomous trading/wallet connector, “guaranteed profit” pack, or
unneeded deployment/cloud skill was installed. This selection covers useful workflows
without adding order authority or a large unrelated instruction catalog.

## Maintenance and provenance

`.agents/skills-lock.json` records the source revision and file hashes for the new skills,
plus hashes of existing reference manifests. The original `skills-lock.json` is preserved.
Before an update, inspect its diff and changes to bundled scripts. Existing skill licenses
and attribution remain in place; the official downloaded directories retain their files.

Validation checks manifests, names, local reference paths, and whether bundled executable
helpers can be inspected without running external services. It does not prove every future
workflow is correct, nor certify a trading strategy.
