# market-view — Plan & Documentation

This folder is the master plan for building **market-view**, a personal AI-assisted trading research, learning and execution platform for Indian markets, built on a Groww broker account.

It combines three inputs, found in [../research/](../research/):
- `my-view.txt`: what I want
- `chat-gpt-research.txt`: a 27-stage build plan
- `deepseek-research.txt`: a regulation-first, risk-first roadmap

Section 01 compares the three and adds what they missed or got wrong.

## Read in this order

| # | Document | What it answers |
|---|---|---|
| 00 | [Vision & Principles](00-vision-and-principles.md) | What are we building, and what rules never bend? |
| 01 | [Research Synthesis](01-research-synthesis.md) | What did each source say, where do they agree, what's corrected? |
| 02 | [Learning Path](02-learning-path.md) | What do I need to learn about trading, and in what order? |
| 03 | [Architecture](03-architecture.md) | How is the software structured? Modules, data model, flows. |
| 04 | [Roadmap](04-roadmap.md) | **The build plan:** phases, deliverables, and gates I must pass to move on |
| 05 | [Risk Management](05-risk-management.md) | Stop-loss, profit booking, position sizing, kill switch, capital ladder |
| 06 | [Strategies & Validation](06-strategies-and-validation.md) | First strategies, how to backtest honestly, how to know a strategy is real |
| 07 | [AI Layer](07-ai-layer.md) | Which AI (Claude / DeepSeek / Grok)? Where AI helps, and how it learns from mistakes |
| 08 | [Market Analysis & Data](08-market-analysis-data.md) | Every factor that moves the Indian market, and where to get the data |
| 09 | [Groww, Compliance & Costs](09-broker-groww-compliance-costs.md) | Groww API, SEBI algo rules, static IP, all monthly costs |
| 10 | [Tech Stack & Setup](10-tech-stack-and-setup.md) | Install steps for this Windows machine, repo layout, first commands |

## One-paragraph summary

Do **not** start by building an AI that predicts the market. Build a **research and execution system** in this order:
1. **Data** — historical candles into DuckDB.
2. **Honest backtesting** — real Indian costs, next-bar execution, walk-forward validation.
3. **Three boring, explainable strategies.**
4. **Risk engine** — sizing, stops, daily loss cap, kill switch.
5. **Paper trading** on live Groww data for at least 8–12 weeks.
6. **AI as an advisor** — regime detection, signal ranking, news sentiment, and journal analysis that learns from mistakes.
7. **Tiny live capital, only then** — increased step by step as results stay consistent.

The AI never places orders directly. The "learning from mistakes" loop is a disciplined cycle:

```
journal → hypothesis → re-backtest → paper → promote
```

It is **not** "let the AI retrain itself on live money."

> Educational and research project. Nothing here is financial advice. Most retail traders lose money; SEBI's own studies found roughly 9 out of 10 individual F&O traders made net losses. This plan is designed to keep me among the survivors by losing small, learning fast, and only scaling what's proven.
