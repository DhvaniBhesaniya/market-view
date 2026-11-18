import { useQuery } from "@tanstack/react-query"
import { ChartCandlestick, TriangleExclamationPoint } from "lucide-react"
import { useMemo, useState } from "react"
import { Link, useParams } from "react-router"

import { PriceChart, type Marker, type PriceLevel } from "@/components/charts/price-chart"
import { SeriesChart, type SeriesSpec } from "@/components/charts/series-chart"
import { Metric, MetricGrid } from "@/components/metric"
import { LoadingBlock, Page, PageHeader, QueryError } from "@/components/page"
import { Term } from "@/components/term"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { api, type RunDetail, type Trade } from "@/lib/api"
import { date, int, num, pct, r, rupees, rupeesCompact, toneClass } from "@/lib/format"
import { cn } from "@/lib/utils"

function shiftDays(d: string, days: number): string {
  const x = new Date(`${d.slice(0, 10)}T00:00:00Z`)
  x.setUTCDate(x.getUTCDate() + days)
  return x.toISOString().slice(0, 10)
}

/** One trade on its chart: entry/exit arrows, the initial stop and the target. */
function TradeChart({ t }: { t: Trade }) {
  const entry = date(t.entry_time)
  const exit = date(t.exit_time)
  const candles = useQuery({ queryKey: ["candles", t.symbol, shiftDays(entry, -180), shiftDays(exit, 90)], queryFn: () => api.candles(t.symbol, shiftDays(entry, -180), shiftDays(exit, 90)) })
  const ema = useQuery({
    queryKey: ["ind", t.symbol, "trade", entry],
    queryFn: () => api.computeIndicators(t.symbol, [{ key: "e20", ind: "ema", params: { n: 20 } }, { key: "e50", ind: "ema", params: { n: 50 } }], shiftDays(entry, -180), shiftDays(exit, 90)),
  })
  const markers = useMemo<Marker[]>(() => [{ time: entry, kind: "entry", text: "buy" }, { time: exit, kind: t.net_pnl >= 0 ? "exit" : "stop", text: t.exit_reason }], [entry, exit, t])
  const levels = useMemo<PriceLevel[]>(() => {
    const l: PriceLevel[] = [{ price: t.entry_price, label: "entry", kind: "entry" }, { price: t.initial_stop, label: "initial stop", kind: "stop" }]
    if (t.target) l.push({ price: t.target, label: "target", kind: "target" })
    return l
  }, [t])
  const overlays = useMemo(() => (ema.data ? [
    { key: "e20", label: "EMA(20)", points: ema.data.e20.value },
    { key: "e50", label: "EMA(50)", points: ema.data.e50.value },
  ] : []), [ema.data])
  if (!candles.data) return <LoadingBlock height={380} />
  return <PriceChart bars={candles.data.bars} markers={markers} levels={levels} overlays={overlays} height={380} />
}

function Bars({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1])
  const max = Math.max(1, ...entries.map(([, v]) => v))
  return (
    <ul className="flex flex-col gap-1.5">
      {entries.map(([k, v]) => (
        <li key={k} className="grid grid-cols-[minmax(0,1fr)_3rem] items-center gap-2 text-xs">
          <div className="relative h-6 overflow-hidden rounded bg-muted">
            <div className="absolute inset-y-0 left-0 bg-primary/25" style={{ width: `${(v / max) * 100}%` }} />
            <span className="relative truncate px-2 leading-6">{k}</span>
          </div>
          <span className="num text-right">{int(v)}</span>
        </li>
      ))}
    </ul>
  )
}

function TradesTable({ trades, onPick }: { trades: Trade[]; onPick: (t: Trade) => void }) {
  const [q, setQ] = useState("")
  const [sort, setSort] = useState<{ k: keyof Trade; dir: 1 | -1 }>({ k: "exit_time", dir: -1 })
  const [limit, setLimit] = useState(100)
  const rows = useMemo(() => {
    const f = q ? trades.filter((t) => t.symbol.toLowerCase().includes(q.toLowerCase()) || t.exit_reason.toLowerCase().includes(q.toLowerCase())) : trades
    return [...f].sort((a, b) => {
      const x = a[sort.k], y = b[sort.k]
      return (typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y))) * sort.dir
    })
  }, [trades, q, sort])
  const head = (k: keyof Trade, label: React.ReactNode, right = true) => (
    <TableHead className={right ? "text-right" : ""}>
      <button type="button" className="hover:text-foreground" onClick={() => setSort((s) => ({ k, dir: s.k === k ? (s.dir === 1 ? -1 : 1) : -1 }))}>
        {label}{sort.k === k ? (sort.dir === 1 ? " ↑" : " ↓") : ""}
      </button>
    </TableHead>
  )
  return (
    <div className="flex flex-col gap-2">
      <Input placeholder="Filter by symbol or exit reason…" value={q} onChange={(e) => setQ(e.target.value)} className="max-w-xs" aria-label="Filter trades" />
      <Table>
        <TableHeader><TableRow>
          {head("symbol", "Symbol", false)}{head("entry_time", "Entry", false)}{head("exit_time", "Exit", false)}
          {head("entry_price", "Buy")}{head("exit_price", "Sell")}{head("qty", "Qty")}
          {head("net_pnl", "Net P&L")}{head("r_multiple", <Term k="r_multiple">R</Term>)}
          {head("mae_pct", <Term k="mae">MAE</Term>)}{head("mfe_pct", <Term k="mfe">MFE</Term>)}{head("bars_held", "Days")}
          {head("exit_reason", "Exit reason", false)}
        </TableRow></TableHeader>
        <TableBody>
          {rows.slice(0, limit).map((t, i) => (
            <TableRow key={`${t.symbol}-${t.entry_time}-${i}`} className="cursor-pointer" onClick={() => onPick(t)}>
              <TableCell className="font-medium">{t.symbol}</TableCell>
              <TableCell className="num text-xs">{date(t.entry_time)}</TableCell>
              <TableCell className="num text-xs">{date(t.exit_time)}</TableCell>
              <TableCell className="num text-right">{num(t.entry_price)}</TableCell>
              <TableCell className="num text-right">{num(t.exit_price)}</TableCell>
              <TableCell className="num text-right">{int(t.qty)}</TableCell>
              <TableCell className={cn("num text-right", toneClass(t.net_pnl))}>{rupees(t.net_pnl)}</TableCell>
              <TableCell className={cn("num text-right", toneClass(t.r_multiple))}>{r(t.r_multiple)}</TableCell>
              <TableCell className="num text-right text-muted-foreground">{pct(t.mae_pct, 1)}</TableCell>
              <TableCell className="num text-right text-muted-foreground">{pct(t.mfe_pct, 1)}</TableCell>
              <TableCell className="num text-right">{t.bars_held}</TableCell>
              <TableCell className="text-xs">{t.exit_reason}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {rows.length > limit && <Button variant="outline" size="sm" className="self-center" onClick={() => setLimit((l) => l + 200)}>Show more ({rows.length - limit} left)</Button>}
    </div>
  )
}

function Report({ d }: { d: RunDetail }) {
  const m = d.metrics
  const [picked, setPicked] = useState<Trade | null>(null)
  const equitySeries = useMemo<SeriesSpec[]>(() => [
    { key: "eq", label: "Strategy equity (₹)", points: d.equity, color: "primary" },
    ...(d.benchmark.length ? [{ key: "b", label: "NIFTY 50 buy-and-hold (same capital)", points: d.benchmark, color: "muted" as const, dashed: true }] : []),
    { key: "dd", label: "Drawdown % (lower pane)", points: d.drawdown, kind: "area" as const, color: "down" as const, pane: 1 },
  ], [d])
  const fewTrades = m.trades < 100
  const totalR = d.trades.reduce((a, t) => a + t.r_multiple, 0)
  return (
    <>
      <Alert>
        <TriangleExclamationPoint />
        <AlertTitle>Simulated past results, not a promise of profit</AlertTitle>
        <AlertDescription>
          <ul className="list-disc pl-4">
            <li>Includes Indian charges ({rupees(m.total_charges)} paid) and 0.05% slippage per side; entries fill at the <Term k="next_open">next open</Term>.</li>
            {fewTrades && <li>Only {m.trades} closed trades: too few to separate skill from luck (Gate 3 needs ≥ 100).</li>}
            {d.params.open_positions_at_end?.length > 0 && <li>{d.params.open_positions_at_end.length} position(s) were still open at the end ({d.params.open_positions_at_end.join(", ")}): in the equity curve, not in trade stats.</li>}
            {d.events.length > 0 && <li>{d.events.length} breaker event(s): see the Events tab.</li>}
            {m.warnings?.map((w) => <li key={w}>{w}</li>)}
          </ul>
        </AlertDescription>
      </Alert>

      <MetricGrid>
        <Metric label="Total return" term="total_return" value={pct(m.total_return_pct)} tone={m.total_return_pct >= 0 ? "up" : "down"} sub={`NIFTY ${pct(m.benchmark_return_pct)}`} />
        <Metric label="CAGR" term="cagr" value={pct(m.cagr_pct)} sub={`NIFTY ${pct(m.benchmark_cagr_pct)}`} />
        <Metric label="Max drawdown" term="max_drawdown" value={pct(m.max_drawdown_pct)} tone={m.max_drawdown_pct < -15 ? "down" : "flat"} sub={`NIFTY ${pct(m.benchmark_max_drawdown_pct as number)}`} />
        <Metric label="Profit factor" term="profit_factor" value={num(m.profit_factor)} tone={m.profit_factor >= 1.3 ? "up" : m.profit_factor < 1 ? "down" : "warn"} sub="≥ 1.3 needed" />
        <Metric label="Expectancy" term="expectancy_r" value={r(m.expectancy_r)} tone={m.expectancy_r > 0 ? "up" : "down"} sub={`${r(totalR)} in total`} />
        <Metric label="Trades" term="trades" value={int(m.trades)} tone={fewTrades ? "warn" : "flat"} sub={`win rate ${pct(m.win_rate_pct, 1, false)}`} />
        <Metric label="Sharpe" term="sharpe" value={num(m.sharpe)} sub={`NIFTY ${num(m.benchmark_sharpe as number)}`} />
        <Metric label="Sortino" term="sortino" value={num(m.sortino)} />
        <Metric label="Charges paid" term="charges" value={rupeesCompact(m.total_charges)} sub={`${num(m.charges_pct_of_gross_profit as number, 0)}% of gross profit`} />
        <Metric label="Exposure" term="exposure" value={pct(m.exposure_pct, 1, false)} sub={`avg ${num(m.avg_bars_held as number, 1)} days held`} />
        <Metric label="Avg win / loss" value={`${rupees(m.avg_win)} / ${rupees(m.avg_loss)}`} />
        <Metric label="Worst losing streak" value={`${m.max_consecutive_losses as number} trades`} sub="expect worse live" />
      </MetricGrid>

      <Card>
        <CardHeader>
          <CardTitle className="font-heading">Equity vs <Term k="benchmark">NIFTY buy-and-hold</Term></CardTitle>
          <CardDescription>{d.params.start} → {d.params.end} · starting capital {rupees(d.params.initial_capital)} · {d.symbols_count} symbols</CardDescription>
        </CardHeader>
        <CardContent>
          <SeriesChart series={equitySeries} height={460} paneHeights={[130]} valueFormat={(v) => (Math.abs(v) >= 1000 ? `₹${(v / 1e5).toFixed(2)}L` : `${v.toFixed(1)}%`)} />
        </CardContent>
      </Card>

      <Tabs defaultValue="trades">
        <TabsList className="max-w-full justify-start overflow-x-auto">
          <TabsTrigger value="trades">Trades ({d.trades.length})</TabsTrigger>
          <TabsTrigger value="years">Year by year</TabsTrigger>
          <TabsTrigger value="why">Exits &amp; rejections</TabsTrigger>
          <TabsTrigger value="symbols">By symbol</TabsTrigger>
          <TabsTrigger value="events">Events ({d.events.length})</TabsTrigger>
          <TabsTrigger value="params">Parameters</TabsTrigger>
        </TabsList>
        <TabsContent value="trades">
          <Card><CardContent className="pt-4">
            {d.trades.length === 0 ? <p className="text-sm text-muted-foreground">No closed trades.</p> : <TradesTable trades={d.trades} onPick={setPicked} />}
          </CardContent></Card>
        </TabsContent>
        <TabsContent value="years">
          <Card><CardContent className="pt-4">
            <Table>
              <TableHeader><TableRow><TableHead>Year</TableHead><TableHead className="text-right">Strategy</TableHead><TableHead className="text-right">NIFTY</TableHead><TableHead className="text-right">Difference</TableHead></TableRow></TableHeader>
              <TableBody>
                {d.yearly.map((y) => (
                  <TableRow key={y.year}>
                    <TableCell className="num">{y.year}</TableCell>
                    <TableCell className={cn("num text-right", toneClass(y.strategy_pct))}>{pct(y.strategy_pct)}</TableCell>
                    <TableCell className={cn("num text-right", toneClass(y.nifty_pct))}>{pct(y.nifty_pct)}</TableCell>
                    <TableCell className={cn("num text-right", toneClass(y.nifty_pct === undefined ? null : y.strategy_pct - y.nifty_pct))}>{y.nifty_pct === undefined ? "–" : pct(y.strategy_pct - y.nifty_pct)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent></Card>
        </TabsContent>
        <TabsContent value="why">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader><CardTitle className="font-heading">How trades ended</CardTitle><CardDescription>Many "time stop" exits = the entry signal has little follow-through.</CardDescription></CardHeader>
              <CardContent><Bars data={m.exit_reasons ?? {}} /></CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="font-heading">Why signals were rejected</CardTitle>
                <CardDescription>{int(d.signals.total)} signals · {int(d.signals.approved)} taken · {int(d.signals.rejected)} rejected by the risk engine</CardDescription>
              </CardHeader>
              <CardContent><Bars data={d.signals.top_rejections ?? {}} /></CardContent>
            </Card>
          </div>
        </TabsContent>
        <TabsContent value="symbols">
          <Card><CardContent className="pt-4">
            <Table>
              <TableHeader><TableRow><TableHead>Symbol</TableHead><TableHead className="text-right">Trades</TableHead><TableHead className="text-right">Net P&amp;L</TableHead><TableHead className="text-right">Avg R</TableHead><TableHead className="text-right">Win %</TableHead><TableHead /></TableRow></TableHeader>
              <TableBody>
                {d.per_symbol.map((s) => (
                  <TableRow key={s.symbol}>
                    <TableCell className="font-medium">{s.symbol}</TableCell>
                    <TableCell className="num text-right">{s.trades}</TableCell>
                    <TableCell className={cn("num text-right", toneClass(s.net_pnl))}>{rupees(s.net_pnl)}</TableCell>
                    <TableCell className={cn("num text-right", toneClass(s.avg_r))}>{r(s.avg_r)}</TableCell>
                    <TableCell className="num text-right">{pct(s.win_pct, 1, false)}</TableCell>
                    <TableCell className="text-right">
                      <Button asChild size="xs" variant="ghost"><Link to={`/chart?symbol=${encodeURIComponent(s.symbol)}&strategy=${Object.keys(d.params.strategies)[0] ?? ""}`}><ChartCandlestick data-icon="inline-start" />chart</Link></Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent></Card>
        </TabsContent>
        <TabsContent value="events">
          <Card><CardContent className="pt-4">
            {d.events.length === 0 ? <p className="text-sm text-muted-foreground">No breaker events.</p> : (
              <ul className="num flex flex-col gap-1 text-xs">{d.events.map((e, i) => <li key={i}>{e}</li>)}</ul>
            )}
          </CardContent></Card>
        </TabsContent>
        <TabsContent value="params">
          <Card><CardContent className="pt-4">
            <pre className="max-h-96 overflow-auto text-xs">{JSON.stringify({ strategies: d.params.strategies, specs: d.params.specs, enforce_breakers: d.params.enforce_breakers, git: d.git }, null, 2)}</pre>
          </CardContent></Card>
        </TabsContent>
      </Tabs>

      <Dialog open={!!picked} onOpenChange={(o) => !o && setPicked(null)}>
        <DialogContent className="sm:max-w-4xl">
          {picked && (
            <>
              <DialogHeader>
                <DialogTitle>{picked.symbol}: {r(picked.r_multiple)} ({rupees(picked.net_pnl)})</DialogTitle>
                <DialogDescription>
                  Bought {date(picked.entry_time)} at {num(picked.entry_price)}, sold {date(picked.exit_time)} at {num(picked.exit_price)} ({picked.exit_reason}) after {picked.bars_held} days.
                  Charges {rupees(picked.charges)}. Why it entered: {picked.reasons || "–"}
                </DialogDescription>
              </DialogHeader>
              <TradeChart t={picked} />
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}

export default function BacktestDetail() {
  const { runId = "" } = useParams()
  const q = useQuery({ queryKey: ["backtest", runId], queryFn: () => api.backtest(runId) })
  return (
    <Page>
      <PageHeader
        title={q.data ? q.data.label : "Backtest"}
        description={q.data && <><Badge variant="outline">{q.data.period}</Badge> <span className="num ml-2 text-xs">{runId} · git {q.data.git}</span></>}
        actions={<Button asChild variant="outline" size="sm"><Link to="/backtests">All backtests</Link></Button>}
      />
      {q.isError ? <QueryError error={q.error} what="this backtest" /> : !q.data ? <LoadingBlock height={500} /> : <Report d={q.data} />}
    </Page>
  )
}
