import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  createChart,
  createSeriesMarkers,
  HistogramSeries,
  LineSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type LogicalRange,
  type MouseEventParams,
  type SeriesMarkerBar,
  type SeriesMarkerBarPosition,
  type SeriesMarkerShape,
  type Time,
  type TickMarkType,
} from "lightweight-charts"
import { useEffect, useMemo, useRef, useState } from "react"

import { MONO_FONT, useChartPalette, withAlpha } from "@/components/charts/chart-theme"
import type { Bar, Point } from "@/lib/api"
import { int, num } from "@/lib/format"
import { chartTime, formatAxisTime, formatCandleTime, timeKey } from "@/lib/chart-time"

export type Overlay = { key: string; label: string; points: Point[]; color?: string; dashed?: boolean }
export type PaneSeries = { key: string; label: string; points: Point[]; color?: string; kind?: "line" | "histogram" }
export type Pane = { key: string; title: string; series: PaneSeries[]; levels?: number[]; height?: number }
export type Marker = {
  time: string
  kind: "entry" | "exit" | "rejected" | "signal" | "stop"
  text?: string
}
export type PriceLevel = { price: number; label: string; kind: "stop" | "target" | "entry" }

type Props = {
  bars: Bar[]
  overlays?: Overlay[]
  panes?: Pane[]
  markers?: Marker[]
  levels?: PriceLevel[]
  showVolume?: boolean
  height?: number
  interval?: string
  /** called with the bar time the user clicked (e.g. to open that signal's details) */
  onPickTime?: (time: string) => void
}

type Legend = { time: string; o: number; h: number; l: number; c: number; v: number; values: { label: string; color: string; value: number | null }[] }

/**
 * Candles + volume + indicator overlays + indicator panes + signal markers, on TradingView Lightweight
 * Charts v5. The chart is rebuilt when its STRUCTURE changes (which series/panes exist) and keeps the
 * visible range across rebuilds, so adding an indicator does not reset your zoom.
 */
// Stable empty defaults: a fresh `[]` each render would rebuild the chart on every render (and loop,
// because building the chart sets the legend state).
const NO_OVERLAYS: Overlay[] = []
const NO_PANES: Pane[] = []
const NO_MARKERS: Marker[] = []
const NO_LEVELS: PriceLevel[] = []

export function PriceChart({ bars, overlays = NO_OVERLAYS, panes = NO_PANES, markers = NO_MARKERS, levels = NO_LEVELS, showVolume = true, height = 520, interval = "1d", onPickTime }: Props) {
  const ref = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const rangeRef = useRef<LogicalRange | null>(null)
  const pickRef = useRef(onPickTime)
  const palette = useChartPalette()
  const [legend, setLegend] = useState<Legend | null>(null)

  useEffect(() => {
    pickRef.current = onPickTime
  }, [onPickTime])

  const byTime = useMemo(() => new Map(bars.map((b) => [timeKey(b.time), b])), [bars])
  const intraday = bars[0]?.time.includes("T") ?? false
  const period = interval !== "1d"

  useEffect(() => {
    const el = ref.current
    if (!el || bars.length === 0) return
    const p = palette
    const chart = createChart(el, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: p.bg },
        textColor: p.muted,
        fontFamily: MONO_FONT,
        fontSize: 11,
        attributionLogo: false,
        panes: { separatorColor: p.border, separatorHoverColor: withAlpha(p.primary, 0.25), enableResize: true },
      },
      grid: { vertLines: { color: p.grid }, horzLines: { color: p.grid } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: p.border },
      timeScale: {
        borderColor: p.border, rightOffset: 4, minBarSpacing: 0.5, timeVisible: intraday, secondsVisible: false,
        tickMarkFormatter: (time: Time, type: TickMarkType) => type >= 3 ? formatAxisTime(time) : null,
      },
      localization: { locale: "en-IN", timeFormatter: (time: Time) => formatCandleTime(time, period) },
    })
    chartRef.current = chart

    const candles = chart.addSeries(CandlestickSeries, {
      upColor: p.up, downColor: p.down, borderUpColor: p.up, borderDownColor: p.down,
      wickUpColor: p.up, wickDownColor: p.down, priceLineColor: p.muted,
    })
    candles.setData(bars.map(({ time, open, high, low, close }) => ({ time: chartTime(time), open, high, low, close })))

    const legendSeries: { label: string; color: string; api: ISeriesApi<"Line" | "Histogram"> }[] = []

    if (showVolume) {
      const vol = chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "vol", lastValueVisible: false, priceLineVisible: false })
      vol.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })
      vol.setData(bars.map((b) => ({ time: chartTime(b.time), value: b.volume, color: withAlpha(b.close >= b.open ? p.up : p.down, 0.35) })))
    }

    overlays.forEach((o, i) => {
      const color = o.color ?? p.series[i % p.series.length]
      const s = chart.addSeries(LineSeries, {
        color, lineWidth: 2, lineStyle: o.dashed ? LineStyle.Dashed : LineStyle.Solid,
        priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
      })
      s.setData(o.points.map((pt) => ({ time: chartTime(pt.time), value: pt.value })))
      legendSeries.push({ label: o.label, color, api: s })
    })

    panes.forEach((pane, pi) => {
      const paneIndex = pi + 1
      pane.series.forEach((ps, si) => {
        const color = ps.color ?? p.series[(si + pi + overlays.length) % p.series.length]
        const s = ps.kind === "histogram"
          ? chart.addSeries(HistogramSeries, { color: withAlpha(color, 0.6), priceLineVisible: false, lastValueVisible: false }, paneIndex)
          : chart.addSeries(LineSeries, { color, lineWidth: 2, priceLineVisible: false, lastValueVisible: true, crosshairMarkerVisible: false }, paneIndex)
        s.setData(ps.points.map((pt) => ({ time: chartTime(pt.time), value: pt.value })))
        if (si === 0) {
          for (const lvl of pane.levels ?? []) {
            s.createPriceLine({ price: lvl, color: withAlpha(p.muted, 0.7), lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: "" })
          }
        }
        legendSeries.push({ label: `${pane.title} ${ps.label}`.trim(), color, api: s })
      })
      chart.panes()[paneIndex]?.setHeight(pane.height ?? 110)
    })

    const kindStyle: Record<Marker["kind"], { position: SeriesMarkerBarPosition; shape: SeriesMarkerShape; color: string }> = {
      entry: { position: "belowBar", shape: "arrowUp", color: p.up },
      signal: { position: "belowBar", shape: "arrowUp", color: p.primary },
      exit: { position: "aboveBar", shape: "arrowDown", color: p.down },
      stop: { position: "aboveBar", shape: "square", color: p.down },
      rejected: { position: "belowBar", shape: "circle", color: withAlpha(p.muted, 0.8) },
    }
    // a marker's time must match a bar; drop any that don't (e.g. outside the loaded window)
    const ms = markers
      .filter((m) => byTime.has(timeKey(m.time)))
      .sort((a, b) => a.time.localeCompare(b.time))
      .map((m): SeriesMarkerBar<Time> => ({ time: chartTime(m.time), ...kindStyle[m.kind], text: m.text }))
    if (ms.length) createSeriesMarkers(candles, ms)

    for (const lv of levels) {
      const color = lv.kind === "stop" ? p.down : lv.kind === "target" ? p.up : p.primary
      candles.createPriceLine({ price: lv.price, color, lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: lv.label })
    }

    if (rangeRef.current) chart.timeScale().setVisibleLogicalRange(rangeRef.current)
    else chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, bars.length - 260), to: bars.length + 4 })
    const onRange = (r: LogicalRange | null) => {
      rangeRef.current = r
    }
    chart.timeScale().subscribeVisibleLogicalRangeChange(onRange)

    const last = bars[bars.length - 1]
    const lastValues = legendSeries.map(({ label, color, api }) => {
      const d = api.data().at(-1) as { value?: number } | undefined
      return { label, color, value: d?.value ?? null }
    })
    const latest: Legend = { time: last.time, o: last.open, h: last.high, l: last.low, c: last.close, v: last.volume, values: lastValues }
    setLegend(latest)
    const onMove = (param: MouseEventParams<Time>) => {
      // param.time is undefined outside the data range: show the latest bar then
      const b = param.time !== undefined ? byTime.get(timeKey(param.time)) : undefined
      if (!b) {
        setLegend(latest)
        return
      }
      setLegend({
        time: b.time, o: b.open, h: b.high, l: b.low, c: b.close, v: b.volume,
        values: legendSeries.map(({ label, color, api }) => {
          const d = param.seriesData.get(api) as { value?: number } | undefined  // undefined between bars
          return { label, color, value: d?.value ?? null }
        }),
      })
    }
    const onClick = (param: MouseEventParams<Time>) => {
      const b = param.time !== undefined ? byTime.get(timeKey(param.time)) : undefined
      if (b) pickRef.current?.(b.time)
    }
    chart.subscribeCrosshairMove(onMove)
    chart.subscribeClick(onClick)

    return () => {
      chart.unsubscribeCrosshairMove(onMove)
      chart.unsubscribeClick(onClick)
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(onRange)
      chart.remove()
      chartRef.current = null
    }
  }, [bars, overlays, panes, markers, levels, showVolume, palette, byTime, intraday, period])

  if (bars.length === 0) return null
  return (
    <div className="relative" style={{ height }} data-testid="price-chart">
      <div ref={ref} className="absolute inset-0" />
      {legend && (
        <div className="pointer-events-none absolute top-2 left-2 z-10 flex max-w-[75%] flex-col gap-0.5 rounded-md bg-card/80 px-2 py-1 text-[11px] backdrop-blur-sm">
          <div className="num flex flex-wrap gap-x-3 text-muted-foreground">
            <span className="text-foreground" data-testid="candle-time">{formatCandleTime(legend.time, period)}</span>
            <span>O {num(legend.o)}</span>
            <span>H {num(legend.h)}</span>
            <span>L {num(legend.l)}</span>
            <span className={legend.c >= legend.o ? "text-up" : "text-down"}>C {num(legend.c)}</span>
            {showVolume && <span>Vol {int(legend.v)}</span>}
          </div>
          {legend.values.length > 0 && (
            <div className="num flex flex-wrap gap-x-3">
              {legend.values.map((v) => (
                <span key={v.label} style={{ color: v.color }}>
                  {v.label} {v.value === null ? "–" : num(v.value)}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
