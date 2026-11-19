# 12 — Original Paper Trading Runbook (historical)

> Superseded on 2026-11-19 by [the web operating guide](17-web-paper-automation.md).
> The trading CLI has been removed; commands below document the original implementation and no
> longer launch the application. Double-click `Start Market View.vbs` and use the web controls.

Everything runs through one command, `uv run mv ...`. Prefer clicking? `uv run mv ui` opens the web UI ([15](15-web-ui.md)). Paper mode is the only mode: live orders are locked in code.

## 1. One-time setup

```powershell
cd C:\dhvani-cs\personal\market-view
uv sync                                   # installs Python 3.12 deps into .venv
copy .env.example .env                    # then fill in tokens (never commit .env)
uv run pytest                             # 53 tests: costs, risk, look-ahead, kill switch, paper cycle...
uv run mv doctor                          # checks config, data, tokens, LIVE_TRADING=false
uv run mv data download --source yfinance --start 2008-01-01   # free daily history, ~2 min
uv run mv data validate                   # review flagged jumps / bad bars
```

### When the Upstox account is ready
1. Upstox Developer Apps → create an app → generate the **Analytics token**. It's read-only, valid about a year, cannot place orders, and needs no static IP for market data.
2. Put it in `.env` as `UPSTOX_ACCESS_TOKEN=...`
3. `uv run mv upstox check` should print a NIFTY 50 last price.
4. `uv run mv data download --source upstox --start 2008-01-01`. Daily history goes back to 2000. Add `--interval 15m --start 2022-01-01` for intraday history (since Jan 2022).
5. With the token set, paper trading automatically uses Upstox for live quotes (`live_data_source: auto` in `config/paper.yaml`) instead of 15-minute-delayed Yahoo quotes.

Prefer the daily OAuth token instead? Use `uv run mv upstox login-url`, log in, copy the `code` from the redirect URL, then run `uv run mv upstox exchange-code <code>`. That token expires at 03:30 IST every day.

## 2. Research loop (backtests)

```powershell
uv run mv backtest run --strategy all --period validate        # portfolio of all enabled strategies
uv run mv backtest run --strategy trend_v1 --period full       # 2010-2022 research window
uv run mv backtest run --strategy trend_v1 --period full --enforce-breakers   # halt exactly like live
uv run mv validate walkforward trend_v1                        # year-by-year out-of-sample
uv run mv validate walkforward trend_v1 --grid '{"stop_atr":[1.5,2,2.5]}'
uv run mv validate sensitivity trend_v1                        # plateau or spike?
uv run mv validate montecarlo trend_v1                         # range of drawdowns to expect
uv run mv backtest experiments                                 # every run ever, never overwritten
```
Each run writes `reports/backtests/<run_id>/report.html`, with an equity curve vs NIFTY, the drawdown, every trade and its exit reason, and sanity warnings.

**The test period (2023–2025) is locked.** `--period test --unlock-test` runs it, logs the run, and warns on re-runs. Use it once per strategy version, after Gate 3.

### Backtest defaults to know
- Breakers are **recorded, not enforced**, by default ("WOULD PAUSE" events). Otherwise one early losing streak would hide 12 years of data. `--enforce-breakers` shows the live behaviour.
- The universe is **today's** NIFTY 50 (survivorship bias flatters results). Add removed stocks to `former_members` in `config/universe.yaml` as you find them.

## 3. Daily paper-trading loop

Either leave the scheduler running (laptop or VPS) during market days:
```powershell
uv run mv paper run            # 09:20 open job, every 5 min monitor, 15:45 EOD (IST, NSE trading days only)
```
Or run the jobs by hand:

| When (IST) | Command | What happens |
|---|---|---|
| after 15:35 | `uv run mv paper eod` | Download today's candles; trail stops / flag exits for open positions; mark to market; generate tomorrow's signals (risk pre-checked) |
| 09:20 next day | `uv run mv paper open` | Exits first, then entries at the real open price (skipped if it gapped below the stop). Every entry immediately gets a **broker-side stop** (simulated OCO) |
| during session | `uv run mv paper monitor` | Feed prices to resting stops/targets, scale-out at +1.5R (trend), check the daily loss cap and stale data → kill switch |
| any time | `uv run mv paper status` | Equity, drawdown, positions, pending signals, kill switch |
| any time | `uv run mv paper reconcile` | Broker positions must equal our records; a mismatch fires the kill switch |

Telegram alerts: set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env` to get entries, exits, breakers and errors on your phone.

## 4. Safety controls

```powershell
uv run mv risk killswitch status
uv run mv risk killswitch on --reason "going on holiday"
uv run mv risk killswitch off --reason "reviewed: feed restored, positions reconciled"   # note >= 10 chars required
uv run mv risk size 1000 972          # position size calculator (44 shares on Rs 5 lakh at 0.25% risk)
```
The kill switch blocks **new entries** only. Exits and resting stops keep working, so positions are never left unprotected.

## 5. Weekly review (Friday, 45 min — docs/05 section 7)

```powershell
uv run mv journal weekly        # P&L, avg R, win %, MAE/MFE per strategy; top rejection reasons
uv run mv journal trades
uv run mv journal signals
```
The Claude skills can help. Ask Claude Code, for example, "run /trader-in-news on my open positions", "/trader-in-insiders on BEL", or "/signal-postmortem on this week's losers". Pick **one** hypothesis per week, implement it as a new strategy version (`trend_v2`), and run it through the full pipeline.

## 6. Where things live

| Path | Contents (all gitignored) |
|---|---|
| `data/clean/<source>/<interval>/*.parquet` | Merged candles; `data/raw/...` keeps every download; `data/revisions.jsonl` logs changed values |
| `data/paper/broker.json`, `trader.json` | Paper account: cash, positions, resting stops, pending signals |
| `data/journal.duckdb` | Signals, risk decisions, orders, trades, events, equity snapshots |
| `data/killswitch.json` | Kill-switch state + history |
| `data/experiments.jsonl` | Every backtest run (params, git SHA, metrics) |
| `reports/backtests/` | HTML/CSV reports |

`uv run mv paper reset --yes` starts a fresh paper account. The journal is kept.
