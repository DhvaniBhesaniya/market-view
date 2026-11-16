# Strategy card — trend_v1 (trend-following pullback)

Code: [src/market_view/strategies/trend.py](../../src/market_view/strategies/trend.py)

| | |
|---|---|
| **Thesis** | Trends persist. Buying a pullback to the 20 EMA inside an uptrend gives a closer stop (better R) than chasing highs. |
| **Universe / timeframe** | NIFTY 50, daily, long only, CNC |
| **Market filter** | NIFTY 50 close > its 50 EMA |
| **Entry (signal on close, fill next open)** | 20 EMA > 50 EMA; 50 EMA rising (10-bar slope > 0); low touched within 1×ATR of the 20 EMA in the last 3 bars; close > 20 EMA; RSI(14) 50–70; volume ≥ 1.2× its 20-day average |
| **Stop** | Lower of: 5-bar swing low, or close − 2×ATR(14) |
| **Profit booking** | Sell 50% at +1.5R → stop to breakeven → exit the rest when close < 20 EMA |
| **Time stop** | 15 bars without reaching the scale-out |
| **Expected regime** | TREND_UP |
| **Kill criteria** | Strategy drawdown ≥ 10% of capital, or 6 consecutive losses → pause and review |

## Results history

| Date | Version | Period | Trades | PF | Exp. R | Return | Max DD | Note |
|---|---|---|---|---|---|---|---|---|
| 2026-11-05 | v1 | 2010–2022 (full) | 751 | 0.95 | −0.02 | −4.4% | −6.7% | Baseline. Win 48%, charges 21% of gross profit, 11 breaker events. Not tradable as-is. |

## Ideas to test (one at a time, each as a new version)
- Require ADX > 20 (avoid choppy "trends").
- Only trade in the TREND_UP regime.
- Wider initial stop (2.5×ATR) with a smaller size.
