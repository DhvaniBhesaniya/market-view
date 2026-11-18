import { useQuery } from "@tanstack/react-query"
import { ChartCandlestick, CopyPlus, ShieldCheck } from "lucide-react"
import { Link, useParams } from "react-router"

import { LoadingBlock, Page, PageHeader, QueryError } from "@/components/page"
import { RunBacktestDialog } from "@/components/run-backtest"
import { Term } from "@/components/term"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { api } from "@/lib/api"
import { describeCondition } from "@/lib/describe"
import { int, pct, runTime, toneClass } from "@/lib/format"
import { cn } from "@/lib/utils"

export default function StrategyDetail() {
  const { id = "" } = useParams()
  const q = useQuery({ queryKey: ["strategy", id], queryFn: () => api.strategy(id) })
  const runs = useQuery({ queryKey: ["backtests", id], queryFn: () => api.backtests(id) })
  if (q.isError) return <Page><QueryError error={q.error} what={`strategy ${id}`} /></Page>
  const s = q.data
  return (
    <Page>
      <PageHeader
        title={id}
        description={s ? (s.kind === "rule" ? s.describe : s.description) : undefined}
        actions={s && (
          <>
            <Button asChild variant="outline" size="sm"><Link to={`/chart?strategy=${id}`}><ChartCandlestick data-icon="inline-start" />Signals on chart</Link></Button>
            <Button asChild variant="outline" size="sm"><Link to={`/validation?strategy=${id}`}><ShieldCheck data-icon="inline-start" />Validate</Link></Button>
            {s.kind === "rule" && (
              <Button asChild variant="outline" size="sm"><Link to={`/builder?from=${id}`}><CopyPlus data-icon="inline-start" />Edit as v{s.version + 1}</Link></Button>
            )}
            <RunBacktestDialog strategyId={id} />
          </>
        )}
      />
      {!s ? <LoadingBlock height={300} /> : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <Card>
            <CardHeader>
              <CardTitle className="font-heading">Rules</CardTitle>
              <CardDescription>
                {s.kind === "rule"
                  ? <>Saved {s.created_at?.slice(0, 16).replace("T", " ")}. Versions never change after saving: editing creates v{s.version + 1}.</>
                  : "Hand-written in src/market_view/strategies/. A parameter change means a new version in code."}
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4 text-sm">
              {s.hypothesis && (
                <div className="rounded-md border-l-2 border-primary bg-primary/5 px-3 py-2">
                  <span className="text-xs text-muted-foreground">Why it should work (hypothesis)</span>
                  <p>{s.hypothesis}</p>
                </div>
              )}
              {s.spec && (
                <div className="flex flex-col gap-2">
                  <span className="text-xs font-medium text-muted-foreground">BUY when ALL of</span>
                  <ul className="flex flex-col gap-1">{s.spec.entry.map((c, i) => <li key={i} className="num rounded bg-muted/60 px-2 py-1 text-xs">{describeCondition(c)}</li>)}</ul>
                  {s.spec.exit.length > 0 && (
                    <>
                      <span className="text-xs font-medium text-muted-foreground">SELL at next open when ANY of</span>
                      <ul className="flex flex-col gap-1">{s.spec.exit.map((c, i) => <li key={i} className="num rounded bg-muted/60 px-2 py-1 text-xs">{describeCondition(c)}</li>)}</ul>
                    </>
                  )}
                </div>
              )}
              <div className="flex flex-col gap-1">
                <span className="text-xs font-medium text-muted-foreground">Parameters</span>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3">
                  {Object.entries(s.defaults).map(([k, v]) => (
                    <div key={k} className="flex justify-between gap-2 border-b border-dashed py-0.5 text-xs">
                      <span className="truncate text-muted-foreground">{k}</span><span className="num">{String(v)}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {s.enabled && <Badge>enabled for paper trading</Badge>}
                {s.scale_out_r && <Badge variant="outline">scale out 50% at {s.scale_out_r}R</Badge>}
                {s.allowed_regimes && <Badge variant="outline"><Term k="regime">regimes</Term>: {s.allowed_regimes.join(", ")}</Badge>}
              </div>
            </CardContent>
          </Card>
          {s.card_md && (
            <Card>
              <CardHeader>
                <CardTitle className="font-heading">Strategy card</CardTitle>
                <CardDescription>docs/strategies/{id}.md: thesis and results history</CardDescription>
              </CardHeader>
              <CardContent>
                <pre className="max-h-[520px] overflow-auto text-xs leading-relaxed whitespace-pre-wrap">{s.card_md}</pre>
              </CardContent>
            </Card>
          )}
        </div>
      )}
      <Card>
        <CardHeader>
          <CardTitle className="font-heading">Every backtest of {id}</CardTitle>
          <CardDescription>Kept forever (data/experiments.jsonl). Compare periods: a strategy that only works in train is curve-fitted.</CardDescription>
        </CardHeader>
        <CardContent>
          {!runs.data ? <LoadingBlock height={120} /> : runs.data.length === 0 ? <p className="text-sm text-muted-foreground">Not backtested yet.</p> : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>When</TableHead><TableHead>Run</TableHead><TableHead>Period</TableHead>
                  <TableHead className="text-right"><Term k="total_return">Return</Term></TableHead>
                  <TableHead className="text-right"><Term k="max_drawdown">Max DD</Term></TableHead>
                  <TableHead className="text-right"><Term k="profit_factor">PF</Term></TableHead>
                  <TableHead className="text-right"><Term k="sharpe">Sharpe</Term></TableHead>
                  <TableHead className="text-right"><Term k="trades">Trades</Term></TableHead>
                  <TableHead>git</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.data.map((r) => (
                  <TableRow key={r.run_id}>
                    <TableCell className="text-xs text-muted-foreground">{runTime(r.run_id)}</TableCell>
                    <TableCell><Link className="hover:underline" to={`/backtests/${encodeURIComponent(r.run_id)}`}>{r.label}</Link></TableCell>
                    <TableCell><Badge variant="outline">{r.period}</Badge></TableCell>
                    <TableCell className={cn("num text-right", toneClass(r.metrics.total_return_pct))}>{pct(r.metrics.total_return_pct)}</TableCell>
                    <TableCell className="num text-right">{pct(r.metrics.max_drawdown_pct)}</TableCell>
                    <TableCell className="num text-right">{r.metrics.profit_factor?.toFixed(2)}</TableCell>
                    <TableCell className="num text-right">{r.metrics.sharpe?.toFixed(2)}</TableCell>
                    <TableCell className="num text-right">{int(r.metrics.trades)}</TableCell>
                    <TableCell className="num text-xs text-muted-foreground">{r.git}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </Page>
  )
}
