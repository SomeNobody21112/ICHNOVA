import { motion } from 'framer-motion'
import { useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { HBars, Sparkline } from '../components/charts'
import IndiaMap, { type MapStation } from '../components/IndiaMap'
import { Icon, Panel, Stamp, Tabs, Tag } from '../components/ui'
import { fmtAgo, fmtFreq } from '../lib/format'
import { BANDS, DAY, occupancy, STATIONS, ZONES } from '../lib/sim'
import { stationName, useApp } from '../lib/store'
import type { Level } from '../lib/types'

function ScaleUp({ counts }: { counts: number[] }) {
  const steps = ['evidence record', 'signal records (30 d)', 'records at one station', 'monitoring stations', 'regional zones', 'national picture']
  return (
    <Panel title="From one decoded signal to national intelligence" right={<Tag kind="SIMULATED" />}>
      <div className="row-wrap" style={{ gap: 0, alignItems: 'stretch' }}>
        {steps.map((s, i) => (
          <motion.div key={s} className="row" style={{ gap: 0 }} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.25 * i }}>
            {i > 0 && <motion.div style={{ height: 2, background: 'linear-gradient(90deg, var(--line-3), var(--cyan))', width: 34 }} initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ delay: 0.25 * i - 0.1 }} />}
            <div className="card" style={{ minWidth: 150, textAlign: 'center', padding: '12px 14px' }}>
              <div className="kpi-value" style={{ fontSize: 26, color: i === steps.length - 1 ? 'var(--cyan)' : undefined }}>{counts[i]}</div>
              <div className="muted" style={{ fontSize: 12 }}>{s}</div>
            </div>
          </motion.div>
        ))}
      </div>
      <p className="dim" style={{ margin: '12px 0 0' }}>Each evidence record becomes a fingerprint. Fingerprints recur across captures and stations; recurrence across zones becomes a pattern an analyst can act on.</p>
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
          <div className="eyebrow">Cross-signal intelligence</div>
          <h1 className="page-title">{level === 'NATIONAL' ? 'National RF intelligence' : level === 'REGIONAL' ? 'Regional intelligence' : 'Station intelligence'}</h1>
          <div className="page-sub">Aggregated patterns, not waveforms. Views match the operational level.</div>
        </div>
        <Tag kind="SIMULATED">Simulated monitoring data</Tag>
      </div>
      <Tabs<Level> value={level} onChange={setLevel} tabs={[{ id: 'FIELD', label: 'Level 1 · Field' }, { id: 'REGIONAL', label: 'Level 2 · Regional' }, { id: 'NATIONAL', label: 'Level 3 · National' }]} />
      {params.get('view') === 'scale' && <div style={{ marginBottom: 14 }}><ScaleUp counts={counts} /></div>}

      {level === 'NATIONAL' && (
        <div className="col" style={{ gap: 14 }}>
          <div className="grid g-4">
            <Panel title="Active signal classes"><HBars items={[{ label: 'Known', value: known, color: '#3ec28f' }, { label: 'Recurring', value: recurrent, color: '#5fd0f0' }, { label: 'Emerging', value: emerging, color: '#a393ff' }, { label: 'Unknown', value: unknownN, color: '#e9b949' }]} /></Panel>
            <Panel title="Anomalies"><HBars items={[{ label: 'New', value: world.anomalies.filter((a) => a.kind === 'New').length, color: '#f08c4a' }, { label: 'Persistent', value: world.anomalies.filter((a) => a.kind === 'Persistent').length, color: '#e9b949' }, { label: 'Recurring', value: world.anomalies.filter((a) => a.kind === 'Recurring').length, color: '#5fd0f0' }]} /></Panel>
            <Panel title="Interference & incidents"><HBars items={[{ label: 'Active cases', value: world.incidents.filter((i) => i.status !== 'CLOSED').length, color: '#f08c4a' }, { label: 'Cross-station', value: world.incidents.filter((i) => i.stationIds.length > 1).length, color: '#e9b949' }, { label: 'Closed', value: world.incidents.filter((i) => i.status === 'CLOSED').length, color: '#465666' }]} /></Panel>
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
                    <span className={`pri pri-${i.priority}`}>{i.priority}</span>
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
