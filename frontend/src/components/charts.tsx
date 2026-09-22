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
                {s.fill && <path d={`${d}L${sx(s.x[s.x.length - 1])},${H - pb}L${sx(s.x[0])},${H - pb}Z`} fill={s.color} opacity={0.1} />}
                <path d={d} fill="none" stroke={s.color} strokeWidth={s.width ?? 1.5} strokeLinejoin="round" />
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
        const el = <circle key={p.label} cx="60" cy="60" r={r} fill="none" stroke={p.color} strokeWidth="14" strokeDasharray={`${len} ${c - len}`} strokeDashoffset={-acc} transform="rotate(-90 60 60)" />
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

export function TimelineStrip({ lanes, events, from, to, height = 150, onPick }: {
  lanes: { id: string; label: string }[]; events: { t: number; lane: string; id?: string; tone?: string }[]
  from: number; to: number; height?: number; onPick?: (id: string) => void
}) {
  const W = 800, lh = Math.max(18, (height - 24) / Math.max(1, lanes.length)), pl = 120
  const H = lanes.length * lh + 24
  const sx = (t: number) => pl + ((t - from) / (to - from || 1)) * (W - pl - 10)
  const days: number[] = []
  const d0 = new Date(from); d0.setHours(0, 0, 0, 0)
  for (let d = d0.getTime() + 86400000; d < to; d += 86400000) days.push(d)
  // Every day gets a gridline, but a label only where one fits. Over a few weeks the daily labels
  // would otherwise overprint each other into an unreadable smear.
  const LABEL_W = 58
  const perDay = (W - pl - 10) / Math.max(1, days.length)
  const step = Math.max(1, Math.ceil(LABEL_W / Math.max(perDay, 1)))
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: H }}>
      {days.map((d, i) => (
        <g key={d}>
          <line x1={sx(d)} x2={sx(d)} y1={0} y2={H - 18} stroke="var(--line)" />
          {/* Skipped rather than right-anchored near the edge: anchoring it pulls the label back
              on top of the previous one. */}
          {i % step === 0 && sx(d) + LABEL_W <= W && (
            <text x={sx(d) + 3} y={H - 5} className="axis">
              {new Date(d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })}
            </text>
          )}
        </g>
      ))}
      {lanes.map((l, i) => (
        <g key={l.id}>
          <line x1={pl} x2={W - 10} y1={i * lh + lh / 2} y2={i * lh + lh / 2} stroke="var(--line)" />
          <text x={pl - 8} y={i * lh + lh / 2 + 3} textAnchor="end" className="axis">{l.label}</text>
        </g>
      ))}
      {events.map((e, k) => {
        const i = lanes.findIndex((l) => l.id === e.lane)
        if (i < 0) return null
        return (
          <circle key={k} cx={sx(e.t)} cy={i * lh + lh / 2} r={4} fill={e.tone ?? 'var(--amber)'} stroke="var(--panel)" strokeWidth="1.5"
            style={{ cursor: onPick && e.id ? 'pointer' : 'default', animation: `fadein 0.4s ${k * 0.012}s both` }}
            onClick={() => e.id && onPick?.(e.id)}>
            <title>{new Date(e.t).toLocaleString('en-GB', { timeZone: 'Asia/Kolkata' })}</title>
          </circle>
        )
      })}
      <style>{'@keyframes fadein { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: none; } }'}</style>
    </svg>
  )
}
