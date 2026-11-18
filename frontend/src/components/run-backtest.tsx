import { useMutation, useQueryClient } from "@tanstack/react-query"
import { FlaskConical } from "lucide-react"
import { useEffect, useState } from "react"
import { Link } from "react-router"
import { toast } from "sonner"

import { PeriodToggle } from "@/components/pickers"
import { Term } from "@/components/term"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import { Switch } from "@/components/ui/switch"
import { elapsed, useJob } from "@/hooks/use-job"
import { api, type Metrics } from "@/lib/api"
import { pct } from "@/lib/format"

/** Start a backtest job and follow it. Used from strategy cards, the strategy page and the backtests page. */
export function useRunBacktest() {
  const qc = useQueryClient()
  const [jobId, setJobId] = useState<string | null>(null)
  const job = useJob<{ run_id: string; metrics: Metrics }>(jobId)
  const start = useMutation({
    mutationFn: api.runBacktest,
    onSuccess: (j) => setJobId(j.id),
    onError: (e) => toast.error("Backtest not started", { description: e.message }),
  })
  const status = job.data?.status
  useEffect(() => {
    if (status === "done") {
      qc.invalidateQueries({ queryKey: ["backtests"] })
      qc.invalidateQueries({ queryKey: ["strategies"] })
      qc.invalidateQueries({ queryKey: ["strategy"] })
    }
  }, [status, qc])
  return { start, job: job.data, reset: () => setJobId(null), busy: start.isPending || status === "queued" || status === "running" }
}

export function JobLine({ job }: { job: ReturnType<typeof useRunBacktest>["job"] }) {
  if (!job) return null
  if (job.status === "error") return <p className="text-sm text-destructive">Failed: {job.error}</p>
  if (job.status !== "done")
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner /> {job.status === "queued" ? "Queued…" : `Running… ${elapsed(job)}`} (a 13-year backtest of 50 stocks takes ~10-30 s)
      </p>
    )
  const m = job.result?.metrics
  return (
    <p className="text-sm">
      Done in {elapsed(job)}: <span className="num">{pct(m?.total_return_pct)}</span>, <span className="num">{m?.trades}</span> trades.{" "}
      <Link className="font-medium text-primary underline-offset-4 hover:underline" to={`/backtests/${encodeURIComponent(job.result?.run_id ?? "")}`}>Open the report</Link>
    </p>
  )
}

export function RunBacktestDialog({ strategyId, variant = "default", size = "sm" }: { strategyId: string; variant?: "default" | "outline"; size?: "sm" | "default" }) {
  const [open, setOpen] = useState(false)
  const [period, setPeriod] = useState("validate")
  const [enforce, setEnforce] = useState(false)
  const { start, job, busy, reset } = useRunBacktest()
  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o && !busy) reset() }}>
      <DialogTrigger asChild>
        <Button variant={variant} size={size}><FlaskConical data-icon="inline-start" />Backtest</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Backtest {strategyId}</DialogTitle>
          <DialogDescription>
            Runs on all stored NIFTY 50 stocks with Indian charges, slippage and the real risk engine. Signals fill at the <Term k="next_open">next open</Term>.
          </DialogDescription>
        </DialogHeader>
        <FieldGroup>
          <Field>
            <FieldLabel>Period</FieldLabel>
            <PeriodToggle value={period} onChange={setPeriod} />
          </Field>
          <Field orientation="horizontal">
            <Switch id="enforce" checked={enforce} onCheckedChange={setEnforce} />
            <FieldLabel htmlFor="enforce"><Term k="enforce_breakers">Enforce breakers</Term></FieldLabel>
          </Field>
          <FieldDescription>Off is the research default: breaker hits are recorded, not enforced.</FieldDescription>
        </FieldGroup>
        <JobLine job={job} />
        <DialogFooter>
          <Button disabled={busy} onClick={() => start.mutate({ strategies: [strategyId], period, enforce_breakers: enforce })}>
            {busy ? <Spinner data-icon="inline-start" /> : <FlaskConical data-icon="inline-start" />}
            {busy ? "Running" : "Run backtest"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
