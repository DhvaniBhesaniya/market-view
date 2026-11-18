import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Download, Settings2 } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { useSearchParams } from "react-router"

import { PriceChart, type Marker, type PriceLevel } from "@/components/charts/price-chart"
import { IndicatorPicker, paramValid, useIndicatorCatalog, type ActiveIndicator } from "@/components/indicator-picker"
import { LoadingBlock, Page, PageHeader, QueryError } from "@/components/page"
import { StrategySelect, SymbolPicker } from "@/components/pickers"
import { Term } from "@/components/term"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Switch } from "@/components/ui/switch"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { api, type ChartDownload, type ChartSource } from "@/lib/api"
import { buildIndicatorLayers, RANGES, startFor, type RangeKey } from "@/lib/chart-data"
import { num, pct } from "@/lib/format"
import { customInterval, formatCandleTime, INTERVALS, type IntervalUnit } from "@/lib/chart-time"
import { useJob } from "@/hooks/use-job"
import { cn } from "@/lib/utils"

const STORE_KEY = "mv.chart.v1"
const DEFAULT_INDICATORS: ActiveIndicator[] = [
  { key: "ema20", ind: "ema", params: { n: 20 } },
  { key: "ema50", ind: "ema", params: { n: 50 } },
  { key: "rsi14", ind: "rsi", params: { n: 14 } },
]

type Saved = { indicators: ActiveIndicator[]; range: RangeKey; volume: boolean; interval: string; source?: ChartSource }

function loadSaved(): Saved {
  try {
    const raw = localStorage.getItem(STORE_KEY)
    if (raw) return { indicators: DEFAULT_INDICATORS, range: "3Y", volume: true, interval: "1d", ...JSON.parse(raw) }
  } catch {
    /* storage blocked: use defaults */
  }
  return { indicators: DEFAULT_INDICATORS, range: "3Y", volume: true, interval: "1d" }
}

export default function ChartPage() {
  const qc = useQueryClient()
  const [params, setParams] = useSearchParams()
  const symbol = params.get("symbol") || "RELIANCE"
  const strategy = params.get("strategy") || ""
  const setQuery = (k: string, v: string) => {
    const next = new URLSearchParams(params)
    if (v) next.set(k, v)
    else next.delete(k)
    setParams(next, { replace: true })
  }

  const [saved] = useState(loadSaved)  // read localStorage once, on mount
  const [indicators, setIndicators] = useState<ActiveIndicator[]>(saved.indicators)
  const [range, setRange] = useState<RangeKey>(saved.range)
  const [volume, setVolume] = useState(saved.volume)
  const [interval, setInterval] = useState(params.get("interval") || saved.interval)
  const [selectedSource, setSource] = useState<ChartSource | undefined>(saved.source)
  const [customCount, setCustomCount] = useState("5")
  const [customUnit, setCustomUnit] = useState<IntervalUnit>("m")
  const [customOpen, setCustomOpen] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const status = useQuery({ queryKey: ["status"], queryFn: api.status })
  const source: ChartSource = selectedSource ?? (status.data?.data_source === "upstox" ? "upstox" : "yfinance")
  const intraday = /[mh]$/.test(interval)
  const daily = interval === "1d"
  const customValue = customInterval(customCount, customUnit)
  const job = useJob<ChartDownload>(jobId)
  const downloading = !!jobId && (!job.data || job.data.status === "queued" || job.data.status === "running")
  const [picked, setPicked] = useState<string | null>(params.get("at"))
  useEffect(() => {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify({ indicators, range, volume, interval, source }))
    } catch {
      /* ignore */
    }
  }, [indicators, range, volume, interval, source])

  useEffect(() => {
    if (job.data?.status !== "done") return
    void qc.invalidateQueries({ queryKey: ["candles"] })
    void qc.invalidateQueries({ queryKey: ["ind"] })
    void qc.invalidateQueries({ queryKey: ["symbols"] })
    void qc.invalidateQueries({ queryKey: ["preview"] })
  }, [job.data?.status, qc])

  function changeInterval(value: string) {
    setPicked(null)
    setInterval(value)
    setRange(/[mh]$/.test(value) ? "5D" : "3Y")
    setQuery("interval", value)
  }

  const { data: catalog = [] } = useIndicatorCatalog()
  const symbols = useQuery({ queryKey: ["symbols", source], queryFn: () => api.chartSymbols(source), staleTime: 60_000 })
  const last = symbols.data?.find((r) => r.symbol === symbol)?.last
  const today = status.data?.now.slice(0, 10) ?? new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" })
  const start = startFor(range, intraday ? today : last)

  const download = useMutation({
    mutationFn: () => api.downloadChart({ symbol, interval, source, start }),
    onSuccess: (result) => setJobId(result.id),
  })

  const candles = useQuery({
    queryKey: ["candles", symbol, start, interval, source],
    queryFn: () => api.candles(symbol, start, undefined, { interval, source }),
    enabled: !!symbols.data,
  })

  // only send indicators whose params are all valid (an invalid box just pauses that one indicator)
  // (memoised: a new array each render would rebuild the chart on every render)
  const valid = useMemo(() => indicators.filter((a) => {
    const d = catalog.find((x) => x.id === a.ind)
    return d && d.params.every((p) => paramValid(p, a.params[p.name]))
  }), [indicators, catalog])
  const ind = useQuery({
    queryKey: ["ind", symbol, start, valid, interval, source],
    queryFn: () => api.computeIndicators(symbol, valid, start, undefined, { interval, source }),
    enabled: valid.length > 0 && !!candles.data?.bars.length,
  })
  const preview = useQuery({
    queryKey: ["preview", strategy, symbol, start, source],
    queryFn: () => api.preview({ strategy_id: strategy, symbol, start, source }),
    enabled: !!strategy && daily && !!candles.data?.bars.length,
  })

  const { overlays, panes } = useMemo(() => buildIndicatorLayers(valid, catalog, ind.data), [valid, catalog, ind.data])
  const markers = useMemo<Marker[]>(() => {
    if (!daily) return []
    const m: Marker[] = (preview.data?.signals ?? []).map((s) => ({ time: s.time, kind: s.time === picked ? "entry" : "signal" }))
    for (const t of preview.data?.exits ?? []) m.push({ time: t, kind: "exit" })
    return m
  }, [preview.data, picked, daily])
  const pickedSignal = daily ? preview.data?.signals.find((s) => s.time === picked) : undefined
  const levels = useMemo<PriceLevel[]>(() => {
    if (!pickedSignal) return []
    const out: PriceLevel[] = [{ price: pickedSignal.close, label: "signal close", kind: "entry" }, { price: pickedSignal.stop, label: "stop", kind: "stop" }]
    if (pickedSignal.target) out.push({ price: pickedSignal.target, label: "target", kind: "target" })
    return out
  }, [pickedSignal])

  const bars = candles.data?.bars ?? []
  const lastBar = bars.at(-1)
  const prev = bars.at(-2)
  const chg = lastBar && prev ? ((lastBar.close / prev.close) - 1) * 100 : null

  return (
    <Page>
      <PageHeader
        title="Chart"
        description={<>Choose the size of each candle separately from how much history to show. Hover a candle for its date, time and prices in IST.</>}
      />
      <div className="flex flex-wrap items-center gap-2">
        <SymbolPicker value={symbol} onChange={(s) => { setPicked(null); setQuery("symbol", s) }} />
        <Select value={source} onValueChange={(v) => { setPicked(null); setSource(v as ChartSource) }}>
          <SelectTrigger aria-label="Chart data source" size="sm"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="yfinance">Yahoo Finance</SelectItem><SelectItem value="upstox">Upstox</SelectItem></SelectContent>
        </Select>
        <StrategySelect value={strategy} onChange={(v) => { setPicked(null); setQuery("strategy", v) }} allowNone placeholder="Show a strategy's signals" />
        <div className="flex items-center gap-2 px-1">
          <Switch id="vol" checked={volume} onCheckedChange={setVolume} />
          <Label htmlFor="vol" className="text-xs">Volume</Label>
        </div>
        {lastBar && (
          <div className="ml-auto flex items-baseline gap-3">
            <span className="font-heading text-lg font-semibold">{symbol}</span>
            <span className="num text-lg">{num(lastBar.close)}</span>
            <span className={cn("num text-sm", chg !== null && chg >= 0 ? "text-up" : "text-down")}>{pct(chg)}</span>
          </div>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-lg border bg-card p-3">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="text-xs font-medium">Candle interval</span>
          <ToggleGroup className="max-w-full flex-wrap" type="single" role="radiogroup" variant="outline" size="sm" value={interval} onValueChange={(v) => v && changeInterval(v)} aria-label="Candle interval">
            {INTERVALS.map((v) => <ToggleGroupItem key={v} value={v}>{v}</ToggleGroupItem>)}
            {!INTERVALS.includes(interval) && <ToggleGroupItem value={interval}>{interval}</ToggleGroupItem>}
          </ToggleGroup>
          <Popover open={customOpen} onOpenChange={setCustomOpen}>
            <PopoverTrigger asChild><Button variant="outline" size="sm"><Settings2 className="size-3.5" />Custom</Button></PopoverTrigger>
            <PopoverContent className="w-72">
              <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); if (customValue) { changeInterval(customValue); setCustomOpen(false) } }}>
                <span className="text-sm font-medium">Custom candle interval</span>
                <div className="flex gap-2">
                  <Input aria-label="Custom interval amount" type="number" min={1} step={1} value={customCount} onChange={(e) => setCustomCount(e.target.value)} />
                  <Select value={customUnit} onValueChange={(v) => setCustomUnit(v as IntervalUnit)}>
                    <SelectTrigger aria-label="Custom interval unit"><SelectValue /></SelectTrigger>
                    <SelectContent>{([['s', 'Seconds'], ['m', 'Minutes'], ['h', 'Hours'], ['d', 'Days'], ['w', 'Weeks'], ['M', 'Months']] as const).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <p className="text-xs text-muted-foreground">{customUnit === "s" ? "Seconds need a recorded tick-data feed. These sources provide history from 1 minute; seconds cannot be made from minute or daily candles." : "Use a positive whole number. Custom candles combine observed smaller candles; missing trades are never invented."}</p>
                <Button type="submit" disabled={!customValue}>Apply interval</Button>
              </form>
            </PopoverContent>
          </Popover>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Label htmlFor="chart-history" className="text-xs">History</Label>
          <Select value={range} onValueChange={(v) => setRange(v as RangeKey)}>
            <SelectTrigger id="chart-history" aria-label="History range" size="sm"><SelectValue /></SelectTrigger>
            <SelectContent>{(Object.keys(RANGES) as RangeKey[]).map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <Button className="sm:ml-auto" size="sm" variant="outline" disabled={download.isPending || downloading || (source === "upstox" && !status.data?.upstox_token_set)} onClick={() => { setJobId(null); download.mutate() }}>
          <Download className="size-3.5" />{download.isPending || downloading ? "Downloading…" : "Download / update candles"}
        </Button>
      </div>
      <div className="flex flex-col gap-1 text-xs text-muted-foreground" data-testid="chart-provenance">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">{source === "yfinance" ? "Yahoo Finance via yfinance" : "Upstox"}</Badge>
          <Badge variant="secondary">Stored history · not live</Badge>
          <span>{source === "yfinance" ? "Split/dividend adjusted; may differ from your broker’s raw prices." : "Broker candles; corporate-action adjustment is not guaranteed."}</span>
        </div>
        {candles.data?.last_observation && <span>Latest stored candle starts {formatCandleTime(candles.data.last_observation)}. {candles.data.aggregated && `${interval} candles combine ${candles.data.source_interval} observations.`}</span>}
        <span>Times are Asia/Kolkata (IST). Daily timestamps mark session start, not an intraday trade. Provider history limits apply; seconds require tick data.</span>
        {source === "upstox" && !status.data?.upstox_token_set && <span>Upstox downloads need your read-only access token configured. Previously saved candles can still be viewed.</span>}
        {candles.data?.truncated && <span>Showing the latest 20,000 candles. Select a shorter history range for a smaller chart.</span>}
      </div>
      {download.isError && <QueryError error={download.error} what="market data download" />}
      {job.data?.status === "error" && <QueryError error={new Error(job.data.error ?? "Download failed")} what="market data download" />}
      {job.data?.status === "done" && job.data.result && <p className="text-xs text-muted-foreground" role="status">Downloaded {job.data.result.bars_downloaded} {job.data.result.source_interval} candles for {job.data.result.symbol} ({job.data.result.start} to {job.data.result.end}).</p>}
      <IndicatorPicker value={indicators} onChange={setIndicators} />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <Card className="min-w-0 overflow-hidden py-0">
          {candles.isError ? <div className="p-4"><QueryError error={candles.error} what={`${symbol} candles`} /></div>
            : !candles.data ? <LoadingBlock height={560} /> : bars.length === 0 ? (
              <div className="flex min-h-80 flex-col items-center justify-center gap-2 p-6 text-center" data-testid="chart-no-data">
                <span className="font-medium">No {interval} candles in this view</span>
                <p className="max-w-md text-sm text-muted-foreground">{candles.data.message ?? "Choose a different history range or download newer data."}</p>
                <p className="max-w-md text-xs text-muted-foreground">Use “Download / update candles” above. Minute charts require minute data; daily prices cannot supply it.</p>
              </div>
            ) : (
              <PriceChart
                key={`${symbol}:${source}:${interval}`}
                bars={bars}
                overlays={overlays}
                panes={panes}
                markers={markers}
                levels={levels}
                showVolume={volume}
                interval={interval}
                height={420 + panes.reduce((h, p) => h + (p.height ?? 110), 0)}
                onPickTime={(t) => preview.data?.signals.some((s) => s.time === t) && setPicked(t)}
              />
            )}
          {ind.isError && <div className="p-3"><QueryError error={ind.error} what="indicators" /></div>}
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="font-heading">{strategy ? strategy : "Strategy signals"}</CardTitle>
            <CardDescription>
              {!daily ? "Strategy signals are defined on daily candles. Select 1d to view them; indicators here follow your selected candle interval." : strategy ? <>Arrows mark days the strategy said BUY at the close. It would buy at the <Term k="next_open">next open</Term>. Click an arrow or a row for the reasons.</>
                : "Pick a strategy above to see where it would have bought on this chart."}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {daily && preview.isError && <QueryError error={preview.error} what="signals" />}
            {daily && preview.data && (
              <>
                <div className="flex flex-wrap gap-1.5">
                  <Badge variant="secondary">{preview.data.signals.length} signals</Badge>
                  {preview.data.exits && preview.data.exits.length > 0 && <Badge variant="outline">{preview.data.exits.length} exit-rule days</Badge>}
                </div>
                {preview.data.condition_stats && (
                  <div className="flex flex-col gap-1 text-xs">
                    <span className="text-muted-foreground">How often each rule was true (of {preview.data.bars} days):</span>
                    {preview.data.condition_stats.map((c) => (
                      <div key={c.label} className="flex justify-between gap-2"><span className="truncate">{c.label}</span><span className="num">{c.true_bars}</span></div>
                    ))}
                    <div className="flex justify-between gap-2 font-medium"><span>all together</span><span className="num">{preview.data.all_conditions_bars}</span></div>
                    {!!preview.data.blocked_by_market_filter && (
                      <div className="flex justify-between gap-2 text-muted-foreground"><span>blocked by <Term k="market_filter">market filter</Term></span><span className="num">{preview.data.blocked_by_market_filter}</span></div>
                    )}
                  </div>
                )}
                {pickedSignal && (
                  <div className="flex flex-col gap-1.5 rounded-md border border-primary/50 bg-primary/5 p-2.5 text-xs">
                    <div className="flex justify-between"><span className="font-medium">{pickedSignal.time}</span>{pickedSignal.regime && <Badge variant="outline">{pickedSignal.regime}</Badge>}</div>
                    <div className="num flex flex-wrap gap-x-3">
                      <span>close {num(pickedSignal.close)}</span>
                      <span className="text-down">stop {num(pickedSignal.stop)}</span>
                      {pickedSignal.target && <span className="text-up">target {num(pickedSignal.target)}</span>}
                    </div>
                    <span className="num text-muted-foreground">risk {pct(((pickedSignal.close - pickedSignal.stop) / pickedSignal.close) * 100, 2, false)} of price per share</span>
                    <ul className="flex list-disc flex-col gap-0.5 pl-4">{pickedSignal.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
                  </div>
                )}
                <ScrollArea className="h-72">
                  <ul className="flex flex-col pr-3">
                    {[...preview.data.signals].reverse().map((s) => (
                      <li key={s.time}>
                        <button type="button" onClick={() => setPicked(s.time)}
                          className={cn("num flex w-full justify-between rounded px-1.5 py-1 text-left text-xs hover:bg-accent", picked === s.time && "bg-accent")}>
                          <span>{s.time}</span><span>{num(s.close)}</span><span className="text-down">{num(s.stop)}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </ScrollArea>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </Page>
  )
}
