import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { CircleCheck, CircleX, Play } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { useSearchParams } from "react-router"
import { Area, Bar, BarChart, CartesianGrid, ComposedChart, Line, ReferenceLine, XAxis, YAxis } from "recharts"
import { toast } from "sonner"

import { Metric, MetricGrid } from "@/components/metric"
import { LoadingBlock, Page, PageHeader } from "@/components/page"
import { PeriodToggle, StrategySelect } from "@/components/pickers"
import { Term } from "@/components/term"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
import { Spinner } from "@/components/ui/spinner"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { elapsed, useJob } from "@/hooks/use-job"
import { api, type ValidationRecord } from "@/lib/api"
import { pct, r, toneClass } from "@/lib/format"
import { gate3Candidate } from "@/lib/gates"
import { cn } from "@/lib/utils"

type Kind = ValidationRecord["kind"]

function useValidationRun(kind: Kind) {
  const qc = useQueryClient()
  const [jobId, setJobId] = useState<string | null>(null)
  const job = useJob<ValidationRecord>(jobId)
  const start = useMutation({
    mutationFn: (body: { strategy: string; period?: string }) => api.runValidation(kind, body),
    onSuccess: (j) => setJobId(j.id),
    onError: (e) => toast.error("Not started", { description: e.message }),
  })
  const status = job.data?.status
  useEffect(() => {
    if (status === "done") qc.invalidateQueries({ queryKey: ["validations"] })
    if (status === "error") toast.error(`${kind} failed`, { description: job.data?.error ?? "" })
  }, [status, qc, kind, job.data?.error])
  return { start, job: job.data, busy: start.isPending || status === "queued" || status === "running" }
}

function RunBar({ kind, strategy, period, note }: { kind: Kind; strategy: string; period?: string; note: string }) {
  const { start, job, busy } = useValidationRun(kind)
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button disabled={!strategy || busy} onClick={() => start.mutate({ strategy, period })}>
        {busy ? <Spinner data-icon="inline-start" /> : <Play data-icon="inline-start" />}
        {busy ? `Running ${elapsed(job)}` : "Run"}
      </Button>
      <span className="text-xs text-muted-foreground">{note}</span>
    </div>
  )
}

const num = (v: unknown) => (typeof v === "number" ? v : Number(v))

function WalkForward({ rec }: { rec: ValidationRecord }) {
  const rows = (rec.rows ?? []).map((x) => ({ window: String(x.test_window), strategy: num(x.return_pct), nifty: num(x.nifty_return_pct), trades: num(x.trades), pf: num(x.profit_factor), exp: num(x.expectancy_r) }))
  const s = rec.summary as { windows: number; profitable_windows_pct: number; beat_nifty_windows_pct: number; total_trades: number; gate_3_walkforward_ok: boolean }
  const config = { strategy: { label: "Strategy", color: "var(--chart-1)" }, nifty: { label: "NIFTY", color: "var(--chart-3)" } } satisfies ChartConfig
  return (
    <div className="flex flex-col gap-4">
      <MetricGrid>
        <Metric label="Profitable windows" value={pct(s.profitable_windows_pct, 0, false)} tone={s.gate_3_walkforward_ok ? "up" : "down"} sub="Gate 3 needs ≥ 60%" />
        <Metric label="Beat NIFTY" value={pct(s.beat_nifty_windows_pct, 0, false)} sub={`of ${s.windows} yearly windows`} />
        <Metric label="Trades" term="trades" value={s.total_trades} />
      </MetricGrid>
      <ChartContainer config={config} className="h-72 w-full">
        <BarChart data={rows}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="window" tickLine={false} axisLine={false} />
          <YAxis tickFormatter={(v) => `${v}%`} width={48} />
          <ReferenceLine y={0} stroke="var(--muted-foreground)" />
          <ChartTooltip content={<ChartTooltipContent />} />
          <Bar dataKey="strategy" fill="var(--color-strategy)" radius={3} />
          <Bar dataKey="nifty" fill="var(--color-nifty)" radius={3} />
        </BarChart>
      </ChartContainer>
      <Table>
        <TableHeader><TableRow><TableHead>Test year</TableHead><TableHead className="text-right">Return</TableHead><TableHead className="text-right">NIFTY</TableHead><TableHead className="text-right">PF</TableHead><TableHead className="text-right">Exp. R</TableHead><TableHead className="text-right">Trades</TableHead></TableRow></TableHeader>
        <TableBody>{rows.map((x) => (
          <TableRow key={x.window}>
            <TableCell className="num">{x.window}</TableCell>
            <TableCell className={cn("num text-right", toneClass(x.strategy))}>{pct(x.strategy)}</TableCell>
            <TableCell className="num text-right text-muted-foreground">{pct(x.nifty)}</TableCell>
            <TableCell className="num text-right">{x.pf.toFixed(2)}</TableCell>
            <TableCell className={cn("num text-right", toneClass(x.exp))}>{r(x.exp)}</TableCell>
            <TableCell className="num text-right">{x.trades}</TableCell>
          </TableRow>
        ))}</TableBody>
      </Table>
    </div>
  )
}

function Sensitivity({ rec }: { rec: ValidationRecord }) {
  const rows = rec.rows ?? []
  const params = [...new Set(rows.map((x) => String(x.param)))]
  const plateau = new Map((rec.plateau ?? []).map((p) => [String(p.param), p]))
  const maxAbs = Math.max(0.05, ...rows.map((x) => Math.abs(num(x.expectancy_r))))
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">Each cell is the <Term k="expectancy_r">expectancy</Term> with that one parameter changed. Green neighbours all round = a plateau (robust). One green cell among red = a spike (curve-fit).</p>
      <Table>
        <TableHeader><TableRow><TableHead>Parameter</TableHead><TableHead>Values tested (−20% … +20%)</TableHead><TableHead>Plateau?</TableHead></TableRow></TableHeader>
        <TableBody>
          {params.map((p) => {
            const cells = rows.filter((x) => String(x.param) === p)
            const pl = plateau.get(p)
            return (
              <TableRow key={p}>
                <TableCell className="font-medium">{p}</TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {cells.map((c) => {
                      const e = num(c.expectancy_r)
                      const a = Math.min(1, Math.abs(e) / maxAbs)
                      return (
                        <div key={String(c.value)} title={`PF ${num(c.profit_factor).toFixed(2)}, ${c.trades} trades, return ${pct(num(c.return_pct))}`}
                          className={cn("num flex min-w-16 flex-col rounded px-2 py-1 text-center text-[11px]", num(c.factor) === 1 && "ring-1 ring-primary")}
                          style={{ background: `color-mix(in oklch, var(--${e >= 0 ? "up" : "down"}) ${Math.round(12 + a * 45)}%, transparent)` }}>
                          <span className="text-muted-foreground">{String(c.value)}</span>
                          <span>{r(e)}</span>
                        </div>
                      )
                    })}
                  </div>
                </TableCell>
                <TableCell>{pl?.all_profitable ? <Badge>plateau</Badge> : <Badge variant="outline">no</Badge>}</TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}

function MonteCarlo({ rec }: { rec: ValidationRecord }) {
  const f = rec.fan
  const s = rec.summary as { error?: string; final_return_pct: Record<string, number>; max_drawdown_pct: Record<string, number>; longest_losing_streak: Record<string, number>; prob_loss_pct: number; runs: number; risk_pct_per_trade: number }
  const data = useMemo(() => (f && !f.error ? f.trade_no.map((n, i) => ({ n, band: [f.p5[i], f.p95[i]], mid: [f.p25[i], f.p75[i]], p50: f.p50[i], actual: f.actual[i] })) : []), [f])
  if (s?.error || f?.error) return <Alert><AlertTitle>Not enough trades</AlertTitle><AlertDescription>{s?.error ?? f?.error}</AlertDescription></Alert>
  const fanConfig = { band: { label: "p5-p95", color: "var(--chart-3)" }, mid: { label: "p25-p75", color: "var(--chart-3)" }, p50: { label: "median", color: "var(--chart-1)" }, actual: { label: "actual order", color: "var(--foreground)" } } satisfies ChartConfig
  const histConfig = { count: { label: "trades", color: "var(--chart-2)" } } satisfies ChartConfig
  return (
    <div className="flex flex-col gap-4">
      <MetricGrid>
        <Metric label="Return, bad case (p5)" value={pct(s.final_return_pct.p5)} tone={s.final_return_pct.p5 >= 0 ? "up" : "down"} sub={`median ${pct(s.final_return_pct.p50)}`} />
        <Metric label="Max DD, typical" term="max_drawdown" value={pct(s.max_drawdown_pct.p50)} sub={`1-in-20: ${pct(s.max_drawdown_pct.p95)}`} />
        <Metric label="Max DD, worst seen" value={pct(s.max_drawdown_pct.worst)} tone="down" sub={`of ${s.runs} reshuffles`} />
        <Metric label="Losing streak" value={`${s.longest_losing_streak.p50} → ${s.longest_losing_streak.p95}`} sub="typical → 1-in-20" />
        <Metric label="Chance of a loss" value={pct(s.prob_loss_pct, 1, false)} tone={s.prob_loss_pct > 20 ? "down" : "flat"} sub={`at ${s.risk_pct_per_trade}% risk/trade`} />
      </MetricGrid>
      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <div className="flex flex-col gap-1">
          <span className="text-sm font-medium">The cone of plausible equity paths (% return after N trades)</span>
          <ChartContainer config={fanConfig} className="h-80 w-full">
            <ComposedChart data={data}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="n" tickLine={false} axisLine={false} />
              <YAxis tickFormatter={(v) => `${v}%`} width={48} />
              <ReferenceLine y={0} stroke="var(--muted-foreground)" />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Area dataKey="band" stroke="none" fill="var(--color-band)" fillOpacity={0.18} isAnimationActive={false} />
              <Area dataKey="mid" stroke="none" fill="var(--color-mid)" fillOpacity={0.3} isAnimationActive={false} />
              <Line dataKey="p50" stroke="var(--color-p50)" dot={false} strokeWidth={2} isAnimationActive={false} />
              <Line dataKey="actual" stroke="var(--color-actual)" dot={false} strokeDasharray="4 3" isAnimationActive={false} />
            </ComposedChart>
          </ChartContainer>
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-sm font-medium">Distribution of trade results (<Term k="r_multiple">R</Term>)</span>
          <ChartContainer config={histConfig} className="h-80 w-full">
            <BarChart data={(f?.r_histogram ?? []).map((b) => ({ ...b, bucket: `${b.from}` }))}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="bucket" tickLine={false} axisLine={false} interval="preserveStartEnd" />
              <YAxis width={36} />
              <ReferenceLine x="0" stroke="var(--muted-foreground)" />
              <ChartTooltip content={<ChartTooltipContent labelFormatter={(_, p) => { const b = p?.[0]?.payload; return b ? `${b.from}R to ${b.to}R` : "" }} />} />
              <Bar dataKey="count" fill="var(--color-count)" radius={2} />
            </BarChart>
          </ChartContainer>
        </div>
      </div>
    </div>
  )
}

function Latest({ kind, strategy, children }: { kind: Kind; strategy: string; children: (rec: ValidationRecord) => React.ReactNode }) {
  const q = useQuery({ queryKey: ["validations", strategy, kind], queryFn: () => api.validations(strategy, kind), enabled: !!strategy })
  const [idx, setIdx] = useState(0)
  if (!strategy) return null
  if (!q.data) return <LoadingBlock height={200} />
  if (q.data.length === 0)
    return <Empty className="border"><EmptyHeader><EmptyTitle>Not run yet for {strategy}</EmptyTitle><EmptyDescription>Press Run above. Results are saved to data/validations.jsonl.</EmptyDescription></EmptyHeader></Empty>
  const rec = q.data[Math.min(idx, q.data.length - 1)]
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <span>Showing run from {rec.created_at.slice(0, 16).replace("T", " ")}{rec.period ? ` · period ${rec.period}` : ""} · git {rec.git}</span>
        {q.data.length > 1 && (
          <select className="rounded border bg-background px-1 py-0.5" value={idx} onChange={(e) => setIdx(Number(e.target.value))} aria-label="Earlier runs">
            {q.data.map((x, i) => <option key={x.id} value={i}>{x.created_at.slice(0, 16).replace("T", " ")}</option>)}
          </select>
        )}
      </div>
      {children(rec)}
    </div>
  )
}

function Gate3Checklist({ strategy }: { strategy: string }) {
  const s = useQuery({ queryKey: ["strategy", strategy], queryFn: () => api.strategy(strategy), enabled: !!strategy })
  const wf = useQuery({ queryKey: ["validations", strategy, "walkforward"], queryFn: () => api.validations(strategy, "walkforward"), enabled: !!strategy })
  const sens = useQuery({ queryKey: ["validations", strategy, "sensitivity"], queryFn: () => api.validations(strategy, "sensitivity"), enabled: !!strategy })
  if (!strategy || !s.data) return null
  const bt = gate3Candidate(s.data)
  const wfRec = wf.data?.[0]
  const wfOk = (wfRec?.summary as { gate_3_walkforward_ok?: boolean } | undefined)?.gate_3_walkforward_ok
  const sensRec = sens.data?.[0]
  const sensOk = sensRec ? (sensRec.plateau ?? []).every((p) => p.all_profitable) && (sensRec.plateau ?? []).length > 0 : undefined
  const items: { label: React.ReactNode; ok: boolean | undefined; why: string }[] = [
    { label: <>Out-of-sample PF ≥ 1.3, ≥ 100 trades, DD ≤ 15%</>, ok: bt.ok, why: bt.why },
    { label: <><Term k="walkforward">Walk-forward</Term>: profitable in ≥ 60% of years</>, ok: wfOk, why: wfRec ? `${(wfRec.summary as { profitable_windows_pct: number }).profitable_windows_pct}% of windows` : "not run" },
    { label: <><Term k="sensitivity">Neighbouring parameters</Term> (±20%) still profitable</>, ok: sensOk, why: sensRec ? (sensOk ? "plateau on every parameter" : "some parameter has a losing neighbour") : "not run" },
  ]
  const all = items.every((i) => i.ok)
  return (
    <Card>
      <CardHeader>
        <CardTitle className="font-heading">Gate 3 checklist for {strategy}</CardTitle>
        <CardDescription>All must pass before the locked 2023-2025 test is run (once, from the CLI). Never lower the bar to make a strategy pass.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {items.map((it, i) => (
          <div key={i} className="flex items-start gap-2 text-sm">
            {it.ok ? <CircleCheck className="mt-0.5 size-4 shrink-0 text-up" /> : <CircleX className={cn("mt-0.5 size-4 shrink-0", it.ok === false ? "text-down" : "text-muted-foreground")} />}
            <div className="flex flex-col"><span>{it.label}</span><span className="text-xs text-muted-foreground">{it.why}</span></div>
          </div>
        ))}
        <p className={cn("pt-1 text-sm font-medium", all ? "text-up" : "text-muted-foreground")}>
          {all ? "All research checks pass: the strategy has earned one run on the locked test period." : "Not ready for paper trading yet. That is a normal and useful result."}
        </p>
      </CardContent>
    </Card>
  )
}

export default function Validation() {
  const [params, setParams] = useSearchParams()
  const strategy = params.get("strategy") || ""
  const [period, setPeriod] = useState("full")
  return (
    <Page>
      <PageHeader
        title="Validation"
        description="A good backtest is not enough: these tests ask whether the edge survives new years, small parameter changes and bad luck in the order of trades."
        actions={<StrategySelect value={strategy} onChange={(v) => setParams(v ? { strategy: v } : {}, { replace: true })} />}
      />
      {!strategy ? (
        <Empty className="border"><EmptyHeader><EmptyTitle>Pick a strategy</EmptyTitle><EmptyDescription>Choose a strategy at the top right to validate it.</EmptyDescription></EmptyHeader></Empty>
      ) : (
        <>
          <Gate3Checklist strategy={strategy} />
          <Tabs defaultValue="walkforward">
            <TabsList>
              <TabsTrigger value="walkforward">Walk-forward</TabsTrigger>
              <TabsTrigger value="sensitivity">Sensitivity</TabsTrigger>
              <TabsTrigger value="montecarlo">Monte Carlo</TabsTrigger>
            </TabsList>
            <TabsContent value="walkforward">
              <Card>
                <CardHeader>
                  <CardTitle className="font-heading"><Term k="walkforward">Walk-forward</Term></CardTitle>
                  <CardDescription>Each year from 2014 to 2022 is tested on its own, as if you started trading on 1 January of that year.</CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-4">
                  <RunBar kind="walkforward" strategy={strategy} note="~9 backtests, usually under a minute." />
                  <Latest kind="walkforward" strategy={strategy}>{(rec) => <WalkForward rec={rec} />}</Latest>
                </CardContent>
              </Card>
            </TabsContent>
            <TabsContent value="sensitivity">
              <Card>
                <CardHeader>
                  <CardTitle className="font-heading"><Term k="sensitivity">Parameter sensitivity</Term></CardTitle>
                  <CardDescription>Every numeric parameter nudged ±10% and ±20% (whole numbers move by ±1, ±2).</CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-4">
                  <div className="flex flex-wrap items-center gap-3"><PeriodToggle value={period} onChange={setPeriod} /></div>
                  <RunBar kind="sensitivity" strategy={strategy} period={period} note="One backtest per value: can take several minutes on 'full'. It runs in the background." />
                  <Latest kind="sensitivity" strategy={strategy}>{(rec) => <Sensitivity rec={rec} />}</Latest>
                </CardContent>
              </Card>
            </TabsContent>
            <TabsContent value="montecarlo">
              <Card>
                <CardHeader>
                  <CardTitle className="font-heading"><Term k="montecarlo">Monte Carlo</Term></CardTitle>
                  <CardDescription>1,000 reshuffles of the strategy's own trade results show how different the SAME edge could have felt.</CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-4">
                  <div className="flex flex-wrap items-center gap-3"><PeriodToggle value={period} onChange={setPeriod} /></div>
                  <RunBar kind="montecarlo" strategy={strategy} period={period} note="One backtest + 1,000 simulations: ~20-40 s." />
                  <Latest kind="montecarlo" strategy={strategy}>{(rec) => <MonteCarlo rec={rec} />}</Latest>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      )}
    </Page>
  )
}
