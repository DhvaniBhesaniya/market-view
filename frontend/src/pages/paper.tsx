import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { OctagonX, ShieldCheck } from "lucide-react"
import { useMemo, useState } from "react"
import { toast } from "sonner"

import { SeriesChart } from "@/components/charts/series-chart"
import { DemandWatch } from "@/components/demand-watch"
import { PaperAutomationCard } from "@/components/paper-automation"
import { WeeklyReviewCard } from "@/components/weekly-review"
import { Metric, MetricGrid } from "@/components/metric"
import { LoadingBlock, Page, PageHeader, QueryError } from "@/components/page"
import { Term } from "@/components/term"
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { api, type Point } from "@/lib/api"
import { dateTime, num, pct, r, rupees, toneClass } from "@/lib/format"
import { cn } from "@/lib/utils"

function KillSwitchCard() {
  const qc = useQueryClient()
  const ks = useQuery({ queryKey: ["killswitch"], queryFn: api.killswitch, refetchInterval: 15_000 })
  const [text, setText] = useState("")
  const act = useMutation({
    mutationFn: (action: "on" | "off") => api.setKillswitch(action, text.trim()),
    onSuccess: (s) => {
      toast[s.active ? "warning" : "success"](s.active ? "Kill switch ON: no new entries" : "Kill switch OFF: entries allowed again")
      setText("")
      qc.invalidateQueries({ queryKey: ["killswitch"] })
      qc.invalidateQueries({ queryKey: ["status"] })
    },
    onError: (e) => toast.error("Kill switch unchanged", { description: e.message }),
  })
  const active = ks.data?.active
  const tooShort = text.trim().length < (active ? 10 : 3)
  return (
    <Card className={cn(active && "border-destructive/60")}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 font-heading">
          {active ? <OctagonX className="size-5 text-down" /> : <ShieldCheck className="size-5 text-up" />}
          <Term k="kill_switch">Kill switch</Term>: {active ? "ON" : "off"}
        </CardTitle>
        <CardDescription>
          {active ? <>Since {dateTime(ks.data?.since)} ({ks.data?.source}): {ks.data?.reason}</> : "The kill switch is off. Automation permission and risk checks still apply to every entry."}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Field data-invalid={(!!text && tooShort) || undefined}>
          <FieldLabel htmlFor="ks-note">{active ? "Why is it safe to resume? (required, ≥ 10 characters)" : "Reason for stopping new trades"}</FieldLabel>
          <Textarea id="ks-note" rows={2} value={text} onChange={(e) => setText(e.target.value)} aria-invalid={(!!text && tooShort) || undefined}
            placeholder={active ? "e.g. feed restored, positions reconciled, reviewed the losing day" : "e.g. going on holiday / something looks wrong"} />
          <FieldDescription>Restarting after a halt is a deliberate decision, so it is written down (data/killswitch.json).</FieldDescription>
        </Field>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant={active ? "outline" : "destructive"} disabled={tooShort || act.isPending} className="self-start">
              {active ? "Turn kill switch off" : "Turn kill switch on"}
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{active ? "Allow new entries again?" : "Stop all new entries?"}</AlertDialogTitle>
              <AlertDialogDescription>
                {active ? "Automation permission and risk checks will still apply after this reset." : "The paper trader will skip every new entry until you turn this off with a note. Paper exits still require the application and a fresh feed."}
                {" "}Note: “{text.trim()}”
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={() => act.mutate(active ? "off" : "on")}>{active ? "Turn off" : "Turn on"}</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
        {ks.data && ks.data.history.length > 0 && (
          <ul className="flex flex-col gap-1 border-t pt-2 text-xs text-muted-foreground">
            {ks.data.history.slice(0, 6).map((h, i) => (
              <li key={i}><Badge variant={h.action === "ON" ? "destructive" : "outline"} className="mr-2">{h.action}</Badge>{dateTime(h.at)}: {h.reason ?? h.note}</li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

function JournalTable({ table }: { table: "trades" | "signals" | "events" | "orders" }) {
  const q = useQuery({ queryKey: ["journal", table], queryFn: () => api.journal(table, 300) })
  if (q.isError) return <QueryError error={q.error} what={`journal ${table}`} />
  if (!q.data) return <LoadingBlock height={160} />
  if (q.data.length === 0) return <p className="py-6 text-center text-sm text-muted-foreground">Nothing in the {table} journal yet.</p>
  const cols: Record<string, string[]> = {
    trades: ["exit_time", "strategy_id", "symbol", "qty", "entry_price", "exit_price", "net_pnl", "r_multiple", "exit_reason"],
    signals: ["ts", "stage", "strategy_id", "symbol", "approved", "qty", "ref_price", "stop", "reasons"],
    events: ["ts", "level", "message"],
    orders: ["ts", "symbol", "side", "qty", "order_type", "status", "tag", "note"],
  }
  return (
    <Table>
      <TableHeader><TableRow>{cols[table].map((c) => <TableHead key={c}>{c.replace(/_/g, " ")}</TableHead>)}</TableRow></TableHeader>
      <TableBody>
        {q.data.map((row, i) => (
          <TableRow key={i}>
            {cols[table].map((c) => {
              const v = row[c]
              const cls = c === "net_pnl" || c === "r_multiple" ? toneClass(v) : ""
              const text = c === "net_pnl" ? rupees(v) : c === "r_multiple" ? r(v) : typeof v === "number" ? num(v) : c.endsWith("time") || c === "ts" ? dateTime(v) : String(v ?? "–")
              return <TableCell key={c} className={cn(typeof v === "number" && "num text-right", "text-xs", cls)}>{text}</TableCell>
            })}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

export default function Paper() {
  const paper = useQuery({ queryKey: ["paper"], queryFn: api.paper, refetchInterval: 30_000 })
  const eq = useQuery({ queryKey: ["journal", "equity"], queryFn: () => api.journal("equity", 5000) })
  const equityPoints = useMemo<Point[]>(() => {
    const byDay = new Map<string, number>()
    for (const row of [...(eq.data ?? [])].reverse()) byDay.set(String(row.ts).slice(0, 10), Number(row.equity))
    return [...byDay.entries()].sort().map(([time, value]) => ({ time, value }))
  }, [eq.data])
  const p = paper.data
  return (
    <Page>
      <PageHeader title="Paper trading" description="The full system running on real market data with simulated money: the dress rehearsal before any real rupee (Gates 4 and 5)." />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="flex min-w-0 flex-col gap-4">
          {paper.isError ? <QueryError error={paper.error} what="the paper account" /> : !p ? <LoadingBlock height={200} /> : !p.started ? (
            <Empty className="border">
              <EmptyHeader>
                <EmptyTitle>The paper account has not started yet</EmptyTitle>
                <EmptyDescription>Use Paper automation to start a research trial with simulated capital. The scheduler follows the configured IST schedule while this application is running.</EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <>
              <MetricGrid>
                <Metric label="Equity" value={rupees(p.equity)} sub={`started ${rupees(p.initial_capital)}`} />
                <Metric label="Return" term="total_return" value={pct(p.return_pct)} tone={p.return_pct >= 0 ? "up" : "down"} />
                <Metric label="Drawdown" term="max_drawdown" value={pct(-Math.abs(p.drawdown_pct))} tone={p.drawdown_pct > 5 ? "down" : "flat"} sub="breaker at 12%" />
                <Metric label="Cash" value={rupees(p.cash)} />
                <Metric label="Open risk" term="stop" value={rupees(p.open_risk)} sub="lost if every stop hits" />
                <Metric label="Last jobs" value={p.last_eod ?? "–"} sub={`open ${p.last_open ?? "–"}`} />
              </MetricGrid>
              {equityPoints.length > 1 && (
                <Card><CardHeader><CardTitle className="font-heading">Paper equity</CardTitle></CardHeader>
                  <CardContent><SeriesChart series={[{ key: "eq", label: "Equity (₹)", points: equityPoints, color: "primary" }]} height={240} /></CardContent>
                </Card>
              )}
              <Card>
                <CardHeader>
                  <CardTitle className="font-heading">Open positions</CardTitle>
                  <CardDescription>Simulated protective stops are managed by this application. They require fresh quotes and a running process; they are not live broker orders.</CardDescription>
                </CardHeader>
                <CardContent>
                  {Object.keys(p.positions).length === 0 ? <p className="text-sm text-muted-foreground">No open positions.</p> : (
                    <Table>
                      <TableHeader><TableRow><TableHead>Symbol</TableHead><TableHead>Strategy</TableHead><TableHead className="text-right">Qty</TableHead><TableHead className="text-right">Entry</TableHead><TableHead className="text-right">Last</TableHead><TableHead className="text-right">Stop</TableHead><TableHead className="text-right">Target</TableHead><TableHead className="text-right">P&amp;L</TableHead><TableHead className="text-right">Days</TableHead><TableHead>Note</TableHead></TableRow></TableHeader>
                      <TableBody>{Object.entries(p.positions).map(([sym, x]) => {
                        const pnl = (x.last_price - x.entry_price) * x.qty
                        return (
                          <TableRow key={sym}>
                            <TableCell className="font-medium">{sym}</TableCell><TableCell className="text-xs">{x.strategy_id}</TableCell>
                            <TableCell className="num text-right">{x.qty}</TableCell><TableCell className="num text-right">{num(x.entry_price)}</TableCell>
                            <TableCell className="num text-right">{num(x.last_price)}</TableCell><TableCell className="num text-right text-down">{num(x.stop)}</TableCell>
                            <TableCell className="num text-right">{num(x.target)}</TableCell><TableCell className={cn("num text-right", toneClass(pnl))}>{rupees(pnl)}</TableCell>
                            <TableCell className="num text-right">{x.bars_held}</TableCell>
                            <TableCell className="text-xs">{x.exit_next_open ? `exit at open: ${x.exit_next_open}` : x.scaled_out ? "scaled out" : ""}</TableCell>
                          </TableRow>
                        )
                      })}</TableBody>
                    </Table>
                  )}
                  {p.pending_entries.length > 0 && <p className="mt-3 text-sm">Pending for the next open: {p.pending_entries.join(", ")}</p>}
                  {Object.keys(p.disabled_strategies).length > 0 && <p className="mt-2 text-sm text-down">Paused strategies: {Object.entries(p.disabled_strategies).map(([k, v]) => `${k} (${v})`).join("; ")}</p>}
                </CardContent>
              </Card>
            </>
          )}
          <Card>
            <CardHeader><CardTitle className="font-heading">Journal</CardTitle><CardDescription>Every signal, risk decision, order, trade and event (data/journal.duckdb): the raw material for the weekly review.</CardDescription></CardHeader>
            <CardContent>
              <Tabs defaultValue="trades">
                <TabsList><TabsTrigger value="trades">Trades</TabsTrigger><TabsTrigger value="signals">Signals</TabsTrigger><TabsTrigger value="orders">Orders</TabsTrigger><TabsTrigger value="events">Events</TabsTrigger></TabsList>
                {(["trades", "signals", "orders", "events"] as const).map((t) => <TabsContent key={t} value={t}><JournalTable table={t} /></TabsContent>)}
              </Tabs>
            </CardContent>
          </Card>
          <WeeklyReviewCard />
          <DemandWatch />
        </div>
        <div className="order-first flex flex-col gap-4 xl:order-last">
          <PaperAutomationCard />
          <KillSwitchCard />
        </div>
      </div>
    </Page>
  )
}
