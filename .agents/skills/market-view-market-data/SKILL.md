---
name: market-view-market-data
description: Build or assess market-view NSE data ingestion, Parquet history, live feeds, auction observations, corporate actions, and session calendars with causal timestamps and source provenance.
---

# NSE data in market-view

Inspect `src/market_view/data/`, `src/market_view/calendar.py`, and the actual source settings.
Use the existing normalized OHLCV interface; distinguish stored bar-open timestamps from the
time when a completed bar becomes available to a strategy.

- Keep raw downloads append-only and log revised clean values. Pin a data version for each
  experiment rather than assuming a mutable clean Parquet file is reproducible.
- Distinguish adjusted Yahoo data from unadjusted broker candles. Check splits, bonuses,
  dividends, symbol/ISIN changes, delistings, and historical membership with effective dates.
- Verify freshness from exchange timestamps and last-traded time, not the HTTP fetch time.
  Missing/stale quotes must have explicit policy before they can reach an entry.
- Check the exchange calendar and current session status, including auction eligibility and
  broker cutoffs. Do not assume every security has the same closing session.
- Intraday relative volume compares the same elapsed session window with prior sessions;
  never compare 09:30 volume with a full day's volume or rank on end-of-day activity.
- Pre-open imbalance research needs actual timestamped auction snapshots with field
  semantics, coverage, and entitlement checked. OHLCV does not contain order cancellations,
  queue history, or historical auction demand. Do not fabricate those fields.
- Read broker documentation for authentication, entitlements, rate limits, pagination, and
  replay behavior. Reuse approved authenticated adapters; do not rely on keyless endpoints
  or scraping fallbacks merely because a third-party skill happens to use them.

Read `../../../docs/14-strategy-research.md` for identified data prerequisites and costs.
For dataframe implementation, optionally read `../../../.claude/skills/pandas-pro/SKILL.md`.
For an actual streaming task, optionally read
`../../../.claude/skills/websocket-engineer/SKILL.md`; Redis and distributed services are not
requirements for this modular monolith.

Official read-only references for an Upstox task:

- https://upstox.com/developer/api-documentation/v3/get-market-data-feed/
- https://github.com/upstox/upstox-skills/blob/master/skills/upstox/references/market-data.md
- https://github.com/upstox/upstox-skills/blob/master/skills/upstox/references/websocket.md

Check these against current API docs. The upstream full `upstox` skill also contains direct
order/account mutation workflows; it is not installed or delegated execution authority here.
