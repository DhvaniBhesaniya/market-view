// Typed client for the local market-view API (src/market_view/api/app.py).
// The API has no order endpoints; nothing here can place a trade.

export type Point = { time: string; value: number }
export type Bar = { time: string; timestamp?: string; open: number; high: number; low: number; close: number; volume: number }
export type ChartSource = "yfinance" | "upstox"
export type ChartOptions = { interval?: string; source?: ChartSource }
export type ChartData = {
  symbol: string; bars: Bar[]; source: ChartSource; interval: string; source_interval: string
  timezone: string; adjusted: boolean; live: boolean; aggregated: boolean; needs_download: boolean
  last_observation: string | null; downloaded_at: string | null; message: string | null; truncated: boolean
}
export type ChartDownload = { symbol: string; source: ChartSource; interval: string; source_interval: string; bars_downloaded: number; start: string; end: string }

export type Status = {
  live_trading: boolean
  mode: "paper"
  killswitch: { active: boolean; reason: string | null; since: string | null; source: string | null }
  data: Record<string, number>
  data_source: string
  upstox_token_set: boolean
  telegram_set: boolean
  risk_per_trade_pct: number
  daily_loss_cap_pct: number
  initial_capital: number
  paper_capital: number
  enabled_strategies: string[]
  periods: Record<string, { start: string; end: string | null; locked: boolean }>
  paper_started: boolean
  now: string
}

export type SymbolRow = {
  symbol: string
  kind: "index" | "stock" | "former"
  sector: string
  bars: number
  first: string | null
  last: string | null
}

export type IndicatorParam = { name: string; default: number; min: number; max: number; integer: boolean; label: string }
export type IndicatorDef = {
  id: string
  label: string
  group: string
  placement: "price" | "pane"
  outputs: string[]
  explain: string
  levels: number[]
  value_range: [number, number] | null
  params: IndicatorParam[]
}

export type Operand =
  | { kind: "indicator"; ind: string; params: Record<string, number>; output?: string | null }
  | { kind: "value"; value: number }
export type Op = ">" | "<" | ">=" | "<=" | "crosses_above" | "crosses_below"
export type Condition = { left: Operand; op: Op; right: Operand }
export type Regime = "TREND_UP" | "TREND_DOWN" | "RANGE" | "HIGH_VOL"
export type RuleSpec = {
  name: string
  version?: number
  description: string
  hypothesis: string
  entry: Condition[]
  exit: Condition[]
  stop: { type: "atr" | "percent" | "swing_low"; value: number }
  target: { type: "none" | "r_multiple" | "percent"; value: number | null }
  time_stop_bars: number | null
  trail_atr_mult: number | null
  market_filter: boolean
  allowed_regimes: Regime[] | null
  created_at?: string | null
}

export type Metrics = {
  trades: number
  total_return_pct: number
  cagr_pct: number
  max_drawdown_pct: number
  sharpe: number
  sortino: number
  profit_factor: number
  expectancy_r: number
  win_rate_pct: number
  total_charges: number
  benchmark_return_pct: number | null
  benchmark_cagr_pct: number | null
  exposure_pct: number
  start: string
  end: string
  breaker_events: number
  [k: string]: unknown
}

export type RunSummary = {
  run_id: string
  label: string
  period: string
  git: string | null
  strategies: string[]
  has_report: boolean
  enforce_breakers: boolean | null
  metrics: Metrics
}

export type StrategyInfo = {
  id: string
  name: string
  version: number
  kind: "builtin" | "rule"
  description: string
  defaults: Record<string, number | string | boolean>
  enabled: boolean
  scale_out_r: number | null
  allowed_regimes: string[] | null
  has_card: boolean
  runs: number
  latest: Record<"train" | "validate" | "full", RunSummary | null>
  spec?: RuleSpec
  describe?: string
  hypothesis?: string
  created_at?: string
  card_md?: string | null
}

export type Trade = {
  strategy_id: string
  symbol: string
  entry_time: string
  exit_time: string
  entry_price: number
  exit_price: number
  qty: number
  initial_stop: number
  target: number | null
  gross_pnl: number
  charges: number
  net_pnl: number
  r_multiple: number
  bars_held: number
  mae_pct: number
  mfe_pct: number
  exit_reason: string
  reasons: string
}

export type RunDetail = {
  run_id: string
  label: string
  period: string
  git: string | null
  metrics: Metrics & { warnings: string[]; exit_reasons: Record<string, number> }
  events: string[]
  params: { strategies: Record<string, Record<string, unknown>>; start: string; end: string; initial_capital: number;
    open_positions_at_end: string[]; enforce_breakers?: boolean; specs?: Record<string, RuleSpec> }
  symbols_count: number
  equity: Point[]
  benchmark: Point[]
  drawdown: Point[]
  yearly: { year: number; strategy_pct: number; nifty_pct?: number }[]
  trades: Trade[]
  signals: { total: number; approved?: number; rejected?: number; top_rejections?: Record<string, number> }
  per_symbol: { symbol: string; trades: number; net_pnl: number; avg_r: number; win_pct: number }[]
}

export type SignalRow = {
  ts: string
  strategy_id: string
  symbol: string
  confidence: number
  ref_price: number
  stop: number
  approved: boolean
  qty: number
  reasons: string | null
}

export type Preview = {
  strategy_id: string
  symbol: string
  bars: number
  signals: { time: string; close: number; stop: number; target: number | null; regime: string | null; reasons: string[] }[]
  exits?: string[]
  condition_stats?: { label: string; true_bars: number }[]
  all_conditions_bars?: number
  blocked_by_market_filter?: number
}

export type Job<R = unknown> = {
  id: string
  kind: string
  params: Record<string, unknown>
  status: "queued" | "running" | "done" | "error"
  created_at: string
  started_at: string | null
  finished_at: string | null
  result: R | null
  error: string | null
}

export type ValidationRecord = {
  id: string
  kind: "walkforward" | "sensitivity" | "montecarlo"
  strategy: string
  created_at: string
  git: string
  period?: string
  rows?: Record<string, unknown>[]
  summary?: Record<string, unknown>
  plateau?: Record<string, unknown>[]
  fan?: {
    error?: string
    trade_no: number[]
    p5: number[]; p25: number[]; p50: number[]; p75: number[]; p95: number[]
    actual: number[]
    r_histogram: { from: number; to: number; count: number }[]
  }
  trades?: number
  grid?: Record<string, number[]> | null
}

export type PaperStatus =
  | { started: false; how: string }
  | {
      started: true
      equity: number
      cash: number
      return_pct: number
      drawdown_pct: number
      open_risk: number
      initial_capital: number
      positions: Record<string, { strategy_id: string; qty: number; entry_price: number; stop: number; target: number | null;
        last_price: number; bars_held: number; scaled_out: boolean; exit_next_open: string | null }>
      pending_entries: string[]
      disabled_strategies: Record<string, string>
      killswitch: boolean
      last_eod: string | null
      last_open: string | null
      last_monitor: string | null
    }

export type KillSwitchState = {
  active: boolean
  reason: string | null
  since: string | null
  source: string | null
  history: { at: string; action: "ON" | "OFF"; reason?: string; note?: string; source?: string }[]
}

export type AutomationStatus = {
  entries_enabled: boolean; worker_running: boolean; research_only: boolean; heartbeat: string | null
  busy: string | null; last_error: string | null; calendar_through_year: number; limitation: string
  schedule: { open_job: string; eod_job: string; monitor_every_minutes: number }
  last_job: { kind: string; finished_at: string; result: unknown } | null
}
export type ProcessReview = { risk_ok: boolean; plan_ok: boolean; selection_ok: boolean; execution_ok: boolean; note: string; reviewed_at?: string }
export type DemandSnapshot = {
  snapshot_id: string | null; captured_at?: string; session?: string; auction_verified: false; limitation: string
  rows: { symbol: string; buy_quantity: number | null; sell_quantity: number | null; imbalance_pct: number | null; last_price: number | null; response_time: string | null; last_trade_time: string | null }[]
}

export type ResearchMetrics = {
  trades: number; total_return_pct: number; max_drawdown_pct: number; profit_factor: number | null
  expectancy_r: number; total_charges: number; sharpe: number
}
export type ResearchReport = {
  id: string; created_at: string; fingerprint: string; status: string; protocol: string
  input_symbols: number; promotion_allowed: false; blockers: string[]; remaining_evidence: string[]
  checks: Record<string, boolean>; reused: boolean; llm_used: false
  runs: { label: string; strategy: string; start: string; end: string; status: string;
    params: Record<string, number>; metrics?: ResearchMetrics; error?: string }[]
}
export type ResearchOverview = {
  status: { enabled: boolean; busy: boolean; stage: string | null; schedule: string; protocol: string
    max_backtests: number; llm_required: false; automatic_promotion: false; last_error: string | null
    worker_running: boolean; heartbeat: string | null }
  market: { available: boolean; as_of: string | null; regime: string; source?: string; calendar_age_days?: number
    close?: number; ema50?: number; ema200?: number; adx?: number; vix?: number | null; news_available: false; meaning?: string }
  reports: ResearchReport[]
}
export type WeekSummary = { trades: number; net_pnl: number; win_rate_pct: number | null; biggest_win: number | null; biggest_loss: number | null; charges: number; avg_r: number | null; pnl_basis: string }
export type WeeklyReview = {
  week_start: string; week_end: string; summary: WeekSummary; strengths: string[]; mistakes: string[]
  patterns: string[]; actions: string[]; progress: string; plan_saved: boolean
  previous: { week_start: string; summary: WeekSummary; actions: { index: number; text: string; completed: boolean; note: string }[] }
  rating: { score: number | null; components: Record<string, number>; reviewed: number; total: number; basis: string; explanation: string }
  trades: { trade_id: number; symbol: string; strategy_id: string; entry_time: string; exit_time: string; net_pnl: number; exit_reason: string; review: ProcessReview | null }[]
}

export class ApiError extends Error {
  status: number
  details: string[]
  constructor(status: number, message: string, details: string[] = []) {
    super(message)
    this.status = status
    this.details = details
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  })
  if (!res.ok) {
    let detail: unknown = res.statusText
    try {
      detail = (await res.json()).detail
    } catch {
      /* non-JSON error body */
    }
    const details = Array.isArray(detail)
      ? detail.map((d) => (typeof d === "string" ? d : (d?.msg ?? JSON.stringify(d))))
      : []
    const message = typeof detail === "string" ? detail : details.join("; ") || `HTTP ${res.status}`
    throw new ApiError(res.status, message, details)
  }
  return (await res.json()) as T
}

const post = <T>(path: string, body: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(body) })
const qs = (params: Record<string, string | number | undefined | null>) => {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") q.set(k, String(v))
  const s = q.toString()
  return s ? `?${s}` : ""
}
const enc = encodeURIComponent

export const api = {
  status: () => request<Status>("/status"),
  symbols: () => request<SymbolRow[]>("/symbols"),
  chartSymbols: (source: ChartSource) => request<SymbolRow[]>(`/symbols${qs({ source })}`),
  candles: (symbol: string, start?: string, end?: string, options: ChartOptions = {}) =>
    request<ChartData>(`/candles/${enc(symbol)}${qs({ start, end, ...options })}`),
  downloadChart: (body: { symbol: string; interval: string; source: ChartSource; start?: string; end?: string }) =>
    post<Job<ChartDownload>>("/chart/download", body),
  indicators: () => request<IndicatorDef[]>("/indicators"),
  computeIndicators: (symbol: string, items: { key: string; ind: string; params: Record<string, number> }[], start?: string, end?: string, options: ChartOptions = {}) =>
    post<Record<string, Record<string, Point[]>>>("/indicators/compute", { symbol, items, start, end, ...options }),
  strategies: () => request<StrategyInfo[]>("/strategies"),
  strategy: (id: string) => request<StrategyInfo>(`/strategies/${enc(id)}`),
  validateSpec: (spec: RuleSpec) =>
    post<{ ok: boolean; errors: string[]; describe?: string; params?: Record<string, number>; next_version?: number; normalized?: RuleSpec }>(
      "/strategies/validate", spec),
  saveSpec: (spec: RuleSpec) => post<StrategyInfo>("/strategies", spec),
  preview: (body: { strategy_id?: string; spec?: RuleSpec; symbol: string; start?: string; end?: string; source?: ChartSource }) =>
    post<Preview>("/strategies/preview", body),
  backtests: (strategy?: string) => request<RunSummary[]>(`/backtests${qs({ strategy })}`),
  backtest: (runId: string) => request<RunDetail>(`/backtests/${enc(runId)}`),
  backtestSignals: (runId: string, symbol: string) =>
    request<SignalRow[]>(`/backtests/${enc(runId)}/signals${qs({ symbol })}`),
  runBacktest: (body: { strategies: string[]; period: string; enforce_breakers?: boolean; symbols?: string[] }) =>
    post<Job<{ run_id: string; metrics: Metrics }>>("/backtests", body),
  runValidation: (kind: ValidationRecord["kind"], body: { strategy: string; period?: string; grid?: Record<string, number[]> }) =>
    post<Job<ValidationRecord>>(`/validations/${kind}`, body),
  validations: (strategy?: string, kind?: string) => request<ValidationRecord[]>(`/validations${qs({ strategy, kind })}`),
  job: <R>(id: string) => request<Job<R>>(`/jobs/${enc(id)}`),
  jobs: () => request<Job[]>("/jobs"),
  paper: () => request<PaperStatus>("/paper"),
  automation: () => request<AutomationStatus>("/paper/automation"),
  controlPaper: (action: "start" | "pause", acknowledge_research = false) => post<AutomationStatus>("/paper/automation", { action, acknowledge_research }),
  weeklyReview: (day: string) => request<WeeklyReview>(`/mentor/weekly${qs({ day })}`),
  reviewTrade: (id: number, review: ProcessReview) => post<{ ok: boolean }>(`/mentor/trades/${id}`, review),
  saveWeeklyPlan: (day: string) => post<{ ok: boolean }>("/mentor/weekly/plan", { day }),
  trackWeeklyAction: (day: string, action_index: number, completed: boolean, note: string) => post<{ ok: boolean }>("/mentor/weekly/plan", { day, action_index, completed, note }),
  checkConnection: () => post<{ ok: boolean; checked_at: string; scope: string }>("/data/check", {}),
  downloadDaily: () => post<Job>("/data/download", {}),
  demand: () => request<DemandSnapshot>("/market/demand"),
  captureDemand: () => post<DemandSnapshot>("/market/demand", {}),
  research: () => request<ResearchOverview>("/research"),
  runResearch: () => post<Job<ResearchReport>>("/research/run", {}),
  controlResearch: (enabled: boolean) => post<ResearchOverview["status"]>("/research/control", { enabled }),
  journal: (table: "trades" | "signals" | "events" | "equity" | "orders", limit = 200) =>
    request<Record<string, unknown>[]>(`/journal/${table}${qs({ limit })}`),
  killswitch: () => request<KillSwitchState>("/killswitch"),
  setKillswitch: (action: "on" | "off", reason: string) => post<KillSwitchState>("/killswitch", { action, reason }),
  dataQuality: () =>
    request<{ source: string; by_kind: Record<string, number>; needs_review: { symbol: string; kind: string; ts: string; detail: string }[]; total: number }>(
      "/data/quality"),
}
