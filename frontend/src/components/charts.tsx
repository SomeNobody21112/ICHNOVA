import { useCallback, useEffect, useRef, useState } from 'react'
import { cssVar, parseColor, rampStops, useTheme } from '../lib/theme'
import type { AllHypotheses } from '../lib/types'

/** Canvas cannot read var(); resolve theme tokens (and 'var(--x)' strings) to concrete colours. */
export function resolveColor(c: string) {
  const m = /^var\((--[\w-]+)\)$/.exec(c.trim())
  return m ? cssVar(m[1]) : c
}
export function withAlpha(c: string, a: number) {
  const [r, g, b] = parseColor(resolveColor(c))
  return `rgba(${r},${g},${b},${a})`
}
let rampCache: { key: string; spec: number[][]; occ: number[][] } | null = null
function ramp(kind: 'spec' | 'occ') {
  const key = document.documentElement.dataset.theme ?? 'light'
  if (!rampCache || rampCache.key !== key) rampCache = { key, spec: rampStops('spec'), occ: rampStops('occ') }
  return rampCache[kind]
}
function interp(stops: number[][], t: number) {
  const x = Math.max(0, Math.min(1, t))
  const p = x * (stops.length - 1)
  const i = Math.min(stops.length - 2, Math.floor(p))
  const f = p - i
  const a = stops[i], b = stops[i + 1]
  return `rgb(${a[0] + (b[0] - a[0]) * f | 0},${a[1] + (b[1] - a[1]) * f | 0},${a[2] + (b[2] - a[2]) * f | 0})`
}

function useCanvas(draw: (ctx: CanvasRenderingContext2D, w: number, h: number) => void, deps: unknown[]) {
  const ref = useRef<HTMLCanvasElement>(null)
  const { theme } = useTheme()
  const [size, setSize] = useState({ w: 0, h: 0 })
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight }))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  useEffect(() => {
    const el = ref.current
    if (!el || !size.w || !size.h) return
    const dpr = window.devicePixelRatio || 1
    el.width = Math.round(size.w * dpr)
    el.height = Math.round(size.h * dpr)
    const ctx = el.getContext('2d')!
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, size.w, size.h)
    draw(ctx, size.w, size.h)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [size, theme, ...deps])
  return ref
}

// Spectrum and occupancy ramps come from the theme (--ramp-*, --occ-*): background-coloured when quiet.
export function specColor(t: number) {
  return interp(ramp('spec'), t)
}

export function occColor(t: number) {
  return interp(ramp('occ'), t)
}

/** Matrix heatmap: data[row][col], rows drawn top→bottom. */
export function Heatmap({ data, height = 220, color = occColor, onCell, highlightRow, lo, hi }: {
  data: number[][]; height?: number; color?: (t: number) => string; onCell?: (r: number, c: number) => void
  highlightRow?: number; lo?: number; hi?: number
}) {
  const flat = data.flat()
  const mn = lo ?? Math.min(...flat)
  const mx = hi ?? Math.max(...flat)
  const ref = useCanvas((ctx, w, h) => {
    const R = data.length, C = data[0]?.length ?? 0
    if (!R || !C) return
    const cw = w / C, ch = h / R
    for (let r = 0; r < R; r++) for (let c = 0; c < C; c++) {
      ctx.fillStyle = color((data[r][c] - mn) / (mx - mn || 1))
      ctx.fillRect(c * cw, r * ch, Math.ceil(cw), Math.ceil(ch))
    }
    if (highlightRow != null) {
      ctx.strokeStyle = withAlpha('var(--accent)', 0.9)
      ctx.lineWidth = 1.5
      ctx.strokeRect(0.5, highlightRow * ch + 0.5, w - 1, ch - 1)
    }
  }, [data, mn, mx, highlightRow])
  return (
    <div className="canvas-box" style={{ height }}>
      <canvas ref={ref} style={{ cursor: onCell ? 'crosshair' : 'default' }} onClick={(e) => {
        if (!onCell) return
        const rect = e.currentTarget.getBoundingClientRect()
        const c = Math.floor(((e.clientX - rect.left) / rect.width) * (data[0]?.length ?? 1))
        const r = Math.floor(((e.clientY - rect.top) / rect.height) * data.length)
        onCell(r, c)
      }} />
    </div>
  )
}

/** Spectrogram from an evidence pack: db[freq][time]; drawn time →, frequency ↑. */
export function Spectrogram({ db, f, t, height = 240 }: { db: number[][]; f: number[]; t: number[]; height?: number }) {
  const flat = db.flat().sort((a, b) => a - b)
  const lo = flat[Math.floor(flat.length * 0.05)] ?? 0
  const hi = flat[Math.floor(flat.length * 0.995)] ?? 1
  const flipped = [...db].reverse()
  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: '52px 1fr', gap: 6 }}>
        <div className="col mono" style={{ justifyContent: 'space-between', fontSize: 11, color: 'var(--muted)', textAlign: 'right', height }}>
          <span>{(f[f.length - 1] / 1e3).toFixed(0)} kHz</span><span>0</span><span>{(f[0] / 1e3).toFixed(0)} kHz</span>
        </div>
        <Heatmap data={flipped} height={height} color={specColor} lo={lo} hi={hi} />
      </div>
      <div className="row mono" style={{ justifyContent: 'space-between', fontSize: 11, color: 'var(--muted)', paddingLeft: 58, marginTop: 4 }}>
        <span>0 ms</span><span>time →</span><span>{((t[t.length - 1] ?? 0) * 1e3).toFixed(2)} ms</span>
      </div>
    </div>
  )
}

export interface WaterfallEvent { id: string; f0: number; f1: number; label: string; tone: string; startRow: number; rows: number }

/** Live-scrolling waterfall (simulated stream). New rows enter at the top; detections are boxed and clickable. */
export function LiveWaterfall({ height = 380, channels = 160, events, running = true, seed = 1, onEvent }: {
  height?: number; channels?: number; events: WaterfallEvent[]; running?: boolean; seed?: number; onEvent?: (id: string) => void
}) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const rowsRef = useRef<number[][]>([])
  const tick = useRef(0)
  const boxes = useRef<{ id: string; x: number; y: number; w: number; h: number }[]>([])
  const [hover, setHover] = useState<string | null>(null)
  const evRef = useRef(events)
  evRef.current = events

  useEffect(() => {
    const el = canvas.current!
    let raf = 0
    let last = 0
    const rowH = 3
    const render = (ts: number) => {
      raf = requestAnimationFrame(render)
      if (ts - last < 45) return
      last = ts
      const w = el.clientWidth, h = el.clientHeight
      const dpr = window.devicePixelRatio || 1
      if (el.width !== Math.round(w * dpr)) { el.width = Math.round(w * dpr); el.height = Math.round(h * dpr) }
      const ctx = el.getContext('2d')!
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      const maxRows = Math.ceil(h / rowH)
      if (running || rowsRef.current.length < maxRows) {
        const k = tick.current++
        const row: number[] = []
        for (let c = 0; c < channels; c++) {
          const x = Math.sin(c * 12.9898 + k * 78.233 + seed * 3.1) * 43758.5453
          let v = 0.12 + 0.18 * (x - Math.floor(x))
          for (const ev of evRef.current) {
            const period = 40 + ev.startRow % 37
            const on = (k + ev.startRow) % period < ev.rows
            if (on && c >= ev.f0 && c <= ev.f1) v += 0.5 + 0.25 * Math.sin((c - ev.f0) / Math.max(1, ev.f1 - ev.f0) * Math.PI)
          }
          if (c % 53 === 17) v += 0.3
          row.push(v)
        }
        rowsRef.current.unshift(row)
        if (rowsRef.current.length > maxRows) rowsRef.current.length = maxRows
      }
      const cw = w / channels
      ctx.clearRect(0, 0, w, h)
      rowsRef.current.forEach((row, r) => {
        for (let c = 0; c < channels; c++) {
          ctx.fillStyle = specColor(row[c])
          ctx.fillRect(c * cw, r * rowH, Math.ceil(cw), rowH)
        }
      })
      boxes.current = []
      const k = tick.current
      for (const ev of evRef.current) {
        const period = 40 + ev.startRow % 37
        const phase = (k + ev.startRow) % period
        const age = phase < ev.rows ? 0 : phase - ev.rows + 1
        const top = age * rowH
        const bh = (phase < ev.rows ? phase + 1 : ev.rows) * rowH
        if (top > h) continue
        const x = ev.f0 * cw - 2, bw = (ev.f1 - ev.f0 + 1) * cw + 4
        boxes.current.push({ id: ev.id, x, y: top, w: bw, h: bh })
        ctx.strokeStyle = resolveColor(hover === ev.id ? 'var(--text)' : ev.tone)
        ctx.lineWidth = hover === ev.id ? 1.6 : 1.1
        ctx.strokeRect(x + 0.5, top + 0.5, bw, Math.max(bh, 6))
        ctx.fillStyle = resolveColor(ev.tone)
        ctx.font = '10px "IBM Plex Mono", monospace'
        ctx.fillText(ev.label, x + 3, top + Math.max(bh, 6) + 11)
      }
    }
    raf = requestAnimationFrame(render)
    return () => cancelAnimationFrame(raf)
  }, [channels, running, seed, hover])

  const hit = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const x = e.clientX - rect.left, y = e.clientY - rect.top
    return boxes.current.find((b) => x >= b.x && x <= b.x + b.w && y >= b.y - 4 && y <= b.y + Math.max(b.h, 6) + 14)?.id ?? null
  }
  return (
    <div className="canvas-box" style={{ height }}>
      <canvas ref={canvas} style={{ cursor: hover ? 'pointer' : 'crosshair' }}
        onMouseMove={(e) => setHover(hit(e))} onMouseLeave={() => setHover(null)}
        onClick={(e) => { const id = hit(e); if (id && onEvent) onEvent(id) }} />
    </div>
  )
}

export function Constellation({ points, height = 260, ideal }: { points: number[][]; height?: number; ideal?: string | null }) {
  const ref = useCanvas((ctx, w, h) => {
    const s = Math.min(w, h) / 2 - 12
    const cx = w / 2, cy = h / 2
    ctx.strokeStyle = cssVar('--line-2')
    ctx.lineWidth = 1
    for (const k of [0.5, 1, 1.5]) { ctx.beginPath(); ctx.arc(cx, cy, (s / 1.8) * k, 0, Math.PI * 2); ctx.stroke() }
    ctx.beginPath(); ctx.moveTo(cx - s, cy); ctx.lineTo(cx + s, cy); ctx.moveTo(cx, cy - s); ctx.lineTo(cx, cy + s); ctx.stroke()
    const scale = s / 1.8
    ctx.fillStyle = withAlpha('var(--cyan)', 0.6)
    for (const [re, im] of points) {
      ctx.beginPath(); ctx.arc(cx + re * scale, cy - im * scale, 1.7, 0, Math.PI * 2); ctx.fill()
    }
    const ref: number[][] = ideal === 'BPSK' ? [[1, 0], [-1, 0]] : ideal === 'QPSK' ? [[0.707, 0.707], [-0.707, 0.707], [0.707, -0.707], [-0.707, -0.707]] : []
    ctx.strokeStyle = cssVar('--amber')
    ctx.lineWidth = 1.5
    for (const [re, im] of ref) {
      const x = cx + re * scale, y = cy - im * scale
      ctx.beginPath(); ctx.moveTo(x - 6, y); ctx.lineTo(x + 6, y); ctx.moveTo(x, y - 6); ctx.lineTo(x, y + 6); ctx.stroke()
    }
  }, [points, ideal])
  return <div className="canvas-box" style={{ height }}><canvas ref={ref} /></div>
}

export function LinePlot({ series, height = 180, yLabel, xLabel, yMin, yMax, markers }: {
  series: { x: number[]; y: number[]; color: string; width?: number; fill?: boolean }[]
  height?: number; yLabel?: string; xLabel?: string; yMin?: number; yMax?: number; markers?: { x: number; label: string; color: string }[]
}) {
  // Drawn at the container's real pixel width. The old version stretched a fixed viewBox with
  // preserveAspectRatio="none", which distorted every label and let the y-axis title sit on a tick.
  const box = useRef<HTMLDivElement>(null)
  const [W, setW] = useState(0)
  useEffect(() => {
    const el = box.current
    if (!el) return
    const ro = new ResizeObserver(() => setW(el.clientWidth))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  const allX = series.flatMap((s) => s.x), allY = series.flatMap((s) => s.y)
  const x0 = Math.min(...allX), x1 = Math.max(...allX)
  const y0 = yMin ?? Math.min(...allY), y1 = yMax ?? Math.max(...allY)
  const H = height, pl = 46, pb = 8, pt = 8, pr = 10
  const sx = (x: number) => pl + ((x - x0) / (x1 - x0 || 1)) * (W - pl - pr)
  const sy = (y: number) => pt + (1 - (y - y0) / (y1 - y0 || 1)) * (H - pt - pb)
  // Enough decimals to tell adjacent ticks apart (0.25 stays 0.25, not a second "0.3").
  const step = Math.abs(y1 - y0) / 4
  const dec = step >= 5 || step === 0 ? 0 : Math.min(3, Math.max(0, Math.ceil(-Math.log10(step) + 0.3)))
  return (
    <div className="lineplot" ref={box}>
      {yLabel && <div className="lineplot-y">{yLabel}</div>}
      <svg width="100%" height={H} role="img" aria-label={[yLabel, xLabel].filter(Boolean).join(' against ') || 'line chart'}>
        {W > 0 && <>
          {[0, 0.25, 0.5, 0.75, 1].map((k) => (
            <g key={k}>
              <line x1={pl} x2={W - pr} y1={pt + k * (H - pt - pb)} y2={pt + k * (H - pt - pb)} stroke="var(--line)" />
              <text x={pl - 8} y={pt + k * (H - pt - pb) + 3.5} textAnchor="end">{(y1 - k * (y1 - y0)).toFixed(dec)}</text>
            </g>
          ))}
          {series.map((s, i) => {
            const d = s.x.map((x, k) => `${k ? 'L' : 'M'}${sx(x).toFixed(1)},${sy(s.y[k]).toFixed(1)}`).join('')
            return (
              <g key={i}>
                {s.fill && <path className="lp-fill" d={`${d}L${sx(s.x[s.x.length - 1])},${H - pb}L${sx(s.x[0])},${H - pb}Z`} fill={s.color} opacity={0.1} />}
                <path className="lp-line" pathLength={1} d={d} fill="none" stroke={s.color} strokeWidth={s.width ?? 1.5} strokeLinejoin="round" style={{ animationDelay: `${i * 120}ms` }} />
              </g>
            )
          })}
          {markers?.map((m, i) => (
            <g key={i}>
              <line x1={sx(m.x)} x2={sx(m.x)} y1={pt} y2={H - pb} stroke={m.color} strokeDasharray="3 3" />
              <text x={sx(m.x) + 4} y={pt + 10} style={{ fill: m.color }}>{m.label}</text>
            </g>
          ))}
        </>}
      </svg>
      {xLabel && <div className="lineplot-x">{xLabel}</div>}
    </div>
  )
}

export function Sparkline({ values, color = 'var(--cyan)', w = 90, h = 26 }: { values: number[]; color?: string; w?: number; h?: number }) {
  const mn = Math.min(...values), mx = Math.max(...values)
  const d = values.map((v, i) => `${i ? 'L' : 'M'}${(i / (values.length - 1)) * w},${h - 2 - ((v - mn) / (mx - mn || 1)) * (h - 4)}`).join('')
  return <svg width={w} height={h}><path d={d} fill="none" stroke={color} strokeWidth={1.4} /></svg>
}

export function HBars({ items, max, fmt = (v: number) => String(v) }: { items: { label: string; value: number; color?: string; note?: string }[]; max?: number; fmt?: (v: number) => string }) {
  const m = max ?? Math.max(...items.map((i) => i.value), 1)
  return (
    <div className="col" style={{ gap: 7 }}>
      {items.map((it) => (
        <div key={it.label} style={{ display: 'grid', gridTemplateColumns: 'minmax(90px, 32%) 1fr 64px', gap: 10, alignItems: 'center', fontSize: 12.5 }}>
          <span className="dim" title={it.note}>{it.label}</span>
          <div className="meter" style={{ height: 10 }}><i style={{ '--fill': it.value / m, background: it.color ?? 'var(--cyan)' } as React.CSSProperties} /></div>
          <span className="mono" style={{ textAlign: 'right' }}>{fmt(it.value)}</span>
        </div>
      ))}
    </div>
  )
}

export function Donut({ parts, size = 120, label }: { parts: { value: number; color: string; label: string }[]; size?: number; label?: string }) {
  const total = parts.reduce((a, p) => a + p.value, 0) || 1
  let acc = 0
  const r = 44, c = 2 * Math.PI * r
  return (
    <svg viewBox="0 0 120 120" width={size} height={size} style={{ flex: 'none' }}>
      <circle cx="60" cy="60" r={r} fill="none" stroke="var(--panel-3)" strokeWidth="14" />
      {parts.map((p) => {
        const len = (p.value / total) * c
        const el = <circle key={p.label} className="donut-seg" cx="60" cy="60" r={r} fill="none" stroke={p.color} strokeWidth="14" strokeDasharray={`${len} ${c - len}`} strokeDashoffset={-acc} transform="rotate(-90 60 60)" />
        acc += len
        return el
      })}
      {label && size >= 44 && <text x="60" y="64" textAnchor="middle" style={{ fill: 'var(--text)', font: `600 ${Math.round((12 * 120 / size) * 10) / 10}px var(--cond)` }}>{label}</text>}
    </svg>
  )
}

/** Radial fingerprint: 10 genome axes as a closed polygon plus spokes. */
export function GenomeGlyph({ values, size = 150, color = 'var(--cyan)', compare, labels }: { values: number[]; size?: number; color?: string; compare?: number[]; labels?: string[] }) {
  const n = values.length, R = 50
  const pt = (v: number, i: number) => {
    const a = (i / n) * Math.PI * 2 - Math.PI / 2
    return [60 + Math.cos(a) * R * v, 60 + Math.sin(a) * R * v]
  }
  const poly = (vals: number[]) => vals.map((v, i) => pt(Math.max(0.06, v), i).map((x) => x.toFixed(1)).join(',')).join(' ')
  return (
    // The labelled viewBox is wide enough to hold the axis names, and nothing is allowed to paint
    // outside it: with overflow visible the names spilled over whatever sat beside the glyph.
    <svg viewBox={labels ? '-115 -14 350 148' : '0 0 120 120'} width={size} height={size * (labels ? 0.423 : 1)}>
      {[0.33, 0.66, 1].map((k) => <polygon key={k} points={poly(Array(n).fill(k))} fill="none" stroke="var(--line)" />)}
      {values.map((_, i) => { const [x, y] = pt(1, i); return <line key={i} x1="60" y1="60" x2={x} y2={y} stroke="var(--line)" /> })}
      {compare && <polygon points={poly(compare)} fill="var(--amber)" fillOpacity={0.1} stroke="var(--amber)" strokeWidth="1" strokeDasharray="3 2" />}
      <polygon points={poly(values)} fill={color} fillOpacity={0.14} stroke={color} strokeWidth="1.4" />
      {values.map((v, i) => { const [x, y] = pt(Math.max(0.06, v), i); return <circle key={i} cx={x} cy={y} r="1.8" fill={color} /> })}
      {labels?.map((l, i) => {
        const [x, y] = pt(1.28, i)
        return <text key={l} x={x} y={y} textAnchor={x < 55 ? 'end' : x > 65 ? 'start' : 'middle'} style={{ fill: 'var(--muted)', font: '10px var(--sans)' }}>{l}</text>
      })}
    </svg>
  )
}

const CODE_COLORS: Record<string, string> = { K7: 'var(--cyan)', K5: 'var(--violet)', K3: 'var(--green)' }

/** Every tested hypothesis: x = hypothesis index (grouped by code), y = −log10 p, with the Bonferroni line. */
export function Landscape({ all, threshold, isAccepted, isRejected, filter, height = 260 }: {
  all: AllHypotheses; threshold: number; isAccepted: (i: number) => boolean; isRejected: (i: number) => boolean
  filter: (i: number) => boolean; height?: number
}) {
  const n = all.log10_p.length
  const order = useCallback(() => {
    const idx = Array.from({ length: n }, (_, i) => i)
    const rank: Record<string, number> = { K7: 0, K5: 1, K3: 2 }
    return idx.sort((a, b) => (rank[all.code[a]] ?? 3) - (rank[all.code[b]] ?? 3) || all.rows[a] * all.cols[a] - all.rows[b] * all.cols[b])
  }, [all, n])
  const ymax = Math.max(-threshold * 1.4, ...all.log10_p.map((v) => -v)) + 0.5
  const ref = useCanvas((ctx, w, h) => {
    const pl = 34, pb = 16, pt = 8
    const o = order()
    const sy = (v: number) => pt + (1 - v / ymax) * (h - pt - pb)
    ctx.strokeStyle = cssVar('--line')
    ctx.fillStyle = cssVar('--muted')
    ctx.font = '10px "IBM Plex Mono", monospace'
    for (let k = 0; k <= 4; k++) {
      const v = (ymax * k) / 4
      ctx.beginPath(); ctx.moveTo(pl, sy(v)); ctx.lineTo(w, sy(v)); ctx.stroke()
      ctx.fillText(v.toFixed(0), 4, sy(v) + 3)
    }
    const sx = (j: number) => pl + (j / Math.max(1, n - 1)) * (w - pl - 4)
    const C = { acc: cssVar('--green'), rej: cssVar('--orange'), sig: cssVar('--amber') }
    o.forEach((i, j) => {
      if (!filter(i)) return
      const acc = isAccepted(i), rej = isRejected(i)
      const v = -all.log10_p[i]
      ctx.fillStyle = acc ? C.acc : rej ? C.rej : v >= -threshold ? C.sig : withAlpha(CODE_COLORS[all.code[i]] ?? 'var(--cyan)', 0.55)
      const r = acc || rej ? 3.2 : 1.3
      ctx.beginPath(); ctx.arc(sx(j), sy(v), r, 0, Math.PI * 2); ctx.fill()
    })
    ctx.strokeStyle = C.sig
    ctx.setLineDash([5, 4])
    ctx.beginPath(); ctx.moveTo(pl, sy(-threshold)); ctx.lineTo(w, sy(-threshold)); ctx.stroke()
    ctx.setLineDash([])
    ctx.fillStyle = C.sig
    ctx.fillText(`acceptance bar  −log10(α/M) = ${(-threshold).toFixed(2)}`, pl + 6, sy(-threshold) - 5)
  }, [all, threshold, filter, isAccepted, isRejected, ymax])
  return <div className="canvas-box" style={{ height }}><canvas ref={ref} /></div>
}

const HOUR = 3600e3, DAY = 24 * HOUR
const TICK_STEPS = [15 * 60e3, 30 * 60e3, HOUR, 3 * HOUR, 6 * HOUR, 12 * HOUR, DAY, 2 * DAY, 7 * DAY]
const MIN_SPAN = 20 * 60e3
const fmtTick = (t: number, step: number) => new Date(t).toLocaleString('en-GB', step >= DAY
  ? { day: '2-digit', month: 'short' } : { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false })
const fmtWhen = (t: number) => new Date(t).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false })

/** Observations per station over time, zoomable.
 *
 *  Marks closer than a click target merge into a count bubble; selecting a bubble zooms to the
 *  observations inside it, so every single observation becomes reachable. The overview strip below
 *  shows the whole period with the current window: drag the window to pan, drag across the strip to
 *  choose a new window. + / − / Show all, Ctrl + scroll and double-click also zoom. */
export function TimelineStrip({ lanes, events, from, to, onPick }: {
  lanes: { id: string; label: string }[]; events: { t: number; lane: string; id?: string; tone?: string }[]
  from: number; to: number; height?: number; onPick?: (id: string) => void
}) {
  const box = useRef<HTMLDivElement>(null)
  const detail = useRef<SVGSVGElement>(null)
  const [W, setW] = useState(0)
  const [view, setView] = useState<[number, number]>([from, to])
  const [hover, setHover] = useState<{ x: number; y: number; text: string } | null>(null)
  useEffect(() => {
    const el = box.current
    if (!el) return
    const ro = new ResizeObserver(() => setW(el.clientWidth))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  useEffect(() => { setView([from, to]) }, [from, to])

  const pl = 136, pr = 18, laneH = 42, top = 10
  const H = top + lanes.length * laneH + 28
  const plotW = Math.max(1, W - pl - pr)
  const [v0, v1] = view
  const span = v1 - v0
  const sx = (t: number) => pl + ((t - v0) / span) * plotW
  const tAt = (px: number) => v0 + ((px - pl) / plotW) * span

  const clamp = useCallback((a: number, b: number): [number, number] => {
    const s = Math.max(MIN_SPAN, b - a)
    if (s >= to - from) return [from, to]
    const start = Math.max(from, Math.min(a, to - s))
    return [start, start + s]
  }, [from, to])
  const zoomAt = useCallback((t: number, f: number) => {
    setView(([a, b]) => { const s = t - (t - a) * f; return clamp(s, s + (b - a) * f) })
  }, [clamp])

  // Ctrl/Cmd + wheel zooms around the pointer; a plain wheel keeps scrolling the page.
  useEffect(() => {
    const svg = detail.current
    if (!svg) return
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) return
      e.preventDefault()
      const r = svg.getBoundingClientRect()
      zoomAt(tAt(e.clientX - r.left), Math.exp(e.deltaY * 0.002))
    }
    svg.addEventListener('wheel', onWheel, { passive: false })
    return () => svg.removeEventListener('wheel', onWheel)
  })

  // Ticks aligned to local clock time (hours on the hour, days at midnight).
  const step = TICK_STEPS.find((s) => (s / span) * plotW >= 88) ?? TICK_STEPS[TICK_STEPS.length - 1]
  const off = new Date(v0).getTimezoneOffset() * 60e3
  const ticks: number[] = []
  for (let t = Math.ceil((v0 - off) / step) * step + off; t <= v1 && ticks.length < 60; t += step) ticks.push(t)

  // Merge marks in a lane that are closer than a comfortable click target.
  const GAP = 16
  const groups = lanes.map((l) => {
    const ev = events.filter((e) => e.lane === l.id && e.t >= v0 && e.t <= v1).sort((a, b) => a.t - b.t)
    const out: (typeof ev)[] = []
    for (const e of ev) {
      const g = out[out.length - 1]
      if (g && sx(e.t) - sx(g[g.length - 1].t) < GAP) g.push(e)
      else out.push([e])
    }
    return out
  })
  const visible = groups.reduce((a, g) => a + g.reduce((b, x) => b + x.length, 0), 0)
  const act = (fn: () => void) => ({
    onClick: fn,
    onKeyDown: (e: React.KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fn() } },
  })

  // ---- overview strip: whole period, current window, drag to pan or choose
  const OH = 34
  const ox = (t: number) => pl + ((t - from) / (to - from || 1)) * plotW
  const oT = (px: number) => from + ((px - pl) / plotW) * (to - from)
  const drag = useRef<{ mode: 'pan' | 'select'; anchor: number; offset: number; moved: boolean } | null>(null)
  const onOverviewDown = (e: React.PointerEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect()
    const t = oT(e.clientX - r.left)
    drag.current = { mode: t >= v0 && t <= v1 ? 'pan' : 'select', anchor: t, offset: t - v0, moved: false }
    e.currentTarget.setPointerCapture(e.pointerId)
  }
  const onOverviewMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const d = drag.current
    if (!d) return
    const r = e.currentTarget.getBoundingClientRect()
    const t = oT(e.clientX - r.left)
    if (Math.abs(ox(t) - ox(d.anchor)) > 3) d.moved = true
    if (!d.moved) return
    if (d.mode === 'pan') setView(clamp(t - d.offset, t - d.offset + span))
    else setView(clamp(Math.min(d.anchor, t), Math.max(d.anchor, t)))
  }
  const onOverviewUp = () => {
    const d = drag.current
    drag.current = null
    if (d && !d.moved && d.mode === 'select') setView(clamp(d.anchor - span / 2, d.anchor + span / 2))   // a click centres the window there
  }
  const zoomed = v0 > from || v1 < to

  return (
    <div className="tl" ref={box}>
      <div className="tl-bar">
        <span className="muted">Showing <b className="mono">{fmtWhen(v0)}</b> – <b className="mono">{fmtWhen(v1)}</b> · {visible} of {events.length} observations</span>
        <span className="spacer" />
        <div className="seg" role="group" aria-label="Timeline zoom">
          <button aria-label="Zoom out" disabled={!zoomed} onClick={() => zoomAt((v0 + v1) / 2, 2)}>−</button>
          <button aria-label="Zoom in" disabled={span <= MIN_SPAN} onClick={() => zoomAt((v0 + v1) / 2, 0.5)}>+</button>
          <button disabled={!zoomed} onClick={() => setView([from, to])}>Show all</button>
        </div>
      </div>
      {W > 0 && <>
        <div className="tl-plot" onMouseLeave={() => setHover(null)}>
          <svg ref={detail} width={W} height={H} role="group" aria-label="Observation timeline"
            onDoubleClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); const x = e.clientX - r.left; if (x > pl) zoomAt(tAt(x), 0.5) }}>
            {ticks.map((t) => (
              <g key={t}>
                <line x1={sx(t)} x2={sx(t)} y1={top} y2={H - 24} stroke="var(--line)" />
                <text x={sx(t)} y={H - 8} textAnchor="middle" className="tl-tick">{fmtTick(t, step)}</text>
              </g>
            ))}
            {lanes.map((l, i) => {
              const y = top + i * laneH + laneH / 2
              return (
                <g key={l.id}>
                  <line x1={pl} x2={W - pr} y1={y} y2={y} stroke="var(--line-2)" />
                  <text x={pl - 12} y={y + 4} textAnchor="end" className="tl-lane">{l.label}</text>
                  {groups[i].map((g) => {
                    const x0 = sx(g[0].t), x1 = sx(g[g.length - 1].t)
                    const tone = g[0].tone ?? 'var(--amber)'
                    if (g.length === 1) {
                      const e = g[0]
                      const label = `${l.label} · ${fmtWhen(e.t)}${e.id ? ` · ${e.id}` : ''}`
                      return (
                        <g key={`${e.t}-${e.id}`} className="tl-dot" role="button" tabIndex={0} aria-label={`${label}. Open the signal record.`}
                          onMouseEnter={() => setHover({ x: x0, y, text: label })} onFocus={() => setHover({ x: x0, y, text: label })} onBlur={() => setHover(null)}
                          {...act(() => { if (e.id) onPick?.(e.id) })}>
                          <circle cx={x0} cy={y} r={11} fill="transparent" />
                          <circle cx={x0} cy={y} r={5.5} fill={tone} stroke="var(--panel)" strokeWidth={1.5} />
                        </g>
                      )
                    }
                    const a = g[0].t, b = g[g.length - 1].t
                    const pad = Math.max((b - a) * 0.3, 20 * 60e3)
                    const label = `${g.length} observations, ${fmtWhen(a)} – ${fmtWhen(b)}`
                    const w = Math.max(24, x1 - x0 + 20)
                    const cx = (x0 + x1) / 2
                    return (
                      <g key={`${a}-${g.length}`} className="tl-cluster" role="button" tabIndex={0} aria-label={`${label}. Zoom in to choose one.`}
                        onMouseEnter={() => setHover({ x: cx, y, text: `${label} · select to zoom in` })} onFocus={() => setHover({ x: cx, y, text: label })} onBlur={() => setHover(null)}
                        {...act(() => { setHover(null); setView(clamp(a - pad, b + pad)) })}>
                        <rect x={cx - w / 2} y={y - 10} width={w} height={20} rx={10} fill={tone} fillOpacity={0.16} stroke={tone} />
                        <text x={cx} y={y + 4} textAnchor="middle" className="tl-count">{g.length}</text>
                      </g>
                    )
                  })}
                </g>
              )
            })}
          </svg>
          {hover && <div className="tl-tip" style={{ left: hover.x, top: hover.y - 14, transform: `translate(${hover.x > W - 200 ? '-100%' : '-50%'}, -100%)` }}>{hover.text}</div>}
        </div>
        <svg className="tl-overview" width={W} height={OH} onPointerDown={onOverviewDown} onPointerMove={onOverviewMove}
          onPointerUp={onOverviewUp} onPointerCancel={onOverviewUp} role="img" aria-label="Whole period. Drag the window to pan, or drag across to choose a range.">
          <rect x={pl} y={4} width={plotW} height={OH - 8} rx={4} fill="var(--panel-2)" stroke="var(--line)" />
          {events.map((e, i) => <line key={i} x1={ox(e.t)} x2={ox(e.t)} y1={10} y2={OH - 10} stroke={e.tone ?? 'var(--amber)'} strokeOpacity={0.7} />)}
          <rect className="tl-window" x={ox(v0)} y={3} width={Math.max(6, ox(v1) - ox(v0))} height={OH - 6} rx={4} />
          <text x={pl - 12} y={OH / 2 + 4} textAnchor="end" className="tl-lane">Whole period</text>
        </svg>
      </>}
    </div>
  )
}
