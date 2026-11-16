# 11 — Free Market Data for Research & Paper Trading (₹0 budget)

> **Decision (2026-11-05): Upstox** is the API data source for research and paper trading.
> - **Token:** the *Analytics token* is read-only, valid about a year, cannot place orders, and needs no static IP for market data.
> - **History:** daily candles back to 2000; 1-minute to hourly candles back to January 2022.
> - **Until the token arrives:** the software runs on free yfinance data. Switching is automatic once `UPSTOX_ACCESS_TOKEN` is set.
>
> Adapter: `src/market_view/data/sources/upstox_source.py`. Setup steps: [12-paper-trading-runbook.md](12-paper-trading-runbook.md).

Goal: get through Phases 0–5 (learning, backtesting, live paper trading) **without paying for data**. The Groww Trade API (₹499/month) is only needed once real orders go through Groww in Phase 7.

Our architecture separates the **data source** from the **broker** (see [03](03-architecture.md)). So we can read data from a free source and still trade through Groww later. Only the adapter changes.

## 1. What each free source is good for

| Source | Cost | What you get | Limits | Use it for |
|---|---|---|---|---|
| **yfinance** (Yahoo Finance) | Free, no account | Daily OHLCV for NSE stocks (`RELIANCE.NS`) and indices (`^NSEI`, `^NSEBANK`) going back decades; global markets, USD/INR, crude, US yields | Intraday: 1m only for the last 7 days; 5m/15m/30m/60m only for the last 60 days. Not exchange-grade; occasional gaps or bad ticks. Unofficial, so it can break | **Phase 0–3 daily backtests**, macro/global series |
| **NSE bhavcopy archives** (nseindia.com) | Free, official | End-of-day OHLC, volume, **delivery %**, for every stock, every day; F&O bhavcopy (OI) | EOD only; site is rate-limited and needs browser-like headers | Cross-checking yfinance; delivery % and OI features |
| NSE website reports | Free, official | FII/DII daily flows, index constituents and changes, corporate actions, announcements, results calendar, ASM/GSM lists, India VIX history | Manual or light scraping; respect terms | Market context, survivorship-free universe, risk lists |
| `jugaad-data` / `nsepython` (Python libs) | Free, unofficial | Wrappers that download NSE bhavcopy, index history, and live quotes | Unofficial scrapers; can break when NSE changes its site | Convenience for the above |
| **FYERS API** | Free (needs a free FYERS account) | REST + **WebSocket live data**, historical candles including **minute data** (roughly the last 1–2 years for 1m), orders | Needs a FYERS demat/trading account (₹0 to open; check current terms) | **Live paper-trading feed** + intraday history |
| **Angel One SmartAPI** | Free (needs a free Angel One account) | REST + WebSocket live data, historical candles, NSE/BSE/MCX | Account needed; TOTP login | Alternative/backup to FYERS |
| Groww app / web charts | Free with my existing account | Real-time charts with indicators | Manual viewing only, no API | Learning to read charts; eyeballing signals |
| **TradingView** (Basic plan) | Free | Excellent charts, NSE real-time for many symbols, Pine Script backtester for quick idea checks | 2 indicators per chart, 1 saved layout, ads | Visual learning; quickly sanity-checking a strategy idea |
| FRED (St. Louis Fed) | Free, official | US yields, DXY, global macro series | — | Macro factors |
| RBI DBIE, MOSPI | Free, official | Indian rates, CPI, IIP, GDP | Release dates matter (use them, not the reference period) | Macro regime |
| RSS feeds (business news), NSE announcements | Free | Headlines + links | Respect each site's terms | News & sentiment pipeline (Phase 6) |
| Kaggle NSE datasets | Free | Some historical 1m/5m NIFTY datasets uploaded by users | Unknown quality: verify against official data before trusting | Extra intraday history for experiments only |

## 2. Recommended ₹0 setup

```
Phase 0–3  (backtesting on daily candles)
  yfinance daily  ──┐
  NSE bhavcopy    ──┼──▶ validate + cross-check ──▶ Parquet/DuckDB
  NSE index lists ──┘

Phase 4–5  (live paper trading)
  FYERS (or Angel One) free WebSocket ──▶ live candles ──▶ strategies ──▶ PaperBroker
  FYERS free historical 1m/15m       ──▶ intraday history store
  (record every live candle/tick to disk → my own free intraday archive grows daily)

Phase 7  (real money, Groww)
  Groww Trade API ₹499/mo ──▶ GrowwBroker (orders) ; data can stay on FYERS or move to Groww
```

**Decision for the owner:** opening a free FYERS (or Angel One) account just for the data API is optional, but it's the only way to get a **free, live, API-grade feed** for paper trading. Without it, paper trading must run on delayed or daily data: workable for daily swing strategies, not for intraday.

## 3. Rules for using free data safely

1. **Free ≠ verified.** Cross-check yfinance against NSE bhavcopy on a sample. Large mismatches mean that symbol or date isn't trusted.
2. **Adjust for corporate actions.** yfinance's "Adj Close" handles splits and dividends. Bhavcopy is raw. Keep both, and know which one each backtest uses.
3. **Record everything live.** Every candle from the live paper feed is saved. After 6 months I'll own an intraday dataset that no free source provides historically.
4. **Store the source and fetch time** with every row (CLAUDE.md rule 7: never silently overwrite).
5. **Respect terms of use and rate limits.** Throttle scrapers, cache aggressively, and never redistribute data.
6. **A data adapter per source** (`data/sources/yfinance_source.py`, `fyers_source.py` …), all returning the same `Candle` model, so switching sources never touches strategy code.
