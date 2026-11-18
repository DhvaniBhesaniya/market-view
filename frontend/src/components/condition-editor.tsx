import { Trash } from "lucide-react"

import { paramValid, useIndicatorCatalog } from "@/components/indicator-picker"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type { Condition, IndicatorDef, Operand } from "@/lib/api"

const OPS: { v: Condition["op"]; label: string }[] = [
  { v: ">", label: "is above" }, { v: "<", label: "is below" }, { v: ">=", label: "is at or above" }, { v: "<=", label: "is at or below" },
  { v: "crosses_above", label: "crosses above" }, { v: "crosses_below", label: "crosses below" },
]

function IndicatorSelect({ value, onChange, catalog, label }: { value: string; onChange: (d: IndicatorDef) => void; catalog: IndicatorDef[]; label: string }) {
  const groups = [...new Set(catalog.map((d) => d.group))]
  return (
    <Select value={value} onValueChange={(v) => { const d = catalog.find((x) => x.id === v); if (d) onChange(d) }}>
      <SelectTrigger size="sm" className="w-36" aria-label={label}><SelectValue placeholder="indicator" /></SelectTrigger>
      <SelectContent>
        {groups.map((g) => (
          <SelectGroup key={g}>
            <SelectLabel>{g}</SelectLabel>
            {catalog.filter((d) => d.group === g).map((d) => <SelectItem key={d.id} value={d.id}>{d.label}</SelectItem>)}
          </SelectGroup>
        ))}
      </SelectContent>
    </Select>
  )
}

export function OperandEditor({ value, onChange, allowNumber, label }: { value: Operand; onChange: (o: Operand) => void; allowNumber: boolean; label: string }) {
  const { data: catalog = [] } = useIndicatorCatalog()
  const pick = (d: IndicatorDef) =>
    onChange({ kind: "indicator", ind: d.id, params: Object.fromEntries(d.params.map((p) => [p.name, p.default])), output: d.outputs[0] })
  const def = value.kind === "indicator" ? catalog.find((d) => d.id === value.ind) : undefined
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {allowNumber && (
        <ToggleGroup type="single" variant="outline" size="sm" value={value.kind} aria-label={`${label} type`}
          onValueChange={(k) => {
            if (k === "value" && value.kind !== "value") onChange({ kind: "value", value: 50 })
            if (k === "indicator" && value.kind !== "indicator") pick(catalog.find((d) => d.id === "sma") ?? catalog[0])
          }}>
          <ToggleGroupItem value="indicator">indicator</ToggleGroupItem>
          <ToggleGroupItem value="value">number</ToggleGroupItem>
        </ToggleGroup>
      )}
      {value.kind === "value" ? (
        <Input type="number" aria-label={`${label} number`} className="num h-7 w-24" value={Number.isFinite(value.value) ? value.value : ""} step="any"
          onChange={(e) => onChange({ kind: "value", value: e.target.value === "" ? Number.NaN : Number(e.target.value) })} />
      ) : (
        <>
          <IndicatorSelect value={value.ind} onChange={pick} catalog={catalog} label={`${label} indicator`} />
          {def?.params.map((p) => (
            <Input key={p.name} type="number" title={`${p.label}: ${p.min}–${p.max}`} aria-label={`${label} ${def.label} ${p.label}`}
              aria-invalid={!paramValid(p, value.params[p.name])} className="num h-7 w-16" step={p.integer ? 1 : 0.1}
              value={Number.isFinite(value.params[p.name]) ? value.params[p.name] : ""}
              onChange={(e) => onChange({ ...value, params: { ...value.params, [p.name]: e.target.value === "" ? Number.NaN : Number(e.target.value) } })} />
          ))}
          {def && def.outputs.length > 1 && (
            <Select value={value.output ?? def.outputs[0]} onValueChange={(o) => onChange({ ...value, output: o })}>
              <SelectTrigger size="sm" className="w-24" aria-label={`${label} output`}><SelectValue /></SelectTrigger>
              <SelectContent><SelectGroup>{def.outputs.map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}</SelectGroup></SelectContent>
            </Select>
          )}
        </>
      )}
    </div>
  )
}

export function ConditionRow({ value, onChange, onRemove, index, group }: {
  value: Condition
  onChange: (c: Condition) => void
  onRemove?: () => void
  index: number
  group: "entry" | "exit"
}) {
  const label = `${group} ${index + 1}`
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border bg-background/50 p-2" data-testid={`${group}-condition`}>
      <span className="num w-5 text-xs text-muted-foreground">{index + 1}</span>
      <OperandEditor value={value.left} onChange={(left) => onChange({ ...value, left })} allowNumber={false} label={`${label} left`} />
      <Select value={value.op} onValueChange={(op) => onChange({ ...value, op: op as Condition["op"] })}>
        <SelectTrigger size="sm" className="w-36" aria-label={`${label} comparison`}><SelectValue /></SelectTrigger>
        <SelectContent><SelectGroup>{OPS.map((o) => <SelectItem key={o.v} value={o.v}>{o.label}</SelectItem>)}</SelectGroup></SelectContent>
      </Select>
      <OperandEditor value={value.right} onChange={(right) => onChange({ ...value, right })} allowNumber label={`${label} right`} />
      {onRemove && (
        <Button variant="ghost" size="icon-sm" className="ml-auto" aria-label={`Remove ${label}`} onClick={onRemove}><Trash /></Button>
      )}
    </div>
  )
}
