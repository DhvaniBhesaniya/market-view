import { useQuery } from "@tanstack/react-query"
import { Check, ChevronRight, Lock } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"

export function SymbolPicker({ value, onChange, className }: { value: string; onChange: (s: string) => void; className?: string }) {
  const [open, setOpen] = useState(false)
  const { data = [] } = useQuery({ queryKey: ["symbols"], queryFn: api.symbols, staleTime: 60_000 })
  const withData = data.filter((r) => r.bars > 0)
  const groups: [string, typeof withData][] = [
    ["Indices", withData.filter((r) => r.kind === "index")],
    ["NIFTY 50 stocks", withData.filter((r) => r.kind === "stock")],
    ["Former members", withData.filter((r) => r.kind === "former")],
  ]
  const current = data.find((r) => r.symbol === value)
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" role="combobox" aria-expanded={open} aria-label="Symbol" className={cn("w-56 justify-between", className)}>
          <span className="truncate">
            <span className="font-medium">{value || "Pick a symbol"}</span>
            {current && <span className="ml-2 text-xs text-muted-foreground">{current.sector}</span>}
          </span>
          <ChevronRight data-icon="inline-end" className="rotate-90" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72 p-0" align="start">
        <Command>
          <CommandInput placeholder="Search symbol or sector…" />
          <CommandList>
            <CommandEmpty>No stored data for that symbol. Download history from the Data page.</CommandEmpty>
            {groups.map(([label, rows]) =>
              rows.length ? (
                <CommandGroup key={label} heading={label}>
                  {rows.map((r) => (
                    <CommandItem
                      key={r.symbol}
                      value={`${r.symbol} ${r.sector}`}
                      onSelect={() => {
                        onChange(r.symbol)
                        setOpen(false)
                      }}
                    >
                      <Check className={cn(value === r.symbol ? "opacity-100" : "opacity-0")} />
                      <span className="font-medium">{r.symbol}</span>
                      <span className="ml-auto truncate text-xs text-muted-foreground">{r.sector}</span>
                    </CommandItem>
                  ))}
                </CommandGroup>
              ) : null,
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}

export function StrategySelect({ value, onChange, allowNone = false, placeholder = "Pick a strategy", className }: {
  value: string
  onChange: (id: string) => void
  allowNone?: boolean
  placeholder?: string
  className?: string
}) {
  const { data = [] } = useQuery({ queryKey: ["strategies"], queryFn: api.strategies })
  const builtin = data.filter((s) => s.kind === "builtin")
  const rule = data.filter((s) => s.kind === "rule")
  return (
    <Select value={value || "__none"} onValueChange={(v) => onChange(v === "__none" ? "" : v)}>
      <SelectTrigger className={cn("w-56", className)} aria-label="Strategy">
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {allowNone && (
          <SelectGroup>
            <SelectItem value="__none">No strategy</SelectItem>
          </SelectGroup>
        )}
        <SelectGroup>
          <SelectLabel>Built-in (code)</SelectLabel>
          {builtin.map((s) => <SelectItem key={s.id} value={s.id}>{s.id}</SelectItem>)}
        </SelectGroup>
        {rule.length > 0 && (
          <SelectGroup>
            <SelectLabel>Your rule strategies</SelectLabel>
            {rule.map((s) => <SelectItem key={s.id} value={s.id}>{s.id}</SelectItem>)}
          </SelectGroup>
        )}
      </SelectContent>
    </Select>
  )
}

export const PERIOD_HELP: Record<string, string> = {
  train: "2010-2019: design and tune here",
  validate: "2020-2022: out-of-sample check",
  full: "2010-2022: train + validate (never includes test)",
  forward: "2026 onwards: the paper-trading period",
}

export function PeriodToggle({ value, onChange }: { value: string; onChange: (p: string) => void }) {
  return (
    <div className="flex items-center gap-2">
      <ToggleGroup type="single" variant="outline" size="sm" value={value} onValueChange={(v) => v && onChange(v)} aria-label="Period">
        {Object.keys(PERIOD_HELP).map((p) => (
          <Tooltip key={p}>
            <TooltipTrigger asChild>
              <ToggleGroupItem value={p} aria-label={p}>{p}</ToggleGroupItem>
            </TooltipTrigger>
            <TooltipContent>{PERIOD_HELP[p]}</TooltipContent>
          </Tooltip>
        ))}
      </ToggleGroup>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <Lock className="size-3" /> test
          </span>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs">
          2023-2025 is locked. It can be assessed once per frozen strategy version after Gate 3 passes, so it stays a
          fair final exam.
        </TooltipContent>
      </Tooltip>
    </div>
  )
}
