# Independent research workflow

The owner wants routine operation independent of coding agents and LLM subscriptions.
Implement an auditable, bounded research cycle, not an unconstrained self-modifying trader.

- Describe current market regime from completed stored bars, with source/as-of and missingness.
- Run one preregistered hypothesis: unchanged trend pullback versus ADX(14) >= 20 filtering.
- Freeze parameters, source/config/code hashes, exact input snapshots, period boundaries and all
  attempted runs. Exclude the locked test window and forward paper evidence from idea selection.
- Fail closed on research-data problems. Persist blocked/failed/rejected attempts too.
- Compare train and validation, training-only ADX neighbours, doubled friction and fixed yearly
  validation windows. Do not choose a different ADX threshold after seeing validation.
- Separate preliminary numeric checks from full Gate 3 approval: historical membership,
  corporate actions, benchmark/cost verification and independent paper evidence remain required.
- Expose run/status/history and opt-in weekly scheduling through the web. No AI key required.
  No changes to active strategies, capital, risk limits or live broker locks.
- Verify deterministic indicators/filter causality, holdout refusal, input pinning, data vetoes,
  repeated-run accounting, schedule defaults and API/UI behavior using isolated data.

Implemented `/research` with one fixed hypothesis and opt-in Sunday scheduling. Verified with
215 Python tests, 16 frontend tests, production build, Ruff and 24 browser checks. The actual
stored-data audit recorded 52 findings and stopped before strategy trials; no personal paper/live
account was started. Guide 18 records remaining prerequisites rather than claiming full trading
readiness or that this one protocol can discover arbitrary profitable strategies.
