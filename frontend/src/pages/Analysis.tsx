import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Characteristics, WhyPanel } from '../components/evidence'
import { AmPanel, BlindCatalogue, Teletype } from '../components/liveviz'
import type { ReplayDoc, ReplayIndexEntry, ResultEv } from '../lib/live'
import { Icon, Panel, Stamp, Tag } from '../components/ui'
import { CODE_SHORT, fmtInt, fmtP, STATUS_MEANING } from '../lib/format'
import { STATIONS } from '../lib/sim'
import { useApp } from '../lib/store'
import type { EvidencePack, RealAnalysis } from '../lib/types'

interface Sample { name: string; format: string; fs_hz: number; bytes: number; description: string; evidence_id: string }

const STEPS = ['Capture', 'Upload', 'Detect', 'Analyse', 'Classify', 'Verify', 'Report']
const STAGES = [
  { key: 'detect', name: 'Signal detection' },
  { key: 'sps', name: 'Symbol-rate search' },
  { key: 'mod', name: 'Modulation analysis' },
  { key: 'cfo', name: 'CFO estimation' },
  { key: 'fec', name: 'FEC hypothesis search' },
  { key: 'valid', name: 'Statistical validation' },
]

function stageValue(key: string, p: EvidencePack) {
  const d = p.diagnostics, a = p.accept
  switch (key) {
    case 'detect': return d.detection_log10_p <= Math.log10(a.alpha) ? `present · p ${fmtP(d.detection_log10_p)}` : 'not established'
    case 'sps': return `${d.sps_candidates.length} candidates · ${d.sps_candidates.join(', ')}`
    case 'mod': return p.result.modulation ?? `${d.top_hypotheses[0]?.modulation ?? '—'} (candidate)`
    case 'cfo': return `${d.cfo_candidates.length} lines`
    case 'fec': return `${fmtInt(a.n_hypotheses)} hypotheses`
    default: return p.result.status === 'DECODED' ? `accepted · ${CODE_SHORT(p.result.code)}` : a.log10_p <= a.log10_threshold ? 'significant, structurally rejected' : 'not significant'
  }
}

export default function Analysis() {
  const { engine, session, addUpload, log, loadPack } = useApp()
  const nav = useNavigate()
  const [samples, setSamples] = useState<Sample[]>([])
  const [file, setFile] = useState<File | null>(null)
  const [sample, setSample] = useState<Sample | null>(null)
  const [over, setOver] = useState(false)
  const [meta, setMeta] = useState({ station: session?.stationId ?? 'MS-07', antenna: 'Discone, vertical', captured: new Date(Date.now() - 5 * 60e3).toISOString().slice(0, 16), centerMHz: '145.8250', bwKHz: '25', fs: '', notes: '' })
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState(-1)
  const [pack, setPack] = useState<EvidencePack | null>(null)
  const [replay, setReplay] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [recordId, setRecordId] = useState<string | null>(null)
  const [showTech, setShowTech] = useState(false)
  const [realList, setRealList] = useState<ReplayIndexEntry[]>([])
  const [real, setReal] = useState<ReplayIndexEntry | null>(null)
  const [realResult, setRealResult] = useState<RealAnalysis | null>(null)
  const [sampleTab, setSampleTab] = useState<'real' | 'bench'>('real')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { fetch('/samples/samples.json').then((r) => r.json()).then(setSamples).catch(() => setSamples([])) }, [])
  useEffect(() => { fetch('/live/index.json').then((r) => r.json()).then((x: ReplayIndexEntry[]) => setRealList(x.filter((e) => e.mode === 'iq'))).catch(() => setRealList([])) }, [])
  const st = STATIONS.find((s) => s.id === meta.station)
  const step = pack || realResult ? (recordId ? 6 : 5) : running ? 2 + Math.min(3, Math.floor(progress / 2)) : file || sample || real ? 1 : 0

  const runReal = async (entry: ReplayIndexEntry) => {
    setError(null); setPack(null); setRealResult(null); setRecordId(null); setShowTech(false); setReplay(false)
    setRunning(true); setProgress(0)
    const tick = setInterval(() => setProgress((p) => Math.min(p + 1, STAGES.length - 1)), 420)
    try {
      if (engine.online) {
        const meta = await (await fetch(`/api/recordings/${entry.id}.json`)).json()
        const body = await (await fetch(`/api/recordings/${entry.id}.wav`)).arrayBuffer()
        const c = meta.capture
        const q = new URLSearchParams({ format: 'wav', fs: String(c.fs_hz), name: `${entry.id}.wav`, t0_unix: String(c.t0_unix), timing: c.timing,
          center_freq_hz: String(c.tuned_khz * 1e3), notes: `Real recording: ${entry.station} via ${entry.receiver ?? 'KiwiSDR'}` })
        const res = await fetch(`/api/analyze?${q}`, { method: 'POST', body })
        const j = await res.json()
        if (!res.ok) throw new Error(j.error ?? `HTTP ${res.status}`)
        setPack(j as EvidencePack)
        setRealResult((j as EvidencePack).real ?? null)
      } else {
        const doc = (await (await fetch(`/live/${entry.id}.json`)).json()) as ReplayDoc
        const r = doc.events.find((e): e is ResultEv => e.type === 'result')
        if (!r || !r.runs) throw new Error('recorded result missing')
        setRealResult({ samples: 0, fs_hz: 0, duration_s: entry.duration_s ?? 0, timing: null, t0_unix: null, runs: r.runs, timers_s: {}, answer: r.answer })
        setReplay(true)
      }
      setProgress(STAGES.length)
      log(engine.online ? 'Real recording analysed by local engine' : 'Recorded real-signal result replayed', entry.id, entry.station)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      clearInterval(tick)
      setRunning(false)
    }
  }

  const run = async () => {
    setError(null); setPack(null); setRecordId(null); setShowTech(false); setReplay(false)
    setRunning(true); setProgress(0)
    const tick = setInterval(() => setProgress((p) => Math.min(p + 1, STAGES.length - 1)), 420)
    try {
      let result: EvidencePack
      const name = file?.name ?? sample!.name
      const fmt = name.toLowerCase().endsWith('.wav') ? 'wav' : 'iq'
      if (engine.online) {
        const body = file ? await file.arrayBuffer() : await (await fetch(`/samples/${sample!.name}`)).arrayBuffer()
        const q = new URLSearchParams({ format: fmt, ...(meta.fs.trim() ? { fs: meta.fs.trim() } : {}), name, station: meta.station, antenna: meta.antenna, captured_at: meta.captured, notes: meta.notes,
          center_freq_hz: String(Number(meta.centerMHz) * 1e6), bandwidth_hz: String(Number(meta.bwKHz) * 1e3) })
        const res = await fetch(`/api/analyze?${q}`, { method: 'POST', body })
        const j = await res.json()
        if (!res.ok) throw new Error(j.error ?? `HTTP ${res.status}`)
        result = j as EvidencePack
      } else if (sample) {
        result = await loadPack(sample.evidence_id)
        setReplay(true)
      } else {
        throw new Error('The local analysis engine is offline. Start it with "python server/app.py", or choose a sample capture to replay recorded engine output.')
      }
      await new Promise((r) => setTimeout(r, Math.max(0, 420 * STAGES.length - 400)))
      setProgress(STAGES.length)
      setPack(result)
      log(engine.online ? 'Capture analysed by local engine' : 'Recorded engine output replayed', result.id, result.result.status)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      clearInterval(tick)
      setRunning(false)
    }
  }

  const openRecord = () => {
    if (!pack) return
    if (pack.source.kind === 'BENCHMARK') { nav(`/app/signals/${pack.id}`); return }
    const rec = recordId ? { id: recordId } : addUpload(pack, { stationId: meta.station, centerHz: Number(meta.centerMHz) * 1e6 || null, bandwidthHz: Number(meta.bwKHz) * 1e3 || null })
    setRecordId(rec.id)
    nav(`/app/signals/${rec.id}`)
  }

  return (
    <div className="page">
      <div className="page-head">
        <div className="grow">
          <h1 className="page-title">Analyse a capture</h1>
          <div className="page-sub">Bring in an .IQ or .wav recording with its metadata. The engine infers structure, tests hypotheses and accepts only what the evidence supports.</div>
        </div>
        {engine.online ? <Tag kind="LIVE">Local engine v{engine.version}</Tag> : <Tag kind="BENCHMARK">Engine offline: replay only</Tag>}
      </div>

      <div className="panel" style={{ padding: '12px 16px', marginBottom: 14 }}>
        <div className="stepper">
          {STEPS.map((s, i) => (
            <div key={s} className="row" style={{ gap: 0 }}>
              {i > 0 && <span className="step-line" />}
              <span className={`step${i === step ? ' on' : i < step ? ' done' : ''}`}><i>{i < step ? '✓' : i + 1}</i>{s}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: 'minmax(360px, 0.8fr) minmax(0, 1.2fr)', alignItems: 'start' }}>
        <div className="col" style={{ gap: 14 }}>
          <Panel title="1 · Capture file">
            <div className={`drop${over ? ' over' : ''}`} onClick={() => inputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
              onDrop={(e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files[0]; if (f) { setFile(f); setSample(null) } }}>
              <Icon name="upload" size={26} />
              <div style={{ marginTop: 6 }}>{file ? <b>{file.name}</b> : 'Drop an .iq or .wav capture, or click to browse'}</div>
              <div className="muted" style={{ fontSize: 12 }}>{file ? `${(file.size / 1024).toFixed(1)} KB` : '.iq = interleaved float32 I/Q · .wav = int16 stereo I/Q'}</div>
              <input ref={inputRef} type="file" accept=".iq,.wav,.bin,.raw" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) { setFile(f); setSample(null) } }} />
            </div>
            <div className="divider" style={{ margin: '16px 0 10px' }}>or choose a sample recording</div>
            <div className="seg" style={{ width: '100%', marginBottom: 10 }} role="tablist">
              <button role="tab" aria-selected={sampleTab === 'real'} className={sampleTab === 'real' ? 'on' : ''} style={{ flex: 1 }} onClick={() => setSampleTab('real')}>Real transmissions · {realList.length}</button>
              <button role="tab" aria-selected={sampleTab === 'bench'} className={sampleTab === 'bench' ? 'on' : ''} style={{ flex: 1 }} onClick={() => setSampleTab('bench')}>Benchmark · {samples.length}</button>
            </div>
            {sampleTab === 'bench' && <div className="col" style={{ gap: 6 }}>
              {samples.map((s) => (
                <button key={s.name} className={`chip${sample?.name === s.name ? ' on' : ''}`} style={{ height: 'auto', padding: '7px 10px', borderRadius: 6, flexDirection: 'column', alignItems: 'flex-start', gap: 2, textAlign: 'left' }}
                  onClick={() => { setSample(s); setReal(null); setFile(null); setMeta({ ...meta, fs: String(s.fs_hz) }) }}>
                  <span className="mono" style={{ whiteSpace: 'normal' }}>{s.name}</span><span className="muted" style={{ fontSize: 11.5, whiteSpace: 'normal' }}>{s.description}</span>
                </button>
              ))}
            </div>}
            {sampleTab === 'real' && <div className="col" style={{ gap: 6 }}>
              {realList.map((e) => (
                <button key={e.id} className={`chip${real?.id === e.id ? ' on' : ''}`} style={{ height: 'auto', padding: '7px 10px', borderRadius: 6, flexDirection: 'column', alignItems: 'flex-start', gap: 2, textAlign: 'left' }}
                  onClick={() => { setReal(e); setSample(null); setFile(null) }}>
                  <span className="mono" style={{ whiteSpace: 'normal' }}>{e.station}</span><span className="muted" style={{ fontSize: 11.5, whiteSpace: 'normal' }}>{e.operator.split(' — ')[0]} · {e.frequency_khz >= 1000 ? `${e.frequency_khz / 1000} MHz` : `${e.frequency_khz} kHz`} · {e.receiver}</span>
                </button>
              ))}
            </div>}
          </Panel>
          <Panel title="2 · Capture metadata" right={<span className="muted" style={{ fontSize: 11.5 }}>recorded with the evidence</span>}>
            <div className="form-grid">
              <div className="field"><label>Monitoring station</label><select className="select" value={meta.station} onChange={(e) => setMeta({ ...meta, station: e.target.value })}>{STATIONS.map((s) => <option key={s.id} value={s.id}>{s.id} · {s.name}</option>)}</select></div>
              <div className="field"><label>Receiver location</label><input className="input mono" readOnly value={st ? `${st.lat.toFixed(2)}°N ${st.lon.toFixed(2)}°E` : ''} /></div>
              <div className="field"><label>Antenna</label><input className="input" value={meta.antenna} onChange={(e) => setMeta({ ...meta, antenna: e.target.value })} /></div>
              <div className="field"><label>Capture time (IST)</label><input className="input" type="datetime-local" value={meta.captured} onChange={(e) => setMeta({ ...meta, captured: e.target.value })} /></div>
              <div className="field"><label>Centre frequency (MHz)</label><input className="input mono" value={meta.centerMHz} onChange={(e) => setMeta({ ...meta, centerMHz: e.target.value })} /></div>
              <div className="field"><label>Bandwidth (kHz)</label><input className="input mono" value={meta.bwKHz} onChange={(e) => setMeta({ ...meta, bwKHz: e.target.value })} /></div>
              <div className="field full"><label>Sampling rate (Hz) {(file?.name ?? sample?.name ?? '').endsWith('.wav') ? '· read from the WAV header unless you enter a value' : '· a raw .iq file has no header: leave blank if unknown'}</label><input className="input mono" placeholder="Unknown — the engine works in samples per symbol" value={meta.fs} onChange={(e) => setMeta({ ...meta, fs: e.target.value })} /></div>
              <div className="field full"><label>Operator notes</label><textarea className="textarea" value={meta.notes} onChange={(e) => setMeta({ ...meta, notes: e.target.value })} placeholder="Observed intermittently on the evening watch…" /></div>
            </div>
            <button className="btn btn-primary btn-lg" style={{ width: '100%', justifyContent: 'center', marginTop: 12 }} disabled={(!file && !sample && !real) || running} onClick={() => (real ? runReal(real) : run())}>
              {running ? <><span className="spinner" /> Analysing…</> : <><Icon name="analysis" size={15} /> Analyse signal</>}
            </button>
          </Panel>
        </div>

        <div className="col" style={{ gap: 14 }}>
          <Panel title="3 · Analysis pipeline" right={replay ? <Tag kind="BENCHMARK">Replay: recorded engine output</Tag> : pack ? <Tag kind="LIVE" /> : null}>
            {progress < 0 && !pack ? <div className="empty">Choose a capture and start the analysis. Each stage reports what it established.</div> : (
              <div className="pipeline">
                {STAGES.map((s, i) => {
                  const done = pack ? true : i < progress
                  const on = !pack && i === progress && running
                  return (
                    <motion.div key={s.key} className={`stage${on ? ' run' : ''}${done ? ' done' : ''}`} initial={{ opacity: 0, x: -8 }} animate={{ opacity: i <= Math.max(progress, pack ? 99 : 0) ? 1 : 0.35, x: 0 }}>
                      <span>{done ? <Icon name="check" size={15} className="ok" /> : on ? <span className="spinner" /> : <Icon name="dash" size={14} />}</span>
                      <span className="stage-name">{s.name}</span>
                      <span className="stage-val">{pack ? stageValue(s.key, pack) : on ? 'running…' : ''}</span>
                    </motion.div>
                  )
                })}
              </div>
            )}
            {error && <div className="banner amber" style={{ marginTop: 12 }}><Icon name="info" /><span>{error}</span></div>}
          </Panel>

          <AnimatePresence>
            {realResult && (
              <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
                <Panel title="4 · Real-signal receivers" sub="Time codes, start-stop FSK and AM characterisation, run blind over the whole recording"
                  right={replay ? <Tag kind="LIVE">Recorded result</Tag> : <Tag kind="LIVE">Engine result</Tag>}>
                  <div className="row-wrap" style={{ gap: 20, alignItems: 'center' }}>
                    <motion.div initial={{ scale: 1.25, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: 'spring', stiffness: 260, damping: 18 }}>
                      <Stamp status={realResult.answer.status} size="xl" />
                    </motion.div>
                    <div className="grow" style={{ minWidth: 240 }}>
                      <div className="result-summary" style={{ maxHeight: 90 }}>{realResult.answer.summary}</div>
                      {realResult.answer.verification && <div className="mono" style={{ fontSize: 12, marginTop: 6, color: 'var(--green)' }}>arrival − decoded = {realResult.answer.verification.arrival_minus_decoded_ms.toFixed(1)} ms by the receiver&apos;s {realResult.answer.verification.timing === 'gps' ? 'GPS' : 'network'} clock</div>}
                    </div>
                  </div>
                  <div style={{ marginTop: 14 }}><BlindCatalogue runs={realResult.runs} /></div>
                  {realResult.runs.fsk?.status === 'DECODED' && realResult.runs.fsk.text && <div style={{ marginTop: 14 }}><Teletype text={realResult.runs.fsk.text} cps={400} /></div>}
                  {realResult.answer.receiver === 'am' && realResult.runs.am && <div style={{ marginTop: 14 }}><AmPanel am={realResult.runs.am} /></div>}
                  {real && <div className="row-wrap" style={{ marginTop: 14 }}><button className="btn" onClick={() => nav(`/app/monitor?rec=${real.id}`)}><Icon name="monitor" size={14} /> Watch it arrive second by second</button></div>}
                </Panel>
              </motion.div>
            )}
            {pack && !realResult && (
              <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
                <Panel title="4 · Decision" right={<span className="mono muted" style={{ fontSize: 11.5 }}>{pack.id} · {pack.result.runtime.toFixed(2)} s</span>}>
                  <div className="row-wrap" style={{ gap: 20, alignItems: 'center' }}>
                    <motion.div initial={{ scale: 1.25, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: 'spring', stiffness: 260, damping: 18 }}>
                      <Stamp status={pack.result.status} size="xl" />
                    </motion.div>
                    <div className="grow" style={{ minWidth: 240 }}>
                      <div style={{ fontSize: 15 }}>{STATUS_MEANING[pack.result.status]}</div>
                      <div className="muted" style={{ fontSize: 12.5, marginTop: 4 }}>
                        {fmtInt(pack.accept.n_hypotheses)} hypotheses evaluated · best p {fmtP(pack.accept.log10_p)} against a bar of {fmtP(pack.accept.log10_threshold)}
                      </div>
                    </div>
                  </div>
                  <div className="row-wrap" style={{ marginTop: 16 }}>
                    <button className="btn btn-primary" onClick={openRecord}><Icon name="signals" size={14} /> Open signal record</button>
                    <button className="btn" onClick={() => setShowTech(!showTech)}><Icon name="eye" size={14} /> {showTech ? 'Hide' : 'Show'} technical evidence</button>
                    <button className="btn" onClick={() => { openRecord(); }}><Icon name="incidents" size={14} /> Create incident from record</button>
                    <button className="btn btn-ghost" onClick={() => nav(`/app/reports?signal=${pack.source.kind === 'BENCHMARK' ? pack.id : recordId ?? ''}`)}><Icon name="reports" size={14} /> Report</button>
                  </div>
                </Panel>
                {showTech && (
                  <div className="grid g-2" style={{ marginTop: 14 }}>
                    <Characteristics pack={pack} />
                    <WhyPanel pack={pack} />
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
