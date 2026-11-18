import { useQuery } from "@tanstack/react-query"
import { Lock, Moon, OctagonX, Sun } from "lucide-react"
import { Link } from "react-router"

import { Term } from "@/components/term"
import { useTheme } from "@/components/theme-provider"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { api } from "@/lib/api"

/** Always-visible safety state: mode, live-trading switch, kill switch, data source. */
export function StatusBar() {
  const { data: s, isError } = useQuery({ queryKey: ["status"], queryFn: api.status, refetchInterval: 15_000 })
  const { theme, setTheme } = useTheme()
  const dark = theme === "dark" || (theme === "system" && document.documentElement.classList.contains("dark"))
  return (
    <header className="sticky top-0 z-20 flex h-12 shrink-0 items-center gap-2 border-b bg-background/90 px-3 backdrop-blur">
      <SidebarTrigger />
      <Separator orientation="vertical" className="mr-1 data-[orientation=vertical]:h-5" />
      {isError ? (
        <Badge variant="destructive">API offline: run `uv run mv ui`</Badge>
      ) : (
        <div className="flex min-w-0 flex-wrap items-center gap-1.5">
          <Badge variant="secondary" data-testid="mode-badge">Paper mode</Badge>
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge variant={s?.live_trading ? "destructive" : "outline"} className="gap-1">
                <Lock data-icon="inline-start" />
                {s?.live_trading ? "LIVE env set" : "Live trading off"}
              </Badge>
            </TooltipTrigger>
            <TooltipContent className="max-w-xs">
              Live orders need LIVE_TRADING=true AND a --live CLI flag, and only after the Phase 5 gate. This UI has no
              order buttons at all.
            </TooltipContent>
          </Tooltip>
          {s?.killswitch.active && (
            <Link to="/paper">
              <Badge variant="destructive" className="gap-1" data-testid="killswitch-badge">
                <OctagonX data-icon="inline-start" />
                Kill switch ON
              </Badge>
            </Link>
          )}
          {s && (
            <span className="hidden text-xs text-muted-foreground md:inline">
              data: {s.data_source} ({s.data[s.data_source] ?? 0} symbols)
              {s.upstox_token_set ? "" : " · Upstox token not set"}
            </span>
          )}
        </div>
      )}
      <div className="ml-auto flex items-center gap-1">
        <span className="hidden text-xs text-muted-foreground lg:inline">
          hover <Term k="kill_switch">underlined words</Term> to learn them
        </span>
        <Button variant="ghost" size="icon" aria-label="Toggle theme" onClick={() => setTheme(dark ? "light" : "dark")}>
          {dark ? <Sun /> : <Moon />}
        </Button>
      </div>
    </header>
  )
}
