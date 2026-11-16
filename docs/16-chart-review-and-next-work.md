# 16 — Chart review and remaining work

Reviewed 2026-11-16 against Claude's supplied handoff and the actual repository.

## What was checked and changed

The React/FastAPI research app, rule builder, backtest reports, validations and paper-account
views are present. The chart originally read only `1d` Parquet files and serialized every
timestamp as a business date. Its history buttons did not offer intraday candle intervals.

This change adds separate interval/history controls, custom minute/hour/day/week/month
aggregation, source selection and freshness information, an explicit single-symbol history
download job, missing-data states, and IST date/time hover labels. Indicators follow the
chosen timeframe; daily strategy signals remain on daily charts. Trading/risk settings and
real account state are unchanged. See [the UI guide](15-web-ui.md) for usage and limits.

## Where the chart prices come from

The rendering library is **TradingView Lightweight Charts v5.3**. Prices flow through:

`Yahoo Finance / Upstox -> native adapter -> saved Parquet -> chart API -> browser canvas`.

At review time `config/backtest.yaml` selects **yfinance**, no Upstox token is configured,
and the real stored dataset has only daily candles. RELIANCE has 4,647 saved daily rows,
from 2008-01-01 through 2026-11-05. The displayed chart is therefore saved historical data,
not a live price stream. The new download button can obtain the selected interval's data.

A read-only public Yahoo request returned **295 actual five-minute RELIANCE observations**
from 2026-11-11 09:15 IST through 2026-11-16 15:25 IST, with unique timestamps. Those smoke-test
results were not saved into the owner's market store. Browser tests use synthetic minute
observations only inside their isolated temporary workspace.

## How accurate is it?

The transformations and rendering are testable; the upstream prices still need independent
verification. There is no established accuracy percentage for this dataset. Yahoo's adapter
uses `auto_adjust=True` for history, including splits/dividends; broker raw charts can show
different price levels for that reason. Data can also be delayed, missing or revised.
[yfinance download documentation](https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html).

The existing validator was run read-only over **53 saved daily symbols** (normal index
zero-volume/jump exceptions excluded). It reported:

| Flag | Count | Interpretation |
| --- | ---: | --- |
| Price jump >20% | 49 | Corporate action, real exceptional move, or bad data; investigate individually |
| OHLC inconsistency | 7 | Reported high/low does not bound another price; requires source comparison |
| Zero volume | 896 | Could be suspended/non-trading observations or source issues; requires context |

These flags are not a measured price-error rate. In particular, **56 jump/OHLC observations
need review** before treating the history as verified. No flagged market row was edited.
Compare a representative dated sample and every flagged row against NSE/broker records,
using the same adjustment convention, timestamps, corporate actions and session definition.

## Remaining work, in priority order

1. **Data reliability:** resolve those flags; add point-in-time former index members and
   effective membership dates, corporate-action records, and pinned data versions per run.
2. **Execution costs and benchmark:** compare with a dated real contract note; resolve the
   previously identified MIS brokerage/exchange-fee/IPFT/DP assumptions; compare adjusted
   stock outcomes with a total-return or appropriately tradable benchmark.
3. **Live chart feed / seconds:** add an authenticated streaming recorder, freshness and
   reconnection handling, exchange/session timestamps and actual tick history. Aggregate
   seconds only from sufficiently granular observations; the present HTTP history adapters
   do not provide those bars.
4. **Intraday strategy support:** session-aware risk resets, intraday replay/fills, cutoff
   exits and failures, relative volume and appropriate fees. Charting five-minute candles
   does not validate the daily trading engine for five-minute execution.
5. **Paper operations:** resolve the documented daily-loss reset policy, then unattended
   operation, stale/missing-feed and reconciliation drills, and strategy validation gates.

No strategy has earned promotion based on these chart changes. The research queue remains
in [14 — Strategy research](14-strategy-research.md).

## Verification

The implementation adds regression coverage for same-day timestamps, OHLCV aggregation,
session anchors, calendar bars and underlying freshness, invalid/seconds requests, missing
data, finer-data download jobs, and time formatting independent of browser timezone. The
existing browser suite is extended with interval/hover and missing-data checks. Browser
verification also exercises the builder, backtests, paper views and phone layout on a
temporary copy of data rather than the real account.

Completed checks: **166 Python tests**, **16 frontend unit tests**, TypeScript checks, ESLint,
Ruff, the production build, and **21 full browser checks with zero browser/HTTP errors**.
A final focused chart browser run also passed all 3 checks. Five-minute hover and monthly
screenshots were visually inspected. Existing dependency deprecation warnings remain; no
new runtime dependency was added for this feature.
