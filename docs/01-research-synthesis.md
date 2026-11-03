# 01 — Research Synthesis

The three source documents in [../research/](../research/), compared and reconciled, with corrections based on checks done in November 2026.

## 1. What each source contributes

| Source | Core message | Biggest contribution |
|---|---|---|
| **my-view.txt** | I have Groww. I want strategy trading, paper testing, strong risk management, market and news analysis, an AI that trades and learns, and to learn myself. | The goals and constraints. Above all: **Groww**, **beginner**, **learn and grow**. |
| **ChatGPT** | Build a reliable platform first. Prove simple strategies after costs. Add AI only where it measurably helps. 27 stages. | Detailed architecture, the AI layers (regime → ranking → sentiment → journal intelligence), the capital ladder, and "AI never touches the broker". |
| **DeepSeek** | Regulation and mindset first. Paper trade, use a risk shield, start minimal. | The Indian cost emphasis, the OMS state machine, a "paper-first with two switches" design, sentiment as a *filter*, and the price-action feature list. |

## 2. Where all three agree (high-confidence decisions)

1. **Rule-based strategies first, AI later.** AI is an amplifier, not a saviour.
2. **Backtest → paper → tiny live → scale.** No shortcuts.
3. **Indian transaction costs** (STT, GST, stamp duty, exchange, SEBI, brokerage) **must be in every backtest**.
4. **Look-ahead bias, survivorship bias and overfitting** are the main ways to fool yourself. Defend with chronological splits, walk-forward testing and holdouts.
5. **The risk engine sits between strategy and broker.** It enforces position sizing, daily loss cap, max drawdown breaker and a kill switch.
6. **Broker-side stop-loss** right after entry.
7. **A trade journal is the "learning from mistakes" dataset.**
8. **Static IP + broker-approved API** is required under SEBI's retail algo framework.
9. **Start small:** a NIFTY 50 universe, 2–3 strategies, swing or positional timeframes.
10. **Python** for research and ML. Modular monolith. Dockerised VPS for deployment.

## 3. Where they differ, and the decision taken

| Topic | ChatGPT | DeepSeek | **Decision** | Why |
|---|---|---|---|---|
| Broker | FYERS (free API) → Dhan → Zerodha | Zerodha / Dhan / Groww / OpenAlgo | **Groww Trade API** | I already have a Groww account, and its API is now mature. See §4. |
| Risk per trade | 0.25–0.5% | 1–2% (or fractional Kelly) | **0.25% while learning, max 0.5%** | Beginners have unknown edge. Small risk keeps me in the game long enough to learn. Kelly needs a reliable edge estimate, which I don't have. |
| Paper trading duration | "Serious period", enough trades to compare | 2–4 weeks (min 2) | **≥ 8–12 weeks AND ≥ 50 closed trades per strategy** | 2–4 weeks is statistically meaningless for swing strategies, which might make 5–10 trades a month. |
| Database | PostgreSQL + TimescaleDB from day 1 | CSV/Parquet or TSDB | **DuckDB + Parquet first, Postgres + Timescale from Phase 4** | Zero setup on Windows, very fast for research, and the vectorbt skill supports DuckDB. Postgres arrives when a long-running paper service needs concurrent writes. |
| Dashboard | React + TypeScript + Lightweight Charts | Streamlit | **Jupyter/Plotly → Streamlit (Phase 4) → React (Phase 6+)** | Fastest feedback while learning. React is worth it once the workflows are known. |
| Backtester | vectorbt / backtesting.py | Event-driven required (OpenEngine, PyTradeX …) | **Both:** vectorbt for fast idea screening, our own event-driven engine as the source of truth | vectorbt is fast but makes order logic easy to fudge. An event-driven engine shares code with paper and live trading. |
| Rust | Execution and data infrastructure later | — | **Only if measured necessary** | For swing trading at a 10-orders/sec ceiling, Python is fast enough. Rust stays a learning project, not a dependency. |

## 4. Corrections & updates (verified November 2026)

### 4.1 Groww now has a full Trade API, so we use it

Neither research file looked deeply at Groww, but it fits my situation best:
- **Official Python SDK:** `pip install growwapi`. Docs: <https://groww.in/trade-api/docs/python-sdk>
- **Price:** about **₹499 + GST per month**, covering orders, live data, historical data, portfolio and margin. No usage-based charges.
- **Segments:** CASH, FNO and commodity across NSE, BSE and MCX.
- **Historical candles:** from 1 minute to monthly, back to **2020** for equities, indices and FNO. Per-request windows are limited: 30 days for 1–5 minute candles, 90 days for 10–30 minute, 180 days for hourly and above. So we page through history and store it locally.
- **Live data:** a WebSocket feed with up to 1,000 subscriptions, plus LTP, quote and OHLC endpoints.
- **Smart orders** (GTT/OCO) let us place broker-side stops and targets. This is critical for safety.
- **Auth:** API key + secret (daily approval), or a **TOTP flow** that never expires (suits automation).
- **Rate limits:** orders 10/sec and 250/min; live data 10/sec and 300/min; non-trading calls 20/sec and 500/min.
- **OpenAlgo supports Groww**, so the installed vectorbt skills can fetch Indian data through it.

**Consequence:** the ChatGPT plan's "FYERS first" no longer applies to me. FYERS or yfinance stay as optional *free* sources for early history before I pay for the Groww API.

### 4.2 SEBI retail algo framework is now live

- Effective for all brokers from **1 April 2026** (circular "Safer Participation of Retail Investors in Algorithmic Trading", Feb 2025).
- All API orders must go through the broker's approved API. Brokers **tag algo orders** with an exchange-issued ID.
- **Static IP whitelisting is mandatory for order placement.** Data-only calls don't need it.
- **Threshold:** 10 orders per second per exchange per client. Below it, a personal algo doesn't need separate exchange registration. Above it, the strategy must be registered. A swing strategy will be far below this. To be safe, our execution engine **hard-caps at 5 orders/sec**.
- Rules evolve. **Re-check Groww's and NSE's current requirements before Phase 7** (going live).

### 4.3 Claims from the sources to treat carefully

- DeepSeek names several GitHub projects (PyTradeX, Trading-Kavach, OpenEngine, ml4t-india, price-action-lib). Treat them as **reading material for design ideas, not dependencies**. Their maintenance and quality aren't verified. **OpenAlgo** (marketcalls) is the exception: well known and actively maintained.
- "80–90% of retail algo traders lose money" is not a sourced statistic. The **verified** figure is SEBI's own F&O studies: about **9 in 10 individual F&O traders made net losses**. Either way the lesson is the same.
- ChatGPT's specific broker prices (FYERS free, Dhan ₹499, Zerodha ₹500) were correct when written but change often. Re-check before paying.
- DeepSeek's Zerodha notes (6 AM token expiry, weekly IP change) are Zerodha-specific. For Groww, see §4.1.

## 5. What all three sources missed

1. **Tax.** Intraday equity profit is *speculative business income*. Delivery profit is STCG/LTCG. F&O is *non-speculative business income*. These carry different rates, ITR forms and possibly audit requirements. The journal must export a tax-ready P&L. Get a CA's advice before trading live.
2. **Corporate actions.** Splits, bonuses and dividends break raw price history. Store adjusted *and* raw prices, plus a `corporate_actions` table.
3. **Market calendar.** NSE holidays, Muhurat trading, special sessions, and pre-open (09:00–09:15) and closing sessions.
4. **Circuit limits and ASM/GSM lists.** Some stocks get price bands or surveillance restrictions. The risk engine must reject them.
5. **A benchmark comparison is mandatory.** If a strategy doesn't beat **NIFTY 50 buy-and-hold** (or a NIFTYBEES SIP) after costs and risk, the simplest option wins.
6. **A personal learning curriculum** with checkpoints. Covered in [02-learning-path.md](02-learning-path.md).
7. **An honest answer to "which AI is best?"** Covered in [07-ai-layer.md](07-ai-layer.md).

## 6. Final decision record (summary)

| Decision | Choice |
|---|---|
| Market / universe | NSE cash equities, NIFTY 50 (later NIFTY 100 / sector ETFs) |
| Style | Swing / positional on daily and hourly candles; 15-minute only after the daily strategies work |
| Broker | Groww Trade API (subscribe when Phase 2 needs it) |
| Data | yfinance / NSE bhavcopy (free, Phase 1) → Groww historical + WebSocket |
| Language | Python 3.12 + uv |
| Storage | DuckDB/Parquet → PostgreSQL + TimescaleDB |
| Backtest | vectorbt (screening) + own event-driven engine (truth) |
| AI | Claude via API as research assistant and journal analyst; LightGBM for regime and ranking; FinBERT/LLM for news. **Advisory only.** |
| Risk | 0.25% risk per trade, 1% daily loss cap, 10% max drawdown → strategy halt |
| Go-live | Only after the Phase 5 gate. Start at ₹10–25k. |
