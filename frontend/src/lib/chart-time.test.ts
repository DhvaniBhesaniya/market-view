import { describe, expect, it } from "vitest"

import { chartTime, customInterval, formatCandleTime, timeKey } from "./chart-time"

describe("chart timestamps", () => {
  it("keeps distinct intraday instants and formats the exchange time regardless of browser timezone", () => {
    const first = chartTime("2026-11-16T09:15:00+05:30")
    const next = chartTime("2026-11-16T09:20:00+05:30")
    expect(typeof first).toBe("number")
    expect(Number(next) - Number(first)).toBe(300)
    expect(new Date(Number(first) * 1000).toISOString()).toBe("2026-11-16T03:45:00.000Z")
    expect(formatCandleTime("2026-11-16T03:45:00Z")).toContain("09:15:00")
    expect(formatCandleTime("2026-11-16T03:45:00Z")).toContain("IST")
  })

  it("keeps business dates and resolves library BusinessDay crosshair values", () => {
    expect(chartTime("2026-11-16")).toBe("2026-11-16")
    expect(timeKey({ year: 2026, month: 11, day: 16 })).toBe("2026-11-16")
    expect(formatCandleTime({ year: 2026, month: 11, day: 16 })).toContain("09:15")
    expect(formatCandleTime("2026-11-16")).toContain("session start")
  })

  it("finds the same candle for numeric and ISO crosshair keys", () => {
    const iso = "2026-11-16T09:15:00+05:30"
    expect(timeKey(chartTime(iso))).toBe(timeKey(iso))
  })
})

describe("custom candle intervals", () => {
  it("distinguishes minutes and months", () => {
    expect(customInterval("5", "m")).toBe("5m")
    expect(customInterval("3", "M")).toBe("3M")
  })

  it("rejects fractions, zero, oversized requests and unavailable seconds", () => {
    expect(customInterval("0", "m")).toBeNull()
    expect(customInterval("1.5", "m")).toBeNull()
    expect(customInterval("391", "m")).toBeNull()
    expect(customInterval("30", "s")).toBeNull()
  })
})
