import {
  AreaSeries,
  BaselineSeries,
  ColorType,
  createChart,
  HistogramSeries,
  LineSeries,
  LineStyle,
  type Time,
} from "lightweight-charts"
import { useEffect, useRef } from "react"

import { MONO_FONT, useChartPalette, withAlpha } from "@/components/charts/chart-theme"
import type { Point } from "@/lib/api"

export type SeriesSpec = {
  key: string
  label: string
  points: Point[]
  kind?: "line" | "area" | "histogram" | "baseline"
  /** "up" | "down" | "primary" | "muted" | 0-4 (chart palette index) */
  color?: "up" | "down" | "primary" | "muted" | number
  dashed?: boolean
  pane?: number
  baseValue?: number
}

type Props = {
  series: SeriesSpec[]
  height?: number
  paneHeights?: number[]
  percent?: boolean
  valueFormat?: (v: number) => string
}

/** Time-series lines (equity vs NIFTY, drawdown, journal equity) on Lightweight Charts. */
const NO_HEIGHTS: number[] = []  // stable default: a new [] each render would rebuild the chart

export function SeriesChart({ series, height = 320, paneHeights = NO_HEIGHTS, percent = false, valueFormat }: Props) {
  const ref = useRef<HTMLDivElement | null>(null)
  const p = useChartPalette()

  useEffect(() => {
    const el = ref.current
    if (!el || series.every((s) => s.points.length === 0)) return
    const chart = createChart(el, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: p.bg }, textColor: p.muted, fontFamily: MONO_FONT, fontSize: 11,
        attributionLogo: false, panes: { separatorColor: p.border, enableResize: true },
      },
      grid: { vertLines: { color: p.grid }, horzLines: { color: p.grid } },
      rightPriceScale: { borderColor: p.border },
      timeScale: { borderColor: p.border },
      localization: {
        locale: "en-IN",
        priceFormatter: valueFormat ?? (percent ? (v: number) => `${v.toFixed(1)}%` : undefined),
      },
    })
    const colorOf = (c: SeriesSpec["color"], i: number) =>
      c === "up" ? p.up : c === "down" ? p.down : c === "primary" ? p.primary : c === "muted" ? p.muted
        : typeof c === "number" ? p.series[c % p.series.length] : p.series[i % p.series.length]

    series.forEach((s, i) => {
      const color = colorOf(s.color, i)
      const data = s.points.map((pt) => ({ time: pt.time as Time, value: pt.value }))
      const pane = s.pane ?? 0
      const common = { priceLineVisible: false, lastValueVisible: true, title: "" }
      if (s.kind === "area") {
        chart.addSeries(AreaSeries, { ...common, lineColor: color, topColor: withAlpha(color, 0.05), bottomColor: withAlpha(color, 0.35), lineWidth: 2, invertFilledArea: true }, pane).setData(data)
      } else if (s.kind === "histogram") {
        chart.addSeries(HistogramSeries, { ...common, color: withAlpha(color, 0.7) }, pane).setData(data)
      } else if (s.kind === "baseline") {
        chart.addSeries(BaselineSeries, {
          ...common, baseValue: { type: "price", price: s.baseValue ?? 0 },
          topLineColor: p.up, topFillColor1: withAlpha(p.up, 0.25), topFillColor2: withAlpha(p.up, 0.02),
          bottomLineColor: p.down, bottomFillColor1: withAlpha(p.down, 0.02), bottomFillColor2: withAlpha(p.down, 0.25),
        }, pane).setData(data)
      } else {
        chart.addSeries(LineSeries, { ...common, color, lineWidth: 2, lineStyle: s.dashed ? LineStyle.Dashed : LineStyle.Solid }, pane).setData(data)
      }
    })
    paneHeights.forEach((h, i) => chart.panes()[i + 1]?.setHeight(h))
    chart.timeScale().fitContent()
    return () => chart.remove()
  }, [series, paneHeights, percent, valueFormat, p])

  return (
    <div className="flex flex-col gap-2" data-testid="series-chart">
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        {series.map((s, i) => (
          <span key={s.key} className="flex items-center gap-1.5">
            <span
              className="inline-block h-0.5 w-4 rounded-full"
              style={{ background: s.kind === "baseline" ? p.up : s.color === undefined ? p.series[i % p.series.length]
                : s.color === "up" ? p.up : s.color === "down" ? p.down : s.color === "primary" ? p.primary
                : s.color === "muted" ? p.muted : p.series[(s.color as number) % p.series.length],
                opacity: s.dashed ? 0.7 : 1 }}
            />
            {s.label}
          </span>
        ))}
      </div>
      <div className="relative" style={{ height }}>
        <div ref={ref} className="absolute inset-0" />
      </div>
    </div>
  )
}
