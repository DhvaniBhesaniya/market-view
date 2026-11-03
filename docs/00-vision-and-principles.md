# 00 — Vision & Principles

## The vision, in my words (from `my-view.txt`)

- Trade through my **Groww** account using **strategies**, with proper data.
- **Paper trade** to test and explore strategies on real data before risking money.
- **Create, test, learn from, and upgrade** strategies so they get better with market data.
- **Proper risk management.** Don't be greedy. Use proper stop-loss and profit booking.
- Analyse the market from every angle: **news, global factors, macro**.
- Eventually, **AI-driven live trading** that learns from its mistakes and experience.
- I'm new and want to **learn and grow** alongside the software.

## The vision, restated as an engineering problem

> Build a trading **research and execution system** that continuously tests hypotheses, quantifies uncertainty, controls risk, learns from actual outcomes, and only executes validated strategies.

This framing beats "build an AI that predicts the stock market" for three reasons:
1. **It is testable.** Every component has a measurable output: a backtest metric, paper-vs-backtest drift, slippage.
2. **It survives being wrong.** Most strategy ideas will fail. The system is built to kill them cheaply in backtest and paper trading, before they touch real money.
3. **It makes "AI learning" concrete.** The AI improves the system by finding patterns in losing trades, proposing filters, and ranking signals. Each improvement goes through the same validation gates as a human idea.

## What "success" means at each stage

| Stage | Success is NOT | Success IS |
|---|---|---|
| Learning | Knowing 100 indicators | Explaining why a trade made or lost money, including costs |
| Backtesting | A huge return number | An out-of-sample, after-cost result that survives walk-forward and parameter tweaks |
| Paper trading | Profit in 2 weeks | Paper results that match backtest expectations (low drift) over 8–12 weeks |
| Live (tiny) | Making money fast | Execution that matches paper; no operational incidents; the risk limits actually fire |
| Scaling | Doubling capital | Consistent risk-adjusted returns across different market regimes |

## Core principles

1. **Survival first, profit second.** Max drawdown and risk of ruin matter more than returns. A strategy that makes 40% with a 50% drawdown is unusable.
2. **Paper by default.** The system boots into paper mode. Live mode needs two deliberate switches.
3. **AI advises, rules decide, the risk engine vetoes.** An LLM hallucination must never become a ₹5 lakh order.
4. **Boring before clever.** Start with three simple, explainable strategies. If you can't explain why a trade happened, you can't learn from it.
5. **Costs are part of the strategy.** STT, brokerage, GST, stamp duty and slippage are modelled from day one. Many attractive strategies die here, and that's good: they die before they reach my money.
6. **Out-of-sample or it didn't happen.** One backtest proves nothing. Walk-forward, holdout periods and robustness checks are required.
7. **Version everything.** Data, strategy code, parameters and results are versioned so "what actually worked" is never a guess.
8. **Journal everything.** Every signal, rejection, fill, slippage event and outcome gets recorded. The journal is the dataset the AI learns from.
9. **No greed by design.** Profit booking and stop rules are written *before* entry and enforced by code, not by feelings in the moment.
10. **Small steps, real gates.** Each phase has exit criteria (see [04-roadmap.md](04-roadmap.md)). I don't skip gates because I'm excited.

## Explicit non-goals (for at least the first year)

- Options selling and complex option strategies
- Scalping, HFT, sub-second strategies (impossible for retail anyway)
- Fully autonomous AI agents with broker access
- Reinforcement learning as the trading brain
- Thousands of symbols, dozens of strategies, 100 indicators
- Microservices
