import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"

import { Metric, MetricGrid } from "@/components/metric"
import { LoadingBlock, QueryError } from "@/components/page"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { api, type ProcessReview, type WeeklyReview } from "@/lib/api"
import { dateTime, pct, rupees } from "@/lib/format"

const CHECKS = [["risk_ok", "Risk management"], ["plan_ok", "Followed the plan"], ["selection_ok", "Trade selection"], ["execution_ok", "Execution"]] as const

function PriorAction({ week, action }: { week: string; action: WeeklyReview["previous"]["actions"][number] }) {
  const client = useQueryClient()
  const [note, setNote] = useState(action.note)
  const update = useMutation({
    mutationFn: () => api.trackWeeklyAction(week, action.index, !action.completed, note),
    onSuccess: () => { client.invalidateQueries({ queryKey: ["weekly-review"] }); toast.success("Follow-through evidence saved") },
    onError: (e) => toast.error(e.message),
  })
  return <div className="flex flex-col gap-2 rounded-md border p-3 text-sm"><p>{action.index+1}. {action.text}</p>
    <p className="text-xs text-muted-foreground">{action.completed ? "Marked complete" : "Open"} — operator assessment</p>
    <label className="text-xs">Follow-through evidence<Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="What was actually done? Include evidence rather than the week's profit." /></label>
    <Button variant="outline" className="self-start" disabled={note.trim().length < 10 || update.isPending} onClick={() => update.mutate()}>{action.completed ? "Reopen action" : "Mark action complete"}</Button>
  </div>
}

function ReviewTrade({ trade }: { trade: WeeklyReview["trades"][number] }) {
  const client = useQueryClient()
  const [checks, setChecks] = useState<Record<string, string>>(() => Object.fromEntries(CHECKS.map(([key]) => [key, trade.review ? String(trade.review[key]) : ""])))
  const [note, setNote] = useState(trade.review?.note ?? "")
  const save = useMutation({
    mutationFn: () => api.reviewTrade(trade.trade_id, { ...Object.fromEntries(CHECKS.map(([key]) => [key, checks[key] === "true"])), note } as ProcessReview),
    onSuccess: () => { client.invalidateQueries({ queryKey: ["weekly-review"] }); toast.success("Process evidence saved") },
    onError: (e) => toast.error(e.message),
  })
  return <details className="rounded-md border p-3">
    <summary className="cursor-pointer text-sm">{trade.symbol} · {dateTime(trade.exit_time)} · {rupees(trade.net_pnl)} · {trade.review ? "reviewed" : "needs process evidence"}</summary>
    <div className="mt-3 grid gap-3 sm:grid-cols-2">
      {CHECKS.map(([key, title]) => <label className="flex flex-col gap-1 text-xs" key={key}>{title}
        <select aria-label={title} className="h-9 rounded-md border bg-background px-2" value={checks[key]} onChange={(e) => setChecks({ ...checks, [key]: e.target.value })}>
          <option value="">Not assessed</option><option value="true">Passed, with evidence</option><option value="false">Failed</option>
        </select>
      </label>)}
      <label className="flex flex-col gap-1 text-xs sm:col-span-2">Evidence: compare signal, sizing, stop and fills
        <Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Explain which recorded rules passed or failed. Profit alone is not evidence." />
      </label>
      <Button className="justify-self-start" variant="outline" disabled={save.isPending || note.trim().length < 10 || CHECKS.some(([key]) => !checks[key])} onClick={() => save.mutate()}>Save process review</Button>
    </div>
  </details>
}

export function WeeklyReviewCard() {
  const client = useQueryClient()
  const [day, setDay] = useState(() => new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" }))
  const q = useQuery({ queryKey: ["weekly-review", day], queryFn: () => api.weeklyReview(day), enabled: !!day })
  const w = q.data
  const savePlan = useMutation({ mutationFn: () => api.saveWeeklyPlan(day),
    onSuccess: () => { client.invalidateQueries({ queryKey: ["weekly-review"] }); toast.success("Next week's three priorities saved") },
    onError: (e) => toast.error(e.message),
  })
  return <Card>
    <CardHeader>
      <CardTitle className="font-heading">Weekly trading mentor</CardTitle>
      <CardDescription>Actual paper journal only. Assess decisions separately from profit. Weeks run Monday–Sunday in IST.</CardDescription>
      <label className="mt-2 flex max-w-xs flex-col gap-1 text-xs">Choose a day in the review week<Input type="date" value={day} onChange={(e) => setDay(e.target.value)} /></label>
    </CardHeader>
    <CardContent className="flex flex-col gap-5">
      {q.isError ? <QueryError error={q.error} what="the weekly review" /> : !w ? <LoadingBlock height={200} /> : <>
        <section className="flex flex-col gap-2"><h3 className="font-semibold">Weekly Summary</h3><p className="text-xs text-muted-foreground">{w.week_start} to {w.week_end}. {w.summary.pnl_basis}</p>
          <MetricGrid><Metric label="Net P&L" value={rupees(w.summary.net_pnl)} /><Metric label="Win rate" value={w.summary.win_rate_pct == null ? "N/A" : pct(w.summary.win_rate_pct)} sub={`${w.summary.trades} closed trades`} /><Metric label="Biggest win" value={w.summary.biggest_win == null ? "N/A" : rupees(w.summary.biggest_win)} /><Metric label="Biggest loss" value={w.summary.biggest_loss == null ? "N/A" : rupees(w.summary.biggest_loss)} /></MetricGrid>
        </section>
        {([["What I Did Well", w.strengths], ["My Biggest Mistakes", w.mistakes], ["Patterns I Should Notice", w.patterns], ["Next Week's Action Plan", w.actions]] as const).map(([title, rows]) => <section key={title}><h3 className="font-semibold">{title}</h3><ul className="mt-2 list-disc space-y-1 pl-5 text-sm">{rows.map((row) => <li key={row}>{row}</li>)}</ul></section>)}
        <p className="text-xs text-muted-foreground">{w.progress}</p>
        <Button className="self-start" variant="outline" disabled={w.plan_saved || !w.summary.trades || savePlan.isPending} onClick={() => savePlan.mutate()}>{w.plan_saved ? "Next week's plan saved" : "Save next week's plan"}</Button>
        {w.previous.actions.length > 0 && <section className="flex flex-col gap-2"><h3 className="font-semibold">Follow-through on last week's plan</h3>{w.previous.actions.map((action) => <PriorAction key={`${w.previous.week_start}-${action.index}`} week={w.previous.week_start} action={action} />)}</section>}
        <section><h3 className="font-semibold">Final Rating — {w.rating.score == null ? "Not rated" : `${w.rating.score}/10`}</h3><p className="mt-1 text-sm">{w.rating.explanation}</p><p className="text-xs text-muted-foreground">{w.rating.basis}</p>
          {Object.entries(w.rating.components).map(([key, value]) => <p key={key} className="text-xs">{key.replaceAll("_", " ")}: {value}/10</p>)}
        </section>
        {w.trades.length > 0 && <section className="flex flex-col gap-2"><h3 className="font-semibold">Review the decisions</h3>{w.trades.map((t) => <ReviewTrade key={`${t.trade_id}-${t.review?.reviewed_at ?? "new"}`} trade={t} />)}</section>}
      </>}
    </CardContent>
  </Card>
}
