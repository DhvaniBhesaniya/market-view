import { useQuery } from "@tanstack/react-query"
import { Blocks, ChartCandlestick } from "lucide-react"
import { Link } from "react-router"

import { LoadingBlock, Page, PageHeader, QueryError } from "@/components/page"
import { RunBacktestDialog } from "@/components/run-backtest"
import { Term } from "@/components/term"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
import type { RunSummary, StrategyInfo } from "@/lib/api"
import { api } from "@/lib/api"
import { int, pct, toneClass } from "@/lib/format"
import { cn } from "@/lib/utils"
import { gate3Candidate } from "@/lib/gates"

function RunCell({ label, run }: { label: string; run: RunSummary | null }) {
  const m = run?.metrics
  return (
    <div className="flex flex-col gap-0.5 rounded-md bg-muted/50 px-2 py-1.5">
      <span className="text-[11px] text-muted-foreground">{label}</span>
      {m ? (
        <>
          <span className={cn("num text-sm", toneClass(m.total_return_pct))}>{pct(m.total_return_pct)}</span>
          <span className="num text-[11px] text-muted-foreground">PF {m.profit_factor?.toFixed(2)} · {int(m.trades)} tr</span>
        </>
      ) : <span className="text-xs text-muted-foreground">not run</span>}
    </div>
  )
}

function StrategyCard({ s }: { s: StrategyInfo }) {
  const g3 = gate3Candidate(s)
  return (
    <Card>
      <CardHeader>
        <CardTitle className="font-heading">
          <Link to={`/strategies/${s.id}`} className="hover:underline">{s.id}</Link>
        </CardTitle>
        <CardDescription className="line-clamp-3">{s.kind === "rule" ? s.describe : s.description}</CardDescription>
        <CardAction className="flex flex-col items-end gap-1">
          <Badge variant={s.kind === "rule" ? "default" : "secondary"}>{s.kind === "rule" ? "rule" : "built-in"}</Badge>
          {s.enabled && <Badge variant="outline">paper-enabled</Badge>}
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="grid grid-cols-3 gap-2">
          <RunCell label="train" run={s.latest.train} />
          <RunCell label="validate" run={s.latest.validate} />
          <RunCell label="full" run={s.latest.full} />
        </div>
        <p className="text-xs text-muted-foreground">
          <Term k="out_of_sample">Gate 3</Term>: <span className={g3.ok ? "text-up" : ""}>{g3.ok ? "candidate" : "not yet"}</span> ({g3.why})
        </p>
      </CardContent>
      <CardFooter className="flex flex-wrap gap-2">
        <Button asChild size="sm" variant="outline"><Link to={`/strategies/${s.id}`}>Details</Link></Button>
        <Button asChild size="sm" variant="outline"><Link to={`/chart?strategy=${s.id}`}><ChartCandlestick data-icon="inline-start" />Signals</Link></Button>
        <RunBacktestDialog strategyId={s.id} variant="outline" />
      </CardFooter>
    </Card>
  )
}

export default function Strategies() {
  const q = useQuery({ queryKey: ["strategies"], queryFn: api.strategies })
  const rule = q.data?.filter((s) => s.kind === "rule") ?? []
  const builtin = q.data?.filter((s) => s.kind === "builtin") ?? []
  return (
    <Page>
      <PageHeader
        title="Strategies"
        description="Built-in strategies are Python code; rule strategies are the ones you build from indicator conditions. Both run through the same backtester, risk engine and paper trader."
        actions={<Button asChild><Link to="/builder"><Blocks data-icon="inline-start" />Build a strategy</Link></Button>}
      />
      {q.isError ? <QueryError error={q.error} what="strategies" /> : !q.data ? <LoadingBlock height={300} /> : (
        <>
          <section className="flex flex-col gap-3">
            <h2 className="font-heading text-lg font-semibold">Your rule strategies</h2>
            {rule.length === 0 ? (
              <Empty className="border">
                <EmptyHeader>
                  <EmptyTitle>No rule strategies yet</EmptyTitle>
                  <EmptyDescription>Combine indicator conditions into a strategy, preview its signals on a chart, then backtest it honestly.</EmptyDescription>
                </EmptyHeader>
                <EmptyContent><Button asChild><Link to="/builder">Build your first strategy</Link></Button></EmptyContent>
              </Empty>
            ) : (
              <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">{rule.map((s) => <StrategyCard key={s.id} s={s} />)}</div>
            )}
          </section>
          <section className="flex flex-col gap-3">
            <h2 className="font-heading text-lg font-semibold">Built-in strategies</h2>
            <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">{builtin.map((s) => <StrategyCard key={s.id} s={s} />)}</div>
          </section>
        </>
      )}
    </Page>
  )
}
