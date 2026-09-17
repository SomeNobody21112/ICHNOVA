import { geoMercator, geoPath } from 'd3-geo'
import { useMemo, useState } from 'react'
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

export default function IndiaMap({ stations, zone, onZone, onStation, links = [], height = 420, selectedStation }: {
  stations: MapStation[]; zone: Zone | null; onZone?: (z: Zone | null) => void; onStation?: (id: string) => void
  links?: [string, string][]; height?: number; selectedStation?: string | null
}) {
  const states = useMemo(() => toFeatures<ZoneProps>(statesTopo), [])
  const outline = useMemo(() => toFeatures<Record<string, unknown>>(outlineTopo), [])
  const W = 520, H = 580
  const projection = useMemo(() => geoMercator().fitExtent([[12, 12], [W - 12, H - 12]], outline), [outline])
  const path = useMemo(() => geoPath(projection), [projection])
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null)
  const pos = (s: Station) => projection([s.lon, s.lat]) ?? [0, 0]

  return (
    <div className="map-wrap" style={{ height }} onMouseLeave={() => setTip(null)}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="India monitoring map">
        <defs>
          <radialGradient id="glow"><stop offset="0" stopColor="var(--cyan)" stopOpacity="0.35" /><stop offset="1" stopColor="var(--cyan)" stopOpacity="0" /></radialGradient>
          <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="var(--map-grid)" strokeWidth="1" /></pattern>
        </defs>
        <rect width={W} height={H} fill="url(#grid)" />
        {states.features.map((f: Feature<Geometry, ZoneProps>, i) => {
          const z = f.properties.zone
          const cls = zone ? (z === zone ? 'zone-path on' : 'zone-path dim') : 'zone-path'
          return (
            <path key={i} d={path(f) ?? ''} className={cls}
              onClick={() => onZone?.(zone === z ? null : z)}
              onMouseMove={(e) => {
                const r = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect()
                setTip({ x: e.clientX - r.left + 12, y: e.clientY - r.top + 8, text: `${f.properties.ST_NM} · ${z} zone` })
              }} />
          )
        })}
        {outline.features.map((f, i) => <path key={`o${i}`} d={path(f) ?? ''} fill="none" stroke="var(--map-stroke-on)" strokeWidth="1.1" pointerEvents="none" />)}
        {links.map(([a, b], i) => {
          const sa = stations.find((s) => s.id === a), sb = stations.find((s) => s.id === b)
          if (!sa || !sb) return null
          const [x1, y1] = pos(sa), [x2, y2] = pos(sb)
          const mx = (x1 + x2) / 2, my = (y1 + y2) / 2 - Math.hypot(x2 - x1, y2 - y1) * 0.25
          return (
            <path key={`l${i}`} d={`M${x1},${y1}Q${mx},${my} ${x2},${y2}`} fill="none" stroke="var(--amber)" strokeWidth="1.2" strokeDasharray="4 4" opacity="0.8">
              <animate attributeName="stroke-dashoffset" from="16" to="0" dur="1.2s" repeatCount="indefinite" />
            </path>
          )
        })}
        {stations.map((s) => {
          const [x, y] = pos(s)
          const dimmed = zone && s.zone !== zone
          const r = 3.5 + Math.sqrt(s.activity) * 0.9
          const tone = s.alert ? 'var(--orange)' : s.unknown > 3 ? 'var(--amber)' : 'var(--cyan)'
          return (
            <g key={s.id} className="station-dot" opacity={dimmed ? 0.25 : 1} onClick={() => onStation?.(s.id)}
              onMouseMove={(e) => {
                const rr = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect()
                setTip({ x: e.clientX - rr.left + 12, y: e.clientY - rr.top + 8, text: `${s.id} ${s.name} · ${s.activity} signals · ${s.unknown} unresolved` })
              }}>
              <circle cx={x} cy={y} r={r * 3} fill="url(#glow)" />
              <circle cx={x} cy={y} r={r} fill="none" stroke={tone} strokeWidth="1" opacity="0.7">
                <animate attributeName="r" from={r} to={r * 3.2} dur={s.alert ? '1.4s' : '2.6s'} repeatCount="indefinite" />
                <animate attributeName="opacity" from="0.7" to="0" dur={s.alert ? '1.4s' : '2.6s'} repeatCount="indefinite" />
              </circle>
              <circle cx={x} cy={y} r={r} fill={tone} stroke={selectedStation === s.id ? 'var(--text)' : 'var(--panel)'} strokeWidth={selectedStation === s.id ? 2 : 1.4} />
            </g>
          )
        })}
      </svg>
      {tip && <div className="map-tip" style={{ left: tip.x, top: tip.y }}>{tip.text}</div>}
      <div className="map-legend">
        <span className="row"><i className="dot" style={{ background: 'var(--cyan)' }} /> Station activity</span>
        <span className="row"><i className="dot" style={{ background: 'var(--amber)' }} /> Unresolved signals</span>
        <span className="row"><i className="dot" style={{ background: 'var(--orange)' }} /> Open incident</span>
        <span className="muted" style={{ fontSize: 10 }}>Boundaries: DataMeet, Survey of India depiction (CC BY 4.0)</span>
      </div>
    </div>
  )
}
