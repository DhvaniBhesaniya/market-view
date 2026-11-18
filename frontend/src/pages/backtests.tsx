import { useQueries, useQuery } from "@tanstack/react-query"
import { FlaskConical } from "lucide-react"
import { useMemo, useState } from "react"
import { Link } from "react-router"

import { SeriesChart, type SeriesSpec } from "@/components/charts/series-chart"
import { LoadingBlock, Page, PageHeader, QueryError } from "@/components/page"
import { PeriodToggle } from "@/components/pickers"
import { JobLine, useRunBacktest } from "@/components/run-backtest"
import { Term } from "@/components/term"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldDescription, FieldGroup, FieldLabel, FieldSet, FieldLegend } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { api, type Point } from "@/lib/api"
import { int, pct, runTime, toneClass } from "@/lib/format"
import { cn } from "@/lib/utils"

/** Rebase an equity curve to % return from its first point, so runs of different sizes compare fairly. */
function rebase(points: Point[]): Point[] {
  const first = points[0]?.value
  return first ? points.map((p) => ({ time: p.time, value: (p.value / first - 1) * 100 })) : []
}

export default function Backtests() {
  const strategies = useQuery({ queryKey: ["strategies"], queryFn: api.strategies })
  const runs = useQuery({ queryKey: ["backtests"], queryFn: () => api.backtests() })
  const [chosen, setChosen] = useState<string[]>([])
  const [period, setPeriod] = useState("validate")
  const [enforce, setEnforce] = useState(false)
  const [filter, setFilter] = useState("")
  const [compare, setCompare] = useState<string[]>([])
  const { start, job, busy } = useRunBacktest()

  const compared = useQueries({ queries: compare.map((id) => ({ queryKey: ["backtest", id], queryFn: () => api.backtest(id) })) })
  const compareSeries = useMemo<SeriesSpec[]>(() => {
    const out: SeriesSpec[] = compared.flatMap((q, i) => (q.data ? [{ key: q.data.run_id, label: `${q.data.label} · ${q.data.period}`, points: rebase(q.data.equity), color: i }] : []))
    const firstWithBench = compared.find((q) => q.data?.benchmark.length)?.data
    if (firstWithBench) out.push({ key: "nifty", label: "NIFTY 50 (first run's dates)", points: rebase(firstWithBench.benchmark), color: "muted", dashed: true })
    return out
  }, [compared])

  const rows = (runs.data ?? []).filter((r) => !filter || r.strategies.includes(filter))
  const toggleCompare = (id: string) => setCompare((c) => (c.includes(id) ? c.filter((x) => x !== id) : c.length >= 4 ? c : [...c, id]))

  return (
    <Page>
      <PageHeader title="Backtests" description={<>Event-driven simulation with Indian <Term k="charges">charges</Term>, <Term k="slippage">slippage</Term> and the real risk engine. Results are evidence about the past, not a promise about the future.</>} />

      <Card>
        <CardHeader>
          <CardTitle className="font-heading">Run a backtest</CardTitle>
          <CardDescription>Pick one strategy, or several to test them together as one portfolio (shared capital and risk limits).</CardDescription>
        </CardHeader>
        <CardContent>
          <FieldGroup>
            <FieldSet>
              <FieldLegend variant="label">Strategies</FieldLegend>
              {!strategies.data ? <LoadingBlock height={32} /> : (
                <ToggleGroup type="multiple" variant="outline" size="sm" value={chosen} onValueChange={setChosen} className="flex-wrap" aria-label="Strategies to backtest">
                  {strategies.data.map((s) => <ToggleGroupItem key={s.id} value={s.id}>{s.id}</ToggleGroupItem>)}
                </ToggleGroup>
              )}
            </FieldSet>
            <Field>
              <FieldLabel>Period</FieldLabel>
              <PeriodToggle value={period} onChange={setPeriod} />
            </Field>
            <Field orientation="horizontal">
              <Switch id="enf" checked={enforce} onCheckedChange={setEnforce} />
              <FieldLabel htmlFor="enf"><Term k="enforce_breakers">Enforce breakers</Term></FieldLabel>
            </Field>
            <FieldDescription>Universe: today's NIFTY 50 plus listed former members. Today's winners only = survivorship bias, which flatters results.</FieldDescription>
            <div className="flex flex-wrap items-center gap-3">
              <Button disabled={busy || chosen.length === 0} onClick={() => start.mutate({ strategies: chosen, period, enforce_breakers: enforce })}>
                {busy ? <Spinner data-icon="inline-start" /> : <FlaskConical data-icon="inline-start" />}
                {busy ? "Running" : chosen.length > 1 ? `Run portfolio of ${chosen.length}` : "Run backtest"}
              </Button>
              <JobLine job={job} />
            </div>
          </FieldGroup>
        </CardContent>
      </Card>

      {compare.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="font-heading">Comparing {compare.length} run{compare.length > 1 ? "s" : ""}</CardTitle>
            <CardDescription>Equity rebased to % return from each run's first day. Different periods start at different dates, so compare like with like.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {compared.some((q) => q.isLoading) ? <LoadingBlock height={300} /> : <SeriesChart series={compareSeries} height={320} percent />}
            <Table>
              <TableHeader><TableRow>
                <TableHead>Run</TableHead><TableHead className="text-right">Return</TableHead><TableHead className="text-right">CAGR</TableHead>
                <TableHead className="text-right">Max DD</TableHead><TableHead className="text-right">Sharpe</TableHead><TableHead className="text-right">PF</TableHead>
                <TableHead className="text-right">Trades</TableHead><TableHead className="text-right">Charges</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {compared.map((q) => q.data && (
                  <TableRow key={q.data.run_id}>
                    <TableCell>{q.data.label} <Badge variant="outline">{q.data.period}</Badge></TableCell>
                    <TableCell className={cn("num text-right", toneClass(q.data.metrics.total_return_pct))}>{pct(q.data.metrics.total_return_pct)}</TableCell>
                    <TableCell className="num text-right">{pct(q.data.metrics.cagr_pct)}</TableCell>
                    <TableCell className="num text-right">{pct(q.data.metrics.max_drawdown_pct)}</TableCell>
                    <TableCell className="num text-right">{q.data.metrics.sharpe?.toFixed(2)}</TableCell>
                    <TableCell className="num text-right">{q.data.metrics.profit_factor?.toFixed(2)}</TableCell>
                    <TableCell className="num text-right">{int(q.data.metrics.trades)}</TableCell>
                    <TableCell className="num text-right">₹{int(q.data.metrics.total_charges)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Button variant="ghost" size="sm" className="self-start" onClick={() => setCompare([])}>Clear comparison</Button>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="font-heading">Experiment log</CardTitle>
          <CardDescription>Every run ever made, newest first. Tick up to 4 to compare their equity curves.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <ToggleGroup type="single" variant="outline" size="sm" value={filter || "all"} onValueChange={(v) => setFilter(v === "all" || !v ? "" : v)} className="flex-wrap" aria-label="Filter by strategy">
            <ToggleGroupItem value="all">all</ToggleGroupItem>
            {(strategies.data ?? []).map((s) => <ToggleGroupItem key={s.id} value={s.id}>{s.id}</ToggleGroupItem>)}
          </ToggleGroup>
          {runs.isError ? <QueryError error={runs.error} what="backtests" /> : !runs.data ? <LoadingBlock height={200} /> : (
            <Table>
              <TableHeader><TableRow>
                <TableHead className="w-8"><span className="sr-only">Compare</span></TableHead>
                <TableHead>When</TableHead><TableHead>Strategies</TableHead><TableHead>Period</TableHead>
                <TableHead className="text-right"><Term k="total_return">Return</Term></TableHead>
                <TableHead className="text-right"><Term k="benchmark">NIFTY</Term></TableHead>
                <TableHead className="text-right"><Term k="max_drawdown">Max DD</Term></TableHead>
                <TableHead className="text-right"><Term k="profit_factor">PF</Term></TableHead>
                <TableHead className="text-right"><Term k="expectancy_r">Exp. R</Term></TableHead>
                <TableHead className="text-right"><Term k="trades">Trades</Term></TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {rows.map((r) => (
                  <TableRow key={r.run_id} data-state={compare.includes(r.run_id) ? "selected" : undefined}>
                    <TableCell>
                      <input type="checkbox" aria-label={`Compare ${r.run_id}`} className="size-4 accent-primary" checked={compare.includes(r.run_id)}
                        disabled={!compare.includes(r.run_id) && compare.length >= 4} onChange={() => toggleCompare(r.run_id)} />
                    </TableCell>
                    <TableCell className="text-xs whitespace-nowrap text-muted-foreground">{runTime(r.run_id)}</TableCell>
                    <TableCell><Link className="font-medium hover:underline" to={`/backtests/${encodeURIComponent(r.run_id)}`}>{r.label}</Link></TableCell>
                    <TableCell><Badge variant="outline">{r.period}</Badge>{r.enforce_breakers && <Badge variant="secondary" className="ml-1">enforced</Badge>}</TableCell>
                    <TableCell className={cn("num text-right", toneClass(r.metrics.total_return_pct))}>{pct(r.metrics.total_return_pct)}</TableCell>
                    <TableCell className="num text-right text-muted-foreground">{pct(r.metrics.benchmark_return_pct)}</TableCell>
                    <TableCell className="num text-right">{pct(r.metrics.max_drawdown_pct)}</TableCell>
                    <TableCell className="num text-right">{r.metrics.profit_factor?.toFixed(2)}</TableCell>
                    <TableCell className="num text-right">{r.metrics.expectancy_r?.toFixed(3)}</TableCell>
                    <TableCell className="num text-right">{int(r.metrics.trades)}</TableCell>
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
