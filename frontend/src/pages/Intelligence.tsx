import { motion } from 'framer-motion'
import { useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { HBars, Sparkline } from '../components/charts'
import IndiaMap, { type MapStation } from '../components/IndiaMap'
import { CountUp, Icon, Panel, Priority, Stamp, Tabs, Tag } from '../components/ui'
import { geoMercator, geoPath } from 'd3-geo'
import type { FeatureCollection } from 'geojson'
import { feature } from 'topojson-client'
import type { GeometryCollection, Topology } from 'topojson-specification'
import outlineTopo from '../assets/india-outline.topo.json'
import { fmtAgo, fmtFreq } from '../lib/format'
import { BANDS, DAY, occupancy, STATIONS, ZONES } from '../lib/sim'
import { stationName, useApp } from '../lib/store'
import type { Level } from '../lib/types'

const OUTLINE_PATH = (() => {
  const t = outlineTopo as unknown as Topology
  const fc = feature(t, t.objects[Object.keys(t.objects)[0]] as GeometryCollection) as unknown as FeatureCollection
  return geoPath(geoMercator().fitExtent([[6, 4], [74, 76]], fc))(fc) ?? ''
})()

/** Small drawings for each stage of the zoom-out, all on the same 80x80 grid so the row stays aligned. */
function ScaleArt({ level }: { level: number }) {
  const dots = (n: number, r: number, seed: number) => Array.from({ length: n }, (_, i) => {
    const a = (i * 137.5 + seed) * (Math.PI / 180)
    const d = r * Math.sqrt((i + 0.5) / n)
    return [40 + d * Math.cos(a), 40 + d * Math.sin(a)] as const
  })
  const masts = [[22, 30], [52, 20], [60, 52], [30, 60], [40, 40]] as const
  return (
    <svg viewBox="0 0 80 80" className="scale-svg" aria-hidden>
      <circle cx="40" cy="40" r="37" className="scale-ring" />
      {level === 0 && <>
        <motion.circle cx="40" cy="40" r="6" fill="var(--green)" initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring', delay: 0.2 }} />
        <motion.circle cx="40" cy="40" r="6" fill="none" stroke="var(--green)" strokeWidth="1.5" animate={{ r: [6, 22], opacity: [0.9, 0] }} transition={{ repeat: Infinity, duration: 2.2 }} />
      </>}
      {level === 1 && dots(34, 26, 11).map(([x, y], i) => <motion.circle key={i} cx={x} cy={y} r="2.4" fill={i % 7 === 0 ? 'var(--amber)' : i % 3 === 0 ? 'var(--cyan)' : 'var(--green)'} initial={{ opacity: 0 }} animate={{ opacity: 0.9 }} transition={{ delay: 0.3 + i * 0.02 }} />)}
      {level === 2 && <>
        <path d="M40 24 L32 60 M40 24 L48 60 M35 46 H45" stroke="var(--text-2)" strokeWidth="2" fill="none" />
        {[10, 18, 26].map((r, i) => <motion.path key={r} d={`M${40 - r * 0.7} ${24 - r * 0.7} A ${r} ${r} 0 0 1 ${40 + r * 0.7} ${24 - r * 0.7}`} stroke="var(--cyan)" strokeWidth="1.6" fill="none" animate={{ opacity: [0.2, 1, 0.2] }} transition={{ repeat: Infinity, duration: 1.8, delay: i * 0.3 }} />)}
      </>}
      {level === 3 && <>
        {masts.map(([x, y], i) => masts.slice(i + 1).map(([x2, y2], j) => <motion.line key={`${i}-${j}`} x1={x} y1={y} x2={x2} y2={y2} stroke="var(--cyan)" strokeWidth="1" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ delay: 0.4 + (i + j) * 0.08, duration: 0.6 }} />))}
        {masts.map(([x, y], i) => <circle key={i} cx={x} cy={y} r="3.6" fill={i === 4 ? 'var(--amber)' : 'var(--cyan)'} />)}
      </>}
      {level === 4 && [[26, 28], [54, 28], [40, 54]].map(([cx, cy], k) => (
        <g key={k}>
          <circle cx={cx} cy={cy} r="15" fill="var(--cyan)" fillOpacity={0.08} stroke="var(--accent)" strokeDasharray="3 3" />
          {dots(6, 9, k * 40).map(([x, y], i) => <circle key={i} cx={x - 40 + cx} cy={y - 40 + cy} r="1.8" fill="var(--cyan)" />)}
        </g>
      ))}
      {level === 5 && <>
        <motion.path d={OUTLINE_PATH} fill="var(--accent)" fillOpacity={0.16} stroke="var(--cyan)" strokeWidth="1.2" initial={{ pathLength: 0, opacity: 0 }} animate={{ pathLength: 1, opacity: 1 }} transition={{ duration: 1.6, delay: 0.4 }} />
        {[[30, 32], [44, 48], [36, 58], [52, 36], [26, 44]].map(([x, y], i) => <motion.circle key={i} cx={x} cy={y} r="2" fill="var(--amber)" animate={{ opacity: [0.3, 1, 0.3] }} transition={{ repeat: Infinity, duration: 2, delay: i * 0.3 }} />)}
      </>}
    </svg>
  )
}

function ScaleUp({ counts, stationLabel }: { counts: number[]; stationLabel: string }) {
  const steps = [
    ['Evidence record', 'one capture, one accountable decision'],
    ['Signal records', 'every observation in the last 30 days'],
    ['One station', stationLabel],
    ['Monitoring stations', 'sharing fingerprints, not waveforms'],
    ['Regional zones', 'patterns that recur across stations'],
    ['National picture', 'what the spectrum of the country is doing'],
  ]
  return (
    <Panel title="From one decoded signal to national intelligence" sub="Each level aggregates the one before it; above the first stage nothing is a raw waveform">
      <div className="scale">
        {steps.map(([label, note], i) => (
          <motion.div key={label} className={`scale-step${i === steps.length - 1 ? ' last' : ''}`} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12 * i, duration: 0.45 }}>
            <div className="scale-art"><ScaleArt level={i} /></div>
            <div className="scale-num"><CountUp value={counts[i]} /></div>
            <div className="scale-label">{label}</div>
            <div className="scale-note">{note}</div>
            {i < steps.length - 1 && <motion.span className="scale-link" initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ delay: 0.12 * i + 0.3, duration: 0.5 }} />}
          </motion.div>
        ))}
      </div>
    </Panel>
  )
}

export default function Intelligence() {
  const { world, signals, level, setLevel, zone, setZone, session } = useApp()
  const nav = useNavigate()
  const [params] = useSearchParams()
  const sim = signals.filter((s) => s.provenance === 'SIMULATED')
  const mapStations: MapStation[] = STATIONS.map((st) => ({ ...st, activity: sim.filter((s) => s.stationId === st.id).length, unknown: sim.filter((s) => s.stationId === st.id && s.status !== 'DECODED').length, alert: world.incidents.some((i) => i.status !== 'CLOSED' && i.stationIds.includes(st.id)) }))
  const links = world.incidents.filter((i) => i.stationIds.length > 1).map((i) => [i.stationIds[0], i.stationIds[1]] as [string, string])
  const families = useMemo(() => {
    const by = new Map<number, typeof sim>()
    sim.forEach((s) => by.set(s.family, [...(by.get(s.family) ?? []), s]))
    return [...by.entries()].map(([f, ss]) => {
      const recent = ss.filter((s) => Date.now() - s.observedAt < 7 * DAY).length
      const older = ss.length - recent
      return { f, ss, recent, growth: older ? (recent - older / 3) / Math.max(1, older / 3) : 1, zones: new Set(ss.map((s) => STATIONS.find((x) => x.id === s.stationId)?.zone)).size }
    }).sort((a, b) => b.growth - a.growth)
  }, [sim])
  const known = sim.filter((s) => s.library === 'known' || s.library === 'reference').length
  const recurrent = sim.filter((s) => s.library === 'recurrent').length
  const unknownN = sim.filter((s) => s.status !== 'DECODED').length
  const emerging = families.filter((f) => f.growth > 0.5).length
  const counts = [1, sim.length, sim.filter((s) => s.stationId === 'MS-07').length, STATIONS.length, ZONES.length, 1]
  const myStation = session?.stationId ?? 'MS-07'

  return (
    <div className="page">
      <div className="page-head">
        <div className="grow">
          <h1 className="page-title">{level === 'NATIONAL' ? 'National RF intelligence' : level === 'REGIONAL' ? 'Regional intelligence' : 'Station intelligence'}</h1>
          <div className="page-sub">Aggregated patterns, not waveforms. Views match the operational level.</div>
        </div>
        <Tag kind="SIMULATED">Simulated monitoring data</Tag>
      </div>
      <Tabs<Level> value={level} onChange={setLevel} tabs={[{ id: 'FIELD', label: 'Level 1 · Field' }, { id: 'REGIONAL', label: 'Level 2 · Regional' }, { id: 'NATIONAL', label: 'Level 3 · National' }]} />
      {params.get('view') === 'scale' && <div style={{ marginBottom: 14 }}><ScaleUp counts={counts} stationLabel={stationName(myStation)} /></div>}

      {level === 'NATIONAL' && (
        <div className="col" style={{ gap: 14 }}>
          <div className="grid g-4">
            <Panel title="Active signal classes"><HBars items={[{ label: 'Known', value: known, color: 'var(--green)' }, { label: 'Recurring', value: recurrent, color: 'var(--cyan)' }, { label: 'Emerging', value: emerging, color: 'var(--violet)' }, { label: 'Unknown', value: unknownN, color: 'var(--amber)' }]} /></Panel>
            <Panel title="Anomalies"><HBars items={[{ label: 'New', value: world.anomalies.filter((a) => a.kind === 'New').length, color: 'var(--orange)' }, { label: 'Persistent', value: world.anomalies.filter((a) => a.kind === 'Persistent').length, color: 'var(--amber)' }, { label: 'Recurring', value: world.anomalies.filter((a) => a.kind === 'Recurring').length, color: 'var(--cyan)' }]} /></Panel>
            <Panel title="Interference & incidents"><HBars items={[{ label: 'Active cases', value: world.incidents.filter((i) => i.status !== 'CLOSED').length, color: 'var(--orange)' }, { label: 'Cross-station', value: world.incidents.filter((i) => i.stationIds.length > 1).length, color: 'var(--amber)' }, { label: 'Closed', value: world.incidents.filter((i) => i.status === 'CLOSED').length, color: 'var(--faint)' }]} /></Panel>
            <Panel title="Spectrum activity"><HBars items={BANDS.map((b, k) => ({ label: b.id, value: STATIONS.reduce((a, _, i) => a + occupancy(i, k, 13), 0) / STATIONS.length }))} max={1} fmt={(v) => `${Math.round(v * 100)}%`} /></Panel>
          </div>
          <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1.1fr) minmax(0, 0.9fr)' }}>
            <Panel title="Monitoring locations & cross-station correlation" sub="Dashed arcs link stations that observed the same pattern" flush>
              <IndiaMap stations={mapStations} zone={zone} onZone={setZone} links={links} height={460} onStation={(id) => nav(`/app/signals?station=${id}`)} />
            </Panel>
            <div className="col" style={{ gap: 14 }}>
              <Panel title="Emerging signal patterns" flush>
                <div className="list">{families.slice(0, 6).map((f, k) => (
                  <div key={f.f} className="list-item" style={{ gridTemplateColumns: 'auto 1fr auto auto' }} onClick={() => nav(`/app/signals/${f.ss[0].id}`)}>
                    <span className="mono" style={{ color: 'var(--violet)' }}>P-{String.fromCharCode(65 + k)}</span>
                    <div><div style={{ fontSize: 12.5 }}>{f.ss[0].band} {fmtFreq(f.ss[0].centerHz)}</div><div className="muted" style={{ fontSize: 11 }}>{f.ss.length} occurrences · {f.zones} zone(s)</div></div>
                    <Sparkline values={Array.from({ length: 10 }, (_, d) => f.ss.filter((s) => Math.floor((Date.now() - s.observedAt) / (3 * DAY)) === 9 - d).length)} w={70} />
                    <span className="mono" style={{ color: f.growth > 0 ? 'var(--amber)' : 'var(--muted)' }}>{f.growth > 5 ? 'New' : `${f.growth > 0 ? '+' : ''}${Math.round(f.growth * 100)}%`}</span>
                  </div>
                ))}</div>
              </Panel>
              <Panel title="Spectrum recovery opportunities" sub="Lowest mean occupancy (candidates for re-planning review)">
                <HBars items={STATIONS.flatMap((s, i) => BANDS.map((b, k) => ({ label: `${s.name} · ${b.id}`, value: STATIONS.length ? occupancy(i, k, 13) : 0 }))).sort((a, b) => a.value - b.value).slice(0, 5)} max={1} fmt={(v) => `${Math.round(v * 100)}%`} />
              </Panel>
            </div>
          </div>
        </div>
      )}

      {level === 'REGIONAL' && (
        <div className="col" style={{ gap: 14 }}>
          <div className="row-wrap">{ZONES.map((z) => <button key={z.id} className={`chip${zone === z.id ? ' on' : ''}`} onClick={() => setZone(zone === z.id ? null : z.id)}>{z.name}</button>)}</div>
          <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 0.9fr) minmax(0, 1.1fr)' }}>
            <Panel title="Zone map" flush><IndiaMap stations={mapStations} zone={zone} onZone={setZone} links={links} height={440} onStation={(id) => nav(`/app/signals?station=${id}`)} /></Panel>
            <div className="col" style={{ gap: 14 }}>
              <Panel title="Stations" flush>
                <table className="tbl"><thead><tr><th>Station</th><th>Receiver</th><th>Clock</th><th className="num">Signals</th><th className="num">Unresolved</th></tr></thead>
                  <tbody>{mapStations.filter((s) => !zone || s.zone === zone).map((s) => (
                    <tr key={s.id} className="click" onClick={() => nav(`/app/signals?station=${s.id}`)}><td>{s.id} · {s.name}</td><td><span className="row"><i className={`dot ${s.health === 'NOMINAL' ? 'dot-ok' : 'dot-warn'}`} />{s.health}</span></td><td>{s.clock}</td><td className="num">{s.activity}</td><td className="num" style={{ color: s.unknown ? 'var(--amber)' : undefined }}>{s.unknown}</td></tr>
                  ))}</tbody></table>
              </Panel>
              <Panel title="Cross-location correlation · incident queue" flush>
                <div className="list">{world.incidents.filter((i) => !zone || i.stationIds.some((id) => STATIONS.find((s) => s.id === id)?.zone === zone)).map((i) => (
                  <div key={i.id} className="list-item" onClick={() => nav(`/app/incidents/${i.id}`)}>
                    <Priority level={i.priority} />
                    <div><div style={{ fontSize: 12.5 }}>{i.title}</div><div className="muted" style={{ fontSize: 11 }}>{i.stationIds.map(stationName).join(' · ')}</div></div>
                    <span className="muted mono" style={{ fontSize: 11 }}>{fmtAgo(i.lastSeen)}</span>
                  </div>
                ))}</div>
              </Panel>
            </div>
          </div>
        </div>
      )}

      {level === 'FIELD' && (
        <div className="grid g-2" style={{ alignItems: 'start' }}>
          <Panel title={`Station ${stationName(myStation)}`} right={<button className="btn btn-primary btn-sm" onClick={() => nav('/app/analysis')}><Icon name="upload" size={13} /> Capture & analyse</button>} flush>
            <div className="list">{sim.filter((s) => s.stationId === myStation).slice(0, 12).map((s) => (
              <div key={s.id} className="list-item" onClick={() => nav(`/app/signals/${s.id}`)}>
                <span className="mono">{s.id}</span><span className="muted" style={{ fontSize: 12 }}>{fmtFreq(s.centerHz)} · {fmtAgo(s.observedAt)}</span><Stamp status={s.status} investigate={s.investigate} />
              </div>
            ))}</div>
          </Panel>
          <Panel title="Anomalies at this station" flush>
            <div className="list">{world.anomalies.filter((a) => a.stationId === myStation).map((a) => (
              <div key={a.id} className="list-item" onClick={() => nav(`/app/signals/${a.signalId}`)}><span className="mono">{a.id}</span><span className="muted">{a.reasons[0]}</span><span className="mono">{a.score.toFixed(2)}</span></div>
            ))}</div>
            {!world.anomalies.some((a) => a.stationId === myStation) && <div className="empty">No anomalies at this station.</div>}
          </Panel>
        </div>
      )}
    </div>
  )
}
