# 09 — Groww API, Compliance & Costs

> Facts verified November 2026. Broker pricing and SEBI rules change, so re-check the linked sources before paying for anything or going live.

## 1. Groww Trade API

| Item | Detail |
|---|---|
| Docs | <https://groww.in/trade-api/docs/python-sdk> |
| SDK | `pip install growwapi` (Python 3.9+) |
| Subscription | about **₹499 + GST / month**, bought from the Groww Cloud dashboard. Covers orders, live data, historical data, portfolio, margin |
| Segments | CASH, FNO, commodity: NSE, BSE, MCX |
| Auth | (a) API key + secret, **approved daily**; or (b) **TOTP flow**, no expiry, uses `pyotp`. Prefer (b) for automation, with the TOTP secret kept in `.env` |
| Historical candles | `get_historical_candles()`: 1/2/3/5/10/15/30 min, 1h, 4h, 1d, 1w, 1M. History from **2020**. Max per request: 30 days (1–5m), 90 days (10–30m), 180 days (1h+). Page through and store locally |
| Live data | LTP / quote / OHLC endpoints + WebSocket feed (up to 1,000 subscriptions); order-update stream |
| Smart orders | GTT / OCO: used for **broker-side stop-loss and target** |
| Rate limits | Orders 10/s, 250/min · Live data 10/s, 300/min · Non-trading 20/s, 500/min · Auth 5/s, 30/min · Token endpoint 150/day |
| Static IP | **Required for order placement** (SEBI framework). Not needed for data |
| OpenAlgo | Supports Groww (redirect URL `http://127.0.0.1:5000/groww/callback`), so the vectorbt skills can fetch Groww data through OpenAlgo |

**Our usage plan**
- Phases 0–2: free data (yfinance, NSE bhavcopy); no subscription needed.
- Phase 2–3: subscribe when intraday or hourly history becomes necessary.
- Phase 4: read-only integration plus the WebSocket feed in paper mode.
- Phase 7: order methods behind the double switch (`LIVE_TRADING=true` + `--live`), from a static-IP VPS.
- Internal rate limiter set to **50% of Groww's limits**.

## 2. SEBI retail algo framework (in force from 1 April 2026)

What it means for this project:
1. **Orders must go through the broker's official API.** Fine, we use Groww's API.
2. **Static IP whitelisting** for order-placing API calls. Use a VPS with a static IPv4 and register it with Groww.
3. **Algo orders are tagged** with an exchange-provided ID. The broker handles this; we must use the broker's designated mechanism.
4. **Order-rate threshold: 10 orders/second per exchange per client.** Below it, a self-built algo for my own account doesn't need separate strategy registration. Above it, registration is required. Our hard cap is **5/s**, and a swing strategy places only a few orders a day.
5. **Authentication:** 2FA/OAuth or TOTP-based login. Never share API keys; never run someone else's "black-box" algo through my keys.
6. Algos sold to *others* need registration and empanelment. Out of scope: this is personal use only.

**Before Phase 7:** re-read Groww's current API terms and any new NSE/SEBI circulars. Note the date checked in the go-live plan.

Sources: SEBI circular "Safer Participation of Retail Investors in Algorithmic Trading" (Feb 2025), the exchange implementation standards, and Groww API docs.

## 3. Transaction costs (model these in every backtest)

Statutory rates as used in `.claude/skills/vectorbt-expert/rules/indian-market-costs.md`, current at the time of writing:

| Component | Delivery (CNC) | Intraday (MIS) | Futures | Options |
|---|---|---|---|---|
| STT | 0.1% buy **and** sell | 0.025% sell | 0.02% sell | 0.1% sell (premium) |
| Exchange txn (NSE) | ~0.00307% | ~0.00307% | ~0.00183% | ~0.03553% (premium) |
| SEBI fee | 0.0001% | 0.0001% | 0.0001% | 0.0001% |
| Stamp duty | 0.015% buy | 0.003% buy | 0.002% buy | 0.003% buy |
| GST | 18% on (brokerage + exchange + SEBI) | same | same | same |
| Brokerage | **Groww's rate: check groww.in/pricing** (model as `min(₹20, x% × value)`, configurable) | same | flat per order | flat per order |
| DP charge | Per scrip on sell days (delivery). Check Groww | — | — | — |

**Rule of thumb (delivery):** about **0.11% per side + brokerage + DP charge**, so roughly **0.25–0.3% round trip** on a ₹50k trade. A swing trade must expect a move well above this; hence the cost-vs-edge gate in [05](05-risk-management.md).

Implementation: `backtest/costs.py` computes exact per-trade charges, unit-tested against a real Groww contract note (Gate 2).

## 4. Tax (consult a CA before going live)

| Activity | Tax treatment (general) |
|---|---|
| Intraday equity | Speculative business income, at slab rate |
| Delivery held < 12 months | STCG on listed equity (special rate) |
| Delivery held ≥ 12 months | LTCG above the annual exemption |
| F&O | Non-speculative business income, at slab rate; audit thresholds may apply |

The journal must export a per-financial-year P&L (by category, with costs) for the CA and the ITR. Rates and exemptions change with each Budget, so don't hard-code them.

## 5. Monthly running costs

| Item | Phase | Cost / month |
|---|---|---|
| Python, DuckDB, Postgres, vectorbt, LightGBM, Streamlit, React | all | ₹0 |
| yfinance / NSE bhavcopy | 0–3 | ₹0 |
| **Groww Trade API** | 2/4+ | **₹499 + GST** |
| VPS with static IPv4 (Mumbai region; small instance) | 5+ | ~₹500–1,500 |
| Claude API (journal analysis + news tagging, with spend cap) | 6+ | ~₹500–2,000 (usage-based; set a hard monthly limit) |
| Telegram bot | 4+ | ₹0 |
| News API (optional) | 6+ | ₹0–1,500 |
| **Total** | | **₹0 now → about ₹1,500–4,500/month at full build** |

Plus trading capital (Phase 7: start at ₹10–25k) and per-trade charges.
