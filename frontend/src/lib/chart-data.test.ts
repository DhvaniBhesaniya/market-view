import { describe, expect, it } from "vitest"

import type { IndicatorDef } from "./api"
import { buildIndicatorLayers, startFor, type IndicatorInput } from "./chart-data"

const def = (id: string, placement: "price" | "pane", outputs: string[], params: [string, number][] = [], levels: number[] = []): IndicatorDef => ({
  id, label: id.toUpperCase(), group: "x", placement, outputs, explain: "", levels, value_range: null,
  params: params.map(([name, d]) => ({ name, default: d, min: 1, max: 500, integer: true, label: name })),
})

const catalog = [def("ema", "price", ["value"], [["n", 20]]), def("bb", "price", ["upper", "mid", "lower"], [["n", 20], ["k", 2]]),
  def("rsi", "pane", ["value"], [["n", 14]], [30, 70]), def("macd", "pane", ["macd", "signal", "hist"], [["fast", 12], ["slow", 26], ["signal", 9]])]
const pts = [{ time: "2024-01-01", value: 1 }]

describe("buildIndicatorLayers", () => {
  it("routes price indicators to overlays and others to panes", () => {
    const active: IndicatorInput[] = [
      { key: "a", ind: "ema", params: { n: 50 } },
      { key: "b", ind: "bb", params: { n: 20, k: 2 } },
      { key: "c", ind: "rsi", params: { n: 14 } },
      { key: "d", ind: "macd", params: { fast: 12, slow: 26, signal: 9 } },
    ]
    const result = { a: { value: pts }, b: { upper: pts, mid: pts, lower: pts }, c: { value: pts }, d: { macd: pts, signal: pts, hist: pts } }
    const { overlays, panes } = buildIndicatorLayers(active, catalog, result)
    expect(overlays.map((o) => o.label)).toEqual(["EMA(50)", "BB(20,2) upper", "BB(20,2) mid", "BB(20,2) lower"])
    expect(overlays.find((o) => o.label.endsWith("mid"))?.dashed).toBe(true)
    expect(panes.map((p) => p.title)).toEqual(["RSI(14)", "MACD(12,26,9)"])
    expect(panes[0].levels).toEqual([30, 70])
    expect(panes[1].series.map((s) => s.kind)).toEqual(["line", "line", "histogram"])
  })

  it("skips indicators whose results are missing (e.g. still loading)", () => {
    const { overlays, panes } = buildIndicatorLayers([{ key: "x", ind: "ema", params: { n: 5 } }], catalog, {})
    expect(overlays).toEqual([])
    expect(panes).toEqual([])
    expect(buildIndicatorLayers([{ key: "x", ind: "ema", params: {} }], catalog, undefined).overlays).toEqual([])
  })
})

describe("startFor", () => {
  it("counts back from the last bar", () => {
    expect(startFor("1Y", "2026-11-05")).toBe("2025-11-05")
    expect(startFor("6M", "2026-11-05")).toBe("2026-05-05")
    expect(startFor("All", "2026-11-05")).toBeUndefined()
    expect(startFor("1Y", null)).toBeUndefined()
  })
})
