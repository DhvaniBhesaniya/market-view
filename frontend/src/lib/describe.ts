// Plain-text rendering of rule conditions (mirrors RuleSpec.describe() in Python).

import type { Condition, Operand } from "@/lib/api"

const OP_TEXT: Record<Condition["op"], string> = { ">": ">", "<": "<", ">=": "≥", "<=": "≤", crosses_above: "crosses above", crosses_below: "crosses below" }

export function describeOperand(o: Operand): string {
  if (o.kind === "value") return String(o.value)
  const args = Object.values(o.params).join(",")
  const base = args ? `${o.ind.toUpperCase()}(${args})` : o.ind
  return o.output && o.output !== "value" ? `${base} ${o.output}` : base
}

export function describeCondition(c: Condition): string {
  return `${describeOperand(c.left)} ${OP_TEXT[c.op]} ${describeOperand(c.right)}`
}
