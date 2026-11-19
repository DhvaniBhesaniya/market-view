import { useMutation, useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import { ChartCandlestick } from "lucide-react"
import { Link } from "react-router"

import { Metric, MetricGrid } from "@/components/metric"
import { LoadingBlock, Page, PageHeader, QueryError } from "@/components/page"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { api } from "@/lib/api"
import { useJob } from "@/hooks/use-job"
import { date, int } from "@/lib/format"

const KIND_HELP: Record<string, string> = {
  price_jump: "Close moved > 20% in one day. Often an unadjusted split/bonus; sometimes a real crash. Check each one.",
  ohlc_inconsistent: "High below low, or close outside the day's range: a bad bar.",
  zero_volume: "No shares traded. Normal for indices; for a stock it may be a holiday or a data hole.",
  duplicate_ts: "The same day appears twice.",
  gap: "More than 7 calendar days without a bar.",
}

export default function Data() {
  const [jobId, setJobId] = useState<string | null>(null)
  const job = useJob(jobId)
  const check = useMutation({ mutationFn: api.checkConnection, onError: (e) => toast.error(e.message) })
  const download = useMutation({ mutationFn: api.downloadDaily, onSuccess: (j) => setJobId(j.id), onError: (e) => toast.error(e.message) })
  const status = useQuery({ queryKey: ["status"], queryFn: api.status })
  const symbols = useQuery({ queryKey: ["symbols"], queryFn: api.symbols, staleTime: 60_000 })
  const quality = useQuery({ queryKey: ["quality"], queryFn: api.dataQuality, staleTime: 300_000 })
  const rows = symbols.data ?? []
  const stored = rows.filter((r) => r.bars > 0)
  const latest = stored.map((r) => r.last ?? "").sort().at(-1)
  const stale = stored.filter((r) => r.last && latest && r.last < latest)
  return (
    <Page>
      <PageHeader title="Data" description="Daily candles stored append-only in data/ (re-downloads never silently overwrite; changed values are logged). Gate 1 asks for clean, survivorship-aware history." />
      {status.data && !status.data.upstox_token_set && (
        <Alert>
          <AlertTitle>Using free yfinance data (delayed, adjusted)</AlertTitle>
          <AlertDescription>
            Configure a read-only Upstox Analytics token as UPSTOX_ACCESS_TOKEN in the local .env file. Then use Check Upstox connection below. Data access does not authorize live trading.
          </AlertDescription>
        </Alert>
      )}
      <Card><CardHeader><CardTitle className="font-heading">Data connection and history</CardTitle><CardDescription>Read-only Upstox access. Refresh the configured daily universe for research; raw observations are retained.</CardDescription></CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={check.isPending || !status.data?.upstox_token_set} onClick={() => check.mutate()}>Check Upstox connection</Button><Button variant="outline" disabled={download.isPending || (!!jobId && job.data?.status !== "done" && job.data?.status !== "error")} onClick={() => download.mutate()}>Refresh daily history</Button></div>
          {check.data && <p className="text-sm">{check.data.ok ? "Connected" : "No benchmark quote"}. {check.data.scope}</p>}
          {jobId && <p className="text-sm">History job: {job.data?.status ?? "queued"}{job.data?.error ? ` — ${job.data.error}` : ""}. Refresh this page after completion to reload coverage.</p>}
        </CardContent>
      </Card>
      <MetricGrid>
        <Metric label="Symbols with data" value={`${stored.length} / ${rows.length}`} sub={status.data?.data_source} />
        <Metric label="Latest bar" value={latest ?? "–"} sub={stale.length ? `${stale.length} symbol(s) behind` : "all up to date"} tone={stale.length ? "warn" : "flat"} />
        <Metric label="Issues found" value={quality.data ? int(quality.data.total) : "…"} sub="see below" />
        <Metric label="Former members" value={rows.filter((r) => r.kind === "former").length} sub="add more: survivorship bias" tone={rows.some((r) => r.kind === "former") ? "flat" : "warn"} />
      </MetricGrid>
      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="font-heading">Quality report</CardTitle>
            <CardDescription>Gate 1 needs every flagged item explained. Unadjusted splits would show up as fake crashes in backtests.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {quality.isError ? <QueryError error={quality.error} what="data quality" /> : !quality.data ? <LoadingBlock height={200} /> : (
              <>
                <div className="flex flex-col gap-1.5">
                  {Object.entries(quality.data.by_kind).map(([k, n]) => (
                    <div key={k} className="flex flex-col gap-0.5 text-sm">
                      <div className="flex justify-between"><span className="font-medium">{k.replace(/_/g, " ")}</span><span className="num">{int(n)}</span></div>
                      <span className="text-xs text-muted-foreground">{KIND_HELP[k] ?? ""}</span>
                    </div>
                  ))}
                </div>
                <Table>
                  <TableHeader><TableRow><TableHead>Symbol</TableHead><TableHead>Kind</TableHead><TableHead>Date</TableHead><TableHead /></TableRow></TableHeader>
                  <TableBody>
                    {quality.data.needs_review.slice(0, 120).map((i, n) => (
                      <TableRow key={n}>
                        <TableCell className="font-medium">{i.symbol}</TableCell>
                        <TableCell><Badge variant="outline">{i.kind}</Badge></TableCell>
                        <TableCell className="num text-xs">{date(i.ts)}</TableCell>
                        <TableCell className="text-right">
                          <Button asChild size="xs" variant="ghost"><Link to={`/chart?symbol=${encodeURIComponent(i.symbol)}`}><ChartCandlestick data-icon="inline-start" />look</Link></Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="font-heading">Coverage</CardTitle><CardDescription>What is stored per symbol.</CardDescription></CardHeader>
          <CardContent>
            {symbols.isError ? <QueryError error={symbols.error} what="symbols" /> : !symbols.data ? <LoadingBlock height={300} /> : (
              <Table>
                <TableHeader><TableRow><TableHead>Symbol</TableHead><TableHead>Sector</TableHead><TableHead className="text-right">Bars</TableHead><TableHead>From</TableHead><TableHead>To</TableHead></TableRow></TableHeader>
                <TableBody>
                  {rows.map((r) => (
                    <TableRow key={r.symbol}>
                      <TableCell><Link to={`/chart?symbol=${encodeURIComponent(r.symbol)}`} className="font-medium hover:underline">{r.symbol}</Link>{r.kind !== "stock" && <Badge variant="outline" className="ml-2">{r.kind}</Badge>}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">{r.sector}</TableCell>
                      <TableCell className="num text-right">{r.bars ? int(r.bars) : <span className="text-down">none</span>}</TableCell>
                      <TableCell className="num text-xs">{r.first ?? "–"}</TableCell>
                      <TableCell className="num text-xs">{r.last ?? "–"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </Page>
  )
}
