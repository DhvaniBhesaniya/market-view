# 06 — Strategies & Validation

## 1. Starting universe and timeframe

- **Universe:** NIFTY 50 stocks, using *historical* membership to avoid survivorship bias. Benchmark: NIFTY 50 index / NIFTYBEES.
- **Timeframe:** **daily** candles first (swing, holding 3–20 days). Add hourly and 15-minute later, once Groww history is available.
- **Direction:** long only in the cash segment. Shorting cash equities is intraday-only in India, so it's out of scope for now.
- **Product:** CNC (delivery). Remember delivery STT is 0.1% on buy *and* sell, so trades must target meaningful moves (≥ 3–4%).

## 2. The first three strategies (boring on purpose)

Each strategy is a starting hypothesis. Expect parameters and even whole strategies to be discarded.

### `trend_v1` — trend-following pullback
- **Market filter:** NIFTY 50 close > its 50 EMA.
- **Setup:** stock 20 EMA > 50 EMA, and 50 EMA rising (slope over 10 bars > 0).
- **Entry trigger:** close > 20 EMA after a pullback (low touched within 1 × ATR of the 20 EMA in the last 3 bars), RSI(14) between 50 and 70, volume > 1.2 × the 20-day average.
- **Stop:** the lower of the swing low (5 bars) or entry − 2 × ATR(14).
- **Exit:** scale out 50% at +1.5R, trail the rest with the 20 EMA close-below, time stop at 15 bars.
- **Thesis:** trends persist. Buying pullbacks gives better R than chasing.

### `breakout_v1` — 20-day high breakout
- **Market filter:** NIFTY 50 > 50 EMA and India VIX < its 1-year 80th percentile.
- **Entry:** close > the highest high of the prior 20 days, volume > 1.5 × the 20-day average, ADX(14) > 20, and the close is in the top 25% of the day's range.
- **Stop:** entry − 2 × ATR(14), or the breakout bar's low.
- **Exit:** chandelier trail (highest high − 3 × ATR), time stop at 20 bars.
- **Thesis:** volatility expansion with volume often continues. False breakouts are the main enemy, so log them for the AI to study.

### `meanrev_v1` — oversold bounce in an uptrend
- **Filter:** close > 200 SMA (only buy dips in long-term uptrends).
- **Entry:** RSI(2) < 10 (or RSI(14) < 30) and close < the lower Bollinger Band (20, 2).
- **Stop:** entry − 2.5 × ATR(14).
- **Exit:** close > 5 SMA or RSI(2) > 70, or a fixed +2R target; time stop at 7 bars.
- **Thesis:** short-term overreactions in strong stocks revert. This tends to work in range or bull regimes and fail in crashes.

**Why these three:** they behave differently by regime. Trend and breakout like trending markets; mean reversion likes ranges. That gives the regime model in Phase 6 something real to do.

The vectorbt skill also has 12 ready templates (EMA crossover, Donchian, Supertrend, dual momentum, RSI, MACD …) in `.claude/skills/vectorbt-expert/rules/assets/`. Use them for **fast screening** of other ideas before porting the good ones to the event-driven engine.

## 3. The honest-backtest checklist

Every backtest report must answer **yes** to all of these:

- [ ] Signal computed on bar *t* close; fill at bar *t+1* open (or later).
- [ ] Indian costs included (delivery: about 0.11% per side + brokerage). See [09](09-broker-groww-compliance-costs.md).
- [ ] Slippage included (≥ 0.05% per side for NIFTY 50; more for smaller stocks).
- [ ] Universe uses point-in-time index membership (no survivorship).
- [ ] Prices adjusted for splits and bonuses. Dividends handled consistently.
- [ ] Same-bar stop and target → assume the stop hit first.
- [ ] Gaps through the stop are filled at the open, not at the stop price.
- [ ] Position sizing and the risk engine applied (not "all-in each trade").
- [ ] ≥ 100 trades across the sample; report the trade count prominently.
- [ ] Benchmark comparison (NIFTY buy-and-hold) on the same period.
- [ ] Results recorded in the experiment log with git SHA + params + data range.

## 4. Metrics that matter (and target ranges)

| Metric | Meaning | "Interesting" | "Suspicious, check for bugs" |
|---|---|---|---|
| Expectancy (R) | Avg R per trade after costs | > 0.15R | > 1R |
| Profit factor | Gross win / gross loss | 1.3 – 2.0 | > 3 |
| Max drawdown | Worst peak-to-trough | < 15% | < 2% on many trades |
| Sharpe (daily returns) | Risk-adjusted return | 0.8 – 1.5 | > 3 |
| Win rate | % winners | 35–60% (depends on R:R) | > 80% with small R:R |
| Trades | Sample size | ≥ 100 | < 30 means no conclusions |
| Exposure | % time in market | Report it | — |
| MAR | CAGR / max DD | > 0.5 | — |

Don't judge by win rate. 44% wins with +2.3R winners beats 78% wins with −5R losers.

## 5. Validation protocol (in this order)

```
1. In-sample research   2010–2019   explore freely, but log every variant tried
2. Validation           2020–2022   pick ≤ 3 variants, check they still work (includes Covid crash + recovery)
3. Walk-forward         rolling     4-year train → 1-year test, step 1 year
4. Robustness           ±20% on each param → should stay profitable (plateau, not spike)
                        Monte Carlo trade shuffle ×1000 → 95th-percentile drawdown
                        remove the best 5% of trades → still profitable?
                        different universe (NIFTY Next 50) → similar behaviour?
5. Locked test          2023–2025   run ONCE per strategy version. No re-tuning after.
6. Forward / paper      2026+       live paper trading (Phase 5)
```
Count the number of variants tried. If I've tested 200 variants, the best one is probably luck (the multiple-testing problem). The `backtest-expert` skill helps "beat ideas to death".

## 6. Strategy lifecycle & versioning

```
idea → research (vectorbt screen) → event-driven backtest → validation gate
     → paper (≥ 8 weeks) → live small → live scaled → monitored → retired
```
- Versioned as `trend_v1`, `trend_v2` … A param change is a new version. Old versions are never edited.
- Each version has a **strategy card** (`strategies/cards/trend_v1.md`) containing: thesis, rules, params, expected metrics from backtest, the regime it's expected to work in, kill criteria, and results history.
- **Retire** when live/paper metrics fall below the Monte Carlo 5th-percentile expectation for 3 months, or the drawdown breaker fires twice.

## 7. Ideas backlog (later, after the first three are done)

- Relative-strength rotation across sector indices / ETFs (monthly rebalance; low cost, robust)
- NIFTY 50 momentum portfolio (top-10 by 6-month return, monthly)
- Opening Range Breakout on 15-minute (intraday MIS; lower STT, but needs a live feed and tighter operations)
- Post-earnings drift (needs earnings data + news pipeline)
- Pairs/statistical arbitrage within a sector (advanced)
- Index futures trend (only after 1 year live in cash, plus a separate risk study)
