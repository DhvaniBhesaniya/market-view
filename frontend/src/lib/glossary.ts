// The "explain" layer: plain-language definitions shown when hovering a dotted-underlined term.
// Written for someone new to trading: what it is, how to read it, and what good looks like.

export type GlossaryEntry = { term: string; what: string; read: string }

export const GLOSSARY = {
  total_return: {
    term: "Total return",
    what: "How much the account grew or shrank over the whole period, after all charges and slippage.",
    read: "Never judge it alone: a big return with a 40% drawdown is a strategy you would have abandoned halfway.",
  },
  cagr: {
    term: "CAGR",
    what: "Compound annual growth rate: the steady yearly return that would turn the starting capital into the ending capital.",
    read: "Compare it with NIFTY's CAGR over the same dates. A fixed deposit pays ~6-7% with no risk.",
  },
  max_drawdown: {
    term: "Max drawdown",
    what: "The worst fall from a previous high in account value, in %. It is the pain you must sit through.",
    read: "Our limit is 15% at 0.5% risk per trade (Gate 3). Real trading usually feels worse than the backtest.",
  },
  sharpe: {
    term: "Sharpe ratio",
    what: "Average daily return divided by how much returns jump around, scaled to a year. Reward per unit of bumpiness.",
    read: "Below 0.5 weak, 1 decent, above 2 suspicious in a backtest (check for bugs or look-ahead first).",
  },
  sortino: {
    term: "Sortino ratio",
    what: "Like Sharpe, but only DOWNWARD moves count as risk. Upside jumps are not punished.",
    read: "Usually higher than Sharpe. Negative means the strategy lost money on average.",
  },
  profit_factor: {
    term: "Profit factor",
    what: "Total money won on winning trades ÷ total money lost on losing trades, after costs.",
    read: "Below 1.0 loses money. Gate 3 needs at least 1.3 on data the strategy was not tuned on.",
  },
  expectancy_r: {
    term: "Expectancy (R)",
    what: "The average result per trade, measured in R (multiples of the amount risked).",
    read: "+0.2R means each trade earns, on average, 20% of what you risk on it. It must be positive after costs.",
  },
  r_multiple: {
    term: "R-multiple",
    what: "A trade's profit or loss divided by the money it risked (entry − stop) × quantity. 1R = you made what you risked.",
    read: "A stop-out is about −1R. Good systems have many small losses near −1R and some wins of +2R or more.",
  },
  win_rate: {
    term: "Win rate",
    what: "Share of trades that made money after charges.",
    read: "Meaningless on its own: 35% winners can be very profitable if the winners are 3× the losers.",
  },
  trades: {
    term: "Trades",
    what: "Closed round trips (buy, then sell) in the period. Positions still open at the end are not counted.",
    read: "Under ~100 trades, results are mostly luck. Gate 3 needs at least 100 across the full history.",
  },
  charges: {
    term: "Charges",
    what: "Everything the broker and government take: brokerage, STT (0.1% on both sides for delivery), exchange fee, SEBI fee, stamp duty, GST and DP charges.",
    read: "A round trip costs ~0.25-0.3%. Strategies that aim for small moves give much of the edge away here.",
  },
  exposure: {
    term: "Exposure",
    what: "Share of days the strategy had money in at least one position.",
    read: "Low exposure means cash sits idle most of the time. That lowers both risk and return.",
  },
  benchmark: {
    term: "NIFTY buy-and-hold",
    what: "What you would have earned by simply buying the NIFTY 50 index on day one and holding it.",
    read: "Uses the price index (no dividends), so it slightly understates the real index return, by ~1.2-1.5% a year.",
  },
  mae: {
    term: "MAE",
    what: "Maximum adverse excursion: how far the price went AGAINST the trade while you held it (% from entry).",
    read: "Winners with deep MAE survived by luck. If most winners have shallow MAE, the stop could be tighter.",
  },
  mfe: {
    term: "MFE",
    what: "Maximum favourable excursion: the best unrealised profit a trade reached (% from entry).",
    read: "Losers with big MFE gave back profits: an exit or trailing-stop problem.",
  },
  atr: {
    term: "ATR",
    what: "Average True Range: a stock's typical daily move in rupees, including overnight gaps.",
    read: "Stops placed in ATR units adapt to each stock's volatility. 2×ATR ≈ two normal days away.",
  },
  stop: {
    term: "Stop-loss",
    what: "The price at which a losing trade is exited automatically. It defines 1R, the risk per trade.",
    read: "Every entry gets a broker-side stop immediately (safety rule 4). Sizing comes from the stop distance.",
  },
  walkforward: {
    term: "Walk-forward",
    what: "Test the strategy year by year on data it has never seen, optionally re-choosing parameters on the previous years only.",
    read: "Gate 3 needs profit in at least 60% of the yearly test windows.",
  },
  sensitivity: {
    term: "Sensitivity",
    what: "Re-run the backtest with each parameter nudged ±10% and ±20%.",
    read: "A real edge shows a PLATEAU (neighbours also work). A curve-fit shows a SPIKE (only the exact value works).",
  },
  montecarlo: {
    term: "Monte Carlo",
    what: "Reshuffle the strategy's trade results thousands of times to see the RANGE of outcomes the same edge could produce.",
    read: "Plan for the bad end of the band (p5), not the average. A live drawdown inside the band is normal variance.",
  },
  out_of_sample: {
    term: "Out-of-sample",
    what: "Data the strategy was NOT designed or tuned on. Train = 2010-2019, validate = 2020-2022, test 2023-2025 is locked.",
    read: "Only out-of-sample results count as evidence. In-sample results always look better than reality.",
  },
  regime: {
    term: "Market regime",
    what: "The market's current mood from NIFTY: TREND_UP, TREND_DOWN, RANGE (sideways) or HIGH_VOL (India VIX in its top 20%).",
    read: "Most strategies only work in some regimes. Filters by regime are a common improvement.",
  },
  kill_switch: {
    term: "Kill switch",
    what: "A stop-all-new-trades flag. It blocks new entries only; exits and resting stops keep working.",
    read: "It fires automatically on the daily loss cap, a 12% drawdown, stale data or a position mismatch. Turning it off needs a written note.",
  },
  slippage: {
    term: "Slippage",
    what: "The gap between the price you saw and the price you actually got. Modelled as 0.05% per side.",
    read: "Paper trading checks whether real slippage stays within this assumption (Gate 5).",
  },
  next_open: {
    term: "Next-open fill",
    what: "A signal is decided on day t's close and bought at day t+1's open, never at the close that produced it.",
    read: "This is what makes the backtest honest: you cannot trade at a price you only learn after the fact.",
  },
  lookahead: {
    term: "Look-ahead check",
    what: "Every saved strategy is re-computed with future bars cut off. If any past signal changes, it was peeking at the future.",
    read: "A leaking strategy shows fantastic, fake backtests. The check runs automatically before saving.",
  },
  market_filter: {
    term: "Market filter",
    what: "Only take new buys while NIFTY 50 is above its 50-day EMA (the broad market is in an uptrend).",
    read: "Most stocks fall with the market. Buying against a falling market lowers the win rate.",
  },
  time_stop: {
    term: "Time stop",
    what: "Exit after N days if the trade has not worked, freeing the capital and the risk budget.",
    read: "A trade that goes nowhere still costs charges and blocks better setups.",
  },
  trailing_stop: {
    term: "Trailing stop",
    what: "A stop that only moves UP as the price rises: here, k×ATR below the highest high since entry.",
    read: "Lets winners run while locking in part of the gain. Too tight = shaken out by normal noise.",
  },
  enforce_breakers: {
    term: "Enforce breakers",
    what: "Off (research default): breaker hits are recorded as 'WOULD …' events and trading resumes. On: trading halts exactly as paper/live would.",
    read: "Turn it on to see how the real safety rules would have stopped this strategy.",
  },
} satisfies Record<string, GlossaryEntry>

export type GlossaryKey = keyof typeof GLOSSARY
