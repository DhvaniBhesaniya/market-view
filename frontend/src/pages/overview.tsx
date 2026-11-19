import { useQuery } from "@tanstack/react-query"
import { ArrowUpRight, CircleCheck, Circle, CircleDot, Lock } from "lucide-react"
import { Link } from "react-router"

import { Metric, MetricGrid } from "@/components/metric"
import { LoadingBlock, Page, PageHeader, QueryError } from "@/components/page"
import { Term } from "@/components/term"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { api, type RunSummary, type StrategyInfo } from "@/lib/api"
import { gate3Candidate } from "@/lib/gates"
import { int, pct, rupees, runTime, tone, toneClass } from "@/lib/format"
import { cn } from "@/lib/utils"

type GateState = "done" | "now" | "todo" | "locked"
type Gate = { n: number; title: string; state: GateState; need: string; link?: string }

function GateTrack({ gates }: { gates: Gate[] }) {
  const icon = { done: CircleCheck, now: CircleDot, todo: Circle, locked: Lock }
  return (
    <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4" aria-label="Roadmap gates">
      {gates.map((g) => {
        const Icon = icon[g.state]
        const body = (
          <div
            className={cn("flex h-full flex-col gap-1.5 rounded-lg border p-3 transition-colors", {
              "border-primary/60 bg-primary/5": g.state === "now",
              "opacity-60": g.state === "locked",
              "hover:bg-accent/50": !!g.link,
            })}
          >
            <div className="flex items-center gap-2">
              <Icon className={cn("size-4 shrink-0", { "text-up": g.state === "done", "text-primary": g.state === "now", "text-muted-foreground": g.state === "todo" || g.state === "locked" })} />
              <span className="num text-xs text-muted-foreground">Gate {g.n}</span>
              {g.state === "now" && <Badge className="ml-auto">you are here</Badge>}
            </div>
            <span className="font-heading text-sm font-semibold">{g.title}</span>
            <span className="text-xs text-muted-foreground">{g.need}</span>
          </div>
        )
        return <li key={g.n}>{g.link ? <Link to={g.link} className="block h-full rounded-lg focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">{body}</Link> : body}</li>
      })}
    </ol>
  )
}

function ScoreRow({ s }: { s: StrategyInfo }) {
  const v = s.latest.validate?.metrics
  const f = s.latest.full?.metrics
  const g3 = gate3Candidate(s)
  return (
    <TableRow>
      <TableCell>
        <Link to={`/strategies/${s.id}`} className="font-medium hover:underline">{s.id}</Link>
        <div className="text-xs text-muted-foreground">{s.kind === "rule" ? "your rule strategy" : "built-in"}</div>
      </TableCell>
      <TableCell className={cn("num text-right", toneClass(f?.total_return_pct))}>{pct(f?.total_return_pct)}</TableCell>
      <TableCell className="num text-right text-muted-foreground">{pct(f?.benchmark_return_pct)}</TableCell>
      <TableCell className="num text-right">{pct(f?.max_drawdown_pct)}</TableCell>
      <TableCell className={cn("num text-right", f && f.profit_factor < 1 ? "text-down" : "")}>{f ? f.profit_factor.toFixed(2) : "–"}</TableCell>
      <TableCell className={cn("num text-right", v && v.profit_factor >= 1.3 ? "text-up" : v ? "text-down" : "")}>{v ? v.profit_factor.toFixed(2) : "–"}</TableCell>
      <TableCell className="num text-right">{int(f?.trades)}</TableCell>
      <TableCell className="max-w-64">
        <Badge variant={g3.ok ? "default" : "outline"}>{g3.ok ? "candidate" : "not yet"}</Badge>
        <div className="mt-1 truncate text-xs text-muted-foreground" title={g3.why}>{g3.why}</div>
      </TableCell>
    </TableRow>
  )
}

export default function Overview() {
  const status = useQuery({ queryKey: ["status"], queryFn: api.status })
  const strategies = useQuery({ queryKey: ["strategies"], queryFn: api.strategies })
  const runs = useQuery({ queryKey: ["backtests"], queryFn: () => api.backtests() })
  const symbols = useQuery({ queryKey: ["symbols"], queryFn: api.symbols, staleTime: 60_000 })
  const paper = useQuery({ queryKey: ["paper"], queryFn: api.paper })

  if (status.isError) return <Page><QueryError error={status.error} what="system status" /></Page>
  const s = status.data
  const strats = strategies.data ?? []
  const anyCandidate = strats.some((x) => gate3Candidate(x).ok)
  const lastBar = symbols.data?.find((r) => r.symbol === "NIFTY50")?.last
  const p = paper.data

  const gates: Gate[] = [
    { n: 0, title: "Setup & basics", state: "done", need: "Project, tests and tooling are in place." },
    { n: 1, title: "Data you can trust", state: "now", need: "Review flagged price jumps; add former NIFTY 50 members (survivorship).", link: "/data" },
    { n: 2, title: "Honest costs", state: "now", need: "Match the cost model to one real Groww contract note (within ₹1)." },
    { n: 3, title: "A strategy worth paper trading", state: anyCandidate ? "now" : "todo",
      need: anyCandidate ? "A candidate exists: run walk-forward + sensitivity, then the locked test once." : "No strategy passes yet (PF ≥ 1.3 out-of-sample, ≥ 100 trades, DD ≤ 15%).", link: "/strategies" },
    { n: 4, title: "Paper system runs unattended", state: s?.paper_started ? "now" : "todo", need: "One full week of paper runs with no crash + kill-switch fire drills.", link: "/paper" },
    { n: 5, title: "Permission to go live", state: "locked", need: "≥ 50 paper trades per strategy, paper ≈ backtest, written live plan." },
    { n: 6, title: "AI earns its place", state: "locked", need: "Each AI component must beat the non-AI baseline out-of-sample." },
    { n: 7, title: "Tiny live capital", state: "locked", need: "₹10-25k, 0.25% risk, broker-side stops, 3+ months." },
  ]

  return (
    <Page>
      <PageHeader
        title="Overview"
        description="Where the project stands, measured by evidence rather than by code written. Nothing here can place an order."
        actions={
          <>
            <Button asChild variant="outline"><Link to="/chart">Open chart</Link></Button>
            <Button asChild><Link to="/builder">Build a strategy</Link></Button>
          </>
        }
      />

      {!s ? <LoadingBlock height={90} /> : (
        <MetricGrid>
          <Metric label="Mode" value="Paper" sub={s.live_trading ? "LIVE_TRADING env is set!" : "live trading off"} tone={s.live_trading ? "down" : "flat"} />
          <Metric label="Kill switch" term="kill_switch" value={s.killswitch.active ? "ON" : "off"} tone={s.killswitch.active ? "down" : "up"} sub={s.killswitch.reason ?? "new entries allowed"} />
          <Metric label="Market data" value={`${s.data[s.data_source] ?? 0} symbols`} sub={`${s.data_source} · ${lastBar ?? "–"}`} />
          <Metric label="Paper account" value={p?.started ? rupees(p.equity) : "not started"} sub={p?.started ? `${pct(p.return_pct)} since start` : "start from Paper trading"} tone={p?.started ? tone(p.return_pct) : "flat"} />
          <Metric label="Risk per trade" term="r_multiple" value={`${s.risk_per_trade_pct}%`} sub={`= ${rupees((s.paper_capital * s.risk_per_trade_pct) / 100)} on ${rupees(s.paper_capital)}`} />
          <Metric label="Daily loss cap" value={`${s.daily_loss_cap_pct}%`} sub="hit it → kill switch" />
        </MetricGrid>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="font-heading">The road to real money</CardTitle>
          <CardDescription>
            Each gate needs evidence, not just working code (docs/04-roadmap.md). Skipping a gate is how accounts get blown up.
          </CardDescription>
        </CardHeader>
        <CardContent><GateTrack gates={gates} /></CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="font-heading">Strategy scoreboard</CardTitle>
          <CardDescription>
            Latest single-strategy runs, after <Term k="charges">charges</Term> and <Term k="slippage">slippage</Term>.
            Full = 2010-2022; the Gate 3 column uses the <Term k="out_of_sample">out-of-sample</Term> validate run.
          </CardDescription>
          <CardAction><Button asChild variant="ghost" size="sm"><Link to="/backtests">Run a backtest <ArrowUpRight data-icon="inline-end" /></Link></Button></CardAction>
        </CardHeader>
        <CardContent>
          {strategies.isError ? <QueryError error={strategies.error} what="strategies" /> : !strategies.data ? <LoadingBlock height={160} /> : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Strategy</TableHead>
                  <TableHead className="text-right"><Term k="total_return">Return</Term> (full)</TableHead>
                  <TableHead className="text-right"><Term k="benchmark">NIFTY</Term></TableHead>
                  <TableHead className="text-right"><Term k="max_drawdown">Max DD</Term></TableHead>
                  <TableHead className="text-right"><Term k="profit_factor">PF</Term> full</TableHead>
                  <TableHead className="text-right">PF validate</TableHead>
                  <TableHead className="text-right"><Term k="trades">Trades</Term></TableHead>
                  <TableHead>Gate 3</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>{strats.map((x) => <ScoreRow key={x.id} s={x} />)}</TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="font-heading">Recent backtests</CardTitle>
          <CardDescription>Every run is logged forever with its parameters and git version, so results can be reproduced.</CardDescription>
        </CardHeader>
        <CardContent>
          {!runs.data ? <LoadingBlock height={120} /> : runs.data.length === 0 ? (
            <p className="text-sm text-muted-foreground">No runs yet. Start one on the Backtests page.</p>
          ) : (
            <ul className="flex flex-col divide-y">
              {runs.data.slice(0, 6).map((r: RunSummary) => (
                <li key={r.run_id}>
                  <Link to={`/backtests/${encodeURIComponent(r.run_id)}`} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-2 text-sm hover:bg-accent/40">
                    <span className="min-w-48 font-medium">{r.label}</span>
                    <Badge variant="outline">{r.period}</Badge>
                    <span className={cn("num", toneClass(r.metrics.total_return_pct))}>{pct(r.metrics.total_return_pct)}</span>
                    <span className="num text-muted-foreground">PF {r.metrics.profit_factor?.toFixed(2)}</span>
                    <span className="num text-muted-foreground">{int(r.metrics.trades)} trades</span>
                    <span className="ml-auto text-xs text-muted-foreground">{runTime(r.run_id)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </Page>
  )
}
