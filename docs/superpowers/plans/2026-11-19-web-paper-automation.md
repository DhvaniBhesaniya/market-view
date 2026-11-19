# Web-operated paper research

The owner wants browser controls, scheduled paper research, and an honest weekly mentor.
No strategy has passed Gate 3. Automation must not imply a validated edge or enable live orders.

1. Verify actual Upstox read access. Use exchange last-trade timestamps, never fetch time,
   for executable-price freshness. Reject stale/expired signals and reconcile before entries.
2. Replace terminal-only paper scheduling with one application-owned worker, serialized jobs,
   persistent entry-enable state, pause entries while continuing exits, heartbeat and errors.
   Keep the current strategy/risk configuration. Do not start the owner's account as a test.
3. Build a deterministic weekly review from paper journal rows, prior-week comparison,
   annotated process evidence, three priorities, and an explicit insufficient-evidence rating.
4. Replace the user CLI with a desktop launcher and web controls for history/auth checks.
   Preserve research engine, validation gates, raw history and developer verification tools.
5. Explain pre-open observability separately from prediction. Do not present normal depth or
   closing-auction fields as a verified opening-auction feed. Document the remaining recorder,
   point-in-time experiments, realistic auction fills and promotion requirements.
6. Verify risk regressions, scheduler/restart behavior, journal accounting, API and browser UI.

Completed with 203 Python tests, 16 frontend tests, production build, Ruff and 22 browser checks.
Read-only Upstox access verified; no owner paper jobs or live orders started. The operating guide
is `docs/17-web-paper-automation.md`. Verified opening-auction signals, intraday/F&O strategy engines,
profitability validation and unattended service deployment remain separate work, explicitly described
in the guide rather than presented as completed features.
