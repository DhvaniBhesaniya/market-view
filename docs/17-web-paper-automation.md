# Web paper research and the weekly mentor

Updated 2026-11-19. This is the current operating guide. Older terminal commands in historical
plans and runbooks have been superseded; the trading CLI and its Typer/Rich dependencies are removed.
Developer tools (Python, uv, npm, pytest, browser checks) remain necessary to maintain the software.

## What is possible

An automated research and paper system is possible. A perfect profit system is not.
Orders visible before opening can be modified/cancelled, and many aggressive buyers do not
guarantee a rising price after the auction. Every executed trade has a buyer and seller.
Displayed bid quantity is neither completed buying nor a probability of profit.

The current implementations are daily cash-equity swing strategies on the configured NIFTY stock
universe. They may hold overnight. They are not intraday, opening-auction or F&O strategies.
The NIFTY 50 index itself is not an individual cash share; trading its constituents, an ETF,
futures and options are different products with different fills, costs and risks.

All three baseline strategies failed the existing validation gate on the checked data.
Paper operation is therefore an explicitly acknowledged **unvalidated research trial**, not
promotion to a proven strategy. Do not fund live trading on this basis.

## Open and operate

1. Run `uv run market-view start` from the project folder. The application runs inside that terminal
   and opens `http://127.0.0.1:8000`; **Ctrl+C**, closing the terminal, or `uv run market-view stop`
   stops it (`uv run market-view status` checks it). Starting again while it runs opens the existing instance. Initial developer
   setup still needs the Python environment and frontend production build described in README.
2. On **Data**, click **Check Upstox connection**. The configured Analytics token is read-only;
   it suffices for real-data paper simulations. The application never sends Upstox orders.
3. Check daily coverage and quality flags. **Refresh daily history** downloads the configured
   research universe. Charts can download a selected symbol/interval separately.
4. On **Paper trading**, read the research warning, check the acknowledgement, and click
   **Start research paper trial**. Starting verifies read access, creates the simulated account,
   reconciles positions and checks the kill switch. It does not immediately buy a stock.
5. The current config schedules analysis at **15:45 IST**, next-session exits/entries at **09:20**,
   and stop/target monitoring every **5 minutes** on configured NSE trading days. An application
   started after 09:30 skips that day's opening entries. Signals expire after their next trading
   session; repeated opening jobs do not double-enter. Entries use the fresh price at execution,
   not the earlier 09:15 opening print.
6. **Pause new entries** keeps monitoring and exits running for the existing account. The separate
   kill switch vetoes entries until reset with a written explanation. It does not flatten positions.
7. Keep the computer awake and application running. Closing the browser alone is fine; closing the terminal stops it. The
   app is not a Windows service or an auto-start-at-boot installer. Simulated protective stops
   are local records; they cannot act while the application is stopped or prices are unavailable.
   Gaps can exceed a planned stop. The page shows heartbeat, worker state and errors.

Entry permission is persisted across restarts, but relevant configuration/code changes pause it
for review. A process lock prevents a second web worker from owning the same paper account.
Account JSON writes use replacement files; restart reconciliation halts entries on a position or
protection mismatch. This is not a transactional live execution system. Unknown orders/recovery
still require inspection; no live broker methods have been enabled.

Actual exchange last-trade time is used for quote age. Missing, invalid, future or overly old
quotes are excluded and veto new risk; stale prices cannot simulate successful exits. The current
paper quote-age limit remains **900 seconds**, as configured for the older delayed-source workflow;
it has not silently been tightened. A more demanding intraday experiment needs a separately reviewed
feed-latency budget and tick/bar execution model. If data fails, the dashboard error and kill switch
must be reviewed before resuming. Protection-placement failure requests an immediate simulated
exit and halts further entries. Daily loss accounting now includes the opening gap.

The checked calendar currently covers 2026. An unknown future calendar year disables entries;
position monitoring continues with quote freshness checks. Maintain the calendar before extending
the trial into a new year.

Application errors go to `data/application.log`; account state is `data/paper/`; the journal is
`data/journal.duckdb`. Tests use isolated folders, never the owner's account.

## Demand observations

**Capture demand snapshot** reads full Upstox V3 quotes for the configured stock universe and
preserves the raw response, capture time, provider response times and instrument identities in
new files under `data/demand_snapshots/YYYY-MM-DD/`.

While the research trial is enabled, the worker records one observation every 30 seconds during
09:00–09:15 IST. Manual capture also works outside that window, labelled by its actual session.
It cannot reconstruct a missed morning from daily candles. The page always describes the displayed
result as a **saved snapshot**, not a continuous live feed.

The displayed imbalance is `100 * (bid quantity - ask quantity) / (bid quantity + ask quantity)`.
Missing fields remain unknown; a zero book has no ratio. Small books can have extreme percentages.
Sorting this ratio is a way to inspect observations, not a trade ranking. It needs liquidity/value
normalization, timing validation and subsequent outcome evidence before it could become a hypothesis.

**Opening-auction verification is pending.** The connected full-quote API includes bid/ask totals
and fields documented for the closing auction. Their presence does not prove opening-auction
semantics, freshness or eligibility. The software does not relabel them as opening-auction matched
quantity, and does not generate a buy/sell signal from them. A working Analytics token does not by
itself prove that the opening-auction feed is usable.

Sources checked 2026-11-19:

- [NSE pre-open mechanism and current order restrictions](https://www.nseindia.com/static/products-services/equity-market-pre-open).
  Pre-open is 09:00–09:15; SL/IOC orders are not accepted in its order collection. Auction stop
  handling must therefore be designed separately from normal continuous-session trading.
- [Upstox full quotes V3](https://upstox.com/developer/api-documentation/get-full-market-quote-v3/):
  quote timestamps versus last-trade timestamps, quantities, and closing-auction additions.
- [Upstox Analytics token](https://upstox.com/developer/api-documentation/analytics-token/):
  read-only data access; no order placement/modification.

## Weekly mentor

The Paper page computes a deterministic review from actual **paper** journal rows. Select any day
in a Monday–Sunday IST week. No LLM subscription or market prediction is involved.

- **Weekly Summary:** number of closed trades, net closed-trade P&L after charges, win rate,
  biggest actual win/loss, and previous-week comparison. These are complete trades grouped by exit
  week: open positions and unfinished partial exits are excluded. This is not total account weekly
  mark-to-market P&L. No trades means an undefined win rate, not a fabricated success rate.
- **What I Did Well:** documented process checks and risk vetoes. A rejected signal is not a mistake.
- **My Biggest Mistakes:** failed risk/plan/selection/execution reviews, missing evidence, operational
  errors and recurring failures when prior reviews exist. A losing trade alone is not a mistake.
- **Patterns I Should Notice:** exit reasons, costs, net R, holding time, recorded MAE/MFE, and small
  sample caveats. Quote sampling can miss extremes. Emotions and news explanations are not invented.
- **Next Week's Action Plan:** exactly three priorities. **Save next week's plan** freezes their text.
  The next week's review displays that saved plan and lets the operator mark progress with evidence.
  Updates are journalled; operator completion claims are labelled as self-reports.
- **Final Rating:** requires a complete process review of every closed trade in the week. Risk has
  40% weight, plan discipline 30%, selection/execution 20%, all-check consistency 10%. Profit adds no
  points. Missing evidence means **Not rated**; a small reviewed sample is explicitly provisional.
  This is a process score, not proof of skill or statistical edge.

Expand a trade and compare its signal, size, stop, fills and exit reason. Assess all four checks and
write the supporting evidence. The software cannot infer that every rule was followed from P&L
alone, so it does not award a perfect discipline score just because its own code ran.

## Work still needed before the proposed trading styles

1. **Reliable evidence first:** resolve corporate-action/data-quality flags, verify current universe
   membership and trading calendar, and collect timestamped opening observations with verified field
   semantics. The current universe is configured, not automatically guaranteed to equal today's NSE
   membership. Keep raw snapshots and frozen experiment versions.
2. **Test one intraday hypothesis at a time:** e.g. a 15-minute opening-range breakout with completed
   bar confirmation, next-bar execution, spread/liquidity filters, a defined structural/ATR stop,
   portfolio/sector caps, a tested target/trail and a time exit before close. Compare a pre-open demand
   filter against the same strategy without that filter. These are research specifications to develop;
   they are not implemented or validated strategies. The current daily runner cannot be treated as
   an intraday simulator by merely changing the chart interval.
3. **Promotion evidence:** realistic Indian costs, adverse fills, gaps and queue/partial-fill assumptions,
   training/validation separation, walk-forward stability, parameter sensitivity and locked holdout
   discipline. Then compare forward paper operation with the frozen backtest. F&O needs a separate
   contract/expiry/margin/options dataset and risk model. Do not add it as a shortcut to steady income.

Consistent trading means consistently following an evidenced plan and limiting losses. It does not
mean forcing a trade, meeting a daily rupee target, or automatically changing strategy after a loss.

## Verification for this change

- `uv run --offline pytest`: **203 passed**, isolated data. Existing dependency deprecation warnings
  remain; no risk limits or enabled strategies were changed.
- `npm run check`: TypeScript, ESLint, **16 frontend tests**, and production build passed.
- Chromium end-to-end: **22 passed**, no browser/HTTP errors; isolated data and synthetic trades,
  including profitable-but-undisciplined grading, saved plan follow-through, chart source/intervals,
  kill-switch reset notes, and phone width. Screenshots contain test data, not the owner's results.
- Read-only Upstox auth and full quotes verified. The updated batched adapter returned RELIANCE/TCS
  exchange timestamps about 1–2 seconds old at the check; this is an observation, not an uptime guarantee.
- Ruff and changed-file whitespace checks passed. A repository ignore rule was corrected so engine
  `src/market_view/data/` code is visible to version control while root market data remains ignored.
- The owner's paper account and journal were **not** created or started during verification.
