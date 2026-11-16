# Strategy card — breakout_v1 (20-day high breakout)

Code: [src/market_view/strategies/breakout.py](../../src/market_view/strategies/breakout.py)

| | |
|---|---|
| **Thesis** | A volatility expansion on high volume often continues. False breakouts are the main enemy. |
| **Universe / timeframe** | NIFTY 50, daily, long only, CNC |
| **Market filter** | NIFTY 50 > 50 EMA; India VIX below its 1-year 80th percentile |
| **Entry** | Close > highest high of the prior 20 days; volume ≥ 1.5× average; ADX(14) > 20; close in the top 25% of the day's range |
| **Stop** | Close − 2×ATR(14) |
| **Profit booking** | Chandelier trail: highest high since entry − 3×ATR (only ever raised) |
| **Time stop** | 20 bars |
| **Expected regime** | TREND_UP, low/normal volatility |
| **Kill criteria** | Strategy drawdown ≥ 10%, or 6 consecutive losses |

## Results history

| Date | Version | Period | Trades | PF | Exp. R | Return | Max DD | Note |
|---|---|---|---|---|---|---|---|---|
| 2026-11-05 | v1 | 2010–2022 (full) | 500 | 0.83 | −0.09 | −10.7% | −11.9% | Baseline. Win 34%, 21 breaker events. Classic false-breakout problem. |

## Ideas to test
- Enter only on a retest of the breakout level (fewer false breakouts).
- Require the sector index to be breaking out too.
- A tighter trail once +2R is reached.
