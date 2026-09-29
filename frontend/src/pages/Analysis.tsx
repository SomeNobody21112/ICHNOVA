import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Characteristics, Verdict, WhyPanel } from '../components/evidence'
import { AmPanel, BlindCatalogue, Teletype } from '../components/liveviz'
import type { ReplayDoc, ReplayIndexEntry, ResultEv } from '../lib/live'
import { Icon, Panel, Stamp, Tag } from '../components/ui'
import { CODE_FULL, STATUS_LABEL, fmtFs, fmtInt, fmtInterleaver, fmtP, fmtSymRate } from '../lib/format'
import { api } from '../lib/api'
import { useApp, useCan, whyNot } from '../lib/store'
import type { EvidencePack, RealAnalysis, Status } from '../lib/types'

interface Sample { name: string; format: string; fs_hz: number; bytes: number; description: string; evidence_id: string }
/** What is being decoded. Before the decode only `label` and `facts()` are shown: the blind view. */
type Source =
  | { kind: 'file'; key: string; file: File }
  | { kind: 'bench'; key: string; label: string; sample: Sample }
  | { kind: 'real'; key: string; label: string; entry: ReplayIndexEntry }

const STEPS = ['Choose', 'Detect', 'Analyse', 'Classify', 'Verify', 'Decoded']
const STAGES = ['Signal detection', 'Symbol-rate search', 'Modulation analysis', 'CFO estimation', 'FEC hypothesis search', 'Statistical validation']
const RECEIVER: Record<string, string> = { timecode: 'Time-code', fsk: 'Start-stop FSK', am: 'AM broadcast' }

const kb = (n: number) => (n < 1024 ? `${n} B` : `${(n / 1024).toFixed(1)} KB`)
const rate = (hz: number) => (hz >= 1e6 ? `${hz / 1e6} Msps` : hz >= 1e3 ? `${(hz / 1e3).toFixed(1)} ksps` : `${hz} sps`)
const khz = (f: number) => (f >= 1000 ? `${f / 1000} MHz` : `${f} kHz`)
const same = (a: unknown, b: unknown) => (b == null ? undefined : JSON.stringify(a) === JSON.stringify(b))

/** What a receiver knows before any analysis: container, size, length, clock. Nothing about content. */
function facts(s: Source): string[] {
  if (s.kind === 'file') return [s.file.name.split('.').pop()!.toUpperCase(), kb(s.file.size)]
  if (s.kind === 'bench') {
    const n = s.sample.format === 'wav' ? (s.sample.bytes - 44) / 4 : s.sample.bytes / 8
    return [s.sample.format.toUpperCase(), kb(s.sample.bytes), `${fmtInt(n)} samples`, rate(s.sample.fs_hz)]
  }
  return ['WAV', s.entry.duration_s ? `${Math.round(s.entry.duration_s)} s` : 'length unknown', 'GPS-timed']
}

interface Row { k: string; after: string | null; expected?: string | null; ok?: boolean }

function packRows(p: EvidencePack, truth: EvidencePack | null): Row[] {
  const r = p.result, fs = p.capture.fs_hz, t = truth?.benchmark_truth as Record<string, unknown> | undefined
  const present = p.diagnostics.detection_log10_p <= Math.log10(p.accept.alpha)
  return [
    // The detector's line test is blind to QPSK (no x² line); an accepted decode proves presence on its own.
    { k: 'Signal present', after: present ? `Yes · p ${fmtP(p.diagnostics.detection_log10_p)}` : r.status === 'DECODED' ? 'Yes · proven by the decode' : null },
    { k: 'Modulation', after: r.modulation, expected: t?.modulation as string, ok: r.modulation ? same(r.modulation, t?.modulation) : undefined },
    { k: 'Symbol rate', after: r.sps ? `${r.sps} samples/symbol · ${fmtSymRate(r.sps, fs)}` : null, expected: t?.sps ? `${t.sps} samples/symbol` : null, ok: r.sps ? same(r.sps, t?.sps) : undefined },
    { k: 'Carrier offset', after: r.cfo == null ? null : fs ? `${(r.cfo * fs).toFixed(0)} Hz` : `${r.cfo.toFixed(4)} cycles/sample` },
    { k: 'Error-correcting code', after: r.code ? CODE_FULL[r.code] ?? r.code : null, expected: t?.code ? CODE_FULL[t.code as string] ?? String(t.code) : null, ok: r.code ? same(r.code, t?.code) : undefined },
    { k: 'Interleaver', after: r.interleaver ? fmtInterleaver(r.interleaver) : null, expected: t?.interleaver ? fmtInterleaver(t.interleaver as number[]) : null, ok: r.interleaver ? same(r.interleaver, t?.interleaver) : undefined },
    { k: 'Payload', after: r.payload_withheld ? 'Withheld: failed the consistency floor' : r.status === 'DECODED' && r.payload_len ? `${fmtInt(r.payload_len)} bits recovered` : null },
    ...(truth ? [{ k: 'Verdict', after: STATUS_LABEL[r.status], expected: STATUS_LABEL[truth.result.status], ok: r.status === truth.result.status }] : []),
  ]
}

function realRows(rr: RealAnalysis, entry: ReplayIndexEntry | null): Row[] {
  const a = rr.answer
  return [
    { k: 'Receiver that locked', after: a.status === 'UNKNOWN' ? null : RECEIVER[a.receiver ?? ''] ?? a.receiver ?? null },
    { k: 'Protocol', after: a.protocol ?? null, expected: entry?.answer.protocol, ok: a.protocol ? same(a.protocol, entry?.answer.protocol) : undefined },
    { k: 'Decoded content', after: a.summary ?? null },
    { k: 'Operator', after: a.operator ?? null },
    ...(entry ? [{ k: 'Station', after: `${entry.station} · ${khz(entry.frequency_khz)}` }] : []),
  ]
}

/** One row per blind receiver the engine ran, with what it found. BlindCatalogue only covers time codes. */
function ReceiversTried({ runs }: { runs: RealAnalysis['runs'] }) {
  const r = runs as Record<string, { status?: string; reason?: string; protocol?: string | null; code?: string; baud?: number; modulation?: string; carrier_to_noise_db?: number; packets?: unknown[] } | undefined>
  const rows = [
    { key: 'timecode', name: 'Time-code', what: (x: NonNullable<typeof r[string]>) => x.protocol ?? x.reason },
    { key: 'fsk', name: 'Start-stop FSK', what: (x: NonNullable<typeof r[string]>) => x.code ? `${x.code} ${x.baud} Bd` : x.reason },
    { key: 'chu', name: 'CHU (Canada)', what: (x: NonNullable<typeof r[string]>) => x.packets?.length ? `${x.packets.length} packets` : 'no packets found' },
    { key: 'am', name: 'AM broadcast', what: (x: NonNullable<typeof r[string]>) => x.modulation ? `${x.modulation}${x.carrier_to_noise_db != null ? ` · ${x.carrier_to_noise_db} dB C/N` : ''}` : x.reason },
  ].filter((x) => r[x.key])
  if (!rows.length) return <div className="muted">No receiver results were recorded for this capture.</div>
  return (
    <div className="catalogue">
      <div className="catalogue-head"><span>Receivers tried</span><span className="mono">{rows.length} run</span></div>
      {rows.map((x) => {
        const run = r[x.key]!, st = run.status ?? 'UNKNOWN'
        return (
          <div key={x.key} className={`tried-row${st === 'DECODED' ? ' ok' : st === 'SIGNAL_NO_CODE' ? ' mid' : ''}`}>
            <b>{x.name}</b>
            <span className="muted">{x.what(run) ?? ''}</span>
            <span className="catalogue-verdict">{STATUS_LABEL[st as Status] ?? st}</span>
          </div>
        )
      })}
    </div>
  )
}

export default function Analysis() {
  const { engine, session, addUpload, log, loadPack } = useApp()
  const mayAnalyse = useCan('analyse')
  const cannotAnalyse = whyNot(session?.authRole, 'analyse')
  const nav = useNavigate()
  const [samples, setSamples] = useState<Sample[]>([])
  const [realList, setRealList] = useState<ReplayIndexEntry[]>([])
  const [tab, setTab] = useState<'real' | 'bench' | 'file'>('real')
  const [file, setFile] = useState<File | null>(null)
  const [over, setOver] = useState(false)
  const [meta, setMeta] = useState({ fs: '', captured: '', notes: '' })
  const [src, setSrc] = useState<Source | null>(null)
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState(-1)
  const [pack, setPack] = useState<EvidencePack | null>(null)
  const [truth, setTruth] = useState<EvidencePack | null>(null)
  const [realResult, setRealResult] = useState<RealAnalysis | null>(null)
  const [replay, setReplay] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [recordId, setRecordId] = useState<string | null>(null)
  const [showTech, setShowTech] = useState(false)
  const [solved, setSolved] = useState<Record<string, Status>>({})
  const inputRef = useRef<HTMLInputElement>(null)
  const resultRef = useRef<HTMLDivElement>(null)

  useEffect(() => { fetch('/samples/samples.json').then((r) => r.json()).then(setSamples).catch(() => setSamples([])) }, [])
  useEffect(() => { fetch('/live/index.json').then((r) => r.json()).then((x: ReplayIndexEntry[]) => setRealList(x.filter((e) => e.mode === 'iq'))).catch(() => setRealList([])) }, [])

  // Replaying recorded output needs no engine rights; running the engine does.
  const canRun = engine.online ? mayAnalyse : true
  const done = !!(pack || realResult)
  const step = done ? STEPS.length : running ? 1 + Math.min(3, Math.floor(progress / 2)) : src ? 1 : 0

  const post = async (q: URLSearchParams, body: ArrayBuffer) => {
    const res = await api(`/api/analyze?${q}`, { method: 'POST', body })
    const j = await res.json().catch(() => ({}))
    if (!res.ok || !j.result) throw new Error(j.error ?? `Engine returned HTTP ${res.status}`)
    return j as EvidencePack
  }

  const decode = async (s: Source) => {
    if (running || !canRun) return
    setSrc(s); setError(null); setPack(null); setTruth(null); setRealResult(null); setRecordId(null); setShowTech(false); setReplay(false)
    setRunning(true); setProgress(0)
    const tick = setInterval(() => setProgress((p) => Math.min(p + 1, STAGES.length - 1)), 420)
    const t0 = Date.now()
    try {
      let status: Status
      if (s.kind === 'real') {
        const e = s.entry
        if (engine.online) {
          const c = (await (await api(`/api/recordings/${e.id}.json`)).json()).capture
          const body = await (await api(`/api/recordings/${e.id}.wav`)).arrayBuffer()
          // Blind: only the clock goes in (sample rate, GPS time). No station, no frequency.
          const p = await post(new URLSearchParams({ format: 'wav', fs: String(c.fs_hz), name: `${s.label}.wav`, t0_unix: String(c.t0_unix), timing: c.timing }), body)
          if (!p.real) throw new Error('The engine returned no real-signal result for this recording')
          setPack(p); setRealResult(p.real)
          status = p.real.answer.status
        } else {
          const doc = (await (await fetch(`/live/${e.id}.json`)).json()) as ReplayDoc
          const r = doc.events.find((x): x is ResultEv => x.type === 'result')
          if (!r?.runs) throw new Error('Recorded result missing for this recording')
          setRealResult({ samples: 0, fs_hz: 0, duration_s: e.duration_s ?? 0, timing: null, t0_unix: null, runs: r.runs, timers_s: {}, answer: r.answer })
          setReplay(true)
          status = r.answer.status
        }
      } else {
        let p: EvidencePack
        if (engine.online) {
          const name = s.kind === 'file' ? s.file.name : s.sample.name
          const body = s.kind === 'file' ? await s.file.arrayBuffer() : await (await fetch(`/samples/${s.sample.name}`)).arrayBuffer()
          const fs = s.kind === 'bench' ? String(s.sample.fs_hz) : meta.fs.trim()
          const q = new URLSearchParams({ format: name.toLowerCase().endsWith('.wav') ? 'wav' : 'iq', name, ...(fs ? { fs } : {}) })
          if (s.kind === 'file') {
            if (meta.captured) q.set('captured_at', meta.captured)
            if (meta.notes) q.set('notes', meta.notes)
            if (session?.stationId) q.set('station', session.stationId)
          }
          p = await post(q, body)
        } else if (s.kind === 'bench') {
          p = await loadPack(s.sample.evidence_id)
          setReplay(true)
        } else {
          throw new Error('The local analysis engine is offline. Start it with "python server/app.py", or pick a sample recording to replay recorded engine output.')
        }
        if (s.kind === 'bench') setTruth(await loadPack(s.sample.evidence_id).catch(() => null))
        setPack(p)
        status = p.result.status
      }
      // Let the pipeline finish animating so the stages read as work, not a flash.
      await new Promise((r) => setTimeout(r, Math.max(0, 420 * STAGES.length - (Date.now() - t0))))
      setProgress(STAGES.length)
      setSolved((m) => ({ ...m, [s.key]: status }))
      log(engine.online ? 'Capture decoded by local engine' : 'Recorded engine output replayed', s.kind === 'file' ? s.file.name : s.label, status)
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
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
    const rec = recordId ? { id: recordId } : addUpload(pack, { stationId: session?.stationId ?? 'MS-07', centerHz: null, bandwidthHz: null })
    setRecordId(rec.id)
    nav(`/app/signals/${rec.id}`)
  }

  const rows = realResult ? realRows(realResult, src?.kind === 'real' ? src.entry : null) : pack ? packRows(pack, truth) : null
  const hasExpected = !!rows?.some((r) => r.expected)

  const card = (s: Source) => {
    const st = solved[s.key], on = src?.key === s.key
    return (
      <button key={s.key} className={`capcard${on ? ' on' : ''}`} disabled={running || !canRun} title={canRun ? 'Decode this recording' : cannotAnalyse}
        onClick={() => decode(s)} aria-pressed={on}>
        <span className="capcard-top">
          <span className="capcard-name">{s.kind === 'file' ? s.file.name : s.label}</span>
          {on && running ? <span className="spinner" /> : st ? <span className={`capcard-st st-${st}`}>{STATUS_LABEL[st]}</span> : <span className="capcard-go"><Icon name="analysis" size={13} /> Decode</span>}
        </span>
        <span className="capcard-facts">{facts(s).map((f) => <span key={f}>{f}</span>)}</span>
        {st && s.kind === 'real' && <span className="capcard-reveal">{s.entry.station} · {khz(s.entry.frequency_khz)}</span>}
        {st && s.kind === 'bench' && <span className="capcard-reveal">{s.sample.description}</span>}
      </button>
    )
  }

  return (
    <div className="page">
      <div className="page-head">
        <div className="grow">
          <h1 className="page-title">Analyse a capture</h1>
          <div className="page-sub">Blind decoding: the engine gets the samples and their clock, nothing else. It has to find the signal, its structure and its content on its own, or refuse.</div>
        </div>
        {engine.online ? <Tag kind="LIVE">Local engine v{engine.version}</Tag> : <Tag kind="BENCHMARK">Engine offline: replaying recorded output</Tag>}
      </div>

      <div className="panel" style={{ padding: '12px 16px', marginBottom: 14 }}>
        <div className="stepper">
          {STEPS.map((s, i) => (
            <div key={s} className="row" style={{ gap: 0 }}>
              {i > 0 && <span className="step-line" />}
              <span className={`step${i === step ? ' on' : i < step ? ' done' : ''}`}><i>{i < step ? <Icon name="check" size={11} /> : i + 1}</i>{s}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="analyse-grid">
        <Panel title="1 · Choose a capture" sub="Click a recording to decode it. What it is stays hidden until the engine has answered.">
          <div className="seg" style={{ width: '100%', marginBottom: 12 }} role="tablist">
            <button role="tab" aria-selected={tab === 'real'} className={tab === 'real' ? 'on' : ''} style={{ flex: 1 }} onClick={() => setTab('real')}>Real · {realList.length}</button>
            <button role="tab" aria-selected={tab === 'bench'} className={tab === 'bench' ? 'on' : ''} style={{ flex: 1 }} onClick={() => setTab('bench')}>Benchmark · {samples.length}</button>
            <button role="tab" aria-selected={tab === 'file'} className={tab === 'file' ? 'on' : ''} style={{ flex: 1 }} onClick={() => setTab('file')}>Upload</button>
          </div>

          {!canRun && <div className="banner amber" style={{ marginBottom: 12 }}><Icon name="info" /><span>{cannotAnalyse}</span></div>}

          {tab === 'real' && <div className="capcards">
            {realList.map((e, i) => card({ kind: 'real', key: e.id, label: `Recording ${String(i + 1).padStart(2, '0')}`, entry: e }))}
          </div>}
          {tab === 'bench' && <div className="capcards">
            {samples.map((s, i) => card({ kind: 'bench', key: s.name, label: `Benchmark ${String.fromCharCode(65 + i)}`, sample: s }))}
          </div>}
          {tab === 'file' && <>
            <div className={`drop${over ? ' over' : ''}`} onClick={() => inputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
              onDrop={(e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files[0]; if (f) setFile(f) }}>
              <Icon name="upload" size={24} />
              <div style={{ marginTop: 6 }}>{file ? <b>{file.name}</b> : 'Drop an .iq or .wav capture, or click to browse'}</div>
              <div className="muted" style={{ fontSize: 12 }}>{file ? kb(file.size) : '.iq = interleaved float32 I/Q · .wav = int16 stereo I/Q'}</div>
              <input ref={inputRef} type="file" accept=".iq,.wav,.bin,.raw" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) setFile(f) }} />
            </div>
            <div className="section-label" style={{ margin: '16px 0 8px' }}>Basic capture info · all optional</div>
            <div className="form-grid">
              <div className="field full"><label>Sampling rate (Hz) · {file?.name.toLowerCase().endsWith('.wav') ? 'read from the WAV header if blank' : 'a raw .iq has no header: leave blank if unknown'}</label>
                <input className="input mono" inputMode="decimal" placeholder="Unknown" value={meta.fs} onChange={(e) => setMeta({ ...meta, fs: e.target.value })} /></div>
              <div className="field"><label>Capture time (IST)</label><input className="input" type="datetime-local" value={meta.captured} onChange={(e) => setMeta({ ...meta, captured: e.target.value })} /></div>
              <div className="field"><label>Notes</label><input className="input" value={meta.notes} onChange={(e) => setMeta({ ...meta, notes: e.target.value })} placeholder="Heard on the evening watch" /></div>
            </div>
            <button className="btn btn-primary btn-lg" style={{ width: '100%', justifyContent: 'center', marginTop: 12 }} disabled={!file || running || !canRun} title={cannotAnalyse}
              onClick={() => file && decode({ kind: 'file', key: `file:${file.name}:${file.size}`, file })}>
              {running ? <><span className="spinner" /> Decoding…</> : <><Icon name="analysis" size={15} /> Decode blind</>}
            </button>
          </>}
        </Panel>

        <div className="col" style={{ gap: 14, scrollMarginTop: 16 }} ref={resultRef}>
          <Panel title="2 · Blind → Decoded" sub={src ? `${src.kind === 'file' ? src.file.name : src.label} · given: ${facts(src).join(' · ')}` : undefined}
            right={replay ? <Tag kind="BENCHMARK">Replay</Tag> : done ? <Tag kind="LIVE">Engine result</Tag> : null}>
            {!src && <div className="empty">Pick a recording on the left. This panel shows what the engine was given and what it established from the samples alone.</div>}
            {src && !done && (
              <div className="pipeline">
                {STAGES.map((name, i) => {
                  const ok = i < progress, on = i === progress && running
                  return (
                    <motion.div key={name} className={`stage${on ? ' run' : ''}${ok ? ' done' : ''}`} initial={{ opacity: 0, x: -8 }} animate={{ opacity: i <= progress ? 1 : 0.35, x: 0 }}>
                      <span>{ok ? <Icon name="check" size={15} className="ok" /> : on ? <span className="spinner" /> : <Icon name="dash" size={14} />}</span>
                      <span className="stage-name">{name}</span>
                      <span className="stage-val">{on ? 'running…' : ''}</span>
                    </motion.div>
                  )
                })}
              </div>
            )}
            {rows && (
              <div className="bdtab-wrap">
                <table className="bdtab">
                  <thead><tr><th>Property</th><th>Before</th><th>Decoded</th>{hasExpected && <th>Expected</th>}</tr></thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.k}>
                        <th scope="row">{r.k}</th>
                        <td className="muted mono">?</td>
                        <td className={r.after ? '' : 'muted'}>{r.after ?? 'Not established'}</td>
                        {hasExpected && <td className="muted">{r.expected ?? ''}{r.ok !== undefined && <b className={r.ok ? 'bdtab-ok' : 'bdtab-bad'}>{r.ok ? ' ✓' : ' ✗'}</b>}</td>}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {error && <div className="banner amber" style={{ marginTop: 12 }}><Icon name="info" /><span>{error}</span></div>}
          </Panel>

          <AnimatePresence>
            {realResult && (
              <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
                <Panel title="3 · Decode" sub="Time codes, start-stop FSK and AM characterisation, run blind over the whole recording">
                  <div className="row-wrap" style={{ gap: 20, alignItems: 'center' }}>
                    <Stamp status={realResult.answer.status} size="xl" />
                    <div className="grow" style={{ minWidth: 240 }}>
                      <div className="result-summary">{realResult.answer.summary}</div>
                      {realResult.answer.verification && <div className="mono" style={{ fontSize: 12, marginTop: 6, color: 'var(--green)' }}>arrival − decoded = {realResult.answer.verification.arrival_minus_decoded_ms.toFixed(1)} ms by the receiver&apos;s {realResult.answer.verification.timing === 'gps' ? 'GPS' : 'network'} clock</div>}
                    </div>
                  </div>
                  {realResult.runs.fsk?.status === 'DECODED' && realResult.runs.fsk.text && <div style={{ marginTop: 14 }}><Teletype text={realResult.runs.fsk.text} cps={400} /></div>}
                  {realResult.answer.receiver === 'am' && realResult.runs.am && <div style={{ marginTop: 14 }}><AmPanel am={realResult.runs.am} /></div>}
                  <div className="row-wrap" style={{ marginTop: 14 }}>
                    <button className="btn" onClick={() => setShowTech(!showTech)}><Icon name="eye" size={14} /> {showTech ? 'Hide' : 'Show'} every receiver tried</button>
                    {src?.kind === 'real' && <button className="btn" onClick={() => nav(`/app/monitor?rec=${src.entry.id}`)}><Icon name="monitor" size={14} /> Watch it arrive second by second</button>}
                  </div>
                  {showTech && <div style={{ marginTop: 14 }}><ReceiversTried runs={realResult.runs} /><div style={{ marginTop: 12 }}><BlindCatalogue runs={realResult.runs} /></div></div>}
                </Panel>
              </motion.div>
            )}
            {pack && !realResult && (
              <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
                <Panel title="3 · Decision" right={<span className="mono muted" style={{ fontSize: 11.5 }}>{pack.id} · {pack.result.runtime.toFixed(2)} s · {fmtFs(pack.capture)}</span>}>
                  <Verdict pack={pack} />
                  <div className="row-wrap" style={{ marginTop: 16 }}>
                    <button className="btn btn-primary" onClick={openRecord}><Icon name="signals" size={14} /> Open signal record</button>
                    <button className="btn" onClick={() => setShowTech(!showTech)}><Icon name="eye" size={14} /> {showTech ? 'Hide' : 'Show'} technical evidence</button>
                    <button className="btn btn-ghost" onClick={() => nav(`/app/reports?signal=${pack.source.kind === 'BENCHMARK' ? pack.id : recordId ?? ''}`)}><Icon name="reports" size={14} /> Report</button>
                  </div>
                </Panel>
                {showTech && (
                  <div className="grid g-2" style={{ marginTop: 14 }}>
                    <Characteristics pack={pack} />
                    <WhyPanel pack={pack} inVerdict />
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
