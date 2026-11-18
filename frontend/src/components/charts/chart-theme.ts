import { useEffect, useState } from "react"

// Canvas charts cannot read CSS variables, and our tokens are oklch(). Resolve each token to rgb()
// by painting one pixel, so charts follow the exact theme (light/dark) the rest of the UI uses.

export type ChartPalette = {
  bg: string
  text: string
  muted: string
  grid: string
  border: string
  up: string
  down: string
  warn: string
  primary: string
  series: string[]
  isDark: boolean
}

let canvas: HTMLCanvasElement | null = null

function toRgb(cssColor: string, alpha = 1): string {
  canvas ??= document.createElement("canvas")
  canvas.width = canvas.height = 1
  const ctx = canvas.getContext("2d", { willReadFrequently: true })
  if (!ctx) return cssColor
  ctx.clearRect(0, 0, 1, 1)
  ctx.fillStyle = "#000"
  ctx.fillStyle = cssColor
  ctx.fillRect(0, 0, 1, 1)
  const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1).data
  return `rgba(${r}, ${g}, ${b}, ${((a / 255) * alpha).toFixed(3)})`
}

function token(name: string, alpha = 1): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim()
  return v ? toRgb(v, alpha) : "rgba(128,128,128,1)"
}

export function readPalette(): ChartPalette {
  const isDark = document.documentElement.classList.contains("dark")
  return {
    bg: token("card"),
    text: token("foreground"),
    muted: token("muted-foreground"),
    grid: token("border", isDark ? 0.55 : 0.7),
    border: token("border"),
    up: token("up"),
    down: token("down"),
    warn: token("warn"),
    primary: token("primary"),
    series: [1, 2, 3, 4, 5].map((i) => token(`chart-${i}`)),
    isDark,
  }
}

/** Re-reads the palette whenever the <html> class changes (theme toggle). */
export function useChartPalette(): ChartPalette {
  const [palette, setPalette] = useState<ChartPalette>(() => readPalette())
  useEffect(() => {
    const obs = new MutationObserver(() => setPalette(readPalette()))
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["class", "style"] })
    return () => obs.disconnect()
  }, [])
  return palette
}

export function withAlpha(rgba: string, alpha: number): string {
  const m = /rgba?\((\d+),\s*(\d+),\s*(\d+)/.exec(rgba)
  return m ? `rgba(${m[1]}, ${m[2]}, ${m[3]}, ${alpha})` : rgba
}

export const MONO_FONT = "'JetBrains Mono Variable', ui-monospace, monospace"
