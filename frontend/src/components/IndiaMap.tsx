import { geoMercator, geoPath } from 'd3-geo'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { feature } from 'topojson-client'
import type { Feature, FeatureCollection, Geometry } from 'geojson'
import type { GeometryCollection, Topology } from 'topojson-specification'
import statesTopo from '../assets/india-states.topo.json'
import outlineTopo from '../assets/india-outline.topo.json'
import type { Station, Zone } from '../lib/types'

type ZoneProps = { ST_NM: string; zone: Zone }

function toFeatures<P extends Record<string, unknown>>(topo: unknown) {
  const t = topo as Topology
  const key = Object.keys(t.objects)[0]
  return feature(t, t.objects[key] as GeometryCollection) as unknown as FeatureCollection<Geometry, P>
}

export interface MapStation extends Station { activity: number; unknown: number; alert: boolean }

const W = 520, H = 580
const K_MIN = 1, K_MAX = 8
type View = { k: number; x: number; y: number }
const HOME: View = { k: 1, x: 0, y: 0 }

/** Keep the map covering the frame: never pan past its edges. */
function clampView(v: View): View {
  const k = Math.min(K_MAX, Math.max(K_MIN, v.k))
  return { k, x: Math.min(0, Math.max(W - W * k, v.x)), y: Math.min(0, Math.max(H - H * k, v.y)) }
}

/** Station category, carried by shape as well as colour: circle = activity, diamond = unresolved
 *  signals, ringed circle = open incident. */
type Kind = 'activity' | 'unresolved' | 'incident'
const KIND_TONE: Record<Kind, string> = { activity: 'var(--cyan)', unresolved: 'var(--amber)', incident: 'var(--orange)' }
const kindOf = (s: MapStation): Kind => (s.alert ? 'incident' : s.unknown > 3 ? 'unresolved' : 'activity')

function Mark({ kind, x = 0, y = 0, r = 5, stroke = 'var(--panel)', strokeWidth = 1.4 }: { kind: Kind; x?: number; y?: number; r?: number; stroke?: string; strokeWidth?: number }) {
  const tone = KIND_TONE[kind]
  if (kind === 'unresolved') {
    const d = r * 1.25
    return <path d={`M${x},${y - d}L${x + d},${y}L${x},${y + d}L${x - d},${y}Z`} fill={tone} stroke={stroke} strokeWidth={strokeWidth} vectorEffect="non-scaling-stroke" />
  }
  return (
    <>
      {kind === 'incident' && <circle cx={x} cy={y} r={r * 1.75} fill="none" stroke={tone} strokeWidth={1.3} vectorEffect="non-scaling-stroke" />}
      <circle cx={x} cy={y} r={r} fill={tone} stroke={stroke} strokeWidth={strokeWidth} vectorEffect="non-scaling-stroke" />
    </>
  )
}

function LegendMark({ kind }: { kind: Kind }) {
  return <svg className="map-mark" viewBox="-9 -9 18 18" width={14} height={14} aria-hidden="true"><Mark kind={kind} r={4} /></svg>
}

/** Small in the corner by default; opens on hover or keyboard focus, and on tap for touch screens. */
function Legend() {
  const [open, setOpen] = useState(false)
  return (
    <div className={`map-legend${open ? ' open' : ''}`} onMouseLeave={() => setOpen(false)}>
      <button className="map-legend-toggle" aria-expanded={open} aria-controls="map-legend-body" onClick={() => setOpen(!open)}>
        <span className="swatches" aria-hidden="true">{(['activity', 'unresolved', 'incident'] as Kind[]).map((k) => <i key={k} style={{ background: KIND_TONE[k] }} />)}</span>
        Legend
      </button>
      <div className="map-legend-body" id="map-legend-body">
        <div>
          <ul>
            <li><LegendMark kind="activity" /> Station · size = signals observed</li>
            <li><LegendMark kind="unresolved" /> More than 3 unresolved signals</li>
            <li><LegendMark kind="incident" /> Open incident</li>
          </ul>
          <small>Drag to pan. Ctrl + scroll, pinch, double-click or the + / − buttons to zoom. Boundaries: DataMeet, Survey of India depiction (CC BY 4.0).</small>
        </div>
      </div>
    </div>
  )
}

export default function IndiaMap({ stations, zone, onZone, onStation, links = [], height = 420, selectedStation }: {
  stations: MapStation[]; zone: Zone | null; onZone?: (z: Zone | null) => void; onStation?: (id: string) => void
  links?: [string, string][]; height?: number; selectedStation?: string | null
}) {
  const states = useMemo(() => toFeatures<ZoneProps>(statesTopo), [])
  const outline = useMemo(() => toFeatures<Record<string, unknown>>(outlineTopo), [])
  const projection = useMemo(() => geoMercator().fitExtent([[12, 12], [W - 12, H - 12]], outline), [outline])
  const path = useMemo(() => geoPath(projection), [projection])
  const [tip, setTip] = useState<{ x: number; y: number; text: string; flip: boolean } | null>(null)
  const [view, setView] = useState<View>(HOME)
  const [hint, setHint] = useState(false)
  const [grabbing, setGrabbing] = useState(false)
  const svgRef = useRef<SVGSVGElement>(null)
  const wrapRef = useRef<HTMLDivElement>(null)
  const pointers = useRef(new Map<number, { x: number; y: number }>())
  const gesture = useRef<{ moved: number; pinch?: number }>({ moved: 0 })
  const suppressClick = useRef(false)
  const pos = (s: Station) => projection([s.lon, s.lat]) ?? [0, 0]

  /** Client pixels to map units, through the SVG's own letterboxed viewBox transform. */
  const toMap = useCallback((cx: number, cy: number) => {
    const m = svgRef.current?.getScreenCTM()
    if (!m) return { x: W / 2, y: H / 2 }
    const p = new DOMPoint(cx, cy).matrixTransform(m.inverse())
    return { x: p.x, y: p.y }
  }, [])
  const unitsPerPx = () => {
    const m = svgRef.current?.getScreenCTM()
    return m ? 1 / m.a : 1
  }
  const zoomAt = useCallback((px: number, py: number, factor: number) => {
    setView((v) => {
      const k = Math.min(K_MAX, Math.max(K_MIN, v.k * factor))
      return clampView({ k, x: px - (px - v.x) * (k / v.k), y: py - (py - v.y) * (k / v.k) })
    })
  }, [])

  // Ctrl/Cmd + wheel (and trackpad pinch, which arrives as ctrl+wheel) zooms; a plain wheel keeps
  // scrolling the page, so the map never traps someone reading down it.
  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return
    let t = 0
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) {
        setHint(true); clearTimeout(t); t = window.setTimeout(() => setHint(false), 1400)
        return
      }
      e.preventDefault()
      const p = toMap(e.clientX, e.clientY)
      zoomAt(p.x, p.y, Math.exp(-e.deltaY * 0.0022))
    }
    svg.addEventListener('wheel', onWheel, { passive: false })
    return () => { svg.removeEventListener('wheel', onWheel); clearTimeout(t) }
  }, [toMap, zoomAt])

  const onPointerDown = (e: React.PointerEvent) => {
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    gesture.current = { moved: 0 }
    if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()]
      gesture.current.pinch = Math.hypot(a.x - b.x, a.y - b.y)
    }
  }
  const onPointerMove = (e: React.PointerEvent) => {
    const prev = pointers.current.get(e.pointerId)
    if (!prev) return
    const cur = { x: e.clientX, y: e.clientY }
    pointers.current.set(e.pointerId, cur)
    if (pointers.current.size === 2 && gesture.current.pinch) {
      const [a, b] = [...pointers.current.values()]
      const d = Math.hypot(a.x - b.x, a.y - b.y)
      const mid = toMap((a.x + b.x) / 2, (a.y + b.y) / 2)
      zoomAt(mid.x, mid.y, d / gesture.current.pinch)
      gesture.current.pinch = d
      gesture.current.moved += 10
      return
    }
    const dx = cur.x - prev.x, dy = cur.y - prev.y
    gesture.current.moved += Math.abs(dx) + Math.abs(dy)
    if (gesture.current.moved > 4) {
      if (!grabbing) { setGrabbing(true); setTip(null); (e.currentTarget as Element).setPointerCapture?.(e.pointerId) }
      const u = unitsPerPx()
      setView((v) => clampView({ ...v, x: v.x + dx * u, y: v.y + dy * u }))
    }
  }
  const onPointerUp = (e: React.PointerEvent) => {
    pointers.current.delete(e.pointerId)
    if (gesture.current.moved > 4) suppressClick.current = true
    if (pointers.current.size < 2) gesture.current.pinch = undefined
    setGrabbing(false)
  }
  /** A drag or pinch that ends over a state or station must not also select it. */
  const click = (fn: () => void) => () => {
    if (suppressClick.current) { suppressClick.current = false; return }
    fn()
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.target !== e.currentTarget) return
    const pan = (dx: number, dy: number) => setView((v) => clampView({ ...v, x: v.x + dx, y: v.y + dy }))
    switch (e.key) {
      case '+': case '=': zoomAt(W / 2, H / 2, 1.5); break
      case '-': case '_': zoomAt(W / 2, H / 2, 1 / 1.5); break
      case '0': setView(HOME); break
      case 'ArrowLeft': pan(40, 0); break
      case 'ArrowRight': pan(-40, 0); break
      case 'ArrowUp': pan(0, 40); break
      case 'ArrowDown': pan(0, -40); break
      default: return
    }
    e.preventDefault()
  }

  const tipAt = (e: React.MouseEvent, text: string) => {
    if (grabbing) return
    const r = wrapRef.current?.getBoundingClientRect()
    if (!r) return
    // Flip to the left of the cursor near the right edge so the tip never runs out of the frame.
    const x = e.clientX - r.left, y = e.clientY - r.top
    const flip = x > r.width - 240
    setTip({ x: flip ? x - 12 : x + 12, y: y + 10, text, flip })
  }

  // Markers keep roughly their screen size while zooming; geography scales, symbols do not.
  const ms = 1 / Math.pow(view.k, 0.8)

  return (
    <div ref={wrapRef} className={`map-wrap${grabbing ? ' grabbing' : ''}`} style={{ height }} onMouseLeave={() => setTip(null)}
      tabIndex={0} onKeyDown={onKeyDown} aria-label="India monitoring map. Arrow keys pan, plus and minus zoom, 0 resets.">
      <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} role="img" aria-label="India monitoring map"
        onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerCancel={onPointerUp}
        onDoubleClick={(e) => { const p = toMap(e.clientX, e.clientY); zoomAt(p.x, p.y, 2) }}>
        <defs>
          <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="var(--map-grid)" strokeWidth="1" /></pattern>
        </defs>
        <rect width={W} height={H} fill="url(#grid)" />
        <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
          {states.features.map((f: Feature<Geometry, ZoneProps>, i) => {
            const z = f.properties.zone
            const cls = zone ? (z === zone ? 'zone-path on' : 'zone-path dim') : 'zone-path'
            return (
              <path key={i} d={path(f) ?? ''} className={cls} vectorEffect="non-scaling-stroke"
                onClick={click(() => onZone?.(zone === z ? null : z))}
                onMouseMove={(e) => tipAt(e, `${f.properties.ST_NM} · ${z} zone`)} />
            )
          })}
          {outline.features.map((f, i) => <path key={`o${i}`} d={path(f) ?? ''} fill="none" stroke="var(--map-stroke-on)" strokeWidth="1.1" vectorEffect="non-scaling-stroke" pointerEvents="none" />)}
          {links.map(([a, b], i) => {
            const sa = stations.find((s) => s.id === a), sb = stations.find((s) => s.id === b)
            if (!sa || !sb) return null
            const [x1, y1] = pos(sa), [x2, y2] = pos(sb)
            const mx = (x1 + x2) / 2, my = (y1 + y2) / 2 - Math.hypot(x2 - x1, y2 - y1) * 0.25
            return <path key={`l${i}`} d={`M${x1},${y1}Q${mx},${my} ${x2},${y2}`} fill="none" stroke="var(--amber)" strokeWidth="1.2" strokeDasharray="4 4" opacity="0.75" vectorEffect="non-scaling-stroke" pointerEvents="none" />
          })}
          {stations.map((s) => {
            const [x, y] = pos(s)
            const dimmed = zone && s.zone !== zone
            const r = (3.5 + Math.sqrt(s.activity) * 0.9) * ms
            const on = selectedStation === s.id
            return (
              <g key={s.id} className="station-dot" opacity={dimmed ? 0.3 : 1} onClick={click(() => onStation?.(s.id))}
                onMouseMove={(e) => tipAt(e, `${s.id} ${s.name} · ${s.activity} signals · ${s.unknown} unresolved${s.alert ? ' · open incident' : ''}`)}>
                <circle cx={x} cy={y} r={Math.max(r * 2.2, 9 * ms)} fill="transparent" />
                <Mark kind={kindOf(s)} x={x} y={y} r={r} stroke={on ? 'var(--text)' : 'var(--panel)'} strokeWidth={on ? 2 : 1.4} />
              </g>
            )
          })}
        </g>
      </svg>
      {tip && <div className="map-tip" style={{ left: tip.x, top: tip.y, transform: tip.flip ? 'translateX(-100%)' : undefined }}>{tip.text}</div>}
      {hint && <div className="map-hint" role="status">Ctrl + scroll to zoom</div>}
      <div className="map-controls" role="group" aria-label="Map zoom">
        <button aria-label="Zoom in" disabled={view.k >= K_MAX} onClick={() => zoomAt(W / 2, H / 2, 1.5)}>+</button>
        <button aria-label="Zoom out" disabled={view.k <= K_MIN} onClick={() => zoomAt(W / 2, H / 2, 1 / 1.5)}>−</button>
        <button aria-label="Reset view" disabled={view.k === 1} onClick={() => setView(HOME)}>
          <svg viewBox="0 0 24 24" width={15} height={15} aria-hidden="true"><path d="M4 4v6h6M20 20v-6h-6M5.5 15a7.5 7.5 0 0 0 13 2M18.5 9a7.5 7.5 0 0 0-13-2" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </button>
      </div>
      <Legend />
    </div>
  )
}
