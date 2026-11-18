import { describe, expect, it } from "vitest"

import { int, pct, r, rupees, rupeesCompact, runTime, tone } from "./format"

describe("format", () => {
  it("uses Indian digit grouping", () => {
    expect(rupees(500000)).toBe("₹5,00,000")
    expect(rupees(12500000)).toBe("₹1,25,00,000")
    expect(rupees(-84247.45)).toBe("−₹84,247")
    expect(rupees(1234.5, true)).toBe("₹1,234.50")
    expect(int(4623)).toBe("4,623")
  })

  it("compacts lakh and crore", () => {
    expect(rupeesCompact(420000)).toBe("₹4.20 L")
    expect(rupeesCompact(-13000000)).toBe("−₹1.30 Cr")
    expect(rupeesCompact(950)).toBe("₹950")
  })

  it("signs percentages and R", () => {
    expect(pct(4.2)).toBe("+4.20%")
    expect(pct(-1.049)).toBe("−1.05%")
    expect(pct(0)).toBe("0.00%")
    expect(pct(55.3, 1, false)).toBe("55.3%")
    expect(r(1.5)).toBe("+1.50R")
    expect(r(-1)).toBe("−1.00R")
  })

  it("never prints NaN or undefined", () => {
    for (const bad of [undefined, null, Number.NaN, Number.POSITIVE_INFINITY, "x"]) {
      expect(rupees(bad)).toBe("–")
      expect(pct(bad)).toBe("–")
      expect(r(bad)).toBe("–")
    }
  })

  it("classifies tone", () => {
    expect(tone(2)).toBe("up")
    expect(tone(-0.1)).toBe("down")
    expect(tone(0.05, 0.1)).toBe("flat")
    expect(tone(null)).toBe("flat")
  })

  it("reads run ids", () => {
    expect(runTime("20261116-124403-trend_v1-full")).toBe("16 Nov 2026, 12:44")
    expect(runTime("weird")).toBe("weird")
  })
})
