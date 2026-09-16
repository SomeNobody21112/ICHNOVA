import { useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Donut, Heatmap, Sparkline } from '../components/charts'
import IndiaMap, { type MapStation } from '../components/IndiaMap'
import { Icon, Kpi, Panel, Philosophy, Stamp, Tag } from '../components/ui'
import { fmtAgo, fmtFreq } from '../lib/format'
import { BANDS, DAY, occupancy, STATIONS, ZONES } from '../lib/sim'
import { stationName, useApp } from '../lib/store'

export default function Command() {
  const { world, signals, zone, setZone, level, session } = useApp()
  const nav = useNavigate()
  const now = world.now
  const inZone = (stationId: string) => !zone || STATIONS.find((s) => s.id === stationId)?.zone === zone
  const zs = useMemo(() => signals.filter((s) => s.provenance === 'SIMULATED' && inZone(s.stationId)), [signals, zone]) // eslint-disable-line react-hooks/exhaustive-deps
  const active = zs.filter((s) => now - s.lastSeen < DAY)
  const unknown = zs.filter((s) => s.status !== 'DECODED')
  const incidents = world.incidents.filter((i) => i.status !== 'CLOSED' && i.stationIds.some(inZone))
  const anomalies = world.anomalies.filter((a) => inZone(a.stationId))
  const investigating = incidents.filter((i) => i.status === 'UNDER INVESTIGATION')

  const mapStations: MapStation[] = STATIONS.map((st) => {
    const ss = signals.filter((s) => s.stationId === st.id)
    return { ...st, activity: ss.length, unknown: ss.filter((s) => s.status !== 'DECODED').length, alert: world.incidents.some((i) => i.status !== 'CLOSED' && i.stationIds.includes(st.id)) }
  })
  const links = useMemo(() => world.incidents.filter((i) => i.stationIds.length > 1 && i.status !== 'CLOSED').slice(0, 5).map((i) => [i.stationIds[0], i.stationIds[1]] as [string, string]), [world.incidents])

  const daily = (pred: (t: number) => boolean) => Array.from({ length: 14 }, (_, d) => zs.filter((s) => { const age = Math.floor((now - s.observedAt) / DAY); return age === 13 - d && pred(s.observedAt) }).length)
  const hours = 24
  const heat = BANDS.map((_, bi) => Array.from({ length: hours }, (_, h) => {
    const st = STATIONS.map((s, si) => ({ s, si })).filter(({ s }) => !zone || s.zone === zone)
    return st.reduce((a, { si }) => a + occupancy(si, bi, h), 0) / Math.max(1, st.length)
  }))
  const hourly = Array.from({ length: 24 }, (_, h) => {
    const from = now - (24 - h) * 3600e3, to = from + 3600e3
    const inH = zs.filter((s) => s.observedAt >= from && s.observedAt < to)
    return { d: inH.filter((s) => s.status === 'DECODED').length, n: inH.filter((s) => s.status === 'SIGNAL_NO_CODE').length, u: inH.filter((s) => s.status === 'UNKNOWN').length }
  })
  const maxH = Math.max(1, ...hourly.map((x) => x.d + x.n + x.u))

  const alerts = [
    ...world.incidents.filter((i) => i.priority === 'HIGH' && i.status !== 'CLOSED' && i.stationIds.some(inZone)).map((i) => ({ key: i.id, pri: 'HIGH', title: i.title, sub: `${i.events.length} observations · ${i.stationIds.length} station(s)`, to: `/app/incidents/${i.id}`, t: i.lastSeen })),
    ...anomalies.slice(0, 6).map((a) => ({ key: a.id, pri: a.score > 0.8 ? 'HIGH' : 'MEDIUM', title: `Anomaly · ${a.kind} · ${stationName(a.stationId)}`, sub: a.reasons.slice(0, 2).join(' · '), to: `/app/signals/${a.signalId}`, t: a.detectedAt })),
    ...unknown.filter((s) => now - s.observedAt < 2 * DAY).slice(0, 5).map((s) => ({ key: s.id, pri: 'LOW', title: `Unknown signal ${s.id}`, sub: `${fmtFreq(s.centerHz)} · ${stationName(s.stationId)}`, to: `/app/signals/${s.id}`, t: s.observedAt })),
  ].sort((a, b) => (a.pri === b.pri ? b.t - a.t : a.pri === 'HIGH' ? -1 : b.pri === 'HIGH' ? 1 : a.pri === 'MEDIUM' ? -1 : 1)).slice(0, 9)

  const myStation = STATIONS.find((s) => s.id === session?.stationId)

  return (
    <div className="page">
      <div className="page-head">
        <div className="grow">
          <div className="eyebrow">{level === 'NATIONAL' ? 'National RF observability' : level === 'REGIONAL' ? `Regional view${zone ? ` · ${zone}` : ''}` : `Field station · ${myStation?.id} ${myStation?.name}`}</div>
          <h1 className="page-title">Command Center</h1>
          <div className="page-sub"><Philosophy compact /></div>
        </div>
        <Tag kind="SIMULATED">Simulated monitoring data</Tag>
        {zone && <button className="chip on" onClick={() => setZone(null)}>{ZONES.find((z) => z.id === zone)?.name} zone <Icon name="cross" size={11} /></button>}
        <Link className="btn btn-primary" to="/app/analysis"><Icon name="upload" size={14} /> Analyse capture</Link>
      </div>

      <div className="grid g-5" style={{ marginBottom: 14 }}>
        <Kpi label="Signals observed · 30 d" value={zs.length} tag="SIMULATED" spark={<Sparkline values={daily(() => true)} />} />
        <Kpi label="Active · 24 h" value={active.length} note="last seen within a day" spark={<Sparkline values={daily(() => true).slice(-7)} color="#3ec28f" />} />
        <Kpi label="Unknown signals" value={unknown.length} accent="amber" note="no code established" spark={<Sparkline values={daily(() => true).map((v, i) => Math.round(v * (0.3 + (i % 3) * 0.05)))} color="#e9b949" />} />
        <Kpi label="Anomalies" value={anomalies.length} accent="orange" note="require review" />
        <Kpi label="Under investigation" value={investigating.length} note={`${incidents.length} open incidents`} />
      </div>

      <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1.35fr) minmax(320px, 0.65fr)', marginBottom: 14 }}>
        <Panel title={level === 'FIELD' ? 'Station network' : 'National signal activity'} sub="Click a zone to filter the whole dashboard; click a station to open its signals."
          right={<span className="row"><Tag kind="SIMULATED" /></span>} flush>
          <IndiaMap stations={mapStations} zone={zone} onZone={setZone} links={level !== 'FIELD' ? links : []} height={470}
            selectedStation={level === 'FIELD' ? session?.stationId : null}
            onStation={(id) => nav(`/app/signals?station=${id}`)} />
        </Panel>
        <div className="col" style={{ gap: 14 }}>
          <Panel title="Alert queue" sub="Incidents, anomalies and new unknowns" right={<Link to="/app/review" className="btn btn-sm">Review queue</Link>} flush>
            <div className="list">
              {alerts.map((a) => (
                <div key={a.key} className="list-item" onClick={() => nav(a.to)}>
                  <span className={`pri pri-${a.pri}`}>{a.pri}</span>
                  <div className="grow"><div style={{ fontSize: 12.5 }}>{a.title}</div><div className="muted" style={{ fontSize: 11.5 }}>{a.sub}</div></div>
                  <span className="muted mono" style={{ fontSize: 11 }}>{fmtAgo(a.t, now)}</span>
                </div>
              ))}
            </div>
          </Panel>
          {level === 'FIELD' && myStation && (
            <Panel title={`My station · ${myStation.id} ${myStation.name}`} right={<Tag kind="SIMULATED" />}>
              <div className="row-wrap" style={{ gap: 14 }}>
                <span className="row"><i className={`dot ${myStation.health === 'NOMINAL' ? 'dot-ok' : 'dot-warn'}`} /> Receiver {myStation.health}</span>
                <span className="row"><i className={`dot ${myStation.clock === 'SYNCED' ? 'dot-ok' : 'dot-warn'}`} /> Clock {myStation.clock}</span>
                <span className="muted">Bands {myStation.bands.join(' · ')}</span>
              </div>
              <div className="row" style={{ marginTop: 12 }}><Link className="btn btn-primary" to="/app/monitor"><Icon name="monitor" size={14} /> Open live monitor</Link><Link className="btn" to="/app/analysis">Capture & analyse</Link></div>
            </Panel>
          )}
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1.1fr) minmax(0, 0.55fr) minmax(0, 1fr)' }}>
        <Panel title="Spectrum activity · 24 h" sub="Mean band occupancy by hour (rows: HF, VHF, UHF)" right={<Tag kind="SIMULATED" />}>
          <div style={{ display: 'grid', gridTemplateColumns: '44px 1fr', gap: 6 }}>
            <div className="col mono muted" style={{ fontSize: 10.5, justifyContent: 'space-around', height: 150 }}>{BANDS.map((b) => <span key={b.id}>{b.id}</span>)}</div>
            <Heatmap data={heat} height={150} onCell={() => nav('/app/spectrum')} />
          </div>
          <div className="row mono muted" style={{ fontSize: 10, justifyContent: 'space-between', paddingLeft: 50 }}><span>−24 h</span><span>−12 h</span><span>now</span></div>
        </Panel>
        <Panel title="Outcome mix" right={<Tag kind="SIMULATED" />}>
          <div className="row" style={{ gap: 14 }}>
            <Donut size={112} label={String(zs.length)} parts={[
              { value: zs.filter((s) => s.status === 'DECODED').length, color: '#3ec28f', label: 'DECODED' },
              { value: zs.filter((s) => s.status === 'SIGNAL_NO_CODE').length, color: '#5fd0f0', label: 'NO CODE' },
              { value: zs.filter((s) => s.status === 'UNKNOWN').length, color: '#e9b949', label: 'UNKNOWN' },
            ]} />
            <div className="col" style={{ gap: 6 }}>
              <Stamp status="DECODED" /><Stamp status="SIGNAL_NO_CODE" /><Stamp status="UNKNOWN" />
            </div>
          </div>
        </Panel>
        <Panel title="Signal activity timeline · 24 h" right={<Tag kind="SIMULATED" />}>
          <svg viewBox="0 0 480 150" style={{ width: '100%', height: 150 }}>
            {hourly.map((h, i) => {
              const x = 10 + i * 19.5, bw = 13, total = h.d + h.n + h.u
              const sc = 120 / maxH
              return (
                <g key={i}>
                  <rect x={x} y={130 - h.d * sc} width={bw} height={h.d * sc} fill="#3ec28f" rx="1.5" />
                  <rect x={x} y={130 - (h.d + h.n) * sc} width={bw} height={h.n * sc} fill="#5fd0f0" rx="1.5" />
                  <rect x={x} y={130 - total * sc} width={bw} height={h.u * sc} fill="#e9b949" rx="1.5" />
                  {i % 6 === 0 && <text x={x} y={146} className="axis">−{24 - i}h</text>}
                </g>
              )
            })}
          </svg>
        </Panel>
      </div>
    </div>
  )
}
