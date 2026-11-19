import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { LoadingBlock, QueryError } from "@/components/page"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { api } from "@/lib/api"
import { dateTime, int, num } from "@/lib/format"

export function DemandWatch() {
  const client = useQueryClient()
  const q = useQuery({ queryKey: ["demand"], queryFn: api.demand, refetchInterval: 30_000 })
  const capture = useMutation({ mutationFn: api.captureDemand,
    onSuccess: (snapshot) => { client.setQueryData(["demand"], snapshot); toast.success("Read-only demand observation saved") },
    onError: (e) => toast.error("Demand capture failed", { description: e.message }),
  })
  return <Card>
    <CardHeader><CardTitle className="font-heading">Observed stock demand</CardTitle><CardDescription>Current configured NIFTY stock universe. Demand observations are saved every 30 seconds during 09:00–09:15 IST while the paper research trial is enabled. Opening-auction data verification is still pending.</CardDescription></CardHeader>
    <CardContent className="flex flex-col gap-3">
      <Button variant="outline" className="self-start" disabled={capture.isPending} onClick={() => capture.mutate()}>{capture.isPending ? "Reading Upstox…" : "Capture demand snapshot"}</Button>
      {q.isError ? <QueryError error={q.error} what="demand observations" /> : !q.data ? <LoadingBlock height={100} /> : <>
        <p className="text-xs text-muted-foreground">{q.data.limitation}</p>
        {q.data.snapshot_id ? <>
          <p className="text-sm">Captured {dateTime(q.data.captured_at)} · session at capture: {q.data.session?.replaceAll("_", " ")}. This is a saved snapshot, not a continuously live quote.</p>
          <p className="text-xs text-muted-foreground">Sorted by displayed quantity imbalance: 100 × (buy − sell) / (buy + sell). This is not a probability, traded volume, or a buy recommendation. Small books can show extreme percentages.</p>
          <Table><TableHeader><TableRow><TableHead>Stock</TableHead><TableHead className="text-right">Bid quantity</TableHead><TableHead className="text-right">Ask quantity</TableHead><TableHead className="text-right">Imbalance %</TableHead><TableHead>Response time</TableHead></TableRow></TableHeader>
            <TableBody>{q.data.rows.map((row) => <TableRow key={row.symbol}><TableCell>{row.symbol}</TableCell><TableCell className="num text-right">{row.buy_quantity == null ? "Unknown" : int(row.buy_quantity)}</TableCell><TableCell className="num text-right">{row.sell_quantity == null ? "Unknown" : int(row.sell_quantity)}</TableCell><TableCell className="num text-right">{row.imbalance_pct == null ? "N/A" : num(row.imbalance_pct)}</TableCell><TableCell className="text-xs">{dateTime(row.response_time)}</TableCell></TableRow>)}</TableBody>
          </Table>
        </> : <p className="text-sm text-muted-foreground">No demand observations saved. Capturing outside pre-open records that session; it cannot reconstruct the morning auction.</p>}
      </>}
    </CardContent>
  </Card>
}
