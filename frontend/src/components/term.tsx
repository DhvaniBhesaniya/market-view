import type { ReactNode } from "react"

import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card"
import { GLOSSARY, type GlossaryKey } from "@/lib/glossary"

/** The explain layer: a dotted-underlined term that shows a plain-language definition on hover/focus. */
export function Term({ k, children }: { k: GlossaryKey; children?: ReactNode }) {
  const g = GLOSSARY[k]
  return (
    <HoverCard openDelay={150} closeDelay={80}>
      <HoverCardTrigger asChild>
        <span tabIndex={0} className="term rounded-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
          {children ?? g.term}
        </span>
      </HoverCardTrigger>
      <HoverCardContent className="w-80" side="top">
        <div className="flex flex-col gap-2 text-sm">
          <p className="font-heading font-semibold">{g.term}</p>
          <p>{g.what}</p>
          <p className="text-muted-foreground">{g.read}</p>
        </div>
      </HoverCardContent>
    </HoverCard>
  )
}
