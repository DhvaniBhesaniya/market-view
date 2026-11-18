import { describe, expect, it } from "vitest"

import { cond, ind, specIndicators, TEMPLATES, val } from "./templates"

describe("templates", () => {
  it("have unique keys and valid-looking names", () => {
    const keys = TEMPLATES.map((t) => t.key)
    expect(new Set(keys).size).toBe(keys.length)
    for (const t of TEMPLATES) {
      expect(t.spec.name).toMatch(/^[a-z][a-z0-9_]{2,30}$/)
      expect(t.spec.entry.length).toBeGreaterThan(0)
      expect(t.spec.entry.every((c) => c.left.kind === "indicator")).toBe(true)
    }
  })

  it("lists each indicator used once, skipping raw prices", () => {
    const spec = { ...TEMPLATES[0].spec, entry: [cond(ind("rsi", { n: 14 }), "<", val(30)), cond(ind("close"), ">", ind("sma", { n: 200 }))],
      exit: [cond(ind("rsi", { n: 14 }), ">", val(55))] }
    expect(specIndicators(spec).map((x) => x.ind)).toEqual(["rsi", "sma"])
  })
})
