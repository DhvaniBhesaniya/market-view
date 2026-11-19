import type { ReactNode } from "react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Skeleton } from "@/components/ui/skeleton"
import { ApiError } from "@/lib/api"

export function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="flex min-w-0 flex-col gap-1">
        <h1 className="font-heading text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="max-w-3xl text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function Page({ children }: { children: ReactNode }) {
  return <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-5 p-4 md:p-6">{children}</div>
}

export function QueryError({ error, what }: { error: unknown; what: string }) {
  const msg = error instanceof Error ? error.message : String(error)
  const offline = error instanceof TypeError || (error instanceof ApiError && error.status >= 500)
  return (
    <Alert variant="destructive">
      <AlertTitle>Could not load {what}</AlertTitle>
      <AlertDescription>
        {offline ? "The local application is not responding. Run uv run market-view start in the project folder and refresh." : msg}
      </AlertDescription>
    </Alert>
  )
}

export function LoadingBlock({ height = 240 }: { height?: number }) {
  return <Skeleton className="w-full" style={{ height }} />
}
