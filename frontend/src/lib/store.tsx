import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { getToken, logout as apiLogout, onAuthChange } from './api'
import { interleaverBits } from './format'
import { buildWorld, simPack, STATIONS, type World } from './sim'
import type { AuditEvent, BenchmarkData, EvidencePack, Level, Session, SignalRecord, Zone } from './types'

export interface EngineHealth {
  online: boolean
  version?: string
  commit?: string
  checkedAt: number
}

interface ReviewEntry { action: string; t: number; by: string }

interface AppCtx {
  world: World
  signals: SignalRecord[]
  session: Session | null
  signIn: (s: Session) => void
  signOut: () => void
  level: Level
  setLevel: (l: Level) => void
  zone: Zone | null
  setZone: (z: Zone | null) => void
  engine: EngineHealth
  benchmark: BenchmarkData | null
  loadPack: (id: string) => Promise<EvidencePack>
  addUpload: (pack: EvidencePack, meta: { stationId: string; centerHz: number | null; bandwidthHz: number | null }) => SignalRecord
  reviews: Record<string, ReviewEntry>
  review: (signalId: string, action: string) => void
  notes: Record<string, { t: number; by: string; text: string }[]>
  addNote: (incidentId: string, text: string) => void
  audit: AuditEvent[]
  log: (action: string, subject: string, detail?: string) => void
  tour: { active: boolean; scene: number }
  setTour: (t: { active: boolean; scene: number }) => void
}

const Ctx = createContext<AppCtx | null>(null)

function readLS<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key)
    return v ? (JSON.parse(v) as T) : fallback
  } catch {
    return fallback
  }
}

function writeLS(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* storage unavailable: session-only */
  }
}

const BENCH_STATION = 'BENCH'

export function benchmarkRecord(p: EvidencePack, observedAt: number): SignalRecord {
  const top = p.accept.accepted_hypothesis ?? p.diagnostics.top_hypotheses[0] ?? null
  const res = p.result
  return {
    id: p.id, provenance: p.source.kind === 'UPLOAD' ? 'LIVE' : 'BENCHMARK', status: res.status, investigate: false,
    library: res.status === 'DECODED' ? 'reference' : 'unknown', stationId: p.capture.station ?? BENCH_STATION,
    band: null, centerHz: p.capture.center_freq_hz ? Number(p.capture.center_freq_hz) : null,
    bandwidthHz: p.capture.bandwidth_hz ? Number(p.capture.bandwidth_hz) : null,
    observedAt, firstSeen: observedAt, lastSeen: observedAt, occurrences: 1, modulation: res.modulation, sps: res.sps,
    cfo: res.cfo, code: res.code, interleaver: res.interleaver,
    coverage: p.accept.accepted_hypothesis ? p.accept.accepted_hypothesis.coverage_ratio : null,
    hypotheses: p.accept.n_hypotheses, log10p: p.accept.accepted_hypothesis?.log10_p ?? p.accept.log10_p,
    threshold: p.accept.log10_threshold,
    genome: genomeFromPack(p), family: -1, evidenceId: p.id,
    reason: res.status === 'DECODED' ? 'All acceptance checks passed'
      : p.accept.significant_but_rejected.length ? `Significant hypothesis rejected: ${p.accept.significant_but_rejected[0].structural_rejection}`
        : res.status === 'SIGNAL_NO_CODE' ? 'Signal detected; no catalogue code passed statistical acceptance'
          : 'No hypothesis reached significance after multiple-testing correction',
    candidates: top ? [[top.code.split('_')[1]?.toUpperCase() ?? top.code, interleaverBits(top.interleaver) ? `${interleaverBits(top.interleaver)}-bit` : 'no interleaver'].join(' / ')] : [],
    validations: 0, description: p.source.note,
  }
}

function genomeFromPack(p: EvidencePack) {
  const r = p.result
  const h = p.accept.accepted_hypothesis ?? p.diagnostics.top_hypotheses[0]
  return [
    0.5, r.modulation === 'BPSK' ? 0.3 : r.modulation === 'QPSK' ? 0.7 : 0.1, r.sps ? r.sps / 20 : 0.05, 0.5,
    r.cfo != null ? 0.5 + r.cfo * 30 : 0.1, r.code ? (r.code.includes('k7') ? 0.9 : r.code.includes('k5') ? 0.65 : 0.4) : 0.05,
    h && interleaverBits(h.interleaver) ? (interleaverBits(h.interleaver) as number) / 384 : 0.05, 0.4, Math.min(1, Math.max(0.05, 1 + p.diagnostics.detection_log10_p / -30)), 0.5,
  ]
}

export function AppProvider({ children }: { children: ReactNode }) {
  const world = useMemo(() => buildWorld(), [])
  const [session, setSession] = useState<Session | null>(() => readLS('rfap.session', null))
  const [level, setLevelState] = useState<Level>(() => readLS<Session | null>('rfap.session', null)?.role ?? 'NATIONAL')
  const [zone, setZone] = useState<Zone | null>(null)
  const [engine, setEngine] = useState<EngineHealth>({ online: false, checkedAt: 0 })
  const [benchmark, setBenchmark] = useState<BenchmarkData | null>(null)
  const [benchRecords, setBenchRecords] = useState<SignalRecord[]>([])
  const [uploads, setUploads] = useState<{ record: SignalRecord; pack: EvidencePack }[]>([])
  const [packs] = useState(() => new Map<string, EvidencePack>())
  const [reviews, setReviews] = useState<Record<string, ReviewEntry>>(() => readLS('rfap.reviews', {}))
  const [notes, setNotes] = useState<Record<string, { t: number; by: string; text: string }[]>>(() => readLS('rfap.notes', {}))
  const [audit, setAudit] = useState<AuditEvent[]>(() => readLS('rfap.audit', []))
  const [tour, setTour] = useState({ active: false, scene: 0 })

  const actor = session?.name ?? 'system'
  const log = useCallback((action: string, subject: string, detail?: string) => {
    setAudit((a) => {
      const next = [{ t: Date.now(), actor, action, subject, detail }, ...a].slice(0, 400)
      writeLS('rfap.audit', next)
      return next
    })
  }, [actor])

  useEffect(() => {
    let alive = true
    const check = async () => {
      try {
        const res = await fetch('/api/health', { cache: 'no-store' })   // public: no token needed
        const j = await res.json()
        if (alive) setEngine({ online: j.status === 'ready', version: j.engine?.version, commit: j.engine?.commit, checkedAt: Date.now() })
      } catch {
        if (alive) setEngine({ online: false, checkedAt: Date.now() })
      }
    }
    check()
    const id = setInterval(check, 15000)
    return () => { alive = false; clearInterval(id) }
  }, [])

  useEffect(() => {
    fetch('/benchmark.json').then((r) => r.json()).then(setBenchmark).catch(() => setBenchmark(null))
    fetch('/evidence/index.json').then((r) => r.json()).then(async (idx: { id: string }[]) => {
      const loaded = await Promise.all(idx.map((e) => fetch(`/evidence/${e.id}.json`).then((r) => r.json() as Promise<EvidencePack>)))
      loaded.forEach((p) => packs.set(p.id, p))
      const base = Date.now() - 2 * 3600 * 1000
      const records: SignalRecord[] = []
      loaded.forEach((p, i) => {
        // Per pack: one malformed record must not empty the whole library.
        try { records.push(benchmarkRecord(p, base - i * 17 * 60 * 1000)) } catch (err) { console.error('evidence pack skipped', p.id, err) }
      })
      setBenchRecords(records)
    }).catch((err) => { console.error('evidence index unavailable', err); setBenchRecords([]) })
  }, [packs])

  const signals = useMemo(
    () => [...uploads.map((u) => u.record), ...benchRecords, ...world.signals],
    [uploads, benchRecords, world.signals],
  )

  const loadPack = useCallback(async (id: string) => {
    const hit = packs.get(id)
    if (hit) return hit
    const up = uploads.find((u) => u.record.id === id)
    if (up) return up.pack
    if (id.startsWith('BENCH-')) {
      const p = (await (await fetch(`/evidence/${id}.json`)).json()) as EvidencePack
      packs.set(id, p)
      return p
    }
    const rec = world.signals.find((s) => s.id === id)
    if (!rec) throw new Error(`No evidence for ${id}`)
    const p = simPack(rec)
    packs.set(id, p)
    return p
  }, [packs, uploads, world.signals])

  const addUpload = useCallback((pack: EvidencePack, meta: { stationId: string; centerHz: number | null; bandwidthHz: number | null }) => {
    const rec = benchmarkRecord({ ...pack, capture: { ...pack.capture, station: meta.stationId, center_freq_hz: meta.centerHz ?? undefined, bandwidth_hz: meta.bandwidthHz ?? undefined } }, Date.now())
    rec.provenance = 'LIVE'
    rec.id = pack.id
    const band = meta.centerHz == null ? null : meta.centerHz < 30e6 ? 'HF' : meta.centerHz < 300e6 ? 'VHF' : 'UHF'
    rec.band = band
    packs.set(pack.id, pack)
    setUploads((u) => [{ record: rec, pack }, ...u])
    log('Capture analysed', pack.id, `${pack.result.status} · ${pack.accept.n_hypotheses} hypotheses`)
    return rec
  }, [packs, log])

  const review = useCallback((signalId: string, action: string) => {
    setReviews((r) => {
      const next = { ...r, [signalId]: { action, t: Date.now(), by: actor } }
      writeLS('rfap.reviews', next)
      return next
    })
    log(`Review: ${action}`, signalId)
  }, [actor, log])

  const addNote = useCallback((incidentId: string, text: string) => {
    setNotes((n) => {
      const next = { ...n, [incidentId]: [...(n[incidentId] ?? []), { t: Date.now(), by: actor, text }] }
      writeLS('rfap.notes', next)
      return next
    })
    log('Analyst note added', incidentId)
  }, [actor, log])

  const signIn = useCallback((s: Session) => {
    setSession(s)
    setLevelState(s.role)
    writeLS('rfap.session', s)
    setAudit((a) => {
      const next = [{ t: Date.now(), actor: s.name, action: `Signed in (${s.method === 'google' ? 'Google' : 'operator credentials'})`, subject: s.stationId }, ...a].slice(0, 400)
      writeLS('rfap.audit', next)
      return next
    })
  }, [])

  // The token is the session. If it goes (logout, expiry, or a 401 from any call), so does the user.
  useEffect(() => onAuthChange(() => {
    if (!getToken()) {
      setSession(null)
      try { localStorage.removeItem('rfap.session') } catch { /* ignore */ }
    }
  }), [])

  const signOut = useCallback(() => {
    log('Signed out', session?.stationId ?? '')
    void apiLogout()
    setSession(null)
    try { localStorage.removeItem('rfap.session') } catch { /* ignore */ }
  }, [log, session])

  const setLevel = useCallback((l: Level) => setLevelState(l), [])

  const value: AppCtx = {
    world, signals, session, signIn, signOut, level, setLevel, zone, setZone, engine, benchmark, loadPack,
    addUpload, reviews, review, notes, addNote, audit, log, tour, setTour,
  }
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useApp() {
  const c = useContext(Ctx)
  if (!c) throw new Error('useApp outside AppProvider')
  return c
}

export function stationName(id: string) {
  if (id === BENCH_STATION) return 'Evaluation bench (offline)'
  const s = STATIONS.find((x) => x.id === id)
  return s ? `${s.id} · ${s.name}` : id
}

export function usePack(id: string | undefined) {
  const { loadPack } = useApp()
  const [pack, setPack] = useState<EvidencePack | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    if (!id) return
    let alive = true
    setPack(null)
    loadPack(id).then((p) => alive && setPack(p)).catch((e) => alive && setError(String(e)))
    return () => { alive = false }
  }, [id, loadPack])
  return { pack, error }
}
