import { useQuery } from "@tanstack/react-query"
import { Plus, X } from "lucide-react"
import { useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Command, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command"
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card"
import { Input } from "@/components/ui/input"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { api, type IndicatorDef, type IndicatorParam } from "@/lib/api"

export type ActiveIndicator = { key: string; ind: string; params: Record<string, number> }

export function paramValid(p: IndicatorParam, v: number): boolean {
  return Number.isFinite(v) && v >= p.min && v <= p.max && (!p.integer || Number.isInteger(v))
}

export function indicatorLabel(def: IndicatorDef | undefined, params: Record<string, number>): string {
  if (!def) return "?"
  const args = def.params.map((p) => params[p.name] ?? p.default).join(",")
  return args ? `${def.label}(${args})` : def.label
}

export function useIndicatorCatalog() {
  return useQuery({ queryKey: ["indicators"], queryFn: api.indicators, staleTime: Infinity })
}

/** Chips for the active indicators (with editable params) + an "Add indicator" menu grouped by family. */
export function IndicatorPicker({ value, onChange }: { value: ActiveIndicator[]; onChange: (v: ActiveIndicator[]) => void }) {
  const { data: catalog = [] } = useIndicatorCatalog()
  const [open, setOpen] = useState(false)
  const byId = new Map(catalog.map((d) => [d.id, d]))
  const groups = [...new Set(catalog.map((d) => d.group))]
  const add = (d: IndicatorDef) => {
    const params = Object.fromEntries(d.params.map((p) => [p.name, p.default]))
    onChange([...value, { key: `${d.id}-${crypto.randomUUID().slice(0, 8)}`, ind: d.id, params }])
    setOpen(false)
  }
  const setParam = (key: string, name: string, v: number) =>
    onChange(value.map((a) => (a.key === key ? { ...a, params: { ...a.params, [name]: v } } : a)))

  return (
    <div className="flex flex-wrap items-center gap-2">
      {value.map((a) => {
        const d = byId.get(a.ind)
        if (!d) return null
        return (
          <div key={a.key} className="flex items-center gap-1 rounded-md border bg-card py-0.5 pr-0.5 pl-2 text-xs">
            <HoverCard openDelay={250}>
              <HoverCardTrigger asChild>
                <span className="term font-medium" tabIndex={0}>{d.label}</span>
              </HoverCardTrigger>
              <HoverCardContent className="w-80 text-sm">{d.explain}</HoverCardContent>
            </HoverCard>
            {d.params.map((p) => {
              const v = a.params[p.name]
              const ok = paramValid(p, v)
              return (
                <Input
                  key={p.name}
                  type="number"
                  aria-label={`${d.label} ${p.label}`}
                  title={`${p.label}: ${p.min}–${p.max}`}
                  aria-invalid={!ok}
                  className="num h-6 w-14 px-1 text-xs"
                  value={Number.isFinite(v) ? v : ""}
                  step={p.integer ? 1 : 0.1}
                  min={p.min}
                  max={p.max}
                  onChange={(e) => setParam(a.key, p.name, e.target.value === "" ? Number.NaN : Number(e.target.value))}
                />
              )
            })}
            <Button variant="ghost" size="icon-xs" aria-label={`Remove ${d.label}`} onClick={() => onChange(value.filter((x) => x.key !== a.key))}>
              <X />
            </Button>
          </div>
        )
      })}
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button variant="outline" size="sm"><Plus data-icon="inline-start" />Indicator</Button>
        </PopoverTrigger>
        <PopoverContent className="w-80 p-0" align="start">
          <Command>
            <CommandInput placeholder="Search indicators…" />
            <CommandList>
              {groups.map((g) => (
                <CommandGroup key={g} heading={g}>
                  {catalog.filter((d) => d.group === g && d.id !== "close" && d.id !== "open" && d.id !== "high" && d.id !== "low").map((d) => (
                    <CommandItem key={d.id} value={`${d.label} ${d.id} ${d.group}`} onSelect={() => add(d)}>
                      <span className="font-medium">{d.label}</span>
                      <Badge variant="outline" className="ml-auto">{d.placement === "price" ? "on price" : "own pane"}</Badge>
                    </CommandItem>
                  ))}
                </CommandGroup>
              ))}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  )
}
