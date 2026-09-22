import { useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Donut, Heatmap, Sparkline } from '../components/charts'
import IndiaMap, { type MapStation } from '../components/IndiaMap'
import { RealProof } from '../components/realproof'
import { Icon, Kpi, Panel, Priority, Tag } from '../components/ui'
import { fmtAgo, fmtFreq } from '../lib/format'
import { BANDS, DAY, occupancy, STATIONS, ZONES } from '../lib/sim'
import { stationName, useApp } from '../lib/store'

export default function Command() {
  const { world, signals, zone, setZone, level, session, reviews } = useApp()
  const nav = useNavigate()
  const now = world.now
  const inZone = (stationId: string) => !zone || STATIONS.find((s) => s.id === stationId)?.zone === zone
  const zs = useMemo(() => signals.filter((s) => s.provenance === 'SIMULATED' && inZone(s.stationId)), [signals, zone]) // eslint-disable-line react-hooks/exhaustive-deps
  const outcomes = [
    { value: zs.filter((s) => s.status === 'DECODED').length, color: 'var(--green)', label: 'Decoded' },
    { value: zs.filter((s) => s.status === 'SIGNAL_NO_CODE').length, color: 'var(--cyan)', label: 'Signal, no code' },
    { value: zs.filter((s) => s.status === 'UNKNOWN').length, color: 'var(--amber)', label: 'Unknown' },
  ]
  const unknown = zs.filter((s) => s.status !== 'DECODED')
  const incidents = world.incidents.filter((i) => i.status !== 'CLOSED' && i.stationIds.some(inZone))
  const anomalies = world.anomalies.filter((a) => inZone(a.stationId))
  const investigating = incidents.filter((i) => i.status === 'UNDER INVESTIGATION')
  const toReview = signals.filter((s) => (s.status !== 'DECODED' || s.investigate) && !reviews[s.id]).length

  const mapStations: MapStation[] = STATIONS.map((st) => {
    const ss = signals.filter((s) => s.stationId === st.id)
    return { ...st, activity: ss.length, unknown: ss.filter((s) => s.status !== 'DECODED').length, alert: world.incidents.some((i) => i.status !== 'CLOSED' && i.stationIds.includes(st.id)) }
  })
  const links = useMemo(() => world.incidents.filter((i) => i.stationIds.length > 1 && i.status !== 'CLOSED').slice(0, 5).map((i) => [i.stationIds[0], i.stationIds[1]] as [string, string]), [world.incidents])

  const daily = (pred: (t: number) => boolean) => Array.from({ length: 14 }, (_, d) => zs.filter((s) => { const age = Math.floor((now - s.observedAt) / DAY); return age === 13 - d && pred(s.observedAt) }).length)
  const heat = BANDS.map((_, bi) => Array.from({ length: 24 }, (_, h) => {
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
    ...anomalies.slice(0, 6).map((a) => ({ key: a.id, pri: a.score > 0.8 ? 'HIGH' : 'MEDIUM', title: `Anomaly at ${stationName(a.stationId)}`, sub: a.reasons.slice(0, 1).join(' · '), to: `/app/signals/${a.signalId}`, t: a.detectedAt })),
    ...unknown.filter((s) => now - s.observedAt < 2 * DAY).slice(0, 5).map((s) => ({ key: s.id, pri: 'LOW', title: `Unknown signal ${s.id}`, sub: `${fmtFreq(s.centerHz)} · ${stationName(s.stationId)}`, to: `/app/signals/${s.id}`, t: s.observedAt })),
  ].sort((a, b) => (a.pri === b.pri ? b.t - a.t : a.pri === 'HIGH' ? -1 : b.pri === 'HIGH' ? 1 : a.pri === 'MEDIUM' ? -1 : 1)).slice(0, 6)

  const myStation = STATIONS.find((s) => s.id === session?.stationId)
  const scope = level === 'NATIONAL' ? 'all monitoring stations' : level === 'REGIONAL' ? (zone ? `the ${ZONES.find((z) => z.id === zone)?.name} zone` : 'your region') : `${myStation?.id} ${myStation?.name}`
  const firstName = session?.name.split(' ')[0]

  const tasks = [
    { icon: 'analysis', title: 'Analyse a capture', text: 'Upload an .IQ or .wav recording', to: '/app/analysis' },
    { icon: 'monitor', title: 'Live signals', text: 'Real government transmissions', to: '/app/monitor' },
    { icon: 'review', title: `Review queue · ${toReview}`, text: 'Signals awaiting an analyst decision', to: '/app/review' },
    { icon: 'incidents', title: `Incidents · ${incidents.length}`, text: `${investigating.length} under investigation`, to: '/app/incidents' },
  ]

  return (
    <div className="page">
      <div className="page-head">
        <div className="grow">
          <div className="meta">{level === 'NATIONAL' ? 'National view' : level === 'REGIONAL' ? 'Regional view' : 'Field station'}</div>
          <h1 className="page-title">Welcome{firstName ? `, ${firstName}` : ''}</h1>
          <div className="page-sub">What needs attention across {scope}. Monitoring figures on this page are simulated; real-signal results are marked.</div>
        </div>
        <Tag kind="SIMULATED">Monitoring figures simulated</Tag>
        {zone && <button className="chip on" onClick={() => setZone(null)}>{ZONES.find((z) => z.id === zone)?.name} zone <Icon name="cross" size={11} /></button>}
      </div>

      <div className="tasks" style={{ marginBottom: 16 }}>
        {tasks.map((t) => (
          <Link key={t.title} to={t.to} className="task">
            <span className="task-icon"><Icon name={t.icon} /></span>
            <span><span className="task-title">{t.title}</span><span className="task-text">{t.text}</span></span>
            <span className="go"><Icon name="arrow" size={16} /></span>
          </Link>
        ))}
      </div>

      <div className="statbar" style={{ marginBottom: 16 }}>
        <Kpi label="Signals observed · 30 days" value={zs.length} tag="SIMULATED" spark={<Sparkline values={daily(() => true)} />} />
        <Kpi label="Without an established code" value={unknown.length} accent="amber" note="detected or unknown" />
        <Kpi label="Anomalies" value={anomalies.length} accent="orange" note="need review" />
        <Kpi label="Under investigation" value={investigating.length} note={`${incidents.length} open incidents`} />
      </div>

      <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1.4fr) minmax(320px, 0.6fr)', alignItems: 'start' }}>
        <Panel title={level === 'FIELD' ? 'Station network' : 'Monitoring stations'} sub="Select a zone to filter this page, or a station to see its signals" flush>
          <IndiaMap stations={mapStations} zone={zone} onZone={setZone} links={level !== 'FIELD' ? links : []} height={440}
            selectedStation={level === 'FIELD' ? session?.stationId : null}
            onStation={(id) => nav(`/app/signals?station=${id}`)} />
        </Panel>
        <Panel title="Needs attention" sub="Highest priority first" right={<Link to="/app/review" className="btn btn-sm">View all</Link>} flush>
          <div className="list">
            {alerts.map((a) => (
              <div key={a.key} className="list-item" role="link" tabIndex={0} onClick={() => nav(a.to)} onKeyDown={(e) => { if (e.key === 'Enter') nav(a.to) }}>
                <Priority level={a.pri} />
                <div className="grow" style={{ minWidth: 0 }}><div style={{ fontSize: 13 }}>{a.title}</div><div className="muted clamp-2" style={{ fontSize: 12 }} title={a.sub}>{a.sub}</div></div>
                <span className="muted mono" style={{ fontSize: 11.5 }}>{fmtAgo(a.t, now)}</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <div className="section-head">
        <h2>Verified on real transmissions</h2>
        <p className="hide-sm">Open a card to watch the evidence arrive</p>
        <span className="spacer" />
        <Link to="/app/lab" className="btn btn-sm btn-ghost">All results</Link>
      </div>
      <RealProof compact limit={4} />

      <details className="more">
        <summary>Show spectrum trends</summary>
        <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1.1fr) minmax(0, 0.6fr) minmax(0, 1fr)', marginTop: 12 }}>
          <Panel title="Band occupancy · 24 h" sub="Rows: HF, VHF, UHF">
            <div style={{ display: 'grid', gridTemplateColumns: '44px 1fr', gap: 6 }}>
              <div className="col mono muted" style={{ fontSize: 11, justifyContent: 'space-around', height: 150 }}>{BANDS.map((b) => <span key={b.id}>{b.id}</span>)}</div>
              <Heatmap data={heat} height={150} onCell={() => nav('/app/spectrum')} />
            </div>
            <div className="row mono muted" style={{ fontSize: 11, justifyContent: 'space-between', paddingLeft: 50 }}><span>−24 h</span><span>−12 h</span><span>now</span></div>
          </Panel>
          <Panel title="Outcomes">
            {/* A legend, not three verdict stamps: stamps are sized to announce one result and
                spilled out of this narrow card; the legend also carries the counts. */}
            <div className="row-wrap" style={{ gap: 16 }}>
              <Donut size={112} label={String(zs.length)} parts={outcomes} />
              <div className="col" style={{ gap: 8, minWidth: 0, fontSize: 12.5 }}>
                {outcomes.map((o) => (
                  <span key={o.label} className="row" style={{ gap: 8 }}>
                    <i style={{ width: 8, height: 8, borderRadius: 2, background: o.color, flex: 'none' }} />
                    <span className="muted">{o.label}</span>
                    <b className="mono" style={{ marginLeft: 'auto', paddingLeft: 10 }}>{o.value}</b>
                  </span>
                ))}
              </div>
            </div>
          </Panel>
          <Panel title="Signals per hour · 24 h">
            <svg viewBox="0 0 480 150" style={{ width: '100%', height: 150 }}>
              {hourly.map((h, i) => {
                const x = 10 + i * 19.5, bw = 13, total = h.d + h.n + h.u
                const sc = 120 / maxH
                return (
                  <g key={i} className="bar-in" style={{ animationDelay: `${i * 22}ms` }}>
                    <rect x={x} y={130 - h.d * sc} width={bw} height={h.d * sc} fill="var(--green)" rx="1.5" />
                    <rect x={x} y={130 - (h.d + h.n) * sc} width={bw} height={h.n * sc} fill="var(--cyan)" rx="1.5" />
                    <rect x={x} y={130 - total * sc} width={bw} height={h.u * sc} fill="var(--amber)" rx="1.5" />
                  </g>
                )
              })}
            </svg>
            {/* Axis labels live in HTML: text inside a scaled viewBox renders smaller than its stated size. */}
            <div className="row mono muted" style={{ fontSize: 11, justifyContent: 'space-between', marginTop: 2 }}>
              <span>−24 h</span><span>−18 h</span><span>−12 h</span><span>−6 h</span><span>now</span>
            </div>
          </Panel>
        </div>
      </details>
    </div>
  )
}
