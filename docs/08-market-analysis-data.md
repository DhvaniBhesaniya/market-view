# 08 — Market Analysis & Data ("every aspect that affects the market")

This document lists the factors that move Indian equities, how each affects the market, where to get the data, and how the system uses it. It's built up gradually: Phase 1 needs only prices, and Phase 6 uses most of this table.

## 1. Factor map

### A. Price & internal market structure (Phase 1+)
| Factor | Why it matters | Source | Use in system |
|---|---|---|---|
| OHLCV, candles | The base of everything | yfinance (free, prototyping), NSE bhavcopy (official EOD), **Groww historical + WebSocket** | Strategies, backtests |
| NIFTY 50 / BANKNIFTY / sector indices | Market & sector direction | Same | Market filter, relative strength |
| **India VIX** | Expected volatility; high VIX = wider swings, more gap risk | NSE / Groww | Regime, risk scaling |
| Breadth (advance/decline, % above 50 EMA) | Is the rally broad or narrow? | Computed from constituent data | Regime |
| Delivery % | Share of volume that is real buying, not intraday churn | NSE bhavcopy (security-wise delivery) | Feature for breakout quality |
| Open interest, PCR (index options) | Derivatives positioning | NSE F&O bhavcopy / Groww FNO | Feature (Phase 6+) |
| Bulk / block deals | Large-investor activity | NSE daily reports | Event feature |
| ASM/GSM lists, circuit bands | Stocks under surveillance / price limits | NSE | Risk-engine reject list |

### B. Flows (Phase 5+)
| Factor | Why | Source |
|---|---|---|
| **FII/FPI net buy/sell** (cash + F&O) | Foreign money is the biggest marginal driver of large caps | NSE daily FII/DII data; NSDL FPI monitor |
| **DII net** (mutual funds, insurers) | Domestic SIP flows often offset FII selling | NSE daily |
| Mutual fund SIP flows (monthly) | Structural domestic demand | AMFI monthly data |

### C. Global & macro (Phase 5–6)
| Factor | Typical effect on Indian equities | Source |
|---|---|---|
| **GIFT Nifty** (pre-market) | Indicates the opening gap | NSE IX / news sites |
| US markets (S&P 500, Nasdaq) overnight | Risk sentiment carries into the Asian open | yfinance (`^GSPC`, `^IXIC`) |
| Asian markets (Nikkei, Hang Seng) | Same-session sentiment | yfinance |
| **USD/INR** | Weaker rupee → FII outflows; helps IT/pharma exporters | RBI reference rate, yfinance `INR=X` |
| **Crude oil (Brent)** | India imports ~85% of its oil: higher crude → inflation, deficit, pressure on OMCs/paints/aviation | yfinance `BZ=F` |
| **US 10-year yield, Dollar Index (DXY)** | Higher yields or dollar → emerging-market outflows | yfinance `^TNX`, `DX-Y.NYB`; FRED |
| US Fed decisions, US CPI/jobs | Global liquidity | Economic calendar |
| **RBI monetary policy** (repo rate, stance) | Rates → banks, NBFCs, real estate, autos | RBI website (calendar known in advance) |
| India CPI/WPI inflation, GDP, IIP, PMI | Growth/inflation regime | MOSPI, RBI, S&P Global PMI |
| Union Budget (Feb), tax changes (e.g. STT hikes) | Sector-wide repricing; changes our cost model | Government releases |
| Monsoon (IMD forecasts) | Rural demand: FMCG, autos, fertilisers | IMD |
| Geopolitics, elections, war | Volatility shocks | News |
| Gold, copper, steel prices | Sector inputs (metals) | yfinance / MCX |

### D. Company-level (Phase 6)
| Factor | Source |
|---|---|
| Quarterly results (beat/miss), guidance | NSE corporate filings, company IR |
| **Results calendar** (avoid holding through results unless intended) | NSE board-meeting announcements |
| Corporate actions: dividend, split, bonus, buyback | NSE corporate actions |
| Rating changes, management change, order wins, regulatory action | NSE announcements + news |
| Promoter pledging / shareholding changes | NSE shareholding pattern (quarterly) |
| Fundamentals (P/E, ROE, debt) | Screener.in (manual), company filings | 

### E. News & sentiment (Phase 6)
| Source | Notes |
|---|---|
| NSE/BSE corporate announcements | Most reliable, official, and timestamped |
| RSS feeds from Indian business news (Moneycontrol, Economic Times Markets, Business Standard, Livemint) | Check each site's terms; store headline + link + timestamp |
| RBI / SEBI press releases | Policy events |
| NewsData.io / GNews APIs | Paid tiers for volume |
| Social (X, Reddit r/IndianStockMarket) | Noisy and manipulable. Experimental only |

## 2. Daily market-context record (`market_context_daily`)

Computed every trading day at 08:45 IST and again at the close:

```json
{
  "date": "2026-11-03",
  "nifty_close": 0, "nifty_vs_50ema_pct": 0, "nifty_vs_200ema_pct": 0,
  "india_vix": 0, "vix_percentile_1y": 0,
  "breadth_pct_above_50ema": 0, "adv_decl_ratio": 0,
  "fii_cash_net_cr": 0, "dii_cash_net_cr": 0,
  "usdinr": 0, "brent": 0, "us10y": 0, "dxy": 0,
  "sp500_ret_1d": 0, "gift_nifty_gap_pct": 0,
  "events_today": ["RBI policy", "TCS results"],
  "regime": "TREND_UP",
  "news_risk_score": 0.0,
  "ai_brief": "…"
}
```
This record feeds the regime model, the ML ranker and the journal. Stored daily, it lets me later answer: *"Does FII selling of more than ₹3,000 cr predict worse breakout results?"* Questions like that, answered with my own data, are how "market analysis" becomes an edge rather than an opinion.

## 3. Learning exercise (Module L6)

For 4 weeks, each morning before 09:15:
1. Read the context record and the AI brief.
2. Write a one-line expectation (e.g. "gap down, IT outperforms on weak rupee").
3. At the close, score it. After 4 weeks, review which factors actually mattered.

## 4. Data-quality rules

- Always store the **source and fetch time** with each datapoint.
- Macro series are released with a delay (CPI is published mid-month for the previous month). Backtests must use the **release date**, not the reference date, or it's look-ahead bias.
- Index constituents change semi-annually. Use point-in-time membership.
- Re-check scraped sources' terms of use; prefer official APIs and exchange files.
