import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { CircleCheck, CircleExclamationPoint, Plus, Save } from "lucide-react"
import { useMemo, useState } from "react"
import { useNavigate, useSearchParams } from "react-router"
import { toast } from "sonner"

import { PriceChart, type Marker } from "@/components/charts/price-chart"
import { ConditionRow } from "@/components/condition-editor"
import { useIndicatorCatalog } from "@/components/indicator-picker"
import { LoadingBlock, Page, PageHeader, QueryError } from "@/components/page"
import { SymbolPicker } from "@/components/pickers"
import { Term } from "@/components/term"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldDescription, FieldGroup, FieldLabel, FieldSet, FieldLegend } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Spinner } from "@/components/ui/spinner"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { useDebounced } from "@/hooks/use-debounced"
import { api, type Regime, type RuleSpec } from "@/lib/api"
import { buildIndicatorLayers, startFor } from "@/lib/chart-data"
import { BLANK, cond, ind, specIndicators, TEMPLATES, val } from "@/lib/templates"

const REGIMES: Regime[] = ["TREND_UP", "RANGE", "TREND_DOWN", "HIGH_VOL"]
const STOP_HELP = { atr: "× ATR(14) below the signal close", percent: "% below the signal close", swing_low: "days: stop at their lowest low" }

export default function Builder() {
  const [params] = useSearchParams()
  const from = params.get("from")
  // "Edit as new version": start from a saved strategy (same name -> saves as the next version).
  // The form mounts only once the source is loaded, so it can take it as its initial state.
  const source = useQuery({ queryKey: ["strategy", from], queryFn: () => api.strategy(from as string), enabled: !!from })
  if (from && source.isError) return <Page><QueryError error={source.error} what={`strategy ${from}`} /></Page>
  if (from && !source.data) return <Page><LoadingBlock height={400} /></Page>
  const initial = source.data?.spec ? { ...source.data.spec, version: undefined, created_at: undefined } : BLANK
  return <BuilderForm key={from ?? "new"} from={from} initial={initial} />
}

function BuilderForm({ from, initial }: { from: string | null; initial: RuleSpec }) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [spec, setSpec] = useState<RuleSpec>(initial)
  const [symbol, setSymbol] = useState("RELIANCE")
  const set = <K extends keyof RuleSpec>(k: K, v: RuleSpec[K]) => setSpec((s) => ({ ...s, [k]: v }))

  const debounced = useDebounced(spec, 450)
  const check = useQuery({ queryKey: ["validate-spec", debounced], queryFn: () => api.validateSpec(debounced), placeholderData: keepPreviousData })
  const ok = check.data?.ok ?? false
  // "fresh" = the validation result belongs to exactly what is on screen (not a previous edit still shown
  // while the new one is being checked). Save is only allowed then.
  const fresh = !check.isPlaceholderData && !check.isFetching && debounced === spec

  const symbols = useQuery({ queryKey: ["symbols"], queryFn: api.symbols, staleTime: 60_000 })
  const last = symbols.data?.find((r) => r.symbol === symbol)?.last
  const start = startFor("5Y", last)
  // Preview exactly the spec the server just validated (its normalised copy). Using `debounced` here
  // raced: a new invalid edit could be sent while the previous "ok" result was still displayed (-> 422).
  const previewSpec = useMemo(() => (check.data?.ok ? check.data.normalized ?? null : null), [check.data])
  const candles = useQuery({ queryKey: ["candles", symbol, start], queryFn: () => api.candles(symbol, start), enabled: !!last, placeholderData: keepPreviousData })
  const preview = useQuery({
    queryKey: ["preview-spec", previewSpec, symbol, start],
    queryFn: () => api.preview({ spec: previewSpec as RuleSpec, symbol, start }),
    enabled: !!previewSpec && !!last,
    placeholderData: keepPreviousData,
  })
  const { data: catalog = [] } = useIndicatorCatalog()
  const used = useMemo(() => (previewSpec ? specIndicators(previewSpec) : []), [previewSpec])
  const indData = useQuery({
    queryKey: ["ind", symbol, start, used],
    queryFn: () => api.computeIndicators(symbol, used, start),
    enabled: used.length > 0 && !!last,
    placeholderData: keepPreviousData,
  })
  const layers = useMemo(() => buildIndicatorLayers(used, catalog, indData.data), [used, catalog, indData.data])
  const markers = useMemo<Marker[]>(() => [
    ...(preview.data?.signals ?? []).map((s): Marker => ({ time: s.time, kind: "signal" })),
    ...(preview.data?.exits ?? []).map((t): Marker => ({ time: t, kind: "exit" })),
  ], [preview.data])

  const save = useMutation({
    mutationFn: () => api.saveSpec(spec),
    onSuccess: (s) => {
      toast.success(`Saved ${s.id}`, { description: "It passed the look-ahead self-check. Backtest it next." })
      qc.invalidateQueries({ queryKey: ["strategies"] })
      navigate(`/strategies/${s.id}`)
    },
    onError: (e) => toast.error("Not saved", { description: e.message }),
  })

  const updateCond = (group: "entry" | "exit", i: number, c: RuleSpec["entry"][number]) =>
    set(group, spec[group].map((x, j) => (j === i ? c : x)))

  return (
    <Page>
      <PageHeader
        title={from ? `New version of ${from.replace(/_v\d+$/, "")}` : "Build a strategy"}
        description={<>Describe WHEN to buy and HOW to get out, using indicators. Saving runs a <Term k="lookahead">look-ahead check</Term> and creates an immutable version; edits create the next version.</>}
        actions={
          <Button disabled={!ok || !fresh || save.isPending || !spec.name} onClick={() => save.mutate()}>
            {save.isPending ? <Spinner data-icon="inline-start" /> : <Save data-icon="inline-start" />}
            Save {check.data?.next_version ? `as v${check.data.next_version}` : ""}
          </Button>
        }
      />

      {!from && (
        <div className="flex flex-col gap-2">
          <span className="text-xs text-muted-foreground">Start from a classic idea (each is a hypothesis to test, not a recommendation):</span>
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            {TEMPLATES.map((t) => (
              <button key={t.key} type="button" onClick={() => setSpec(structuredClone(t.spec))}
                className="flex flex-col gap-1 rounded-lg border bg-card p-3 text-left transition-colors hover:border-primary/60 hover:bg-primary/5 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
                <span className="font-heading text-sm font-semibold">{t.title}</span>
                <span className="text-xs text-muted-foreground">{t.idea}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="flex min-w-0 flex-col gap-4">
          <Card>
            <CardHeader><CardTitle className="font-heading">Idea</CardTitle></CardHeader>
            <CardContent>
              <FieldGroup>
                <Field data-invalid={check.data?.errors.some((e) => e.startsWith("name")) || undefined}>
                  <FieldLabel htmlFor="name">Name</FieldLabel>
                  <Input id="name" value={spec.name} placeholder="e.g. rsi_dip" disabled={!!from} onChange={(e) => set("name", e.target.value.toLowerCase())} />
                  <FieldDescription>Lowercase letters, digits and _. The version (_v1, _v2…) is added on save.</FieldDescription>
                </Field>
                <Field>
                  <FieldLabel htmlFor="hyp">Hypothesis: why should this work?</FieldLabel>
                  <Textarea id="hyp" rows={2} value={spec.hypothesis} placeholder="A testable belief about market behaviour"
                    onChange={(e) => set("hypothesis", e.target.value)} />
                </Field>
              </FieldGroup>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="font-heading">Buy when ALL of these are true</CardTitle>
              <CardDescription>Checked on each day's close; the buy happens at the <Term k="next_open">next open</Term>.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {spec.entry.map((c, i) => (
                <ConditionRow key={i} index={i} group="entry" value={c} onChange={(x) => updateCond("entry", i, x)}
                  onRemove={spec.entry.length > 1 ? () => set("entry", spec.entry.filter((_, j) => j !== i)) : undefined} />
              ))}
              <Button variant="outline" size="sm" className="self-start" disabled={spec.entry.length >= 8}
                onClick={() => set("entry", [...spec.entry, cond(ind("close"), ">", ind("sma", { n: 50 }))])}>
                <Plus data-icon="inline-start" />Add condition
              </Button>
              <Field orientation="horizontal" className="pt-2">
                <Switch id="mf" checked={spec.market_filter} onCheckedChange={(v) => set("market_filter", v)} />
                <FieldLabel htmlFor="mf">Only while NIFTY 50 is above its 50 EMA (<Term k="market_filter">market filter</Term>)</FieldLabel>
              </Field>
              <FieldSet className="pt-1">
                <FieldLegend variant="label"><Term k="regime">Allowed regimes</Term> (none selected = any)</FieldLegend>
                <ToggleGroup type="multiple" variant="outline" size="sm" value={spec.allowed_regimes ?? []}
                  onValueChange={(v) => set("allowed_regimes", v.length ? (v as Regime[]) : null)} aria-label="Allowed regimes">
                  {REGIMES.map((r) => <ToggleGroupItem key={r} value={r}>{r}</ToggleGroupItem>)}
                </ToggleGroup>
              </FieldSet>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="font-heading">Get out</CardTitle>
              <CardDescription>The <Term k="stop">stop</Term> defines 1R, the risk per trade; position size is calculated from it.</CardDescription>
            </CardHeader>
            <CardContent>
              <FieldGroup>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field>
                    <FieldLabel>Stop-loss</FieldLabel>
                    <div className="flex gap-2">
                      <Select value={spec.stop.type} onValueChange={(t) => set("stop", { type: t as RuleSpec["stop"]["type"], value: t === "atr" ? 2 : t === "percent" ? 5 : 10 })}>
                        <SelectTrigger className="w-32" aria-label="Stop type"><SelectValue /></SelectTrigger>
                        <SelectContent><SelectGroup>
                          <SelectItem value="atr">ATR</SelectItem><SelectItem value="percent">Percent</SelectItem><SelectItem value="swing_low">Swing low</SelectItem>
                        </SelectGroup></SelectContent>
                      </Select>
                      <Input type="number" className="num w-24" aria-label="Stop value" step={spec.stop.type === "swing_low" ? 1 : 0.1} value={Number.isFinite(spec.stop.value) ? spec.stop.value : ""}
                        onChange={(e) => set("stop", { ...spec.stop, value: Number(e.target.value) })} />
                    </div>
                    <FieldDescription>{STOP_HELP[spec.stop.type]}</FieldDescription>
                  </Field>
                  <Field>
                    <FieldLabel>Target</FieldLabel>
                    <div className="flex gap-2">
                      <Select value={spec.target.type} onValueChange={(t) => set("target", { type: t as RuleSpec["target"]["type"], value: t === "none" ? null : t === "r_multiple" ? 2 : 10 })}>
                        <SelectTrigger className="w-32" aria-label="Target type"><SelectValue /></SelectTrigger>
                        <SelectContent><SelectGroup>
                          <SelectItem value="none">None</SelectItem><SelectItem value="r_multiple">R-multiple</SelectItem><SelectItem value="percent">Percent</SelectItem>
                        </SelectGroup></SelectContent>
                      </Select>
                      {spec.target.type !== "none" && (
                        <Input type="number" className="num w-24" aria-label="Target value" step={0.1} value={spec.target.value ?? ""}
                          onChange={(e) => set("target", { ...spec.target, value: Number(e.target.value) })} />
                      )}
                    </div>
                    <FieldDescription>{spec.target.type === "r_multiple" ? <>Sell at entry + {spec.target.value}× the risk (<Term k="r_multiple">R</Term>)</> : spec.target.type === "percent" ? "% above the signal close" : "Exit by rules, time stop or trailing stop"}</FieldDescription>
                  </Field>
                  <Field>
                    <div className="flex items-center gap-2">
                      <Switch id="ts" checked={spec.time_stop_bars !== null} onCheckedChange={(v) => set("time_stop_bars", v ? 15 : null)} />
                      <FieldLabel htmlFor="ts"><Term k="time_stop">Time stop</Term></FieldLabel>
                    </div>
                    {spec.time_stop_bars !== null && (
                      <Input type="number" className="num w-24" aria-label="Time stop days" value={spec.time_stop_bars} onChange={(e) => set("time_stop_bars", Number(e.target.value))} />
                    )}
                  </Field>
                  <Field>
                    <div className="flex items-center gap-2">
                      <Switch id="tr" checked={spec.trail_atr_mult !== null} onCheckedChange={(v) => set("trail_atr_mult", v ? 3 : null)} />
                      <FieldLabel htmlFor="tr"><Term k="trailing_stop">Trailing stop</Term> (× ATR)</FieldLabel>
                    </div>
                    {spec.trail_atr_mult !== null && (
                      <Input type="number" className="num w-24" aria-label="Trailing ATR multiple" step={0.5} value={spec.trail_atr_mult} onChange={(e) => set("trail_atr_mult", Number(e.target.value))} />
                    )}
                  </Field>
                </div>
                <FieldSet>
                  <FieldLegend variant="label">Also sell at the next open when ANY of these is true (optional)</FieldLegend>
                  <div className="flex flex-col gap-2">
                    {spec.exit.map((c, i) => (
                      <ConditionRow key={i} index={i} group="exit" value={c} onChange={(x) => updateCond("exit", i, x)} onRemove={() => set("exit", spec.exit.filter((_, j) => j !== i))} />
                    ))}
                    <Button variant="outline" size="sm" className="self-start" disabled={spec.exit.length >= 8}
                      onClick={() => set("exit", [...spec.exit, cond(ind("rsi", { n: 14 }), ">", val(70))])}>
                      <Plus data-icon="inline-start" />Add exit rule
                    </Button>
                  </div>
                </FieldSet>
              </FieldGroup>
            </CardContent>
          </Card>
        </div>

        {/* sticky: the preview stays in view while you edit the rules on the left */}
        <div className="flex min-w-0 flex-col gap-4 xl:sticky xl:top-16">
          {check.data && !check.data.ok ? (
            <Alert variant="destructive" data-testid="spec-errors">
              <CircleExclamationPoint />
              <AlertTitle>Fix these before saving</AlertTitle>
              <AlertDescription><ul className="list-disc pl-4">{check.data.errors.map((e) => <li key={e}>{e}</li>)}</ul></AlertDescription>
            </Alert>
          ) : check.data?.describe ? (
            <Alert data-testid="spec-describe">
              <CircleCheck />
              <AlertTitle>In plain English</AlertTitle>
              <AlertDescription>{check.data.describe}</AlertDescription>
            </Alert>
          ) : null}

          <Card className="overflow-hidden">
            <CardHeader>
              <CardTitle className="font-heading">Live preview</CardTitle>
              <CardDescription>Where these rules would have said BUY over the last 5 years. Signals only: profit needs a backtest (costs, sizing, exits).</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <SymbolPicker value={symbol} onChange={setSymbol} />
                {preview.data && <Badge variant="secondary">{preview.data.signals.length} signals</Badge>}
                {preview.isFetching && <Spinner />}
              </div>
              {preview.data?.condition_stats && (
                <div className="grid gap-x-4 gap-y-0.5 text-xs sm:grid-cols-2">
                  {preview.data.condition_stats.map((c, i) => (
                    <div key={i} className="flex justify-between gap-2"><span className="truncate">{c.label}</span><span className="num text-muted-foreground">{c.true_bars} days</span></div>
                  ))}
                  <div className="flex justify-between gap-2 font-medium"><span>all at once</span><span className="num">{preview.data.all_conditions_bars} days</span></div>
                  {!!preview.data.blocked_by_market_filter && (
                    <div className="flex justify-between gap-2 text-muted-foreground"><span>blocked by market filter</span><span className="num">{preview.data.blocked_by_market_filter}</span></div>
                  )}
                </div>
              )}
              {!candles.data ? <LoadingBlock height={420} /> : (
                <PriceChart bars={candles.data.bars} overlays={layers.overlays} panes={layers.panes} markers={markers} showVolume={false}
                  height={360 + layers.panes.reduce((h, p) => h + (p.height ?? 110), 0)} />
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </Page>
  )
}
