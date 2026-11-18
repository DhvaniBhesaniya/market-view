// Number formatting in the Indian convention: 5,00,000 (lakh) and 1,25,00,000 (crore).

const inr = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 })
const inr2 = new Intl.NumberFormat("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })

export const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v)

/** ₹ amount. Whole rupees by default; `paise` for prices. */
export function rupees(v: unknown, paise = false): string {
  if (!isNum(v)) return "–"
  const sign = v < 0 ? "−" : ""
  return `${sign}₹${(paise ? inr2 : inr).format(Math.abs(v))}`
}

/** Compact ₹: ₹4.2 L, ₹1.3 Cr. */
export function rupeesCompact(v: unknown): string {
  if (!isNum(v)) return "–"
  const a = Math.abs(v)
  const sign = v < 0 ? "−" : ""
  if (a >= 1e7) return `${sign}₹${(a / 1e7).toFixed(2)} Cr`
  if (a >= 1e5) return `${sign}₹${(a / 1e5).toFixed(2)} L`
  return rupees(v)
}

/** Percent with an explicit sign for changes: +4.20%, −1.05%. */
export function pct(v: unknown, digits = 2, signed = true): string {
  if (!isNum(v)) return "–"
  const s = Math.abs(v).toFixed(digits)
  if (!signed) return `${v < 0 ? "−" : ""}${s}%`
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${s}%`
}

export function num(v: unknown, digits = 2): string {
  if (!isNum(v)) return "–"
  return `${v < 0 ? "−" : ""}${Math.abs(v).toLocaleString("en-IN", { minimumFractionDigits: digits, maximumFractionDigits: digits })}`
}

export function int(v: unknown): string {
  return isNum(v) ? inr.format(v) : "–"
}

/** R-multiple: +1.50R */
export function r(v: unknown): string {
  if (!isNum(v)) return "–"
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(2)}R`
}

/** "up" | "down" | "flat" for colouring a signed value. */
export function tone(v: unknown, flatBand = 0): "up" | "down" | "flat" {
  if (!isNum(v) || Math.abs(v) <= flatBand) return "flat"
  return v > 0 ? "up" : "down"
}

export function date(v: unknown): string {
  if (typeof v !== "string" || !v) return "–"
  return v.slice(0, 10)
}

export function dateTime(v: unknown): string {
  if (typeof v !== "string" || !v) return "–"
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return v
  return d.toLocaleString("en-IN", { timeZone: "Asia/Kolkata", dateStyle: "medium", timeStyle: "short" })
}

/** Run ids look like 20261116-124403-trend_v1-full → "16 Nov 2026, 12:44". */
export function runTime(runId: string): string {
  const m = /^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})/.exec(runId)
  if (!m) return runId
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]))
  return `${d.getUTCDate()} ${d.toLocaleString("en-IN", { month: "short", timeZone: "UTC" })} ${m[1]}, ${m[4]}:${m[5]}`
}

/** Literal class names (Tailwind only generates classes it can see written out in full). */
export function toneClass(v: unknown, flatBand = 0): string {
  const t = tone(v, flatBand)
  return t === "up" ? "text-up" : t === "down" ? "text-down" : ""
}
