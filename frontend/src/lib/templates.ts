import type { Condition, Operand, RuleSpec } from "@/lib/api"

export const ind = (id: string, params: Record<string, number> = {}, output?: string): Operand => ({ kind: "indicator", ind: id, params, ...(output ? { output } : {}) })
export const val = (value: number): Operand => ({ kind: "value", value })
export const cond = (left: Operand, op: Condition["op"], right: Operand): Condition => ({ left, op, right })

const base: Omit<RuleSpec, "name" | "entry"> = {
  description: "", hypothesis: "", exit: [], stop: { type: "atr", value: 2 }, target: { type: "r_multiple", value: 2 },
  time_stop_bars: 15, trail_atr_mult: null, market_filter: true, allowed_regimes: null,
}

/** Starting points that teach a classic idea each. They are hypotheses to test, not recommendations. */
export const TEMPLATES: { key: string; title: string; idea: string; spec: RuleSpec }[] = [
  {
    key: "dip", title: "RSI dip in an uptrend",
    idea: "Buy short-term weakness (RSI < 35) in stocks above their 200-day average; sell when RSI recovers.",
    spec: { ...base, name: "rsi_dip", hypothesis: "Short pullbacks inside a long-term uptrend tend to recover within days.",
      entry: [cond(ind("rsi", { n: 14 }), "<", val(35)), cond(ind("close"), ">", ind("sma", { n: 200 }))],
      exit: [cond(ind("rsi", { n: 14 }), ">", val(55))], target: { type: "none", value: null }, time_stop_bars: 10 },
  },
  {
    key: "cross", title: "EMA crossover",
    idea: "Buy when the 20-day EMA crosses above the 50-day EMA (momentum turning up); trail the stop.",
    spec: { ...base, name: "ema_cross", hypothesis: "A fresh short-term trend that overtakes the medium-term trend tends to continue.",
      entry: [cond(ind("ema", { n: 20 }), "crosses_above", ind("ema", { n: 50 })), cond(ind("adx", { n: 14 }), ">", val(20))],
      exit: [cond(ind("ema", { n: 20 }), "crosses_below", ind("ema", { n: 50 }))], target: { type: "none", value: null },
      time_stop_bars: null, trail_atr_mult: 3 },
  },
  {
    key: "breakout", title: "Donchian breakout",
    idea: "Buy a close above the previous 20-day high on above-average volume.",
    spec: { ...base, name: "donchian_break", hypothesis: "New highs on heavy volume show demand that tends to push prices further.",
      entry: [cond(ind("close"), ">", ind("donchian", { n: 20 }, "upper")), cond(ind("volume_ratio", { n: 20 }), ">", val(1.5))],
      stop: { type: "atr", value: 2 }, target: { type: "r_multiple", value: 3 }, time_stop_bars: 20 },
  },
  {
    key: "bb", title: "Bollinger band reversion",
    idea: "Buy a close below the lower Bollinger band while the long-term trend is up; exit at the middle band.",
    spec: { ...base, name: "bb_revert", hypothesis: "Closes 2 standard deviations below the mean are stretched and tend to snap back.",
      entry: [cond(ind("close"), "<", ind("bb", { n: 20, k: 2 }, "lower")), cond(ind("close"), ">", ind("sma", { n: 200 }))],
      exit: [cond(ind("close"), ">", ind("bb", { n: 20, k: 2 }, "mid"))], target: { type: "none", value: null }, time_stop_bars: 10 },
  },
]

export const BLANK: RuleSpec = { ...base, name: "", entry: [cond(ind("rsi", { n: 14 }), "<", val(30))] }

/** Indicator operands a spec uses (deduplicated), for drawing them on the preview chart. */
export function specIndicators(spec: RuleSpec): { key: string; ind: string; params: Record<string, number> }[] {
  const seen = new Map<string, { key: string; ind: string; params: Record<string, number> }>()
  for (const c of [...spec.entry, ...spec.exit]) {
    for (const o of [c.left, c.right]) {
      if (o.kind !== "indicator" || ["close", "open", "high", "low"].includes(o.ind)) continue
      const key = `${o.ind}:${JSON.stringify(o.params)}`
      if (!seen.has(key)) seen.set(key, { key, ind: o.ind, params: o.params })
    }
  }
  return [...seen.values()]
}
