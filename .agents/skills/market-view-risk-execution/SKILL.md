---
name: market-view-risk-execution
description: Implement or review market-view position sizing, protective stops, order state transitions, risk vetoes, kill switches, and broker reconciliation without enabling live trading.
---

# Risk and execution

Read `../../../docs/05-risk-management.md`, actual `config/risk.yaml`, and the affected code.
This skill provides no authority to enable live orders or operate an account.

- Use the existing Signal -> RiskEngine -> ExecutionEngine -> Broker boundary. Recheck
  actual executable entry price, freshness, current cash, and portfolio state before entry.
- Size whole shares down from the configured loss budget, then cap by cash, exposure,
  liquidity, and portfolio heat. Distinguish planned stop risk from gap/stress loss.
  Include fees/slippage when describing risk; a stop cannot guarantee the maximum loss.
- Use the repository's configured 0.25% risk default and 0.5% ceiling unless the user has
  explicitly authorized a documented change. Third-party 1%-2%, Kelly, and 6%-8% heat
  defaults do not apply here.
- Entries need protective stops. Test placement failure, restart/crash recovery, changes
  after partial exits, and stop/target races. A paper process's simulated OCO is not a real
  broker-side guarantee. No stop placement may leave an entry unintentionally unprotected.
- A raised stop must not trigger on a low printed before the raise. Handle gaps and
  ambiguous intrabar ordering pessimistically; preserve exits during an entry halt.
- Reconcile UNKNOWN orders before retry; test idempotency, duplicate requests, rejects,
  missing fills, and broker/internal position mismatches. Persist enough state for recovery.
- Verify daily/weekly risk resets, loss caps, stale/missing feed behavior, and kill-switch
  behavior at the execution boundary. Use meaningful regression tests for changed behavior.

Optional references:

- `../../../.claude/skills/position-sizer/SKILL.md` for formulas only; override its market/risk defaults.
- `../../../.claude/skills/test-driven-development/SKILL.md` for risk/execution regressions.
- `../../../.claude/skills/llm-trading-agent-security/SKILL.md` for injection/isolation ideas;
  its autonomous wallet examples are outside this application's design.
