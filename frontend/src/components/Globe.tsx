import { geoDistance, geoGraticule10, geoOrthographic, geoPath } from 'd3-geo'
import type { Feature, FeatureCollection, Geometry } from 'geojson'
import { useEffect, useMemo, useRef, useState } from 'react'
import { feature } from 'topojson-client'
import type { GeometryCollection, Topology } from 'topojson-specification'
import { neName, placeLabels, shortestTurn } from '../lib/observatory'

/** A satellite view of Earth: orthographic, so you are looking down at the globe from orbit.
 *
 *  It exists because the receiver step has to answer a physical question — *which transmitters can
 *  this place actually hear, and where are they?* — so the geometry is real: great-circle paths (d3
 *  draws a LineString as a geodesic under this projection), and a horizon that hides the far side of
 *  the planet exactly as the Earth does.
 *
 *  Land comes from /geo/countries-110m.json (Natural Earth via world-atlas, public domain, served by
 *  our own host so this works air-gapped). Motion is one rAF loop easing the rotation to the selected
 *  place; under prefers-reduced-motion it jumps instead of flying.
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
  const [rot, setRot] = useState<Rot>([-20, -12])
  const [w, setW] = useState(760)
  const box = useRef<HTMLDivElement>(null)
  const rotRef = useRef<Rot>([-20, -12])
  const reduce = useRef(false)

  // a ref written in an effect, never during render: the fly-to needs the latest rotation as its
  // starting point without making `rot` a dependency of its own animation
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

  const anchorKey = anchor?.key ?? null
  const anchorLon = anchor?.lon ?? 0
  const anchorLat = anchor?.lat ?? 0

  /** Fly to the anchor: one rAF loop, eased, shortest way round. */
  useEffect(() => {
    if (!anchorKey) return
    const target: Rot = [-anchorLon, -anchorLat]
    if (reduce.current) { setRot(target); return }
    const from = rotRef.current
    const dx = shortestTurn(from[0], target[0])
    const dy = target[1] - from[1]
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
  }, [anchorKey, anchorLon, anchorLat])

  /** Idle drift while no location is chosen — slow enough to read, stopped once one is. */
  useEffect(() => {
    if (anchorKey || !spin || reduce.current) return
    let id = 0
    const step = () => { setRot((r) => [r[0] + 0.045, r[1]]); id = requestAnimationFrame(step) }
    id = requestAnimationFrame(step)
    return () => cancelAnimationFrame(id)
  }, [anchorKey, spin])

  const H = height
  const R = Math.min(w, H) / 2 - 18
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

  return (
    <div ref={box} className="globe-box" style={{ height: H }}>
      <svg viewBox={`0 0 ${w} ${H}`} width="100%" height={H} className="globe" role="img"
        aria-label={anchor
          ? `Satellite view centred on ${anchor.name}, showing ${points.length} transmitters`
          : `Satellite view of Earth showing ${points.length} transmitters`}>
        <defs>
          <radialGradient id="g-limb" cx="50%" cy="50%" r="50%">
            <stop offset="72%" stopColor="var(--cyan)" stopOpacity="0" />
            <stop offset="100%" stopColor="var(--cyan)" stopOpacity="0.45" />
          </radialGradient>
          <radialGradient id="g-ocean" cx="38%" cy="30%" r="80%">
            <stop offset="0%" stopColor="var(--panel-2)" />
            <stop offset="100%" stopColor="var(--bg-2)" />
          </radialGradient>
        </defs>

        <circle cx={cx} cy={cy} r={R} fill="url(#g-ocean)" />
        <path d={path(geoGraticule10()) ?? ''} className="globe-grat" />
        {land && <path d={path(land) ?? ''} className="globe-land" />}
        {borders && <path d={path(borders) ?? ''} className="globe-border" />}
        {/* the country we are listening from, lit */}
        {borders && hi && borders.features.filter((f) => f.properties?.name === hi).map((f, i) => (
          <path key={i} d={path(f as Feature<Geometry>) ?? ''} className="globe-hi" />
        ))}
        {/* atmosphere, then a hard limb so the horizon reads as a horizon */}
        <circle cx={cx} cy={cy} r={R} fill="url(#g-limb)" pointerEvents="none" />
        <circle cx={cx} cy={cy} r={R} className="globe-limb" />

        {/* great-circle paths from the listening place to everything it can hear */}
        {anchor && points.filter((p) => p.key !== anchor.key).map((p) => {
          const d = path({ type: 'LineString', coordinates: [[anchor.lon, anchor.lat], [p.lon, p.lat]] })
          return d ? <path key={`arc-${p.key}`} d={d}
            className={`globe-arc${selected === p.key ? ' on' : ''}`} /> : null
        })}

        {/* markers, then labels pushed apart so they never collide */}
        {marks.filter((m) => m.visible).map(({ p, x, y, ly, side }) => {
          const isAnchor = anchor?.key === p.key
          const lx = x + side * 13
          return (
            <g key={p.key}
              className={`globe-mark${selected === p.key ? ' on' : ''}${isAnchor ? ' here' : ''}`}
              tabIndex={onPick ? 0 : -1} role={onPick ? 'button' : undefined}
              aria-label={`${p.name}, ${p.country}`}
              onClick={() => onPick?.(p)}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onPick?.(p) } }}>
              {isAnchor && <circle cx={x} cy={y} r={6} className="globe-ripple" />}
              <polyline points={`${x},${y} ${lx - side * 4},${ly}`} className="globe-leader" />
              <circle cx={x} cy={y} r={isAnchor ? 5 : 3.6} className="globe-dot" />
              <text x={lx} y={ly} className="globe-name" textAnchor={side === 1 ? 'start' : 'end'}
                dominantBaseline="middle">{p.name}</text>
            </g>
          )
        })}
      </svg>
      {!topo && <div className="globe-wait mono">loading geography…</div>}
    </div>
  )
}
