import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LinePlot, LiveWaterfall, type WaterfallEvent } from '../components/charts'
import { Icon, Panel, Seg, Stamp, Tag } from '../components/ui'
import { fmtBw, fmtFreq, fmtTime } from '../lib/format'
import { BANDS, STATIONS } from '../lib/sim'
import { useApp } from '../lib/store'
import type { Band } from '../lib/types'

const TONE = { DECODED: '#3ec28f', SIGNAL_NO_CODE: '#5fd0f0', UNKNOWN: '#e9b949' }

export default function Monitor() {
  const { signals, session } = useApp()
  const nav = useNavigate()
  const [station, setStation] = useState(session?.stationId ?? 'MS-07')
  const [band, setBand] = useState<Band>('VHF')
  const [running, setRunning] = useState(true)
  const channels = 180
  const b = BANDS.find((x) => x.id === band)!
  const pool = useMemo(() => {
    const here = signals.filter((s) => s.provenance === 'SIMULATED' && s.band === band && s.stationId === station)
    const extra = signals.filter((s) => s.provenance === 'SIMULATED' && s.band === band && s.stationId !== station)
    return [...here, ...extra].slice(0, 7)
  }, [signals, band, station])
  const events: WaterfallEvent[] = pool.map((s, i) => {
    const pos = s.centerHz ? (Math.log(s.centerHz) - Math.log(b.lo)) / (Math.log(b.hi) - Math.log(b.lo)) : 0.5
    const c = Math.max(4, Math.min(channels - 12, Math.round(pos * channels)))
    const w = Math.max(3, Math.min(14, Math.round(((s.bandwidthHz ?? 25e3) / 200e3) * 10) + 3))
    return { id: s.id, f0: c, f1: c + w, label: `${s.id.slice(-6)} ${s.status === 'SIGNAL_NO_CODE' ? 'NO CODE' : s.status}`, tone: TONE[s.status], startRow: 7 + i * 23, rows: 10 + (i * 7) % 18 }
  })
  const spectrum = Array.from({ length: channels }, (_, c) => {
    const x = Math.sin(c * 12.9898 + 7) * 43758.5453
    let v = -92 + 6 * (x - Math.floor(x))
    events.forEach((e) => { if (c >= e.f0 && c <= e.f1) v += 26 })
    return v
  })
  return (
    <div className="page">
      <div className="page-head">
        <div className="grow">
          <div className="eyebrow">Scene: an unknown world</div>
          <h1 className="page-title">Live Monitor</h1>
          <div className="page-sub">Thousands of RF observations exist without a known protocol label. Detections are boxed as they appear; click one to open its evidence record.</div>
        </div>
        <Tag kind="SIMULATED">Simulated receiver stream</Tag>
      </div>
      <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1fr) 340px' }}>
        <Panel title="Waterfall" sub={`${STATIONS.find((s) => s.id === station)?.name} · ${b.label}`} flush
          right={<div className="row">
            <select className="select" style={{ width: 180, height: 30 }} value={station} onChange={(e) => setStation(e.target.value)}>{STATIONS.map((s) => <option key={s.id} value={s.id}>{s.id} · {s.name}</option>)}</select>
            <Seg<Band> options={BANDS.map((x) => ({ id: x.id, label: x.id }))} value={band} onChange={setBand} />
            <button className="btn btn-sm" onClick={() => setRunning(!running)}><Icon name={running ? 'pause' : 'play'} size={12} /> {running ? 'Pause' : 'Resume'}</button>
          </div>}>
          <div style={{ padding: '10px 12px 0' }}>
            <LinePlot series={[{ x: spectrum.map((_, i) => i), y: spectrum, color: '#5fd0f0', fill: true }]} height={110} yLabel="dBm" />
          </div>
          <div style={{ padding: 12 }}>
            <LiveWaterfall height={420} channels={channels} events={events} running={running} seed={station.charCodeAt(4) + band.length} onEvent={(id) => nav(`/app/signals/${id}`)} />
            <div className="row mono muted" style={{ fontSize: 10.5, justifyContent: 'space-between', marginTop: 4 }}>
              <span>{fmtFreq(b.lo)}</span><span>frequency (log) →</span><span>{fmtFreq(b.hi)}</span>
            </div>
          </div>
        </Panel>
        <div className="col" style={{ gap: 14 }}>
          <Panel title="Detections" sub="Most recent in this band" flush>
            <div className="list">
              {pool.map((s) => (
                <div key={s.id} className="list-item" style={{ gridTemplateColumns: '1fr auto' }} onClick={() => nav(`/app/signals/${s.id}`)}>
                  <div><div className="mono" style={{ fontSize: 12 }}>{s.id}</div><div className="muted" style={{ fontSize: 11.5 }}>{fmtFreq(s.centerHz)} · {fmtBw(s.bandwidthHz)} · {fmtTime(s.observedAt)}</div></div>
                  <Stamp status={s.status} />
                </div>
              ))}
            </div>
          </Panel>
          <Panel title="Next step">
            <p className="dim" style={{ marginTop: 0 }}>Record a burst as .IQ or .wav and bring it into the analysis workflow. Nothing is labelled until evidence supports it.</p>
            <button className="btn btn-primary" onClick={() => nav('/app/analysis')}><Icon name="analysis" size={14} /> Analyse a capture</button>
          </Panel>
        </div>
      </div>
    </div>
  )
}
