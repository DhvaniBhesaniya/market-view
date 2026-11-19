import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { Link } from "react-router"
import { toast } from "sonner"

import { Metric, MetricGrid } from "@/components/metric"
import { LoadingBlock, Page, PageHeader, QueryError } from "@/components/page"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useJob } from "@/hooks/use-job"
import { api, type ResearchReport } from "@/lib/api"
import { dateTime, num, pct, r, rupees } from "@/lib/format"

function Report({ report }: { report: ResearchReport }) {
  return <Card>
    <CardHeader><CardTitle className="flex flex-wrap items-center gap-2 font-heading">Research report <Badge variant="outline">{report.status.replaceAll("_", " ")}</Badge></CardTitle>
      <CardDescription>{dateTime(report.created_at)} · {report.protocol} · {report.input_symbols} stored stock histories. {report.reused ? "Existing evidence reused." : ""}</CardDescription>
    </CardHeader>
    <CardContent className="flex flex-col gap-4 text-sm">
      <p>Research candidate only. This report cannot change active strategies, risk limits or trading mode.</p>
      {report.blockers.length > 0 && <details open><summary className="cursor-pointer font-medium">Findings requiring attention ({report.blockers.length})</summary><ul className="mt-2 list-disc space-y-1 pl-5">{report.blockers.slice(0, 50).map((message, i) => <li key={i}>{message}</li>)}</ul>{report.blockers.length > 50 && <p className="mt-2 text-xs text-muted-foreground">Showing the first 50 recorded findings. Review the Data page and the saved report before further experiments.</p>}</details>}
      {report.runs.length > 0 && <Table>
        <TableHeader><TableRow><TableHead>Trial</TableHead><TableHead>Period</TableHead><TableHead className="text-right">Trades</TableHead><TableHead className="text-right">Return</TableHead><TableHead className="text-right">Drawdown</TableHead><TableHead className="text-right">PF</TableHead><TableHead className="text-right">Avg R</TableHead><TableHead className="text-right">Charges</TableHead></TableRow></TableHeader>
        <TableBody>{report.runs.map((trial) => <TableRow key={trial.label}><TableCell className="text-xs">{trial.label}{trial.status !== "complete" && ` · ${trial.status}`}</TableCell><TableCell className="text-xs">{trial.start} → {trial.end}</TableCell><TableCell className="num text-right">{trial.metrics?.trades ?? "—"}</TableCell><TableCell className="num text-right">{pct(trial.metrics?.total_return_pct)}</TableCell><TableCell className="num text-right">{pct(trial.metrics?.max_drawdown_pct)}</TableCell><TableCell className="num text-right">{num(trial.metrics?.profit_factor)}</TableCell><TableCell className="num text-right">{r(trial.metrics?.expectancy_r)}</TableCell><TableCell className="num text-right">{rupees(trial.metrics?.total_charges)}</TableCell></TableRow>)}</TableBody>
      </Table>}
      {Object.keys(report.checks).length > 0 && <ul className="grid gap-1 text-xs sm:grid-cols-2">{Object.entries(report.checks).map(([check, passed]) => <li key={check}>{passed ? "Pass" : "Fail"} · {check.replaceAll("_", " ")}</li>)}</ul>}
      <div><p className="font-medium">Evidence still required before promotion</p><ul className="mt-2 list-disc space-y-1 pl-5">{report.remaining_evidence.map((item) => <li key={item}>{item}</li>)}</ul></div>
      <p className="break-all text-xs text-muted-foreground">Report {report.id}. Frozen evidence fingerprint {report.fingerprint.slice(0, 16)}.</p>
    </CardContent>
  </Card>
}

export default function Research() {
  const client = useQueryClient()
  const q = useQuery({ queryKey: ["research"], queryFn: api.research, refetchInterval: 10_000 })
  const [jobId, setJobId] = useState<string | null>(null)
  const job = useJob<ResearchReport>(jobId)
  const run = useMutation({ mutationFn: api.runResearch, onSuccess: (j) => setJobId(j.id), onError: (e) => toast.error(e.message) })
  const control = useMutation({ mutationFn: api.controlResearch,
    onSuccess: () => client.invalidateQueries({ queryKey: ["research"] }), onError: (e) => toast.error(e.message),
  })
  useEffect(() => {
    if (job.data?.status === "done" || job.data?.status === "error") client.invalidateQueries({ queryKey: ["research"] })
  }, [job.data?.status, client])
  const data = q.data
  const pending = run.isPending || (!!jobId && job.data?.status !== "done" && job.data?.status !== "error")
  return <Page>
    <PageHeader title="Research lab" description="Automatic, reproducible research using stored data and fixed rules. No AI key required. Results never promise profit or silently change trading." />
    {q.isError ? <QueryError error={q.error} what="research evidence" /> : !data ? <LoadingBlock height={300} /> : <>
      <Card><CardHeader><CardTitle className="font-heading">Market context</CardTitle><CardDescription>Latest completed stored NIFTY bar. This describes trend and volatility; it does not understand every market influence.</CardDescription></CardHeader>
        <CardContent className="flex flex-col gap-3">
          {data.market.available ? <><MetricGrid><Metric label="Regime" value={data.market.regime.replaceAll("_", " ")} /><Metric label="NIFTY close" value={num(data.market.close)} /><Metric label="Trend ADX" value={num(data.market.adx)} /><Metric label="India VIX" value={num(data.market.vix)} /></MetricGrid><p className="text-xs text-muted-foreground">{dateTime(data.market.as_of)} IST · {data.market.source} · {data.market.calendar_age_days} calendar days old. {data.market.meaning}</p></> : <p>No completed benchmark history is available. Download and review data first.</p>}
          <p className="text-xs text-muted-foreground">News/event classification is not connected. Gemini could later help explain text or journals; price processing, testing and risk controls run without an LLM.</p>
        </CardContent>
      </Card>
      <Card><CardHeader><CardTitle className="font-heading">Bounded improvement cycle</CardTitle><CardDescription>Fixed hypothesis: add ADX(14) ≥ 20 to the existing daily trend strategy. Compare against the unchanged baseline, not a search through unlimited indicators.</CardDescription></CardHeader>
        <CardContent className="flex flex-col gap-3 text-sm">
          <p>Check data → freeze inputs and code → compare train/validation → test training neighbours and execution friction → record rejection or remaining evidence. Locked test and forward paper history are excluded.</p>
          <p>Up to {data.status.max_backtests} simulations per new evidence set. Identical snapshots reuse results. Unresolved data issues stop testing. Numeric checks alone do not approve a strategy.</p>
          <div className="flex flex-wrap gap-2"><Button disabled={pending || data.status.busy} onClick={() => run.mutate()}>{pending || data.status.busy ? "Research running…" : "Run research cycle"}</Button><Button variant="outline" disabled={control.isPending} onClick={() => control.mutate(!data.status.enabled)}>{data.status.enabled ? "Disable weekly research" : "Enable weekly research"}</Button><Button variant="outline" asChild><Link to="/data">Review data</Link></Button></div>
          <p className="text-xs text-muted-foreground">Weekly research {data.status.enabled ? "enabled" : "disabled"}: {data.status.schedule}. Uses stored history; keep the application and computer running.</p>
          <p className="text-xs text-muted-foreground">Scheduler {data.status.worker_running ? "running" : "offline"} · heartbeat {dateTime(data.status.heartbeat)}.</p>
          {data.status.stage && <p role="status">{data.status.stage}</p>}
          {jobId && <p role="status">Research job: {job.data?.status ?? "queued"}{job.data?.result?.reused ? " · identical evidence reused" : ""}</p>}
          {(job.data?.error || data.status.last_error) && <p role="alert" className="text-down">{job.data?.error ?? data.status.last_error}</p>}
        </CardContent>
      </Card>
      <Card><CardHeader><CardTitle className="font-heading">NSE pre-open observations</CardTitle></CardHeader><CardContent className="flex flex-col gap-2 text-sm"><p>NSE publishes indicative price, quantity, bids/asks and imbalance during pre-open. Orders can change during collection; a large displayed bid book is not a promise of a rising price.</p><p>Our saved Upstox demand observations still need opening-auction field verification before they can become a strategy input.</p><a className="text-primary underline" href="https://www.nseindia.com/market-data/pre-open-market-cm-and-emerge-market" target="_blank" rel="noreferrer">Open the official NSE pre-open page</a></CardContent></Card>
      {data.reports.length ? data.reports.map((report) => <Report key={report.id} report={report} />) : <p className="text-sm text-muted-foreground">No research reports yet. Run a cycle to check the current data and record the first result.</p>}
    </>}
  </Page>
}
