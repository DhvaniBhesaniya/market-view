---
name: market-view-trade-review
description: Review market-view trade journals, rejected signals, paper-versus-backtest drift, and losing-trade patterns to propose evidence-backed experiments.
---

# Review outcomes

Use the real journal/experiment schema in `src/market_view/journal.py` and saved reports.
Read `../../../docs/05-risk-management.md` for the weekly review process.

- State mode, strategy version, sample dates, closed trades, open positions, missing records,
  and comparison period. Compare like exposure, market regime, and costs.
- Separate execution errors, rule violations, expected losing trades, and a potential loss
  of statistical edge. A loss is not automatically a bad decision.
- Compute deterministic group statistics before using narrative explanations. Include net
  R, cost share, MAE/MFE, holding time, actual fills, rejects, and stop behavior.
- Include rejected/unfilled signals where evidence exists; label counterfactual fill and
  outcome assumptions. Avoid attributing a loss to a news event published after the signal.
- Prefer one testable change for the next experiment. Keep the existing strategy immutable;
  require a new version and fresh validation before changing an active portfolio.
- Do not automatically change risk limits, live parameters, or model weights from a review.

Optional references:

- `../../../.claude/skills/signal-postmortem/SKILL.md`
- `../../../.claude/skills/trader-memory-core/SKILL.md`

Use local NSE data and DuckDB records rather than configuring their optional FMP/US feeds.
Their signal hit-rate categories are not substitutes for net, risk-adjusted trade outcomes.
