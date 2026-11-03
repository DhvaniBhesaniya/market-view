# 05 — Risk Management (stop-loss, profit booking, sizing, kill switch)

> "Not to be greedy, proper stop loss and profit booking" (my-view.txt).
> This document turns that into code-enforced rules. The risk engine has **veto power over everything**, including the AI.

All numbers below are **starting defaults for learning**. They're engineering parameters, not personal financial advice. They live in `config/risk.yaml`, and changing them requires a journal note explaining why.

## 1. Risk limits (defaults)

| Limit | Default | Action when hit |
|---|---|---|
| Risk per trade | **0.25%** of capital (max allowed: 0.5%) | Position is sized to fit; reject if qty < 1 |
| Max open positions | 5 (live phase 7: 3) | Reject new entries |
| Portfolio heat (sum of open risk) | 1.5% | Reject new entries |
| Max per sector | 2 positions / 40% exposure | Reject |
| Max position value | 20% of capital | Resize down |
| **Daily loss cap** | **1%** of capital (realised + unrealised) | Halt new entries for the day; alert |
| Weekly loss cap | 2.5% | Halt for the week; mandatory review |
| Strategy drawdown breaker | 10% from that strategy's equity peak | Disable the strategy → back to paper |
| Portfolio drawdown breaker | 12% | **Kill switch**; full review before restart |
| Consecutive losses | 6 in one strategy | Pause the strategy; review if it's normal variance (compare to Monte Carlo) |
| Order rate | 5 orders/sec hard cap (SEBI threshold is 10) | Queue/throttle |
| Liquidity | Avg daily turnover ≥ ₹50 cr; position ≤ 1% of avg daily volume | Reject |
| Cost-vs-edge | Expected move to target ≥ 4× round-trip cost | Reject |
| Restricted lists | ASM/GSM, stocks in circuit, T2T/BE series | Reject |
| Event risk | Results day for the symbol (optional, strategy-dependent) | Reject new entries |

## 2. Position sizing

```
risk_amount  = capital × risk_pct                  # ₹5,00,000 × 0.25% = ₹1,250
risk_per_sh  = entry − stop                        # ₹1,000 − ₹972 = ₹28  (stop = 2 × ATR(14) below entry)
qty          = floor(risk_amount / risk_per_sh)    # 44 shares
position_val = qty × entry                         # ₹44,000 (8.8% of capital) ✓ under 20% cap
```
- **Stops are volatility-based (ATR)**, not arbitrary percentages, so volatile stocks automatically get smaller positions.
- **Regime scaling (Phase 6):** in a high-VIX regime, multiply risk_pct by 0.5.
- **No Kelly** until there are 200+ live trades to estimate the edge. Even then, use ≤ 0.25 × Kelly.
- **Never average down** a losing position. The engine rejects adds to losers.

Skill helper: `position-sizer`.

## 3. Stop-loss rules

1. **Every trade has a stop defined *before* entry.** No stop means no trade (the risk engine rejects the signal).
2. **Initial stop** = the structural level (swing low) or entry − k × ATR, whichever the strategy specifies.
3. **Broker-side stop** is placed via Groww smart orders (GTT / OCO) right after the fill. If the stop placement fails → **immediately exit the position** and alert.
4. **Stops only move in the trade's favour** (trailing). Code forbids widening a stop.
5. **Gap risk:** a stock can gap through the stop. The backtester fills at the open in that case (pessimistic), and Monte Carlo includes gap scenarios.
6. **Time stop:** if a swing trade hasn't reached +1R within N bars (strategy parameter, e.g. 10 days), exit. Dead money is risk.

## 4. Profit booking rules ("not being greedy", encoded)

Choose one **per strategy** and test it in the backtest. Don't improvise live.

| Method | Rule | Good for |
|---|---|---|
| Fixed target | Exit everything at +2R or +3R | Mean reversion |
| **Scale-out** (default) | Sell 50% at +1.5R, move the stop to breakeven, trail the rest with 2 × ATR or the 20 EMA | Trend and breakout |
| Trailing only | Chandelier exit (highest high − 3 × ATR) | Strong trends |
| Time exit | Close after N days regardless | Event or short swings |

Anti-greed rules:
- **The target is set before entry and logged.** Overriding it manually is flagged in the journal.
- **After a +3R day for the portfolio, no new entries** that day (prevents euphoric overtrading).
- **Monthly profit sweep:** in the live phase, 50% of the month's net profit is moved out of the trading account. Profits that aren't taken out tend to be given back.

## 5. Kill switch

**Triggers (automatic):**
- Daily loss cap or portfolio drawdown breaker hit
- Market data stale > 60 seconds during market hours
- Broker API auth failure or repeated 5xx errors / rate-limit errors
- Position reconciliation mismatch (broker ≠ our records)
- Order rejected for an unexpected reason more than 3 times in 10 minutes
- Slippage on a fill > 3× the modelled slippage
- Database unavailable
- Manual: Telegram `/killswitch`, a dashboard button, or the CLI

**Actions:**
1. Block all new orders, enforced in the execution layer, not the strategy.
2. Cancel open entry orders.
3. **Keep** broker-side stops for existing positions. Optionally flatten all positions, depending on the trigger (config).
4. Alert via Telegram with the reason and a snapshot.
5. Restart requires a manual command *and* a written journal note.

The kill switch has its own unit tests and a monthly fire drill during paper trading.

## 6. Capital ladder (live)

```
Paper (Phase 5) ──gate──▶ ₹10–25k ──3 mo──▶ ₹50k ──3 mo──▶ ₹1L ──3 mo──▶ ₹2L ──▶ …
```
- Move up a step only if the last step showed: results consistent with paper, no limit breaches, and drawdown within expectations.
- **Move down a step** after hitting the strategy drawdown breaker, or after 2 consecutive losing months that are worse than the Monte Carlo 10th percentile.
- Only ever trade capital I can afford to lose entirely without changing my life. No loans, no emergency fund money.

## 7. Trade journal (the learning engine)

Each trade record, filled automatically and annotated manually:
- Strategy + version, signal reasons, confidence/ML score
- Entry/exit time and price, planned vs actual (slippage), qty, costs
- Initial stop, target, R-multiple outcome, MAE, MFE, bars held
- Context at entry: regime, NIFTY trend, VIX, sector strength, news sentiment, FII flow
- Exit reason: stop / target / trail / time / manual / kill switch
- **Post-mortem (weekly):** was it a *good trade*? A good trade follows the rules (a loss can still be a good trade). A bad trade breaks them (a win can still be a bad trade).
- AI analysis notes (Phase 6)

**Weekly review ritual (Friday, 45 min):**
1. Rule violations this week (target: zero).
2. Paper/live vs backtest drift: win rate, avg R, slippage.
3. The biggest losers: what did MAE/MFE show? Was the stop too tight, or the entry late?
4. AI journal analyst output → pick at most **one** hypothesis to test next week.
5. Update the learning log: one thing I learned about markets this week.

Skill helpers: `trader-memory-core` (thesis lifecycle, MAE/MFE post-mortems), `signal-postmortem`.
