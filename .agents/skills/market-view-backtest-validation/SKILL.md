---
name: market-view-backtest-validation
description: Design and assess market-view backtests, walk-forward experiments, sensitivity studies, and promotion evidence while controlling leakage, costs, and repeated testing.
---

# Validate a strategy

Read `../../../docs/06-strategies-and-validation.md` and the current configuration first.
Implementation lives in `src/market_view/backtest/` and `src/market_view/validation/`.

1. Record a hypothesis, baseline, immutable version, data snapshot/hash, universe, all tried
   variants, and pass/reject criteria. The experiment log's git SHA alone does not pin data.
2. Check causal indicators and executable timing. Daily close -> next session open; intraday
   bars need session-aware exits and risk resets. Do not assume a daily engine supports MIS.
3. Include current and historically applicable charges, spread, adverse slippage, gaps,
   rejections, and partial fills where material. Check portfolio and per-strategy limits.
4. Separate exploratory research (breakers recorded) from operational simulation
   (`enforce_breakers=True`); report both for candidates and label them clearly.
5. Evaluate chronological validation, walk-forward windows, parameter neighborhoods, regime
   dependence, concentration of profits, and at least doubled execution friction. Report
   costs, trades, drawdown, expectancy, profit factor, exposure, and comparable benchmarks.
6. Use day/week block resampling for correlated trades where possible. Existing independent
   trade-R bootstrap is a sensitivity tool, not a calibrated forecast of live risk.
7. The configured 2023-2025 test window stays locked until the existing gate permits it.
   Do not repeatedly choose new ideas using an already inspected holdout; reserve new forward
   evidence as required. Paper strategies must meet the existing duration AND trade-count gate.

Document unresolved survivorship, corporate actions, end-of-period open positions,
inconsistent fees, and timestamp uncertainty as limitations to the conclusion.

Useful references:

- `../../../.claude/skills/backtest-expert/SKILL.md`
- `../../../.claude/skills/backtesting-frameworks/SKILL.md`
- `../../../.claude/skills/vectorbt-expert/rules/walk-forward.md`

Vectorbt is optional screening, not the project's execution truth. Do not install OpenAlgo,
TA-Lib, or replace native indicators merely to follow a generic example. A third-party
evaluation script's DEPLOY verdict never overrides this repository's evidence gates.
