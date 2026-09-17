import { AnimatePresence, motion } from 'framer-motion'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AmPanel, BlindCatalogue, CensusTable, DecodedTime, EvidenceSteps, MinuteDial, PathCard, progressSteps, RealWaterfall, Teletype, Verification, type FreqLabel } from '../components/liveviz'
import { Icon, Panel, Seg, Stamp, Tag } from '../components/ui'
import { useLiveFeed, type ReplayDoc, type ReplayIndexEntry, type StationsDoc } from '../lib/live'
import { useApp } from '../lib/store'

type Source = { kind: 'replay'; id: string } | { kind: 'live'; session: string; stationKey: string; mode: 'iq' | 'band' }

const GROUPS: { title: string; keys: string[] }[] = [
  { title: 'India · public broadcasting', keys: ['AIR-MW'] },
  { title: 'National time & frequency standards', keys: ['WWV', 'WWVB', 'DCF77', 'MSF', 'JJY', 'CHU'] },
  { title: 'Meteorological services', keys: ['DDH47'] },
]
const FLAG: Record<string, string> = { India: 'IN', 'United States': 'US', Germany: 'DE', 'United Kingdom': 'GB', Japan: 'JP', Canada: 'CA' }

function freq(khz: number) {
  return khz >= 1000 ? `${(khz / 1000).toFixed(khz % 1000 ? 3 : 0)} MHz` : `${khz} kHz`
}

export default function Monitor() {
  const { engine } = useApp()
  const [stations, setStations] = useState<StationsDoc | null>(null)
  const [index, setIndex] = useState<ReplayIndexEntry[]>([])
  const [source, setSource] = useState<Source | null>(null)
  const [doc, setDoc] = useState<ReplayDoc | null>(null)
  const [speed, setSpeed] = useState<'1' | '4' | '16'>('4')
  const [playing, setPlaying] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [starting, setStarting] = useState<string | null>(null)
  const [params, setParams] = useSearchParams()
  const wanted = params.get('rec')

  useEffect(() => {
    fetch('/live/stations.json').then((r) => r.json()).then(setStations).catch(() => setStations(null))
    fetch('/live/index.json').then((r) => r.json()).then((idx: ReplayIndexEntry[]) => {
      setIndex(idx)
      const first = idx.find((e) => e.id === wanted) ?? idx.find((e) => e.station_key === 'JJY') ?? idx[0]
      if (first) setSource({ kind: 'replay', id: first.id })
    }).catch(() => setIndex([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (source?.kind === 'replay' && source.id !== wanted) setParams({ rec: source.id }, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source])

  useEffect(() => {
    if (source?.kind !== 'replay') { setDoc(null); return }
    let alive = true
    setDoc(null)
    fetch(`/live/${source.id}.json`).then((r) => r.json()).then((d: ReplayDoc) => { if (alive) { setDoc(d); setPlaying(true) } })
    return () => { alive = false }
  }, [source])

  const feed = useLiveFeed(source?.kind === 'live' ? { kind: 'live', session: source.session } : { kind: 'replay', doc, speed: Number(speed), playing })
  const st = feed.state

  const stationKey = source?.kind === 'live' ? source.stationKey : doc?.station_key
  const mode = source?.kind === 'live' ? source.mode : doc?.mode
  const station = stationKey && stations ? stations.stations[stationKey] : doc?.station
  const kind = mode === 'band' ? 'band' : station?.analysis ?? 'timecode'
  const layout = station?.protocol && stations ? stations.layouts[station.protocol]?.positions : undefined
  const entry = source?.kind === 'replay' ? index.find((e) => e.id === source.id) : undefined

  const goLive = useCallback(async (key: string, m: 'iq' | 'band') => {
    setError(null)
    setStarting(key + m)
    try {
      const r = await fetch(`/api/live/start?station=${encodeURIComponent(key)}&mode=${m}`, { method: 'POST' })
      const j = await r.json()
      if (!r.ok) throw new Error(j.error ?? `HTTP ${r.status}`)
      setSource({ kind: 'live', session: j.session.id, stationKey: key, mode: m })
    } catch (e) {
      setError(`Could not start a live session: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setStarting(null)
    }
  }, [])

  const stop = async () => {
    if (source?.kind === 'live') await fetch(`/api/live/stop?session=${source.session}`, { method: 'POST' }).catch(() => undefined)
  }

  const labels: FreqLabel[] = useMemo(() => {
    if (kind === 'band') return (st.census?.channels ?? []).filter((c) => c.stations.length).map((c) => ({ hz: c.khz * 1e3, text: `${c.khz} ${c.stations[0].station}`, tone: '#9ff0cf' }))
    if (kind === 'timecode') return [{ hz: 0, text: 'carrier', tone: '#5fd0f0' }]
    return []
  }, [kind, st.census])

  const audioUrl = source?.kind === 'live'
    ? (st.result?.has_audio && st.result.recording_id ? `/api/live/file/${st.result.recording_id}/audio.wav` : null)
    : (st.result?.has_audio && doc ? `/live/${doc.id}.wav` : null)
  const zone = station?.protocol && stations ? stations.layouts[station.protocol]?.zone : undefined
  const progress = feed.duration ? Math.min(1, feed.clock / feed.duration) : 0
  const answer = st.result?.answer

  return (
    <div className="page">
      <div className="page-head">
        <div className="grow">
          <div className="eyebrow">Real transmissions · public receivers · no simulation</div>
          <h1 className="page-title">Live Monitor</h1>
          <div className="page-sub">
            Government and public-service transmitters with published formats, received through volunteer-operated KiwiSDR receivers.
            The engine is told only where to listen: carrier, timing, symbols and protocol are established from the signal, then the
            answer is checked against an independent reference.
          </div>
        </div>
        <span className="row"><i className={`dot ${engine.online ? 'dot-ok' : 'dot-warn'}`} /><span className="muted" style={{ fontSize: 12 }}>{engine.online ? 'Live reception available' : 'Engine offline · recorded sessions only'}</span></span>
      </div>
      {error && <div className="banner amber" style={{ marginBottom: 12 }}><Icon name="flag" /><span>{error}</span></div>}

      <div className="live-grid">
        <aside className="live-rail">
          {GROUPS.map((g) => (
            <div key={g.title} className="col" style={{ gap: 8 }}>
              <div className="eyebrow">{g.title}</div>
              {g.keys.flatMap((key) => {
                const s = stations?.stations[key]
                if (!s) return []
                const recs = index.filter((e) => e.station_key === key)
                const modes: ('iq' | 'band')[] = key === 'AIR-MW' ? ['band', 'iq'] : ['iq']
                return modes.map((m) => {
                  const rec = recs.find((e) => e.mode === m)
                  const active = (source?.kind === 'replay' && rec && source.id === rec.id) || (source?.kind === 'live' && source.stationKey === key && source.mode === m)
                  return (
                    <motion.div key={key + m} className={`station${active ? ' on' : ''}`} layout whileHover={{ y: -1 }}>
                      <div className="row" style={{ gap: 8 }}>
                        <span className="flag mono">{FLAG[s.country] ?? '··'}</span>
                        <b className="grow">{m === 'band' ? 'AIR medium-wave band' : key === 'AIR-MW' ? 'AIR Chennai 720 kHz' : s.name}</b>
                        <span className="mono muted" style={{ fontSize: 11 }}>{m === 'band' ? '531–1602 kHz' : freq(s.frequency_khz)}</span>
                      </div>
                      <div className="muted" style={{ fontSize: 11.5, lineHeight: 1.35 }}>{s.operator.split(' — ')[0]} · {m === 'band' ? 'carrier census vs official list' : s.service}</div>
                      <div className="row" style={{ gap: 6, marginTop: 6 }}>
                        {rec ? <Stamp status={rec.answer.status} /> : <span className="muted" style={{ fontSize: 11 }}>no recording yet</span>}
                        <span className="grow" />
                        {rec && <button className="btn btn-sm" onClick={() => setSource({ kind: 'replay', id: rec.id })}><Icon name="play" size={11} /> Replay</button>}
                        <button className="btn btn-sm btn-primary" disabled={!engine.online || starting !== null} onClick={() => goLive(key, m)} title={engine.online ? 'Receive now' : 'Start the local engine for live reception'}>
                          {starting === key + m ? <span className="spinner" /> : <span className="live-dot" />} Live
                        </button>
                      </div>
                    </motion.div>
                  )
                })
              })}
            </div>
          ))}
          <p className="muted" style={{ fontSize: 11.5 }}>Receivers are shared public infrastructure: sessions are short and at most three run at once.</p>
        </aside>

        <section className="col" style={{ gap: 14, minWidth: 0 }}>
          {!station ? <Panel><div className="empty"><span className="spinner" /> Loading recorded sessions…</div></Panel> : (
            <>
              <div className="live-head">
                <div className="grow">
                  <div className="row" style={{ gap: 10 }}>
                    <h2 className="live-title">{mode === 'band' ? 'All India Radio · medium-wave census' : station.name}</h2>
                    {source?.kind === 'live' ? <span className="tag tag-LIVE">LIVE · {source.session}</span> : <span className="tag tag-LIVE" style={{ opacity: 0.85 }}>RECORDED LIVE CAPTURE</span>}
                  </div>
                  <div className="muted" style={{ fontSize: 12.5 }}>
                    {station.operator} · {station.service}
                    {entry && <> · received {entry.t0_utc.slice(0, 19).replace('T', ' ')} UTC via {entry.receiver}</>}
                  </div>
                </div>
                {source?.kind === 'replay' ? (
                  <div className="row" style={{ gap: 8 }}>
                    <button className="btn btn-sm" onClick={() => { feed.restart(); setPlaying(true) }}><Icon name="back" size={12} /> Restart</button>
                    <button className="btn btn-sm" onClick={() => setPlaying(!playing)}><Icon name={playing ? 'pause' : 'play'} size={12} /> {playing ? 'Pause' : 'Play'}</button>
                    <Seg<'1' | '4' | '16'> options={[{ id: '1', label: '1×' }, { id: '4', label: '4×' }, { id: '16', label: '16×' }]} value={speed} onChange={setSpeed} />
                  </div>
                ) : (
                  <button className="btn btn-sm" onClick={stop} disabled={st.closed}><Icon name="pause" size={12} /> Stop &amp; analyse</button>
                )}
              </div>
              {source?.kind === 'replay' && <div className="live-progress"><motion.span style={{ width: `${progress * 100}%` }} /><em className="mono">{Math.floor(Math.min(feed.clock, feed.duration))} s / {Math.floor(feed.duration)} s of received signal{feed.clock >= feed.duration && feed.duration > 0 ? ' · complete' : ''}</em></div>}

              <div className="live-main">
                <div className="col" style={{ gap: 14, minWidth: 0 }}>
                  {mode !== 'band' && <PathCard station={station} receiver={st.receiver} />}
                  <Panel title={mode === 'band' ? 'Waterfall · 531–1602 kHz' : 'Waterfall · received IQ'} sub={mode === 'band' ? 'Each row is one spectrum from the receiver; labels are carriers matched to the official list' : 'Spectrum around the tuned carrier, computed from the IQ stream as it arrives'} flush
                    right={<span className="mono muted" style={{ fontSize: 11 }}>{st.receiver?.fs_hz ? `${Math.round(st.receiver.fs_hz).toLocaleString('en-IN')} samples/s` : ''}</span>}>
                    <RealWaterfall subscribe={feed.subscribe} height={mode === 'band' ? 300 : 240} labels={labels} unit={mode === 'band' ? 'kHz' : 'Hz'} />
                  </Panel>

                  {kind === 'timecode' && (
                    <div className="tc-grid">
                      <Panel title="Minute dial" sub="Each second lands on its UTC position">
                        <MinuteDial symbols={st.symbols} positions={layout} />
                        <div className="legend" style={{ justifyContent: 'center' }}>
                          <span><i style={{ background: '#5fd0f0' }} />marker</span><span><i style={{ background: '#e9b949' }} />1</span><span><i style={{ background: '#2a3a48' }} />0</span><span><i style={{ background: '#a393ff' }} />hole</span><span><i style={{ background: 'transparent', border: '1px solid #ef5a5a' }} />erased</span>
                        </div>
                      </Panel>
                      <div className="col" style={{ gap: 14 }}>
                        <Panel title="Decoded time" sub="Maximum-likelihood over valid dates; each digit must beat every alternative by 100:1">
                          <DecodedTime decode={st.decode} zoneNote={zone && zone !== 'UTC' ? `broadcast in ${zone}, shown as UTC` : undefined} />
                        </Panel>
                        <Verification decode={st.decode} receiver={st.receiver} />
                      </div>
                    </div>
                  )}
                  {kind === 'fsk' && (
                    <Panel title="Teleprinter" sub={st.fsk?.status === 'DECODED' ? `${st.fsk.code} · ${st.fsk.baud} Bd · shift ${st.fsk.shift_hz?.toFixed(1)} Hz · p = 10^${st.fsk.log10_p?.toFixed(0)}` : st.fsk?.reason ?? 'waiting for keying'}>
                      <Teletype text={st.fsk?.text ?? ''} />
                    </Panel>
                  )}
                  {kind === 'am' && <Panel title="Broadcast parameters"><AmPanel am={st.am ?? st.result?.runs?.am} audioUrl={audioUrl} /></Panel>}
                  {kind === 'band' && <Panel title="Carrier census" flush><CensusTable census={st.census ?? st.result?.census} /></Panel>}
                </div>

                <div className="col" style={{ gap: 14 }}>
                  <Panel title="Evidence as it arrives"><EvidenceSteps steps={progressSteps(kind, st, station)} /></Panel>
                  <AnimatePresence>
                    {answer && (
                      <motion.div initial={{ opacity: 0, y: 12, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} className="panel result-card">
                        <div className="panel-body col" style={{ gap: 10 }}>
                          <Stamp status={answer.status} size="lg" />
                          <div className="result-summary">{answer.summary}</div>
                          {answer.log10_p != null && <div className="mono muted" style={{ fontSize: 11.5 }}>p = 10^{answer.log10_p.toFixed(1)} after correcting for every hypothesis tested</div>}
                          <BlindCatalogue runs={st.result?.runs} />
                          {station.references.map((r) => <a key={r.url} href={r.url} target="_blank" rel="noreferrer" style={{ fontSize: 12 }}><Icon name="link" size={12} /> {r.title}</a>)}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                  {st.error && <div className="banner amber"><Icon name="flag" /><span>{st.error}</span></div>}
                  <Tag kind="LIVE">Real signal · {source?.kind === 'live' ? 'received now' : 'recorded from a live session'}</Tag>
                </div>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  )
}
