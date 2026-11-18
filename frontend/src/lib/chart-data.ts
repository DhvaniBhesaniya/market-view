import type { Overlay, Pane } from "@/components/charts/price-chart"
import type { IndicatorDef, Point } from "@/lib/api"

export type IndicatorInput = { key: string; ind: string; params: Record<string, number> }

function label(def: IndicatorDef, params: Record<string, number>): string {
  const args = def.params.map((p) => params[p.name] ?? p.default).join(",")
  return args ? `${def.label}(${args})` : def.label
}

/** Turn computed indicator series into chart layers: price overlays and one pane per pane-indicator. */
export function buildIndicatorLayers(
  active: IndicatorInput[],
  catalog: IndicatorDef[],
  result: Record<string, Record<string, Point[]>> | undefined,
): { overlays: Overlay[]; panes: Pane[] } {
  const byId = new Map(catalog.map((d) => [d.id, d]))
  const overlays: Overlay[] = []
  const panes: Pane[] = []
  if (!result) return { overlays, panes }
  for (const a of active) {
    const def = byId.get(a.ind)
    const data = result[a.key]
    if (!def || !data) continue
    const name = label(def, a.params)
    if (def.placement === "price") {
      for (const out of def.outputs) {
        overlays.push({ key: `${a.key}:${out}`, label: def.outputs.length > 1 ? `${name} ${out}` : name, points: data[out] ?? [], dashed: out === "mid" })
      }
    } else {
      panes.push({
        key: a.key,
        title: name,
        levels: def.levels,
        height: def.id === "volume" ? 90 : 110,
        series: def.outputs.map((out) => ({
          key: `${a.key}:${out}`,
          label: def.outputs.length > 1 ? out : "",
          points: data[out] ?? [],
          kind: out === "hist" || def.id === "volume" ? ("histogram" as const) : ("line" as const),
        })),
      })
    }
  }
  return { overlays, panes }
}

export const RANGES = { "1D": 1 / 365, "5D": 5 / 365, "1M": 1 / 12, "3M": 0.25, "6M": 0.5, "1Y": 1, "3Y": 3, "5Y": 5, "10Y": 10, All: 0 } as const
export type RangeKey = keyof typeof RANGES

/** Start date (YYYY-MM-DD) for a range ending at `last`. "All" -> undefined (whole history). */
export function startFor(range: RangeKey, last: string | null | undefined): string | undefined {
  const years = RANGES[range]
  if (!years || !last) return undefined
  const d = new Date(`${last}T00:00:00Z`)
  if (range === "1D" || range === "5D") d.setUTCDate(d.getUTCDate() - (range === "1D" ? 1 : 5))
  else d.setUTCMonth(d.getUTCMonth() - Math.round(years * 12))
  return d.toISOString().slice(0, 10)
}
