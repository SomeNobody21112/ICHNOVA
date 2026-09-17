import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { HBars, Heatmap, LinePlot, LiveWaterfall, type WaterfallEvent } from '../components/charts'
import { Icon, Meter, Panel, Seg, Stamp, Tabs, Tag } from '../components/ui'
import { fmtAgo, fmtFreq } from '../lib/format'
import { BANDS, DAY, occupancy, STATIONS, ZONES } from '../lib/sim'
import { stationName, useApp } from '../lib/store'
import type { Band } from '../lib/types'

type View = 'spectrum' | 'waterfall' | 'occupancy' | 'bands' | 'anomalies' | 'history'
type Range = '1h' | '6h' | '24h' | '7d' | '30d'
const RANGE_H: Record<Range, number> = { '1h': 1, '6h': 6, '24h': 24, '7d': 168, '30d': 720 }
const TONE = { DECODED: 'var(--green)', SIGNAL_NO_CODE: 'var(--cyan)', UNKNOWN: 'var(--amber)' }

export default function Spectrum() {
  const { signals, world, session } = useApp()
  const nav = useNavigate()
  const [view, setView] = useState<View>('occupancy')
  const [range, setRange] = useState<Range>('24h')
  const [station, setStation] = useState(session?.stationId ?? 'MS-07')
  const [band, setBand] = useState<Band>('VHF')
  const [overlay, setOverlay] = useState<string>('')
  const si = STATIONS.findIndex((s) => s.id === station)
  const bi = BANDS.findIndex((b) => b.id === band)
  const b = BANDS[bi]
  const bandSignals = useMemo(() => signals.filter((s) => s.provenance === 'SIMULATED' && s.band === band), [signals, band])
  const channels = 40
  const cols = 60
  const occ = Array.from({ length: channels }, (_, c) => Array.from({ length: cols }, (_, t) => occupancy(si, bi, (t / cols) * RANGE_H[range], c)))
  const chanFreq = (c: number) => Math.exp(Math.log(b.lo) + (c / channels) * (Math.log(b.hi) - Math.log(b.lo)))
  const events: WaterfallEvent[] = bandSignals.slice(0, 8).map((s, i) => {
    const pos = s.centerHz ? (Math.log(s.centerHz) - Math.log(b.lo)) / (Math.log(b.hi) - Math.log(b.lo)) : 0.5
    const c = Math.max(4, Math.min(150, Math.round(pos * 160)))
    return { id: s.id, f0: c, f1: c + 5, label: s.id.slice(-6), tone: overlay === s.id ? 'var(--text)' : TONE[s.status], startRow: 5 + i * 19, rows: 12 + i * 3 }
  })
  const psd = Array.from({ length: 200 }, (_, k) => {
    const x = Math.sin(k * 3.7 + si) * 999
    let v = -95 + 5 * (x - Math.floor(x))
    bandSignals.slice(0, 8).forEach((s, j) => { const p = s.centerHz ? (Math.log(s.centerHz) - Math.log(b.lo)) / (Math.log(b.hi) - Math.log(b.lo)) : 0; if (Math.abs(k / 200 - p) < 0.012) v += 24 - j })
    return v
  })
  return (
    <div className="page">
      <div className="page-head">
        <div className="grow">
          <div className="eyebrow">Spectrum intelligence</div>
          <h1 className="page-title">Spectrum Map</h1>
          <div className="page-sub">Occupancy, activity and anomalies by station and band. Click a cell or a detection to open the underlying signal record.</div>
        </div>
        <Tag kind="SIMULATED">Synthetic spectrum records</Tag>
        <select className="select" style={{ width: 190 }} value={station} onChange={(e) => setStation(e.target.value)}>{STATIONS.map((s) => <option key={s.id} value={s.id}>{s.id} · {s.name}</option>)}</select>
        <Seg<Band> options={BANDS.map((x) => ({ id: x.id, label: x.id }))} value={band} onChange={setBand} />
      </div>
      <Tabs<View> value={view} onChange={setView} tabs={[{ id: 'spectrum', label: 'Spectrum' }, { id: 'waterfall', label: 'Waterfall' }, { id: 'occupancy', label: 'Occupancy' }, { id: 'bands', label: 'Band activity' }, { id: 'anomalies', label: 'Anomalies', count: world.anomalies.length }, { id: 'history', label: 'History' }]} />

      {view === 'spectrum' && (
        <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1fr) 320px' }}>
          <Panel title={`Spectrum · ${b.label}`} right={<Tag kind="SIMULATED" />}>
            <LinePlot series={[{ x: psd.map((_, k) => k), y: psd, color: 'var(--cyan)', fill: true }]} height={320} yLabel="dBm" xLabel="frequency (log)" />
          </Panel>
          <Panel title="Detected in band" flush>
            <div className="list">{bandSignals.slice(0, 10).map((s) => (
              <div key={s.id} className="list-item" style={{ gridTemplateColumns: '1fr auto' }} onClick={() => nav(`/app/signals/${s.id}`)}>
                <div><div className="mono" style={{ fontSize: 12 }}>{fmtFreq(s.centerHz)}</div><div className="muted" style={{ fontSize: 11 }}>{s.id} · {stationName(s.stationId)}</div></div><Stamp status={s.status} />
              </div>
            ))}</div>
          </Panel>
        </div>
      )}

      {view === 'waterfall' && (
        <Panel title="Waterfall" sub="Frequency → · time ↓ · colour = signal strength · boxes = detected events"
          right={<div className="row"><span className="muted" style={{ fontSize: 12 }}>Overlay</span><select className="select" style={{ width: 200, height: 30 }} value={overlay} onChange={(e) => setOverlay(e.target.value)}><option value="">none</option>{bandSignals.slice(0, 8).map((s) => <option key={s.id} value={s.id}>{s.id}</option>)}</select><Tag kind="SIMULATED" /></div>}>
          <LiveWaterfall height={460} channels={160} events={events} seed={si + bi * 7} onEvent={(id) => nav(`/app/signals/${id}`)} />
        </Panel>
      )}

      {view === 'occupancy' && (
        <Panel title={`Occupancy · ${stationName(station)} · ${b.label}`} sub="Rows: channel (low → high frequency, bottom → top). Columns: time. Colour: fraction of time occupied."
          right={<div className="row"><Seg<Range> options={(['1h', '6h', '24h', '7d', '30d'] as Range[]).map((r) => ({ id: r, label: r }))} value={range} onChange={setRange} /><Tag kind="SIMULATED" /></div>}>
          <div style={{ display: 'grid', gridTemplateColumns: '84px 1fr', gap: 8 }}>
            <div className="col mono muted" style={{ justifyContent: 'space-between', fontSize: 10.5, height: 380 }}><span>{fmtFreq(chanFreq(channels))}</span><span>{fmtFreq(chanFreq(channels / 2))}</span><span>{fmtFreq(chanFreq(0))}</span></div>
            <Heatmap data={[...occ].reverse()} height={380} onCell={(r) => {
              const f = chanFreq(channels - 1 - r)
              const hit = [...bandSignals].sort((x, y) => Math.abs((x.centerHz ?? 0) - f) - Math.abs((y.centerHz ?? 0) - f))[0]
              if (hit) nav(`/app/signals/${hit.id}`)
            }} />
          </div>
          <div className="row mono muted" style={{ fontSize: 10.5, justifyContent: 'space-between', paddingLeft: 92, marginTop: 4 }}><span>−{range}</span><span>time →</span><span>now</span></div>
          <div className="legend" style={{ marginTop: 10 }}><span><i style={{ background: 'var(--occ-1)' }} />idle</span><span><i style={{ background: 'var(--occ-2)' }} />moderate</span><span><i style={{ background: 'var(--amber)' }} />high</span><span><i style={{ background: 'var(--orange)' }} />saturated</span></div>
        </Panel>
      )}

      {view === 'bands' && (
        <div className="grid g-3">
          {BANDS.map((bb, k) => (
            <Panel key={bb.id} title={bb.label} right={<Tag kind="SIMULATED" />}>
              <HBars items={ZONES.map((z) => {
                const st = STATIONS.map((s, i) => ({ s, i })).filter(({ s }) => s.zone === z.id)
                return { label: z.name, value: st.reduce((a, { i }) => a + occupancy(i, k, 14), 0) / Math.max(1, st.length) }
              })} max={1} fmt={(v) => `${Math.round(v * 100)}%`} />
            </Panel>
          ))}
        </div>
      )}

      {view === 'anomalies' && (
        <div className="grid g-2">
          <Panel title="Anomalies · requires review" flush right={<Tag kind="SIMULATED" />}>
            <div className="list">{world.anomalies.map((a) => (
              <div key={a.id} className="list-item" style={{ gridTemplateColumns: '1fr 180px' }} onClick={() => nav(`/app/signals/${a.signalId}`)}>
                <div><div className="row"><span className="mono">{a.id}</span><span className="stamp stamp-INVESTIGATE">{a.kind.toUpperCase()}</span></div>
                  <div className="muted" style={{ fontSize: 12 }}>{stationName(a.stationId)} · {a.band} · {fmtAgo(a.detectedAt)}</div>
                  <ul style={{ margin: '4px 0 0', paddingLeft: 16, fontSize: 12 }}>{a.reasons.map((r) => <li key={r}>{r}</li>)}</ul></div>
                <div><div className="row muted" style={{ fontSize: 11 }}><span className="grow">Anomaly score</span><span className="mono">{a.score.toFixed(2)}</span></div><Meter value={a.score} tone="segs" /><div className="muted" style={{ fontSize: 11, marginTop: 4 }}>{a.score > 0.8 ? 'HIGH DEVIATION' : 'MODERATE DEVIATION'}</div></div>
              </div>
            ))}</div>
          </Panel>
          <Panel title="How anomalies should be read">
            <div className="banner violet"><Icon name="info" /><span>A high score means <b>deviation from a station's baseline</b>. It is never a threat classification. Every anomaly is routed to review with its reasons.</span></div>
            <div className="hr" />
            <div className="panel-title" style={{ marginBottom: 8 }}>Model card</div>
            <dl className="kv">
              <dt>Model</dt><dd>Baseline anomaly detector (Phase 3)</dd><dt>Version</dt><dd><Tag kind="NOT ESTABLISHED" /></dd>
              <dt>Training dataset</dt><dd><Tag kind="NOT ESTABLISHED" /></dd><dt>Last updated</dt><dd><Tag kind="NOT ESTABLISHED" /></dd>
              <dt>Scores shown</dt><dd><Tag kind="SIMULATED" /></dd>
            </dl>
          </Panel>
        </div>
      )}

      {view === 'history' && (
        <Panel title={`Occupancy history · ${stationName(station)} · 30 days`} right={<Tag kind="SIMULATED" />}>
          <LinePlot height={300} yMin={0} yMax={1} yLabel="occupancy" xLabel="days ago → today" series={BANDS.map((_, k) => ({
            x: Array.from({ length: 30 }, (_, d) => d), y: Array.from({ length: 30 }, (_, d) => Array.from({ length: 8 }, (_, h) => occupancy(si, k, d * 24 + h * 3)).reduce((a, v) => a + v, 0) / 8),
            color: ['var(--cyan)', 'var(--violet)', 'var(--green)'][k],
          }))} />
          <div className="legend">{BANDS.map((bb, k) => <span key={bb.id}><i style={{ background: ['var(--cyan)', 'var(--violet)', 'var(--green)'][k] }} />{bb.label}</span>)}</div>
          <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>{signals.filter((s) => s.stationId === station && Date.now() - s.observedAt < 30 * DAY).length} signal records at this station in the window.</div>
        </Panel>
      )}
    </div>
  )
}
