import {
  Blocks,
  ChartCandlestick,
  Database,
  FlaskConical,
  Layers,
  LayoutDashboard,
  NotebookPen,
  ShieldCheck,
} from "lucide-react"
import { NavLink, useLocation } from "react-router"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar"

// Grouped by the order of the research loop: look -> design -> test -> prove -> practise.
const NAV = [
  { group: "Desk", items: [
    { to: "/", label: "Overview", icon: LayoutDashboard },
    { to: "/chart", label: "Chart", icon: ChartCandlestick },
  ] },
  { group: "Research", items: [
    { to: "/strategies", label: "Strategies", icon: Layers },
    { to: "/builder", label: "Build a strategy", icon: Blocks },
    { to: "/backtests", label: "Backtests", icon: FlaskConical },
    { to: "/validation", label: "Validation", icon: ShieldCheck },
  ] },
  { group: "Practice", items: [
    { to: "/paper", label: "Paper trading", icon: NotebookPen },
    { to: "/data", label: "Data", icon: Database },
  ] },
]

export function AppSidebar() {
  const { pathname } = useLocation()
  const active = (to: string) => (to === "/" ? pathname === "/" : pathname === to || pathname.startsWith(`${to}/`))
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <div className="flex items-center gap-2 px-1 py-1.5">
          <div className="grid size-8 shrink-0 place-items-center rounded-md bg-primary font-heading text-sm font-bold text-primary-foreground">
            mv
          </div>
          <div className="flex min-w-0 flex-col leading-tight group-data-[collapsible=icon]:hidden">
            <span className="font-heading text-sm font-semibold">market-view</span>
            <span className="truncate text-xs text-muted-foreground">NSE research desk</span>
          </div>
        </div>
      </SidebarHeader>
      <SidebarContent>
        {NAV.map((g) => (
          <SidebarGroup key={g.group}>
            <SidebarGroupLabel>{g.group}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {g.items.map((it) => (
                  <SidebarMenuItem key={it.to}>
                    <SidebarMenuButton asChild isActive={active(it.to)} tooltip={it.label}>
                      <NavLink to={it.to} end={it.to === "/"}>
                        <it.icon />
                        <span>{it.label}</span>
                      </NavLink>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>
      <SidebarFooter>
        <p className="px-2 pb-1 text-[11px] leading-snug text-muted-foreground group-data-[collapsible=icon]:hidden">
          Research and paper trading only. Not financial advice.
        </p>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
