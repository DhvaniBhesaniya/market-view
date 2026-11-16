# 14 — What to trade and how to find a strategy worth using

Research date: **2026-11-16**, India. These are research priorities and proposed paper-test
rules, not a claim of profitability or instructions to place a trade. No new strategy was
enabled and no backtest, paper job, or live order was run for this document.

## 1. Recommendation for this software

Build evidence in this order:

1. **Repair/verify the research foundation**: historical universe, corporate actions, costs,
   data snapshots, comparable benchmarks, and operational simulation.
2. **Cash-equity swing research**: small changes to existing trend/breakout rules, plus a
   slower momentum/rotation comparator. The daily engine and data already fit much of this.
3. **One intraday cash experiment**: pre-market candidate selection followed by a confirmed
   opening-range breakout. First add the data and session-aware engine support it needs.
4. **Event and range strategies** after timestamped event data and more intraday history.
5. **Futures/options research later**, in a separate instrument-aware simulator. A stock
   signal is not an options strategy merely because its direction is correct.

This ordering is an engineering/research judgment based on the owner's beginner status and
the existing system, not proof that swing trading has higher future returns.

“F&O” describes instruments. “Intraday” describes holding time. Cash shares, futures, and
options can each be traded intraday; some can also be held for longer. “Daily candles” can
mean swing trading over several days and does not mean closing every position each day.

| Approach | Main attraction | Main difficulty | Priority |
| --- | --- | --- | --- |
| Cash swing, days/weeks | Fits the current engine; more time for decisions | Overnight gaps, delivery costs, changing regimes | First |
| Cash momentum rotation, weeks/months | Lower decision frequency; explicit ranking | Portfolio rebalance support, turnover, concentration and reversal risk | First research comparator |
| Intraday cash ORB/VWAP | No intended overnight holding; measurable same-day rules | Feed quality, spread, fills, timing, repeated false breaks | Paper-only second track |
| Pre-open imbalance | Can describe auction demand and price discovery | Orders change; data history/coverage; not proof of continuation | Feature experiment |
| Futures | Direct directional exposure | Leverage, lot granularity, margin, expiry/rolls, mark-to-market | Later |
| Long options | Premium paid bounds the standalone contract loss | Time decay, volatility repricing, spread, strike/expiry choice | Later |
| Option spreads/selling | Can express volatility/range hypotheses | Multi-leg fills, margin, expiry/assignment and tail exposure | Later; no naked selling as a beginner baseline |

SEBI's August 2026 study reports **87.7%** of individual equity-derivatives traders were
loss-makers in FY26. Its July 2024 cash study found **71%** of individual intraday cash
traders lost money in FY23. These are different cohorts and periods, not a controlled
comparison proving that any alternative is safe. They are strong reasons to require evidence
before risking money.
[SEBI FY25–FY26 study](https://www.sebi.gov.in/reports-and-statistics/research/aug-2026/study-profitability-of-individual-traders-in-the-equity-derivatives-segment-fy25-fy26-_103835.html?outputType=chromeless),
[study PDF](https://www.sebi.gov.in/sebi_data/attachdocs/aug-2026/1787233506209.pdf),
[SEBI intraday cash study](https://www.sebi.gov.in/media-and-notifications/press-releases/jul-2024/sebi-study-finds-that-7-out-of-10-individual-intraday-traders-in-equity-cash-segment-make-losses_84948.html).

## 2. What “high buying in pre-market” actually tells us

Separate three observations:

- **Auction orders**: quantities people currently intend to buy/sell at different prices.
- **Matched quantity**: what can execute at the auction's equilibrium price.
- **Aggressive continuous-session flow**: trades initiated against the available ask/bid.

Every completed trade has both a buyer and a seller. More displayed bids does not identify
institutional buyers or guarantee more future buying. Size also needs normalization: a large
company naturally trades more shares than a small one.

NSE sets an auction price using executable quantity and tie-breaking rules. Its current
cash pre-open page permits order changes during defined collection phases, with random
closure before matching; market-order changes are restricted during the later phase. The
indicative book is not a fixed commitment to support the price throughout the day.
[NSE pre-open mechanics](https://www.nseindia.com/static/products-services/equity-market-pre-open).

Treat pre-open strength as a candidate filter, then test whether actual trading confirms it.
A useful observation set is gap versus adjusted prior close, matched auction turnover versus
its own history, normalized imbalance, spread, price stability across snapshots, verified
catalyst, and sector/index direction. Raw buy/sell ratio alone is the control experiment.

If both comparable buy and sell quantities exist, a candidate feature is
`imbalance = (buy_qty - sell_qty) / (buy_qty + sell_qty)`, with zero/missing denominators
treated as missing. Field definitions and collection timestamps must be consistent. A top-five
depth imbalance is not the same field as unmatched auction imbalance.

Current Upstox V3 documentation exposes pre-open status and indicative equilibrium price;
it also documents auction-related fields for CAS. That does **not** establish historical
pre-open imbalance availability or entitlement for this account. Verify the required fields
on an authorized feed before choosing a provider or making a historical claim.
[Upstox V3 feed](https://upstox.com/developer/api-documentation/v3/get-market-data-feed/).

Daily/5-minute OHLCV cannot reconstruct historical auction orders or cancellations. Start a
timestamped recorder if necessary; test the OHLCV-only version separately. Never backfill
missing imbalance with today's book or infer “smart money” identities from bulk-deal reports
published after the decision.

## 3. Small, preregistered strategy queue

All thresholds below are **starting hypotheses**. Select one candidate at a time; log every
variant. ATR means average true range; EMA/SMA are moving averages; R is the initial planned
price risk per share. A +2R target is twice the entry-to-stop distance before costs.

### A0 — Controls and comparators

- Retain unchanged `trend_v1`, `breakout_v1`, and `meanrev_v1` as controls.
- Compare with a NIFTY total-return series or a tradable broad-market ETF net of its real
  spread/fees/tracking effects, plus cash. Adjust benchmark risk/exposure when claiming skill.
- The current NIFTY price-index comparison omits dividends, whereas Yahoo auto-adjusted
  stock prices include their effect. Resolve this mismatch before interpreting outperformance.
- Measure capital utilization and open positions at period end; closed-trade metrics alone
  are not the complete portfolio result.

### A1 — Trend pullback with one added regime filter

**Hypothesis:** the existing pullback signal loses less in choppy markets when trend strength
is required. First compare `trend_v1` against the same rules with **ADX(14) > 20** only.

- Keep the existing EMA, pullback, RSI, volume, and NIFTY filters unchanged for that test.
- Decide on completed daily bars; enter at the next session's executable open, with modeled
  slippage. Recheck risk using the actual fill; skip gaps through the stop or unacceptable size.
- Keep the signal-time stop: the lower of the five-bar low and close minus 2 ATR, as v1 uses.
- Keep the existing half-exit at +1.5R and subsequent stop/EMA/time-exit rules unchanged.
- Separately, as another logged hypothesis, test the `TREND_UP` regime restriction. Do not
  silently combine both improvements after observing which history they fit.

This is immediately researchable on daily data. A lower drawdown with almost no trades is
not sufficient evidence of an improvement.

### A2 — Breakout followed by a successful retest

**Hypothesis:** waiting for a retest reduces false entries enough to justify missed moves.

- At a completed close, record a break above the prior 20-session high, with the existing
  volume/ADX/market filters. Freeze that breakout level.
- During the next three completed sessions, look for a low within 0.5 signal-day ATR of
  that level and a close back above it. Cancel if it closes below level minus 1 signal-day ATR.
- Only after a confirming close, enter next session open; never claim a fill at the retest
  price earlier in the confirmation bar.
- Stop below the retest low minus 0.1 confirmation-day ATR. Reject if entry is already at or
  below the stop or sizing/cost checks fail. Trail using highest high minus 3 ATR, raised only
  after a completed bar, with a 20-bar time exit. Baseline has no fixed target.
- Compare with unchanged `breakout_v1`; report missed winners and cost changes too.

Needs a small causal state machine inside a versioned strategy; data are daily.

### A3 — Slower volatility-adjusted momentum rotation

**Hypothesis:** persistent relative strength can be captured with lower turnover than short
swing trades. NSE Indices itself defines momentum using six- and twelve-month returns
adjusted for volatility; this establishes a reproducible family to investigate, not the
profitability of our proposed portfolio.
[NSE momentum factsheet](https://www.niftyindices.com/Factsheet/Factsheet_Nifty200_Momentum30.pdf),
[NSE index methodology](https://www.niftyindices.com/Methodology/Method_NIFTY_Equity_Indices.pdf).

- At each completed month-end, eligible historical constituents need 252 sessions of data
  and the project's liquidity filters. Initial comparable universe: historical NIFTY 50.
- Rank `0.5*z(return_126 / vol_252) + 0.5*z(return_252 / vol_252)`, using only completed
  bars and cross-sectional z-scores. Exclude invalid/zero volatility.
- Hold up to five leaders, maximum two per sector; keep a held name until rank falls below
  the top ten to limit turnover. The ordinary risk/cash caps can leave fewer than five names.
- Make changes at the next session's open. Use an initial stop at signal close minus 3 ATR;
  subsequently trail highest completed close minus 3 ATR, effective next session. No fixed
  profit target. Exit on rank removal, stop, or the time of a scheduled risk-off rebalance.
- For the initial market filter, rebalance into cash if NIFTY is below its 200-day SMA at
  month-end. Compare the same portfolio without that filter as one separate experiment.
- Include a tradable ETF rotation variant only after instrument-specific costs are supported.

This is **not** an exact replication of NSE's index selection, weights, or semiannual review.
It needs cross-sectional ranking/rebalance support and point-in-time membership; the current
per-symbol signal interface does not supply that portfolio construction automatically.

### B1 — Pre-market shortlist + 15-minute opening-range breakout

**Hypothesis:** confirmed momentum in unusually active liquid stocks performs better than
buying the largest pre-open bid quantities indiscriminately. Research on US “stocks in play”
motivates the test, but its results cannot be transferred to NSE. A separate 2026 US futures
preprint reports negative ORB conclusions after costs; both are market-specific backtests.
[Original stocks-in-play paper](https://concretumgroup.com/wp-content/uploads/2026/02/A-Profitable-Day-Trading-Strategy-For-The-U.S.-Equity-Market.pdf),
[contrasting futures preprint](https://ssrn.com/abstract=7428398).

Initial **long-only cash paper specification**:

1. Before the open, freeze a liquid eligible universe using information available then.
   Exclude restricted/circuit-locked names, unavailable data, and corporate-action gaps.
   Use no leverage in the first comparison.
2. Record 09:15–09:30 completed trades/bars as the opening range. Freeze its high and low.
3. From 09:30 onward, require a completed five-minute close above the frozen high and
   above session VWAP. Require cumulative volume at that time >= 1.5 times the median
   cumulative volume at the same elapsed time over the prior 20 sessions.
4. Enter at the next bar's executable open, with spread/slippage, only by 10:30 IST. The
   09:30–09:35 confirmation bar cannot be used to enter at 09:30. Skip if price is too far
   above the trigger: initial cap 0.25 prior-day daily ATR; test nearby values separately.
5. Stop at opening-range low minus one valid tick. Reject if planned distance is smaller
   than three current spreads or larger than 0.5 prior-day daily ATR. Size down using the
   risk engine; a wide range can mean no trade.
6. Initial exit rule: full exit at +2R, stop, or session time limit, whichever occurs first.
   Use conservative fills. If stop and target occur in the same unresolved bar, stop first.
7. No re-entry in the same symbol and at most two entries/day for this isolated experiment.
   Start paper risk at 0.10% per trade and 0.50% daily loss cap, both below existing ceilings;
   these are proposed experiment settings, not changes to the active configuration.
8. Be flat by the earliest of 15:10 IST, five minutes before applicable continuous-session
   end, and the broker cutoff less a five-minute buffer. Exit rules need current exchange
   status and security/session eligibility; retry failures and reconcile, rather than
   assuming the scheduled exit filled.

Run an ablation: **same ORB rules without pre-open data** versus **with one pre-open
feature added**. This tests whether auction data adds value beyond the opening price/volume.
Normalize any auction-activity ranking using comparable past observations, not raw share size.

Intraday prerequisites: reliable one/five-minute history and live feed; session-aware engine,
VWAP/relative-volume calculations, MIS charge policy, proper daily risk resets, forced exits,
replay and failure tests. Current paper polling and daily risk resets are not validated for
this specification. Do not present a resampled daily backtest as an intraday result.

### B2/C — Additional families, after the above

| Family | Candidate entry | Stop and exit to specify/test | Additional evidence needed |
| --- | --- | --- | --- |
| VWAP pullback continuation | Strong early move, completed pullback holds VWAP, then close above previous bar high | Below pullback low; +2R/time exit | Same-time relative volume, executable intraday prices |
| Range mean reversion | Range regime; failed break below established support followed by a completed reclaim | Below rejection low; VWAP/mean target, time exit; cost gate | Regime definition fixed before test; avoid trend/news shock days |
| Post-results continuation | Verified results published before decision, then price/volume confirmation | Event-day structural stop; +2R or fixed time exit as separate variants | Timestamped original filings, result history, known-at-time expectations |
| Sector-relative strength | Stock strength agrees with its sector and index context | Structural/ATR stop; exit relative weakness/trail | Historical sector membership and synchronized series |
| Existing mean reversion revisions | Keep `meanrev_v1` entry; test a slower exit separately | Existing hard stop; compare 5-SMA exit with a separately versioned 10-SMA exit | After-cost expectancy, event exclusions as another experiment |

Pairs/statistical arbitrage, market making, expiry scalping, and complex multi-leg options
are not first implementations. Each adds data, execution, or financing assumptions that
need their own testable model.

## 4. Entries, stops, exits, and sizing must work together

A stop defines invalidation; position size adapts to that distance. Do not choose a larger
position and then tighten the stop just to fit a loss budget. Planned risk does not cap gap
losses. A real broker-side stop can also fill worse than its trigger or fail to execute.

For a **hypothetical** Rs 1,00,000 account at the current 0.25% per-trade risk, the budget is
Rs 250. An entry of Rs 1,000 with a Rs 980 stop gives `floor(250/20) = 12` shares before
fees/slippage. Actual permitted quantity can be smaller after costs, cash, liquidity, and
portfolio limits. This example is not a recommendation about a particular stock.

Record separate risk estimates: price-to-stop, fee/slippage-adjusted stop loss, adverse gap,
and correlated portfolio stress. In production, protection must survive a process crash;
the present paper broker simulates protection inside the software.

Profit booking is part of the strategy, not a discretionary response to a green P&L. Compare
fixed targets, trails, and scale-outs as separate versioned experiments. Selling half early
can reduce drawdown and can also remove the rare large winners; it is not always superior.
Moving a stop to the entry price is not cost-adjusted break-even.

Expectancy is approximately `win_rate*average_win - loss_rate*average_loss - average_cost`
when wins/losses are gross; do not subtract costs again when outcomes are already net.
For example, 45% wins averaging 2R and 55% losses averaging 1R leaves 0.35R gross; execution
and fees still have to be deducted. A 2R target alone does not establish that win rate.

## 5. Costs and source conflicts found in this repository

Current source pages do not fully agree on every fee. Groww's pricing page lists NSE equity
exchange charges of 0.00307%, while its intraday help page lists 0.00297%. Use an actual
dated contract note or applicable exchange circular to resolve the rate; retain provenance.
The intraday help page also describes 0.1% brokerage with a minimum rule, whereas current
`config/costs.yaml` uses 0.05% and no minimum for MIS. This must be reconciled before an
intraday profitability claim. The pricing page lists IPFT and GST on DP charges; the existing
flat approximate DP model and missing IPFT deserve a contract-note comparison.
[Groww pricing](https://groww.in/pricing),
[Groww intraday charges](https://groww.in/help/stocks/sx-pricing/what-are-intraday-charges).

NSE's March 31, 2026 circular sets STT from April 1, 2026 at **0.15% of premium on option
sales** and **0.05% on futures sales**. Older derivatives examples in the repository use
different historical rates. Do not copy a cash-share cost model into F&O; apply rates by
effective date. Equity-oriented fund units also have a different delivery STT rule, so an
ETF needs its own classification.
[NSE STT circular](https://nsearchives.nseindia.com/content/circulars/FATAX73524.pdf).

Upstox's 2026 announcements document closing-auction/session changes. The current fixed
calendar is not evidence of correctness for every instrument. Verify applicable session
status and broker cutoffs before intraday execution.
[Upstox announcements](https://upstox.com/developer/api-documentation/announcements/),
[market status](https://upstox.com/developer/api-documentation/appendix/market-status/).

No cost, calendar, or trading configuration was changed in this research task. Those are
identified implementation prerequisites requiring focused tests.

## 6. How a hypothesis earns promotion

Keep the existing gates in `docs/04-roadmap.md`; do not lower them because baselines lose.

1. Freeze one hypothesis, small parameter set, baseline, universe, and rejection criteria.
2. Validate data: former members, effective membership dates, corporate actions, missing
   sessions, price/total-return consistency, release timestamps, and source revisions.
3. Pin code/config/data snapshots, log every experiment, and test train/validation windows.
   As already configured: train 2010–2019, validation 2020–2022, locked test 2023–2025.
4. Use walk-forward windows and inspect bull, bear, range, shock, and recovery periods.
   Intraday history may be shorter; state that limitation rather than inventing ten years.
5. Require the existing evidence targets: validation profit factor >= 1.3 after costs,
   >= 100 trades across history, drawdown <= 15% at the gate's specified risk, >= 60%
   profitable walk-forward windows, and profitable neighboring parameters. Compare risk
   exposure with a sensible benchmark. Treat 100 trades as a minimum, not certainty.
6. Stress doubled costs/slippage, late entries, gaps, rejects, missing feed, correlated
   losses, and removing the best 5% of trades. Resample days/weeks for clustered activity;
   independent trade shuffles do not preserve all dependence.
7. Report both research mode and enforced-breaker results. Current backtests record breakers
   without enforcing them by default; do not label that result operationally executable.
8. Use the locked test only after prior checks and according to the existing access policy.
   Across many versions, repeatedly consulted holdout data stop being a fresh test; protect
   a new forward segment before making further selection claims.
9. Paper trade for **at least 12 weeks AND 50 closed trades per strategy**, whichever takes
   longer, with the current operational/drift gates. Strategy-validation and system-reliability
   paper tests are different: debugging a paper engine does not validate a losing strategy.

For low-frequency rotation with fewer than 100 independent exits, do not invent extra trade
counts or quietly waive the gate. Evaluate rebalance periods, factor exposure, and dependency
explicitly; propose a justified alternative evidence gate for review before promotion.

The three saved November 16 research baselines remain after-cost losers: trend about -4.35%,
breakout -10.68%, and mean reversion -3.73% over 2010–2022. These are repository report values,
not newly rerun results. Their failure is a reason to investigate mechanisms, not promise that
another indicator or an LLM will repair them.

## 7. What must exist before F&O testing is meaningful

- Historical expired contracts and chains, point-in-time strike/expiry selection, lot sizes,
  spreads/quotes, open interest and liquidity, margin and mark-to-market, expiry/roll policy,
  settlement/exercise/assignment behavior, and applicable costs.
- Distinguish direction from time and volatility. Options are sensitive to all three; a
  call can lose despite an upward underlying move if other effects outweigh it.
  [NSE derivatives learning material, Greeks](https://archives.nseindia.com/content/ncfm/SMRepository/DERIVATIVES_EN.pdf).
- A one-lot stop/stress loss must fit the account budget. Otherwise the system rejects the
  instrument; cheap premium does not make the risk appropriate.
- For a later defined-risk spread experiment, model each leg's bid/ask, asynchronous fills,
  fees, exit availability, and worst-case exposure. The terminal payoff diagram does not
  bound every operational or settlement risk.
- Recheck exchange/broker API/algo requirements before live implementation; the current
  live-order lock and paper gates remain in place.
  [SEBI implementation timeline](https://www.sebi.gov.in/sebi_data/attachdocs/sep-2025/1759232056254.pdf).

## 8. Improving the system over time

Use `journal -> deterministic diagnosis -> one hypothesis -> new version -> validation ->
parallel paper -> promotion/retirement`. Keep a champion and a challenger; switching needs
evidence. Track degradation in fills, costs, signals, regime mix, and edge separately.

AI can classify events, explain journal statistics, and suggest testable filters. Preserve
source/model/prompt versions and verify numerical claims. It does not get order tools,
rewrite live rules after a losing day, or choose risk limits. Any ML ranker needs time-aware
labels and out-of-sample comparison against the same strategy without ML.

Every future strategy card should contain: thesis; market/instrument; eligible universe;
data and information cutoff; entry/executable price; stop/target/trailing/time exit;
sizing/exposure; costs; no-trade conditions; regime assumptions; code/data versions; all
experiments; out-of-sample evidence; operational failure handling; and retirement criteria.

## 9. Concrete next research work

Start with **A0 + A1**: reconcile the data/fee/benchmark limitations, then test the single ADX
filter against the unchanged trend baseline. In parallel as a later implementation task,
prepare the recorder and replay prerequisites for **B1**. Evaluate A3 as the slower comparator
once portfolio rebalancing is supported. Choose subsequent work from evidence, not the largest
historical return or the number of indicators available.

Skill setup and invocation examples: [13 — Codex skills](13-codex-skills.md).
