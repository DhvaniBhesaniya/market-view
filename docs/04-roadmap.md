# 04 — Roadmap (phases, deliverables, gates)

Every phase ends with a **gate**: concrete criteria I must meet before moving on. Timelines assume about **8–10 hours per week** alongside a job. Being slower is fine; skipping a gate is not.

```
Phase 0  Setup & market basics         ~2 wks    ₹0
Phase 1  Data foundation               ~3 wks    ₹0
Phase 2  Backtester + costs + 3 strats ~4 wks    ₹0  (Groww API ₹499/mo optional from here)
Phase 3  Validation + risk engine      ~4 wks    ₹0–499/mo
Phase 4  Live paper trading system     ~4 wks    ₹499/mo
Phase 5  Paper trading period          8–12 wks  ₹499/mo + VPS ~₹500–1,500/mo
Phase 6  AI layer (advisory)           parallel with Phase 5, ~8 wks  + LLM API usage
Phase 7  Tiny live capital             3+ months, ₹10–25k capital
Phase 8  Gradual scaling & evolution   ongoing
```
Realistic time from today to the first real-money algo trade: **about 6–8 months.** That's normal and healthy.

---

## Phase 0 — Setup & market basics (weeks 1–2)

**Build**
- [ ] Install Python 3.12, uv, Git config, VS Code Python extension, Docker Desktop (later). See [10](10-tech-stack-and-setup.md).
- [ ] Run the `/setup` skill to create the backtesting venv (skip TA-Lib on Windows unless using the wheel).
- [ ] Project skeleton: `pyproject.toml`, `src/market_view/`, `tests/`, `.env.example`, ruff + pytest + pre-commit.
- [ ] First notebook: download NIFTY 50 daily via yfinance (`^NSEI`, `RELIANCE.NS`) and plot candles + 20/50 EMA.

**Learn:** Module L1 ([02](02-learning-path.md)).
**Gate 0**
- `uv run pytest` passes (even with 1 test).
- I can explain the order types and every charge on a real Groww contract note.

---

## Phase 1 — Data foundation (weeks 3–5)

**Build**
- [ ] `data/models.py`: `Candle`, `Instrument`.
- [ ] `data/sources/yfinance_source.py`: daily history for the NIFTY 50 universe since 2010 (free).
- [ ] `data/sources/nse_bhavcopy.py` (optional): official EOD data for cross-checking.
- [ ] `data/store.py`: append-only Parquet writer + DuckDB views. Re-downloads never silently overwrite.
- [ ] `data/validate.py`: detect gaps, zero volume, OHLC inconsistencies (high < low), price jumps > 20% (usually a split), and duplicates.
- [ ] `data/calendar.py`: NSE trading days and holidays; session times.
- [ ] Historical NIFTY 50 constituents list with dates (NSE publishes index changes). Needed against survivorship bias.
- [ ] `indicators/`: EMA, SMA, RSI, ATR, VWAP, ADX, Bollinger, volume ratio, each unit-tested against pandas-ta.
- [ ] Chart notebook: candles + indicators + volume (Plotly).

**Learn:** Module L2.
**Gate 1**
- 10+ years of daily data for current *and* past NIFTY 50 members stored and validated, with a validation report showing 0 unexplained issues.
- Every indicator matches the reference library within tolerance.

---

## Phase 2 — Backtester, costs, first strategies (weeks 6–9)

**Build**
- [ ] `backtest/costs.py`: Indian cost model per segment (delivery, intraday, futures), with **Groww's brokerage** configurable. Unit-tested against a real contract note.
- [ ] `backtest/slippage.py`: fixed bps + a volatility-scaled option (start at 0.05–0.1% per side for NIFTY 50).
- [ ] `backtest/engine.py`: event-driven, bar by bar. Signal on close of *t* fills at open of *t+1*. Stops and targets checked intrabar using high/low, with a **pessimistic rule**: if both the stop and the target were hit in the same bar, assume the stop hit first.
- [ ] `backtest/metrics.py`: CAGR, Sharpe, Sortino, max DD, profit factor, expectancy (R), win rate, avg win/loss, trades, exposure, longest losing streak, total costs paid.
- [ ] `backtest/report.py`: equity curve, drawdown chart, trade list, and a **benchmark vs NIFTY 50 buy-and-hold**.
- [ ] Strategy base class + 3 strategies from [06](06-strategies-and-validation.md): `trend_v1`, `breakout_v1`, `meanrev_v1`.
- [ ] Cross-check: the same strategy in vectorbt (`/backtest` skill) and in our engine should give *similar* results. Big differences mean a bug.
- [ ] Experiment log: each run is saved with params, data range, git SHA and metrics.

**Learn:** Modules L3 and L5.
**Decision point:** subscribe to the **Groww Trade API (₹499/mo)** now if you want hourly or 15-minute history back to 2020. Otherwise keep daily data until Phase 4.
**Gate 2**
- The cost model matches a real contract note to within ₹1.
- A look-ahead test passes: shifting the data by one bar into the future must *break* performance. If it improves, there's a leak.
- All 3 strategies have full reports. It's OK if they're bad. The goal is an honest pipeline, not a winning strategy.

---

## Phase 3 — Validation + risk engine (weeks 10–13)

**Build — validation**
- [ ] Chronological split: **train 2010–2019, validate 2020–2022, test 2023–2025 (locked), forward 2026+ (paper)**.
- [ ] Walk-forward analysis (rolling 4-year train / 1-year test).
- [ ] Parameter sensitivity heatmaps (`/optimize` skill). Good strategies show **plateaus**, not spikes.
- [ ] Monte Carlo: shuffle trade order 1,000× → distribution of max DD and final equity.
- [ ] Regime breakdown: performance in bull, bear, sideways and high-VIX periods.

**Build — risk engine** (see [05](05-risk-management.md))
- [ ] Position sizing (fixed-fractional, ATR-based stop).
- [ ] Pre-trade checks: max positions, per-trade risk, portfolio heat, sector concentration, daily loss cap, ASM/GSM/circuit filter, min liquidity, cost-vs-edge gate.
- [ ] Drawdown breaker per strategy and per portfolio.
- [ ] Kill-switch module (state + triggers), fully unit-tested.
- [ ] The risk engine is wired into the backtester, so backtests reflect real limits.

**Learn:** Module L4.
**Gate 3 — "is any strategy worth paper trading?"** A strategy must show all of the following:
- Out-of-sample (validation period) profit factor ≥ 1.3 after costs, **≥ 100 trades** across the full history.
- Max drawdown ≤ 15% at 0.5% risk per trade.
- Walk-forward: profitable in ≥ 60% of test windows.
- Neighbouring parameters (±20%) are still profitable.
- Beats NIFTY buy-and-hold on a risk-adjusted basis (Sharpe or MAR), or offers clearly lower drawdown.
- Only *then* run the locked 2023–2025 test, **once**. If it fails, back to research. Don't re-tune on the test set.

If no strategy passes, that's a **successful** Phase 3: the system protected me. Iterate on ideas. Don't lower the gate.

---

## Phase 4 — Live paper trading system (weeks 14–17)

**Build**
- [ ] Subscribe to the Groww Trade API. Store credentials in `.env`; set up the TOTP auth flow.
- [ ] `broker/groww.py`: **read-only first**: instruments, quotes, historical candles, holdings, positions, funds.
- [ ] Groww historical downloader → 1h / 15m candles since 2020 into storage (paged per API limits).
- [ ] `data/live_feed.py`: Groww WebSocket client with reconnect, heartbeat, a stale-data detector, and recording of every tick and candle to disk (for replay).
- [ ] `broker/paper.py`: `PaperBroker` simulating fills at next tick/bar ± slippage, with partial fills for illiquid names and applied costs.
- [ ] `execution/`: order FSM, idempotency, reconciliation (against PaperBroker for now).
- [ ] Scheduler: pre-market job (08:45) → context + universe; bar-close jobs → strategies; EOD job (15:45) → journal + report.
- [ ] Migrate ops data to **PostgreSQL + TimescaleDB** (Docker).
- [ ] Streamlit dashboard: positions, today's signals (taken and rejected, with reasons), P&L, risk state, system health.
- [ ] Telegram notifications: signal, fill, stop hit, risk rejection, kill switch, feed down.
- [ ] Replay mode: run a recorded day through the engine at speed.

**Gate 4**
- The system runs a full trading week unattended in paper mode with no crashes.
- Kill switch tested: manual trigger, daily-loss trigger, stale-feed trigger. All three halt new entries and alert me.
- Reconciliation detects a deliberately injected position mismatch.

---

## Phase 5 — Paper trading period (8–12+ weeks, overlaps Phase 6)

**Run** the Gate-3 strategies on live data in paper mode. Move execution to a **static-IP VPS** during this phase, so the production environment is proven before real money.

**Weekly review** (journal ritual, [05](05-risk-management.md) §7): compare paper vs backtest expectations.

**Gate 5 — "permission to go live"**
- ≥ 50 closed paper trades per strategy (or 12 weeks, whichever is later).
- Paper metrics are within a tolerance band of backtest metrics: profit factor not worse by more than ~25%, and average slippage at or below what the backtest assumed.
- Zero unexplained operational incidents in the last 4 weeks.
- I've written the **live trading plan**: capital, limits, what makes me stop, who I tell (a written commitment helps against greed).
- Tax and accounting are set up (consult a CA) and the journal exports P&L.
- SEBI/Groww algo requirements re-checked; static IP registered.

---

## Phase 6 — AI layer, advisory only (parallel with Phase 5)

Order of value. Details are in [07](07-ai-layer.md).
- [ ] **6a. AI journal analyst** (Claude): weekly analysis of losing trades, producing hypotheses written as testable filters.
- [ ] **6b. Market context brief** (Claude + data): a pre-market note from macro data and news.
- [ ] **6c. Regime classifier:** rules first (ADX, VIX, MA slope, breadth), then LightGBM. Strategies get regime filters.
- [ ] **6d. News & sentiment pipeline:** ingest → map to symbols → event type + sentiment → used as a *filter* ("no new long on an earnings miss").
- [ ] **6e. ML signal ranker:** LightGBM predicts P(trade hits ≥ 1R) from features at signal time; only top-ranked signals are taken.
- [ ] **6f. Research assistant chat:** ask questions about my own data ("which trades had the worst slippage?").

**Gate 6 (per AI component):** each one must improve the **out-of-sample** metric it targets (profit factor, drawdown, or hit rate) in backtest *and* in a parallel paper run versus the non-AI baseline. Otherwise it's switched off. AI earns its place with numbers.

---

## Phase 7 — Tiny live capital (3+ months)

- [ ] `broker/groww.py` order methods, behind `LIVE_TRADING=true` **and** `--live`.
- [ ] Live capital **₹10,000–25,000**; risk per trade 0.25% of *that* capital; max 3 positions.
- [ ] Every entry immediately gets a broker-side stop (Groww smart order / GTT / OCO).
- [ ] The paper system keeps running in parallel as a shadow, to compare live vs paper fills.
- [ ] Daily: check the reconciliation report. Weekly: journal review. Monthly: strategy health review.

**Gate 7 (to increase capital)**
- ≥ 3 months live, ≥ 30 live trades, live results consistent with paper (slippage within budget).
- No limit breaches; the kill switch never needed manual override.
- Then step up the capital ladder (see [05](05-risk-management.md) §6).

---

## Phase 8 — Scale & evolve (ongoing)

- Increase capital along the ladder only after each step passes.
- Add a strategy only through the full pipeline (backtest → validation gate → paper ≥ 8 weeks → live small).
- Expand the universe (NIFTY 100, sector ETFs). Consider index futures only after a year of profitable cash trading *and* a dedicated study of F&O risk.
- React + TypeScript frontend with TradingView Lightweight Charts and a strategy lab UI.
- Rust components only where profiling shows Python is the bottleneck.
- Quarterly: retrain ML models on rolling windows, monitor drift, and retire decaying strategies.

---

## The continuous learning loop (from Phase 5 onwards)

```
   ┌──────────────┐   weekly    ┌──────────────────┐
   │ Trade journal│────────────▶│ AI + me: why did │
   │ (every trade │             │ losers lose?     │
   │  + context)  │             └────────┬─────────┘
   └──────▲───────┘                      ▼
          │                    ┌──────────────────┐
          │                    │ Hypothesis as a  │  e.g. "skip breakouts when
          │                    │ testable filter  │   ADX<18 and NIFTY<VWAP"
          │                    └────────┬─────────┘
          │                             ▼
          │                    ┌──────────────────┐
          │                    │ Backtest v(n+1)  │──fails──▶ archive + note
          │                    │ walk-forward     │
          │                    └────────┬─────────┘
          │                             ▼ passes gate
          │                    ┌──────────────────┐
          └────────────────────│ Paper v(n+1)     │──▶ promote if beats v(n)
                               │ alongside v(n)   │
                               └──────────────────┘
```
This is how the system "learns from its mistakes" without ever gambling real money on an untested idea.
