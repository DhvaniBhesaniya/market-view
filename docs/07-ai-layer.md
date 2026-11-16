# 07 — AI Layer: which AI, where it helps, how it learns

## 1. "Which AI is good? Claude, DeepSeek, Grok?"

The honest answer first: **no LLM can predict stock prices reliably**, and choosing a "smarter" model won't create an edge. LLMs are good at *reading, summarising, classifying, reasoning about your own data, and writing code*. Price prediction is better handled by small, testable statistical/ML models. So the question is really "which model for which job".

| Job | Best fit | Why |
|---|---|---|
| Building this software with me (coding, reviews, explaining concepts) | **Claude (Claude Code)** | Strongest agentic coding workflow; already set up with project skills |
| Journal analysis, research assistant, weekly strategy review | **Claude Sonnet 5** (`claude-sonnet-5`); **Opus 5.5** (`claude-opus-5-5`) for deep monthly reviews | Long-context reasoning over many trades plus structured output; good at "find the pattern in my losers" |
| Bulk news tagging (hundreds of headlines/day → symbol, event, sentiment) | **Claude Haiku 4.5** (`claude-haiku-4-5-20251001`), or **FinBERT** run locally for free | Cheap and fast; FinBERT is a free baseline to compare against |
| Budget alternative for bulk text | DeepSeek | Low cost; fine for classification. Check data-handling terms before sending anything personal |
| Real-time social sentiment (X/Twitter) | Grok has native X access | Social sentiment is noisy and easily manipulated. **Low priority**; treat as an experimental feature only |
| Price/regime/ranking prediction | **LightGBM / XGBoost / logistic regression**, not an LLM | Tabular models on engineered features; testable, fast, cheap, explainable (SHAP) |

**Decision:** Claude as the primary LLM (one provider and one SDK: the `anthropic` Python package), with an `LLMClient` interface so a second provider can be benchmarked later. FinBERT is the free sentiment baseline. LightGBM does the numeric prediction. Use the `claude-api` skill when writing LLM code, and check current pricing and model IDs there rather than hard-coding assumptions.

**Measure, don't trust:** every AI component gets an A/B test against the non-AI baseline (Gate 6 in [04](04-roadmap.md)). The model that wins on *my* out-of-sample data is the right one.

## 2. Where AI sits (and where it never sits)

```
 news, filings, macro ──▶ [LLM: tag + summarise] ──▶ sentiment/event features ─┐
 price/volume data ─────▶ [features] ──▶ [LightGBM: regime, ranker] ──────────┤
                                                                              ▼
                                                     strategy engine (rules) ──▶ Signal + scores
                                                                              ▼
                                                               RISK ENGINE (veto) ──▶ execution ──▶ broker
 journal ──▶ [LLM: analyse losers] ──▶ hypotheses ──▶ backtest pipeline (human approves)
```
**Never:** `LLM → broker`. No LLM tool, MCP server or agent gets order-placement functions. Not even with "confirmation". Prompt injection from a news article must not be able to cause a trade. Use the `llm-trading-agent-security` skill for any design near order flow.

## 3. AI components, in build order (Phase 6)

### 6a. AI journal analyst (highest value, simplest)
- **Input:** last N closed trades with full context (indicators, regime, VIX, sentiment, MAE/MFE, slippage, exit reason).
- **Prompt:** find conditions that over-represent among losers vs winners; propose **at most 3 testable filters** in a strict JSON schema (`{"filter": "ADX(14) < 18", "rationale": "...", "evidence": {...}}`).
- **Output** goes to a review queue → I pick one → it becomes `strategy_v(n+1)` → backtest → paper. The AI proposes; the pipeline disposes.
- **Guard:** also compute the same statistics deterministically (pandas groupby) so the LLM's claims are verified against real numbers.

### 6b. Pre-market context brief
- At 08:30 IST, gather: GIFT Nifty, the US close, Asian markets, USD/INR, crude, US 10-year yield, FII/DII from yesterday, India VIX, today's events (RBI, results, US CPI), and top news.
- Claude writes a 10-line brief plus a structured `market_context` JSON (risk-on/off score, key events). It's stored, so I can later test whether the brief had any predictive value.

### 6c. Regime classifier
- Start **rule-based**: ADX(NIFTY), 50/200 slope, VIX percentile, breadth (% of NIFTY 50 above the 50 EMA) → `TREND_UP | TREND_DOWN | RANGE | HIGH_VOL`.
- Then LightGBM / Hidden Markov Model versions, compared on "does using it improve strategy selection out-of-sample?"
- Use: strategies declare the regimes they're allowed to trade in; high-vol halves the risk per trade.

### 6d. News & sentiment pipeline
- **Sources:** NSE corporate announcements, company results, RSS from business news sites, RBI/SEBI press releases (see [08](08-market-analysis-data.md)).
- **Steps:** dedupe → map to symbol(s) (instrument master + aliases) → event type (earnings beat/miss, guidance, order win, management change, regulatory action, block deal, rating change) → sentiment −1..+1 → confidence.
- Run FinBERT and Claude Haiku side by side. Keep whichever correlates better with the next-day abnormal return.
- **Use as a filter**, not a trigger: block new longs on strong negative events; optionally boost the rank on positive events.
- **Security:** article text is untrusted. It goes into a classification prompt with no tools, and the output is schema-validated.

### 6e. ML signal ranker (meta-labelling)
- Rule strategies generate candidates. The model predicts **P(trade reaches +1R before −1R)** from features at signal time: EMA distances, RSI, ATR%, volume ratio, gap, sector/NIFTY return, regime, VIX, sentiment, and day-of-week.
- Model: LightGBM with **purged walk-forward CV** (no overlap leakage) and calibrated probabilities.
- Trade only candidates above a threshold. This should raise profit factor even if it reduces the trade count.
- Track with MLflow: features, data range, metrics, model version. Monitor drift monthly. Skill: `ml-pipeline`.

### 6f. Research assistant
- Natural-language questions over my DuckDB/Postgres data: "Which strategy loses most in high VIX?", "Show trades with slippage > 0.3%".
- Implemented as Claude plus **read-only** SQL tools against a read-only DB user. No write or execution tools.

## 4. What "the AI learns from its mistakes" actually means here

| Naive version (dangerous) | This project's version |
|---|---|
| AI trades live, loses, "retrains itself", trades again | Every trade is journaled with context |
| Feedback is unvalidated and the model drifts silently | AI and statistics find loss patterns → hypothesis |
| Overfits to the last few weeks | Hypothesis is backtested with walk-forward on years of data |
| Nobody knows which version did what | New version paper-trades **alongside** the old one |
| | Promoted only if better out-of-sample; every version is logged |

Reinforcement learning or fully autonomous agents are **out of scope** until (a) the system has more than 1 year of profitable, stable live operation, and (b) there's a simulator good enough to train in. Even then, the risk engine keeps its veto.

## 5. AI safety checklist (applies to every AI feature)

- [ ] AI output is a score/suggestion, schema-validated, with bounded values.
- [ ] No order/broker functions are reachable from any LLM tool.
- [ ] External text (news, social) is treated as untrusted input; prompt-injection patterns are logged.
- [ ] LLM calls have timeouts. Failure → the system continues *without* AI (degrades gracefully, never blocks risk checks).
- [ ] Every AI output is stored with model ID + prompt version for later evaluation.
- [ ] API keys live in `.env`; per-month spend limits are set in the provider console.
- [ ] Each AI component has a measured, out-of-sample benefit, or it's turned off.

## 6. Multi-agent "analyst team" skills (Day Trader Skill & similar), evaluated 2026-11-05

Popular Claude skill packs split trading into specialist "agents": a scanner, news, entry timer, exit planner, a "time machine" simulator, risk, budget, broker, and so on.

| Pack | What it is | Fit for us |
|---|---|---|
| `Jakeschincariol/day-trader-skill` | 11 skills, US stocks, Yahoo 1m/5m bars, Alpaca paper broker | US only. Ideas worth borrowing |
| `ankurgoels/trader-skills-india` | NSE port of the above: NSE announcements/XBRL results, FII/DII + bulk deals, Yahoo/bhavcopy candles, Zerodha order *tickets* (dry run) | Useful as a **learning companion**. Very new (≈1 star, a handful of commits), so review before use |
| `zubair-trabzada/ai-trading-claude` | 5 parallel agents (technical, fundamental, sentiment, risk, thesis) using web search, PDF reports | Research reports only; US-oriented; no data feed |

**What's good:** the pipeline shape (scanner → news → entry → exit → simulate → risk → size → broker) matches our architecture, the risk checks come before the broker, and paper trading is the default.

**Limits:**
1. **"Time machine" = bootstrap Monte Carlo** of the last ~59 sessions of 5-minute bars. It's a useful *range of outcomes*, but it treats bars as independent (it ignores trends and volatility clustering) and uses a short sample. It's a rough probability, not a forecast.
2. **On-demand LLM analysis isn't a backtest.** You can't reproduce it across 10 years of data, so it can't pass our validation gates.
3. **Day trading** on 5-minute bars is the hardest style for a beginner, and it isn't our starting style (daily swing).
4. **The broker skills conflict with CLAUDE.md rule 2.** An LLM drafting orders, even with a typed "yes", is not allowed in our system.

**Decision:**
- Optionally install the India pack **without** `trader-in-broker`, as a research/learning tool (scanner, news, insiders, analyst, time machine).
- Re-implement the good ideas inside our engine, where they can be tested:
  - time machine → `validation/` (Monte Carlo + "every past time this setup fired" statistics on 10+ years of data)
  - scanner → Phase 4
  - news/insiders/FII → `market_context/`
- A Phase-6 **Claude analyst team** (technical, macro/flows, news/sentiment, bull vs bear debate, risk reviewer) running as parallel subagents is a reasonable *pre-market research report* feature. Its output is a stored, scored report: advisory only, measured like every other AI component.
