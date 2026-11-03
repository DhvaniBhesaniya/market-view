# 02 — Learning Path (trading knowledge, in build order)

I'm new to trading. This curriculum runs **in parallel with the build**: each phase of the [roadmap](04-roadmap.md) needs the knowledge from the matching module here. Building the software *is* the learning method. Each module ends with a checkpoint I must be able to do without help.

Main free resource: **Zerodha Varsity** (<https://zerodha.com/varsity/>). It's broker-neutral in content and the best free Indian-market course. Module numbers below refer to Varsity.

---

## Module L1 — How the market works (Phase 0, weeks 1–2)

**Learn:**
- **Exchanges and instruments:** NSE vs BSE; equity, ETF, index, futures, options; what NIFTY 50 is and how it's built.
- **Orders:** market, limit, stop-loss (SL), stop-loss-market (SL-M), GTT, OCO. Bid/ask, spread, market depth.
- **Products:** CNC (delivery), MIS (intraday, auto square-off), NRML (F&O carry-forward).
- **Session:** pre-open 09:00–09:15, continuous trading 09:15–15:30, closing session, T+1 settlement, holidays.
- **Price bands / circuits, ASM/GSM surveillance**, and why a stock can be untradable.
- **Liquidity, slippage, gaps**, and why the price you see isn't the price you get.

**Read:** Varsity Module 1 (Introduction to Stock Markets).
**Do:** In the Groww app, place a tiny *real* delivery order (₹500 of NIFTYBEES) and a GTT order. Then compute the exact charges from the contract note.
**Checkpoint:** I can explain every line on a contract note (brokerage, STT, exchange charges, GST, SEBI fee, stamp duty).

## Module L2 — Reading charts & technical analysis (Phase 1, weeks 2–5)

**Learn:**
- **Candlesticks and timeframes**, and why the daily chart matters more than the 1-minute chart.
- **Trend:** higher highs and higher lows; moving averages (SMA/EMA 20/50/200).
- **Support and resistance**, breakouts and false breakouts.
- **Momentum:** RSI, MACD. **Volatility:** ATR, Bollinger Bands. **Volume:** volume ratio, VWAP.
- **Trend strength:** ADX. **Market breadth:** advance/decline.

**Read:** Varsity Module 2 (Technical Analysis).
**Do:** Build each indicator myself in pandas, then compare with pandas-ta. Plot candles plus indicators for 5 NIFTY stocks.
**Skill helpers:** `technical-analyst` (ask it to read a chart and explain its reasoning), `pandas-pro`.
**Checkpoint:** For a chart Claude picks at random, I can say trend, key levels, and where a stop would logically go, *before* seeing the next bars.

## Module L3 — Trading costs, tax, and why most traders lose (Phase 1–2)

**Learn:**
- The full cost stack per segment (see [09](09-broker-groww-compliance-costs.md)). Delivery STT is 0.1% *each side*, so frequent delivery trading bleeds money.
- **Break-even move:** how far price must move just to cover costs.
- **Taxes:** intraday = speculative business income; delivery = STCG (held under 12 months) / LTCG; F&O = non-speculative business income. ITR-3 for business income.
- **The behavioural reasons people lose:** overtrading, revenge trading, moving stops, averaging down losers, oversized positions.

**Read:** SEBI's F&O profit and loss study (search "SEBI study F&O losses individual traders"). Varsity Module 9 (Risk Management & Trading Psychology).
**Checkpoint:** Given an entry, stop, target and quantity, I can compute net P&L after all charges by hand.

## Module L4 — Risk management & position sizing (Phase 3)

**Learn:**
- Risk per trade, R-multiples, expectancy = (win% × avg win) − (loss% × avg loss).
- Position size = (capital × risk%) ÷ (entry − stop).
- **Drawdown maths:** a 50% loss needs a 100% gain to recover.
- Risk of ruin, losing streaks (a 45% win-rate system *will* have 8+ losses in a row eventually), and correlation (5 bank stocks = 1 big bet).
- **Profit booking:** fixed targets vs trailing stops vs partial exits (scale out at 1R/2R).

**Read:** [05-risk-management.md](05-risk-management.md); Van K. Tharp, *Trade Your Way to Financial Freedom* (position sizing chapters).
**Skill helpers:** `position-sizer`.
**Checkpoint:** I can explain why a 40%-win-rate strategy can beat an 80%-win-rate one.

## Module L5 — Backtesting & statistics (Phase 2–3)

**Learn:**
- Metrics: CAGR, Sharpe, Sortino, max drawdown, profit factor, expectancy, number of trades, exposure.
- **Biases:** look-ahead, survivorship, data snooping/overfitting, selection bias.
- In-sample vs out-of-sample, walk-forward, Monte Carlo trade-shuffle, parameter sensitivity.
- Why 30 trades prove nothing, and the basics of statistical significance.

**Read:** Ernest Chan, *Quantitative Trading* (2nd ed.); Marcos López de Prado, *Advances in Financial Machine Learning* (chapters 7–8 and 11–12 on backtest overfitting; advanced, read later).
**Skill helpers:** `backtest-expert`, `vectorbt-expert`, `backtesting-frameworks`.
**Checkpoint:** I can take a "great" backtest and find at least 3 reasons it might be fake.

## Module L6 — Macro & market context (Phase 4–5)

**Learn:** FII/DII flows, USD/INR, crude oil, US 10-year yield and the dollar index (DXY), GIFT Nifty, India VIX, RBI policy and inflation (CPI), the earnings season calendar, sector rotation, and global index cues. Details in [08-market-analysis-data.md](08-market-analysis-data.md).

**Read:** Varsity Module 3 (Fundamental Analysis), Module 11 (Personal Finance, for context); RBI monetary policy statements; daily market wrap-ups (Moneycontrol / ET Markets).
**Do:** Write a 5-line "market context" note every morning for 4 weeks *before* the open. Compare it to what happened.
**Checkpoint:** I can explain why the NIFTY moved on 3 recent big days, citing the drivers.

## Module L7 — Machine learning for trading (Phase 6)

**Learn:** framing targets (classification of "next N-bar return > X"), feature engineering, leakage, purged/embargoed cross-validation, LightGBM, probability calibration, and feature importance and SHAP.
**Read:** Stefan Jansen, *Machine Learning for Algorithmic Trading* (2nd ed.).
**Skill helpers:** `ml-pipeline`.
**Checkpoint:** My ML filter improves the out-of-sample profit factor of a rule strategy, and I can show there's no leakage.

## Module L8 — Psychology & process (ongoing)

- Write a trading plan for every strategy before it runs (entry, exit, size, invalidation).
- Run a weekly review ritual (see the journal section in [05](05-risk-management.md)).
- Follow rules over feelings. If I want to override the system, I write down why first and review it later.
- **Read:** Mark Douglas, *Trading in the Zone*.

---

## Weekly learning rhythm

| Day | Activity (≈1 hr/day) |
|---|---|
| Mon–Thu | 30 min reading the current module, 30 min building the matching code |
| Fri | Journal review: what did the paper strategies do and why? |
| Sat | Larger build block (2–3 hrs) |
| Sun | Off, or a light macro read |

## Glossary (starter)

| Term | Meaning |
|---|---|
| **R** | The rupee amount risked on a trade (entry − stop) × qty. A +2R trade made twice what it risked. |
| **ATR** | Average True Range: typical bar size; used for volatility-based stops |
| **MAE / MFE** | Maximum Adverse / Favourable Excursion: how far a trade went against you or for you before exit |
| **Drawdown** | Fall from the equity peak to the trough |
| **Expectancy** | Average profit per trade in R after costs |
| **Profit factor** | Gross profit ÷ gross loss (> 1.3 after costs is interesting; > 2 is suspicious) |
| **Walk-forward** | Repeatedly optimise on a past window, then test on the next unseen window |
| **Regime** | A market state (trending up/down, range, high-vol) in which strategies behave differently |
| **Slippage** | Difference between the expected and actual fill price |
| **GTT / OCO** | Good-Till-Triggered / One-Cancels-Other: broker-side conditional orders for stops and targets |
| **CNC / MIS** | Delivery / Intraday product types |
