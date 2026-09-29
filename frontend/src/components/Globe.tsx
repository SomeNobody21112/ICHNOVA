import { geoCircle, geoDistance, geoGraticule10, geoOrthographic, geoPath } from 'd3-geo'
import type { Feature, FeatureCollection, Geometry } from 'geojson'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { feature } from 'topojson-client'
import type { GeometryCollection, Topology } from 'topojson-specification'
import {
  antipode, clampTilt, clampZoom, neName, placeLabels, shortestTurn, SPIN_EPSILON, SPIN_FRICTION,
  subsolar, ZOOM_MAX, ZOOM_MIN,
} from '../lib/observatory'

/** A satellite view of Earth: orthographic, so you are looking down at the globe from orbit.
 *
 *  It exists because the receiver step has to answer a physical question — *which transmitters can
 *  this place actually hear, and where are they?* — so the geometry is real: great-circle paths (d3
 *  draws a LineString as a geodesic under this projection), a horizon that hides the far side of the
 *  planet exactly as the Earth does, and a day/night terminator computed from the viewer's own clock.
 *
 *  It is also meant to be handled: drag to spin with inertia, wheel to zoom, double-click to
 *  re-centre, arrow keys and +/− for the keyboard. Land comes from /geo/countries-110m.json (Natural
 *  Earth via world-atlas, public domain, served by our own host so this works air-gapped). Every
 *  animation is dropped under prefers-reduced-motion.
 */

export interface GlobePoint {
  key: string
  name: string
  lat: number
  lon: number
  /** country as the station registry spells it, used to highlight the landmass */
  country: string
}

type Rot = [number, number]
const easeInOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2)
const HOME: Rot = [-20, -12]

/** A fixed, seeded star field: seeded so the sky never re-scrambles between renders. It frames the
 *  orbital view and is not pretending to be sky data. */
function stars(n: number, w: number, h: number) {
  let s = 20260927
  const rnd = () => ((s = (s * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff)
  return Array.from({ length: n }, () => ({
    x: rnd() * w, y: rnd() * h, r: 0.3 + rnd() * 0.8, o: 0.15 + rnd() * 0.45,
  }))
}

export function Globe({ points, anchor, selected, onPick, height = 520, spin = true }: {
  points: GlobePoint[]
  /** the place we are listening from; the globe centres on it and arcs radiate from it */
  anchor?: GlobePoint | null
  selected?: string | null
  onPick?: (p: GlobePoint) => void
  height?: number
  spin?: boolean
}) {
  const [topo, setTopo] = useState<Topology | null>(null)
  const [rot, setRot] = useState<Rot>(HOME)
  const [zoom, setZoom] = useState(1)
  const [w, setW] = useState(760)
  const [hover, setHover] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const [nightAt, setNightAt] = useState(() => new Date())

  const box = useRef<HTMLDivElement>(null)
  const svg = useRef<SVGSVGElement>(null)
  // a ref written in an effect, never during render: the fly-to needs the latest rotation as its
  // starting point without making `rot` a dependency of its own animation
  const rotRef = useRef<Rot>(HOME)
  const reduce = useRef(false)
  const drag = useRef<{ x: number; y: number; moved: number; vx: number; vy: number; t: number } | null>(null)

  useEffect(() => { rotRef.current = rot }, [rot])
  useEffect(() => {
    reduce.current = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  }, [])
  useEffect(() => {
    fetch('/geo/countries-110m.json').then((r) => r.json()).then(setTopo).catch(() => setTopo(null))
  }, [])
  // size to the container so the globe is as big as the panel allows, on any screen
  useEffect(() => {
    const el = box.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setW(Math.max(280, e.contentRect.width)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  // the terminator is real, so it has to keep up with the clock; once a minute is finer than a
  // 1-pixel edge can show
  useEffect(() => {
    const id = setInterval(() => setNightAt(new Date()), 60000)
    return () => clearInterval(id)
  }, [])
  // React registers `wheel` as a passive listener, which makes preventDefault a no-op there, so
  // zooming would scroll the page as well. This one has to be attached natively.
  useEffect(() => {
    const el = svg.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      setZoom((z) => clampZoom(z * (e.deltaY > 0 ? 0.9 : 1.1)))
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [])

  const anchorKey = anchor?.key ?? null
  const anchorLon = anchor?.lon ?? 0
  const anchorLat = anchor?.lat ?? 0

  /** Fly to a rotation: one rAF loop, eased, shortest way round the sphere. */
  const flyTo = useCallback((target: Rot) => {
    if (reduce.current) { setRot([target[0], clampTilt(target[1])]); return }
    const from = rotRef.current
    const dx = shortestTurn(from[0], target[0])
    const dy = clampTilt(target[1]) - from[1]
    let id = 0
    let t0 = 0
    const step = (t: number) => {
      if (!t0) t0 = t
      const k = Math.min(1, (t - t0) / 1150)
      const e = easeInOut(k)
      setRot([from[0] + dx * e, from[1] + dy * e])
      if (k < 1) id = requestAnimationFrame(step)
    }
    id = requestAnimationFrame(step)
    return () => cancelAnimationFrame(id)
  }, [])

  useEffect(() => {
    if (!anchorKey) return
    return flyTo([-anchorLon, -anchorLat])
  }, [anchorKey, anchorLon, anchorLat, flyTo])

  /** Idle drift while no location is chosen — slow enough to read, stopped once one is, and never
   *  fighting the user's hand. */
  useEffect(() => {
    if (anchorKey || !spin || reduce.current || dragging) return
    let id = 0
    const step = () => { setRot((r) => [r[0] + 0.045, r[1]]); id = requestAnimationFrame(step) }
    id = requestAnimationFrame(step)
    return () => cancelAnimationFrame(id)
  }, [anchorKey, spin, dragging])

  /* --------------------------------------------------------------------------- interaction */

  const zoomBy = (k: number) => setZoom((z) => clampZoom(z * k))
  const recentre = () => { setZoom(1); flyTo(anchor ? [-anchor.lon, -anchor.lat] : HOME) }

  const onPointerDown = (e: React.PointerEvent<SVGSVGElement>) => {
    // No pointer capture yet: capturing here retargets the click to the <svg>, so a marker or its
    // name would never receive it. Capture starts in onPointerMove once this is really a drag.
    drag.current = { x: e.clientX, y: e.clientY, moved: 0, vx: 0, vy: 0, t: performance.now() }
    setDragging(true)
  }
  const onPointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const d = drag.current
    if (!d) return
    const dx = e.clientX - d.x
    const dy = e.clientY - d.y
    // degrees per pixel shrinks as you zoom in, so the drag keeps feeling 1:1 with the surface
    const k = 0.32 / zoom
    const now = performance.now()
    // velocity in degrees per frame, from the real frame interval
    const dt = Math.max(1, now - d.t)
    d.vx = (dx * k * 16) / dt
    d.vy = (dy * k * 16) / dt
    d.moved += Math.abs(dx) + Math.abs(dy)
    if (d.moved > 6 && !e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.setPointerCapture(e.pointerId)
    d.x = e.clientX
    d.y = e.clientY
    d.t = now
    setRot(([lon, lat]) => [lon + dx * k, clampTilt(lat - dy * k)])
  }
  const endDrag = () => {
    const d = drag.current
    drag.current = null
    setDragging(false)
    if (!d || reduce.current) return
    let vx = d.vx
    let vy = d.vy
    if (Math.abs(vx) < SPIN_EPSILON && Math.abs(vy) < SPIN_EPSILON) return
    // inertia: multiplicative decay, so it always settles rather than ticking forever
    const step = () => {
      vx *= SPIN_FRICTION
      vy *= SPIN_FRICTION
      setRot(([lon, lat]) => [lon + vx, clampTilt(lat - vy)])
      if (Math.abs(vx) > SPIN_EPSILON || Math.abs(vy) > SPIN_EPSILON) requestAnimationFrame(step)
    }
    requestAnimationFrame(step)
  }
  const onKeyDown = (e: React.KeyboardEvent<SVGSVGElement>) => {
    const d = 6 / zoom
    const keys: Record<string, () => void> = {
      ArrowLeft: () => setRot(([a, b]) => [a - d, b]),
      ArrowRight: () => setRot(([a, b]) => [a + d, b]),
      ArrowUp: () => setRot(([a, b]) => [a, clampTilt(b + d)]),
      ArrowDown: () => setRot(([a, b]) => [a, clampTilt(b - d)]),
      '+': () => zoomBy(1.15),
      '=': () => zoomBy(1.15),
      '-': () => zoomBy(1 / 1.15),
      '0': recentre,
    }
    const fn = keys[e.key]
    if (fn) { e.preventDefault(); fn() }
  }

  /* --------------------------------------------------------------------------- projection */

  const H = height
  const R = (Math.min(w, H) / 2 - 18) * zoom
  const cx = w / 2
  const cy = H / 2

  const projection = useMemo(
    () => geoOrthographic().translate([cx, cy]).scale(R).rotate([rot[0], rot[1], 0]),
    [cx, cy, R, rot])
  const path = useMemo(() => geoPath(projection), [projection])

  const { land, borders } = useMemo(() => {
    if (!topo) return { land: null, borders: null }
    const countries = feature(topo, topo.objects.countries as GeometryCollection) as unknown as FeatureCollection<Geometry, { name: string }>
    const landF = feature(topo, topo.objects.land as GeometryCollection) as unknown as FeatureCollection<Geometry, Record<string, never>>
    return { land: landF, borders: countries }
  }, [topo])

  /** The night side: a 90° cap around the anti-solar point, from the viewer's own clock. */
  const night = useMemo(() => {
    const anti = antipode(subsolar(nightAt))
    return geoCircle().center([anti.lon, anti.lat]).radius(90)()
  }, [nightAt])

  const sky = useMemo(() => stars(90, w, H), [w, H])
  const hi = anchor ? neName(anchor.country) : null

  const marks = useMemo(() => {
    const centre: [number, number] = [-rot[0], -rot[1]]
    return placeLabels(points.map((p) => {
      const xy = projection([p.lon, p.lat])
      return {
        p,
        x: xy?.[0] ?? -999,
        y: xy?.[1] ?? -999,
        // orthographic projects the far side too; the horizon test is what hides it
        visible: Boolean(xy) && geoDistance([p.lon, p.lat], centre) < Math.PI / 2 - 0.02,
      }
    }), cx, 15, 12, H - 12)
  }, [points, projection, cx, rot, H])

  // a drag that happens to end over a marker must not also select it
  const pick = (p: GlobePoint) => { if ((drag.current?.moved ?? 0) <= 6) onPick?.(p) }

  return (
    <div ref={box} className="globe-box" style={{ height: H }}>
      <svg ref={svg} viewBox={`0 0 ${w} ${H}`} width="100%" height={H} tabIndex={0} role="application"
        className={`globe${dragging ? ' dragging' : ''}`}
        aria-label={anchor
          ? `Satellite view centred on ${anchor.name}, showing ${points.length} transmitters. Drag to rotate, wheel to zoom, arrow keys to turn.`
          : `Satellite view of Earth showing ${points.length} transmitters. Drag to rotate, wheel to zoom, arrow keys to turn.`}
        onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={endDrag}
        onPointerCancel={endDrag} onKeyDown={onKeyDown} onDoubleClick={recentre}>
        <defs>
          <radialGradient id="g-limb" cx="50%" cy="50%" r="50%">
            <stop offset="72%" stopColor="var(--cyan)" stopOpacity="0" />
            <stop offset="100%" stopColor="var(--cyan)" stopOpacity="0.45" />
          </radialGradient>
          {/* the ocean is lit from upper-left; both stops are theme tokens, because the shared
              surface tokens are near-white in light mode and left the globe unreadable */}
          <radialGradient id="g-ocean" cx="38%" cy="30%" r="80%">
            <stop offset="0%" stopColor="var(--globe-ocean-a)" />
            <stop offset="100%" stopColor="var(--globe-ocean-b)" />
          </radialGradient>
          {/* the globe is a disc, so everything on the surface is clipped to it */}
          <clipPath id="g-clip"><circle cx={cx} cy={cy} r={R} /></clipPath>
        </defs>

        {sky.map((s, i) => (
          <circle key={i} cx={s.x} cy={s.y} r={s.r} className="globe-star" opacity={s.o} />
        ))}

        <circle cx={cx} cy={cy} r={R} fill="url(#g-ocean)" />
        <g clipPath="url(#g-clip)">
          <path d={path(geoGraticule10()) ?? ''} className="globe-grat" />
          {land && <path d={path(land) ?? ''} className="globe-land" />}
          {borders && <path d={path(borders) ?? ''} className="globe-border" />}
          {/* the country we are listening from, lit */}
          {borders && hi && borders.features.filter((f) => f.properties?.name === hi).map((f, i) => (
            <path key={i} d={path(f as Feature<Geometry>) ?? ''} className="globe-hi" />
          ))}
          {/* the real night side, for the viewer's clock */}
          <path d={path(night) ?? ''} className="globe-night" />
        </g>
        {/* atmosphere, then a hard limb so the horizon reads as a horizon */}
        <circle cx={cx} cy={cy} r={R} fill="url(#g-limb)" pointerEvents="none" />
        <circle cx={cx} cy={cy} r={R} className="globe-limb" />

        {/* great-circle paths, drawn transmitter → receiver so the pulse travels inbound */}
        {anchor && points.filter((p) => p.key !== anchor.key).map((p) => {
          const d = path({ type: 'LineString', coordinates: [[p.lon, p.lat], [anchor.lon, anchor.lat]] })
          if (!d) return null
          const on = selected === p.key || hover === p.key
          return (
            <g key={`arc-${p.key}`} className={`globe-arcg${on ? ' on' : ''}`}>
              <path d={d} className="globe-arc" />
              {/* a short dash whose offset animates: a pulse running the path, no SMIL */}
              <path d={d} className="globe-pulse" />
            </g>
          )
        })}

        {/* markers, then labels pushed apart so they never collide */}
        {marks.filter((m) => m.visible).map(({ p, x, y, ly, side }) => {
          const isAnchor = anchor?.key === p.key
          const lx = x + side * 13
          const on = selected === p.key || hover === p.key
          return (
            <g key={p.key}
              className={`globe-mark${on ? ' on' : ''}${isAnchor ? ' here' : ''}`}
              tabIndex={onPick ? 0 : -1} role={onPick ? 'button' : undefined}
              aria-label={`${p.name}, ${p.country}`}
              onPointerEnter={() => setHover(p.key)} onPointerLeave={() => setHover(null)}
              onFocus={() => setHover(p.key)} onBlur={() => setHover(null)}
              onClick={() => pick(p)}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onPick?.(p) } }}>
              {isAnchor && <circle cx={x} cy={y} r={6} className="globe-ripple" />}
              {on && <circle cx={x} cy={y} r={10} className="globe-halo" />}
              <polyline points={`${x},${y} ${lx - side * 4},${ly}`} className="globe-leader" />
              <circle cx={x} cy={y} r={isAnchor ? 5 : 3.6} className="globe-dot" />
              {/* a 3.6 px dot is too small to hit; this invisible disc is the real target */}
              <circle cx={x} cy={y} r={11} fill="transparent" />
              <text x={lx} y={ly} className="globe-name" textAnchor={side === 1 ? 'start' : 'end'}
                dominantBaseline="middle">{p.name}</text>
            </g>
          )
        })}
      </svg>

      <div className="globe-hud mono">
        <span className="globe-hud-read">
          {anchor ? `${anchor.lat.toFixed(2)}°, ${anchor.lon.toFixed(2)}°` : 'drag to rotate'}
        </span>
        <button className="globe-zb" onClick={() => zoomBy(1 / 1.2)}
          disabled={zoom <= ZOOM_MIN} aria-label="Zoom out">−</button>
        <span className="globe-zv">{zoom.toFixed(1)}×</span>
        <button className="globe-zb" onClick={() => zoomBy(1.2)}
          disabled={zoom >= ZOOM_MAX} aria-label="Zoom in">+</button>
        <button className="globe-zb wide" onClick={recentre} aria-label="Re-centre the view">
          recentre
        </button>
      </div>
      {!topo && <div className="globe-wait mono">loading geography…</div>}
    </div>
  )
}
