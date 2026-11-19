import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"

import { LoadingBlock, QueryError } from "@/components/page"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { api } from "@/lib/api"
import { dateTime } from "@/lib/format"

export function PaperAutomationCard() {
  const client = useQueryClient()
  const q = useQuery({ queryKey: ["automation"], queryFn: api.automation, refetchInterval: 15_000 })
  const [ack, setAck] = useState(false)
  const action = useMutation({
    mutationFn: (kind: "start" | "pause") => api.controlPaper(kind, ack),
    onSuccess: (s) => {
      toast.success(s.entries_enabled ? "Research paper trial enabled" : "New paper entries paused")
      for (const key of ["automation", "paper", "status"]) client.invalidateQueries({ queryKey: [key] })
    },
    onError: (e) => toast.error("Paper control failed", { description: e.message }),
  })
  const s = q.data
  const result = s?.last_job?.result
  const notes = result && typeof result === "object"
    ? ["warnings", "alerts", "skipped"].flatMap((key) => {
      const value = (result as Record<string, unknown>)[key]
      return Array.isArray(value) ? value.filter((x): x is string => typeof x === "string") : []
    }) : []
  return <Card>
    <CardHeader>
      <CardTitle className="font-heading">Paper automation</CardTitle>
      <CardDescription>Current daily swing strategies on the configured NIFTY stock universe. No strategy has passed Gate 3. This trial tests operation and collects evidence.</CardDescription>
    </CardHeader>
    <CardContent className="flex flex-col gap-3 text-sm">
      {q.isError ? <QueryError error={q.error} what="paper automation" /> : !s ? <LoadingBlock height={100} /> : <>
        <div className="flex flex-wrap gap-2"><Badge variant={s.entries_enabled ? "default" : "outline"}>{s.entries_enabled ? "Entries enabled" : "Entries paused"}</Badge><Badge variant="outline">{s.worker_running ? "Worker running" : "Worker offline"}</Badge></div>
        <p>IST schedule: entries/exits {s.schedule.open_job}; monitor every {s.schedule.monitor_every_minutes} min; daily analysis {s.schedule.eod_job}.</p>
        <p className="text-xs text-muted-foreground">Heartbeat: {dateTime(s.heartbeat)}. {s.busy ? `Running ${s.busy}.` : "Waiting for the next scheduled job."} Entries missed by 10 minutes are skipped.</p>
        {s.last_job && <details className="text-xs"><summary className="cursor-pointer">Last job: {s.last_job.kind} · {dateTime(s.last_job.finished_at)}{notes.length ? ` · ${notes.length} notices` : ""}</summary><ul className="mt-2 list-disc space-y-1 pl-4">{notes.length ? notes.map((note, i) => <li key={i}>{note}</li>) : <li>No warnings, alerts or skipped actions reported by this job.</li>}</ul></details>}
        <p className="text-xs text-muted-foreground">{s.limitation} Closing the browser is fine while the application remains running. Pausing entries preserves scheduled exits and monitoring.</p>
        {s.last_error && <p role="alert" className="text-down">{s.last_error}</p>}
        {!s.entries_enabled && <label className="flex items-start gap-2 text-xs"><input type="checkbox" className="mt-0.5" checked={ack} onChange={(e) => setAck(e.target.checked)} />I understand this is a simulated research trial, not a proven profitable strategy.</label>}
        <Button disabled={action.isPending || (!s.entries_enabled && !ack)} variant={s.entries_enabled ? "outline" : "default"} onClick={() => action.mutate(s.entries_enabled ? "pause" : "start")}>
          {action.isPending ? "Checking…" : s.entries_enabled ? "Pause new entries" : "Start research paper trial"}
        </Button>
        <p className="text-xs text-muted-foreground">This does not trade F&amp;O or opening auctions. The kill switch remains a separate entry veto. Stop prices can be exceeded by gaps and costs.</p>
      </>}
    </CardContent>
  </Card>
}
