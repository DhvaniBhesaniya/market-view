# Running without an AI subscription

Updated 2026-11-19. The product target is an independently operated research and paper application,
not an endlessly self-modifying system or a guarantee of small losses and daily income.

## What runs without Gemini or a coding agent

Market-data ingestion, candle charts, indicators, descriptive market regimes, predefined strategies,
backtests, costs, risk checks, paper scheduling, journals, numeric weekly reviews, and the research
workflow are ordinary Python/TypeScript programs. They do not need an LLM key to execute.

Optional Gemini work could later summarize sourced news or explain a journal observation. That
integration is not implemented. It must remain advisory: no order authority, strategy-code rewriting,
risk-limit changes or unsourced market claims. Prices and deterministic checks continue if it fails.

Feed credentials, calendars, data corrections, software updates and operational incidents still need
maintenance. Removing AI dependence does not remove those responsibilities.

## Current market description

**Research lab** shows the rule-based regime, NIFTY close, ADX and VIX from completed stored daily
bars, with source, observation time and calendar age. Today's daily bar is excluded before the
regular session closes. This is a measurable description of trend/volatility, not comprehensive
understanding of every factor. News/event analysis and verified auction inputs remain unavailable.

## Bounded improvement workflow

Open **Research lab → Run research cycle**. **Enable weekly research** optionally schedules one
attempt on Sunday after 10:00 IST while the application is running. It starts disabled. The cycle
uses existing stored history; it does not silently fetch news or start a paper/live account.

The first protocol is **trend-adx-research-v1**, hypothesis A1 from guide 14:

- Baseline: the existing daily trend pullback strategy, using a frozen copy of its current parameters.
- Candidate: exactly the same rules plus completed-bar stock ADX(14) >= 20.
- Diagnostic neighbours: ADX thresholds 16 and 24 on **training only**. The candidate stays at 20;
  the software does not choose a threshold using validation results.
- Completed-bar signal, next-session execution, Indian charges, adverse slippage and current risk
  limits are inherited from the existing event-driven backtester.

The workflow:

1. Validate chronological train/validation bounds and refuse overlap with the locked test window.
   Cut data before computing hashes or strategy features. Forward paper history is excluded too.
2. Preserve exact stock and benchmark/context inputs, code files, parameter/config copies, dependency
   versions and input hashes under `data/research_runs/<id>/`. Subsequent data corrections cannot
   rewrite the old experiment. Raw market history is not altered by a research run.
3. Stop on unresolved missing/invalid data, including price-jump and zero-volume flags. A flag does
   not prove an error: genuine crashes, holidays, listing dates and corporate actions need appropriate
   classification. Do not delete inconvenient bars or invent pre-listing history to pass the check.
4. Compare the fixed baseline/candidate on training and validation. If the candidate misses the
   validation sample/profit-factor precheck, record rejection and skip further computation.
5. For a promising candidate, compute full research-history sample/drawdown, doubled charges and
   slippage, an operational run with breakers enforced, and the configured fixed-parameter yearly
   windows. The current protocol permits at most **18 simulations**, not an unlimited optimizer.
6. Record every attempted simulation and its outcome, including failures. Show rejection or
   **needs evidence**. No report can enable a strategy, alter risk limits or unlock live execution.

Identical data/code/config/dependencies reuse the existing report instead of retesting validation.
Failed/interrupted evidence remains visible. Changes create a new experiment; do not exploit that
mechanism to repeatedly select ideas on the same validation history. The fixed-rule windows reuse
previously studied research years and must not be described as newly untouched evidence.

The numeric screen checks validation PF >= 1.3, at least 100 full-history closed trades and 30
validation trades, max drawdown <= 15% at the **actual configured risk**, 60% positive yearly windows,
positive training neighbours, doubled-friction profitability, benchmark Sharpe and baseline
expectancy comparison, plus operational profitability. It is deliberately **not full Gate 3 approval**.
Only the added ADX threshold has neighbour tests here; broader parameter sensitivity and regime/
profit-concentration review remain part of full validation.
Historical membership, corporate actions, contract-note costs, benchmark consistency and independent
holdout/forward-paper requirements still apply. A simulation count or a high score is not an edge.

The active `config/strategies.yaml` and `config/risk.yaml` are untouched. The research candidate is
not registered as an enabled trading strategy. NIFTY constituents, ETFs, intraday cash, futures and
options require their own appropriate universes, contracts, sessions and execution models.

## NSE really does publish pre-open data

The [official pre-open market table](https://www.nseindia.com/market-data/pre-open-market-cm-and-emerge-market)
includes best bid/ask, indicative equilibrium price (IEP), indicative equilibrium quantity (IEQ), and
imbalance fields. The [mechanism description](https://www.nseindia.com/static/products-services/equity-market-pre-open)
also describes cumulative buy/sell quantities disseminated to the trading terminal.

These are quantities and indicative matching information, not the identities of future buyers or
probabilities of profit. Permitted orders can change during collection. The auction's clearing price
already reflects its order book; a trader cannot assume a fill at yesterday's close.

For illustration only: if yesterday's close was Rs 100 and the auction clears at Rs 110, buying in
that auction means paying the clearing price, not automatically earning Rs 10. A later fall to Rs 108
would lose Rs 2 per share before costs. Strong auction demand alone does not answer the exit decision.

A future experiment should compare a price/volume-only strategy with the same strategy plus verified
auction features: imbalance persistence, executable turnover relative to normal turnover, indicative
price stability and sector/index context. Record them **before** the decision cutoff and model actual
auction matching/partial fills. SL orders are not accepted during pre-open collection, so the current
continuous-session protective-stop workflow cannot simply be applied to an auction entry.

The current Upstox demand recorder is still labelled as unverified opening-auction observations.
A public webpage showing a field does not prove the same definition/timestamp is available through
our API. Do not substitute its closing-auction fields or ordinary depth for verified opening data.

## What the first actual audit found

The initial stored-data cycle recorded **52 findings across 49 loaded stock histories**, stopped
before backtesting, and did not promote anything. Examples include ADANIENT corporate-action-sized
jumps and zero-volume observations. JIOFIN had no history in the selected pre-2023 research window;
that requires checking listing dates and historical membership, not claiming data must exist then.
Some large moves may be genuine. These are review findings, not 52 confirmed bad prices.

This is why the application is **not yet ready to be called a validated autonomous trader**. The
next work is a point-in-time universe and corporate-action/data-quality review, then meaningful
strategy evidence, then the required forward paper period. More AI or parameter searches do not
replace those steps. No personal paper account or live trading was started for this audit.

## Verification

- Full Python suite: **215 passed** using isolated data, including causal filtering, fixed trial
  bounds, complete simulation branches, frozen risk/configuration, input pinning, holdout exclusion,
  interrupted evidence and visible scheduler failures.
- Frontend type checks, ESLint, **16 tests** and production build passed.
- Chromium: **24 browser checks passed**, including the new page, schedule controls, data-gate
  reports, result reuse, existing chart/paper flows and phone-width layout; no browser/HTTP errors.
- Ruff and changed-file whitespace checks passed. Existing library deprecation warnings remain.
- Actual stored-data research produced the blocked report described above. The personal paper
  account remains unstarted, active strategy/risk files unchanged, and `LIVE_TRADING=false`.
