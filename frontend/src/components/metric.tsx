import type { ReactNode } from "react"

import { Term } from "@/components/term"
import type { GlossaryKey } from "@/lib/glossary"
import { cn } from "@/lib/utils"

type Tone = "up" | "down" | "warn" | "flat"

/** One number with its (explained) label. Numbers are mono/tabular; colour only encodes direction. */
export function Metric({ label, term, value, sub, tone = "flat", className }: {
  label: string
  term?: GlossaryKey
  value: ReactNode
  sub?: ReactNode
  tone?: Tone
  className?: string
}) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-1 rounded-lg border bg-card px-3 py-2.5", className)}>
      <span className="truncate text-xs text-muted-foreground">{term ? <Term k={term}>{label}</Term> : label}</span>
      <span
        className={cn("num truncate text-lg font-medium", {
          "text-up": tone === "up",
          "text-down": tone === "down",
          "text-warn": tone === "warn",
        })}
      >
        {value}
      </span>
      {sub !== undefined && <span className="num truncate text-xs text-muted-foreground">{sub}</span>}
    </div>
  )
}

export function MetricGrid({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6", className)}>{children}</div>
}
