# Strategy card — meanrev_v1 (oversold bounce in an uptrend)

Code: [src/market_view/strategies/meanrev.py](../../src/market_view/strategies/meanrev.py)

| | |
|---|---|
| **Thesis** | Sharp 2–3 day sell-offs in long-term uptrends tend to bounce. |
| **Universe / timeframe** | NIFTY 50, daily, long only, CNC |
| **Filter** | Close > 200 SMA; regime TREND_UP / RANGE |
| **Entry** | RSI(2) < 10 and close < lower Bollinger band (20, 2) |
| **Stop** | Close − 2.5×ATR(14) |
| **Profit booking** | Fixed target +2R (broker-side OCO), OR exit next open when close > 5 SMA or RSI(2) > 70 |
| **Time stop** | 7 bars |
| **Kill criteria** | Strategy drawdown ≥ 10%, or 6 consecutive losses |

## Results history

| Date | Version | Period | Trades | PF | Exp. R | Return | Max DD | Note |
|---|---|---|---|---|---|---|---|---|
| 2026-11-05 | v1 | 2010–2022 (full) | 568 | 0.86 | −0.03 | −3.7% | −5.6% | Baseline. **Win rate 59% yet loses money**: small wins, and charges take 38% of gross profit (short holds pay delivery STT on both sides). |

## Lesson
A high win rate does not mean a profitable strategy. Average win, average loss and costs decide.

## Ideas to test
- Only trade stocks with low cost relative to ATR (bigger moves per rupee of charges).
- Exit at the 10 SMA instead of the 5 SMA (let winners run a little longer).
