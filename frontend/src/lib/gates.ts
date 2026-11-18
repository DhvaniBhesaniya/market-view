import type { StrategyInfo } from "@/lib/api"

/** Gate 3 (docs/04-roadmap.md) as far as the stored runs can tell. Walk-forward/sensitivity are checked on the Validation page. */
export function gate3Candidate(s: StrategyInfo): { ok: boolean; why: string } {
  const v = s.latest.validate?.metrics
  const f = s.latest.full?.metrics
  if (!v || !f) return { ok: false, why: "needs a validate run and a full run" }
  if (v.profit_factor < 1.3) return { ok: false, why: `validate PF ${v.profit_factor.toFixed(2)} < 1.3` }
  if (f.trades < 100) return { ok: false, why: `${f.trades} trades < 100` }
  if (f.max_drawdown_pct < -15) return { ok: false, why: `max DD ${f.max_drawdown_pct.toFixed(1)}% worse than −15%` }
  return { ok: true, why: "passes PF, trades and drawdown: now check walk-forward + sensitivity" }
}
