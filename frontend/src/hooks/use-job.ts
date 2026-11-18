import { useQuery } from "@tanstack/react-query"

import { api, type Job } from "@/lib/api"

/** Poll a background job (backtest / validation) every second until it is done or failed. */
export function useJob<R>(jobId: string | null) {
  return useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api.job<R>(jobId as string),
    enabled: !!jobId,
    refetchInterval: (q) => {
      const s = (q.state.data as Job<R> | undefined)?.status
      return s === "done" || s === "error" ? false : 1000
    },
  })
}

export function elapsed(job: Job | undefined): string {
  if (!job?.started_at) return ""
  const end = job.finished_at ? new Date(job.finished_at) : new Date()
  const s = Math.max(0, Math.round((end.getTime() - new Date(job.started_at).getTime()) / 1000))
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`
}
