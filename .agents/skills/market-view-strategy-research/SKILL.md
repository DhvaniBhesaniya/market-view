---
name: market-view-strategy-research
description: Research Indian equity trading approaches and write testable strategy specifications for market-view, including swing, intraday, pre-open, and future derivatives experiments.
---

# Strategy research for market-view

Use this for deciding what to test, not for claiming a profitable strategy from a screen.

- Read `../../../docs/14-strategy-research.md` for the research queue and evidence boundaries,
  and `../../../docs/04-roadmap.md` for existing promotion gates.
- Separate instrument (cash, futures, options) from holding period (intraday, swing, rotation).
  State capital, data, execution, and operational requirements; ask for account-specific
  constraints only when a personalized decision needs them.
- Browse current primary sources for exchange mechanics, costs, broker features, and research.
  Prefer NSE/SEBI, the broker's documentation, and original authors. Date every unstable claim.
  Papers from US stocks or futures motivate tests; they do not validate an NSE cash strategy.
- Specify the universe as it existed at the time, information cutoff, exact entry trigger and
  executable price, initial stop, target/trail, time exit, position sizing, exclusions, costs,
  and failure criteria. Label numerical starting parameters as hypotheses.
- Change one hypothesis at a time against the existing version. Record negative trials too.
  Do not optimize on the locked test period or change active trading configuration in research.
- For pre-open ideas, distinguish orders, auction matched quantity, and aggressive executed
  flow. Use timestamped observations; today's OHLCV cannot reconstruct old auction imbalance.
- Deliver a strategy card plus a smallest useful experiment, with missing data and engine work
  identified explicitly. Define what evidence would reject the idea before running it.

Optional existing references, read only when relevant:

- `../../../.claude/skills/backtest-expert/SKILL.md`: hypothesis and robustness methodology.
- `../../../.claude/skills/technical-analyst/SKILL.md`: chart vocabulary, not probabilities.
- `../../../.claude/skills/trader-in-scanner/SKILL.md`: NSE screening ideas; its external data
  fallbacks and scripts need a separate review before execution.
- `../../../.claude/skills/trader-in-news/SKILL.md`: source-backed event context.

Retain the project's risk limits and broker separation when using those references.
