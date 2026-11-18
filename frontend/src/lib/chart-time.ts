import type { Time, UTCTimestamp } from "lightweight-charts"

const DAY = /^\d{4}-\d{2}-\d{2}$/
export type IntervalUnit = "s" | "m" | "h" | "d" | "w" | "M"
export const INTERVAL_LIMITS: Record<IntervalUnit, number> = { s: 0, m: 390, h: 6, d: 365, w: 52, M: 120 }
export const INTERVALS = ["1m", "5m", "15m", "30m", "1h", "1d", "1w", "1M"]

/** Preserve business dates; intraday ISO values become real UTC seconds at the canvas boundary. */
export function chartTime(value: string): Time {
  if (DAY.test(value)) return value
  return (Date.parse(value) / 1000) as UTCTimestamp
}

/** The library returns BusinessDay objects for date-only candles and numbers for intraday. */
export function timeKey(value: Time): string {
  if (typeof value === "number") return String(value)
  if (typeof value === "string") return DAY.test(value) ? value : String(chartTime(value))
  return `${value.year}-${String(value.month).padStart(2, "0")}-${String(value.day).padStart(2, "0")}`
}

const dateTime = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Kolkata", day: "2-digit", month: "short", year: "numeric",
  hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
})
const axisTime = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
})

export function formatCandleTime(value: Time, period = false): string {
  const key = timeKey(value)
  const daily = DAY.test(key)
  const instant = daily ? new Date(`${key}T09:15:00+05:30`) : new Date(Number(key) * 1000)
  return `${dateTime.format(instant)} IST${daily ? period ? " · period start" : " · session start" : ""}`
}

export function formatAxisTime(value: Time): string | null {
  return typeof value === "number" ? axisTime.format(new Date(value * 1000)) : null
}

export function customInterval(count: string, unit: IntervalUnit): string | null {
  if (!/^[1-9]\d*$/.test(count)) return null
  const n = Number(count)
  return n <= INTERVAL_LIMITS[unit] ? `${n}${unit}` : null
}
