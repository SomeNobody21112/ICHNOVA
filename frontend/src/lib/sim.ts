// Deterministic simulated monitoring world. Everything here is SIMULATED and labelled as such
// in the UI. Only the benchmark evidence packs (public/evidence) come from the real engine.
import type { Anomaly, Band, EvidencePack, Hyp, Incident, SignalRecord, Station, Status, Zone } from './types'

function mulberry32(seed: number) {
  return () => {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export const ZONES: { id: Zone; name: string }[] = [
  { id: 'NORTH', name: 'North' }, { id: 'WEST', name: 'West' }, { id: 'CENTRAL', name: 'Central' },
  { id: 'EAST', name: 'East' }, { id: 'NORTHEAST', name: 'North-East' }, { id: 'SOUTH', name: 'South' },
]

export const STATIONS: Station[] = [
  { id: 'MS-01', name: 'Delhi', zone: 'NORTH', lat: 28.61, lon: 77.21, bands: ['HF', 'VHF', 'UHF'], health: 'NOMINAL', clock: 'SYNCED' },
  { id: 'MS-02', name: 'Jalandhar', zone: 'NORTH', lat: 31.33, lon: 75.58, bands: ['HF', 'VHF'], health: 'NOMINAL', clock: 'SYNCED' },
  { id: 'MS-03', name: 'Lucknow', zone: 'NORTH', lat: 26.85, lon: 80.95, bands: ['VHF', 'UHF'], health: 'NOMINAL', clock: 'SYNCED' },
  { id: 'MS-04', name: 'Jaipur', zone: 'NORTH', lat: 26.91, lon: 75.79, bands: ['HF', 'UHF'], health: 'DEGRADED', clock: 'DRIFT' },
  { id: 'MS-05', name: 'Mumbai', zone: 'WEST', lat: 19.08, lon: 72.88, bands: ['HF', 'VHF', 'UHF'], health: 'NOMINAL', clock: 'SYNCED' },
  { id: 'MS-06', name: 'Ahmedabad', zone: 'WEST', lat: 23.02, lon: 72.57, bands: ['VHF', 'UHF'], health: 'NOMINAL', clock: 'SYNCED' },
  { id: 'MS-07', name: 'Nagpur', zone: 'CENTRAL', lat: 21.15, lon: 79.09, bands: ['HF', 'VHF', 'UHF'], health: 'NOMINAL', clock: 'SYNCED' },
  { id: 'MS-08', name: 'Bhopal', zone: 'CENTRAL', lat: 23.26, lon: 77.41, bands: ['HF', 'VHF'], health: 'NOMINAL', clock: 'SYNCED' },
  { id: 'MS-09', name: 'Kolkata', zone: 'EAST', lat: 22.57, lon: 88.36, bands: ['HF', 'VHF', 'UHF'], health: 'NOMINAL', clock: 'SYNCED' },
  { id: 'MS-10', name: 'Bhubaneswar', zone: 'EAST', lat: 20.3, lon: 85.82, bands: ['VHF', 'UHF'], health: 'NOMINAL', clock: 'SYNCED' },
  { id: 'MS-11', name: 'Guwahati', zone: 'NORTHEAST', lat: 26.14, lon: 91.74, bands: ['HF', 'VHF', 'UHF'], health: 'NOMINAL', clock: 'SYNCED' },
  { id: 'MS-12', name: 'Shillong', zone: 'NORTHEAST', lat: 25.58, lon: 91.89, bands: ['HF', 'VHF'], health: 'DEGRADED', clock: 'SYNCED' },
  { id: 'MS-13', name: 'Chennai', zone: 'SOUTH', lat: 13.08, lon: 80.27, bands: ['HF', 'VHF', 'UHF'], health: 'NOMINAL', clock: 'SYNCED' },
  { id: 'MS-14', name: 'Bengaluru', zone: 'SOUTH', lat: 12.97, lon: 77.59, bands: ['VHF', 'UHF'], health: 'NOMINAL', clock: 'SYNCED' },
  { id: 'MS-15', name: 'Thiruvananthapuram', zone: 'SOUTH', lat: 8.52, lon: 76.94, bands: ['HF', 'VHF'], health: 'NOMINAL', clock: 'SYNCED' },
  { id: 'MS-16', name: 'Port Blair', zone: 'SOUTH', lat: 11.62, lon: 92.73, bands: ['HF', 'UHF'], health: 'NOMINAL', clock: 'SYNCED' },
]

export const BANDS: { id: Band; lo: number; hi: number; label: string }[] = [
  { id: 'HF', lo: 3e6, hi: 30e6, label: 'HF 3–30 MHz' },
  { id: 'VHF', lo: 30e6, hi: 300e6, label: 'VHF 30–300 MHz' },
  { id: 'UHF', lo: 300e6, hi: 3e9, label: 'UHF 0.3–3 GHz' },
]

export const GENOME_AXES = [
  'Frequency profile', 'Modulation', 'Symbol structure', 'Bandwidth', 'CFO behaviour',
  'FEC hypothesis', 'Interleaver structure', 'Temporal behaviour', 'Spectral occupancy', 'Capture environment',
]

const CODES = ['conv_k7_r12_171_133', 'conv_k5_r12_23_35', 'conv_k3_r12_7_5']
const DIMS: number[][] = [[6, 10], [8, 15], [10, 12], [12, 20], [16, 24], [8, 16], [5, 24], [10, 24]]
export const DAY = 86400000

export interface World {
  now: number
  stations: Station[]
  signals: SignalRecord[]
  incidents: Incident[]
  anomalies: Anomaly[]
}

export function buildWorld(now = Date.now()): World {
  const r = mulberry32(26147)
  const pick = <T,>(a: T[]) => a[Math.floor(r() * a.length)]
  const signals: SignalRecord[] = []

  // Emitter families: recurring behaviour that similarity search can find again.
  const families = Array.from({ length: 26 }, (_, f) => {
    const band = pick<Band>(['HF', 'HF', 'VHF', 'VHF', 'UHF'])
    const b = BANDS.find((x) => x.id === band)!
    const center = band === 'HF' ? b.lo + r() * (b.hi - b.lo) : Math.exp(Math.log(b.lo) + r() * (Math.log(b.hi) - Math.log(b.lo)))
    const status: Status = f < 14 ? 'DECODED' : f < 20 ? 'SIGNAL_NO_CODE' : 'UNKNOWN'
    return {
      band, center: Math.round(center / 12.5e3) * 12.5e3,
      bw: band === 'HF' ? 3e3 + r() * 9e3 : band === 'VHF' ? 12.5e3 + r() * 12.5e3 : 25e3 + r() * 175e3,
      mod: r() < 0.55 ? 'QPSK' : 'BPSK', sps: pick([4, 5, 6, 8, 10]), code: pick(CODES), dims: pick(DIMS),
      status, stations: Array.from(new Set([pick(STATIONS).id, pick(STATIONS).id].slice(0, 1 + Math.floor(r() * 2)))),
      genome: Array.from({ length: 10 }, () => 0.15 + r() * 0.8),
    }
  })

  for (let i = 0; i < 168; i++) {
    const fi = Math.floor(Math.pow(r(), 1.25) * families.length)
    const fam = families[fi]
    let status = fam.status
    if (status === 'DECODED' && r() < 0.14) status = 'SIGNAL_NO_CODE'
    if (status !== 'UNKNOWN' && r() < 0.06) status = 'UNKNOWN'
    const observedAt = now - Math.floor(Math.pow(r(), 1.6) * 30 * DAY)
    const stationId = r() < 0.8 ? pick(fam.stations) : pick(STATIONS).id
    const decoded = status === 'DECODED'
    const hypotheses = 3000 + Math.floor(r() * 22000)
    const threshold = Math.log10(0.01 / hypotheses)
    const occurrences = 1 + Math.floor(Math.pow(r(), 3) * 60)
    const investigate = status !== 'DECODED' && (occurrences > 12 || r() < 0.12)
    const library = investigate ? 'unknown' : decoded ? (occurrences > 8 ? 'recurrent' : r() < 0.15 ? 'reference' : 'known')
      : r() < 0.2 ? 'archived' : 'unknown'
    const coverage = decoded ? 0.82 + r() * 0.17 : null
    signals.push({
      id: `SIG-2026-${String(4200 + i * 7 + Math.floor(r() * 5)).padStart(6, '0')}`,
      provenance: 'SIMULATED', status, investigate, library, stationId, band: fam.band,
      centerHz: fam.center + (r() - 0.5) * 2000, bandwidthHz: fam.bw * (0.9 + r() * 0.2),
      observedAt, firstSeen: observedAt - Math.floor(r() * 12 * DAY), lastSeen: observedAt, occurrences,
      modulation: status === 'UNKNOWN' && r() < 0.5 ? null : fam.mod,
      sps: status === 'UNKNOWN' ? null : fam.sps, cfo: status === 'UNKNOWN' ? null : (r() - 0.5) * 0.02,
      code: decoded ? fam.code : null, interleaver: decoded ? fam.dims : null, coverage, hypotheses,
      log10p: decoded ? threshold - 1 - r() * 20 : threshold + 0.5 + r() * 4, threshold,
      genome: fam.genome.map((g) => Math.min(1, Math.max(0, g + (r() - 0.5) * 0.12))), family: fi,
      evidenceId: '', reason: decoded ? 'All acceptance checks passed' : status === 'SIGNAL_NO_CODE'
        ? 'Signal detected; no catalogue code passed statistical acceptance' : 'No hypothesis reached significance',
      candidates: decoded ? [] : [`${fam.code.split('_')[1].toUpperCase()} / ${fam.dims[0] * fam.dims[1]}-bit`, `${pick(CODES).split('_')[1].toUpperCase()} / ${pick(DIMS).reduce((a, b) => a * b)}-bit`],
      validations: decoded ? Math.floor(r() * 4) : 0,
    })
  }
  signals.forEach((s) => (s.evidenceId = s.id))
  signals.sort((a, b) => b.observedAt - a.observedAt)

  const unknownFamilies = families.map((f, i) => ({ f, i })).filter((x) => x.f.status !== 'DECODED')
  const kinds = ['Repeated unexplained transmission', 'Harmful interference report', 'Unlicensed band occupancy',
    'New signal class', 'Cross-region recurring emitter', 'Intermittent wideband burst']
  const incidents: Incident[] = unknownFamilies.slice(0, 8).map(({ f, i }, k) => {
    const fam = signals.filter((s) => s.family === i)
    const events = fam.map((s) => ({ t: s.observedAt, stationId: s.stationId, signalId: s.id }))
    const extra = 8 + Math.floor(r() * 36)
    for (let e = 0; e < extra; e++) {
      const base = fam[0]?.observedAt ?? now
      events.push({ t: base - Math.floor(r() * 3 * DAY), stationId: pick(f.stations), signalId: fam[0]?.id ?? '' })
    }
    events.sort((a, b) => a.t - b.t)
    const stationIds = Array.from(new Set(events.map((e) => e.stationId)))
    fam.forEach((s) => (s.incidentId = `INC-2026-${String(19 + k).padStart(3, '0')}`))
    return {
      id: `INC-2026-${String(19 + k).padStart(3, '0')}`, title: `${kinds[k % kinds.length]} · ${f.band} ${(f.center / 1e6).toFixed(3)} MHz`,
      kind: kinds[k % kinds.length], priority: k < 3 ? 'HIGH' : k < 6 ? 'MEDIUM' : 'LOW',
      status: k === 0 || k === 2 ? 'UNDER INVESTIGATION' : k === 7 ? 'CLOSED' : k % 2 ? 'OPEN' : 'MONITORING',
      firstSeen: events[0]?.t ?? now, lastSeen: events[events.length - 1]?.t ?? now, stationIds,
      signalIds: fam.map((s) => s.id), events,
      summary: `${events.length} observations across ${stationIds.length} station${stationIds.length > 1 ? 's' : ''}; ` +
        `no catalogue code established. Pattern persists across capture windows.`,
    }
  })

  const reasonPool = ['New frequency occupancy', 'Unseen signal fingerprint', 'Temporal pattern differs from baseline',
    'Occupancy above station baseline', 'New modulation pattern at this location', 'Repeated unexplained transmission']
  const anomalies: Anomaly[] = signals.filter((s) => s.investigate).slice(0, 14).map((s, k) => ({
    id: `ANM-${String(310 + k)}`, stationId: s.stationId, band: s.band ?? 'VHF', score: 0.55 + r() * 0.44,
    reasons: reasonPool.filter(() => r() < 0.45).slice(0, 3).concat(reasonPool[k % reasonPool.length]).filter((v, i, a) => a.indexOf(v) === i),
    signalId: s.id, detectedAt: s.observedAt, kind: k % 3 === 0 ? 'Recurring' : k % 3 === 1 ? 'New' : 'Persistent',
  }))

  return { now, stations: STATIONS, signals, incidents, anomalies }
}

/** Band occupancy 0..1 for a station, band and hour offset (simulated, diurnal + station bias). */
export function occupancy(stationIdx: number, bandIdx: number, hour: number, channel = 0) {
  const x = Math.sin(stationIdx * 12.9898 + bandIdx * 78.233 + channel * 37.719 + Math.floor(hour) * 0.61) * 43758.5453
  const noise = x - Math.floor(x)
  const diurnal = 0.5 + 0.35 * Math.sin(((hour % 24) - 6) / 24 * Math.PI * 2)
  const hot = (channel * 7 + stationIdx * 3 + bandIdx) % 11 === 0 ? 0.35 : 0
  return Math.min(1, Math.max(0, 0.18 + 0.45 * diurnal * noise + hot))
}

export function cosine(a: number[], b: number[]) {
  let dot = 0, na = 0, nb = 0
  for (let i = 0; i < a.length; i++) { dot += a[i] * b[i]; na += a[i] * a[i]; nb += b[i] * b[i] }
  return dot / (Math.sqrt(na * nb) + 1e-12)
}

/** A simulated evidence pack in the real pack schema, so every page works for simulated records. */
export function simPack(s: SignalRecord): EvidencePack {
  const r = mulberry32(parseInt(s.id.replace(/\D/g, ''), 10) || 7)
  const M = s.hypotheses
  const thr = s.threshold ?? Math.log10(0.01 / M)
  const codes = ['K7', 'K5', 'K3']
  const n = 2600
  const all = { code: [] as string[], rows: [] as number[], cols: [] as number[], sps: [] as number[], modulation: [] as string[],
    cfo: [] as number[], n_checks: [] as number[], n_positive: [] as number[], log10_p: [] as number[] }
  for (let k = 0; k < n; k++) {
    const d = DIMS[Math.floor(r() * DIMS.length)]
    const checks = Math.floor(d[0] * d[1] / 2) - 6
    all.code.push(codes[Math.floor(r() * 3)]); all.rows.push(d[0]); all.cols.push(d[1])
    all.sps.push(s.sps ?? 4 + Math.floor(r() * 6)); all.modulation.push(r() < 0.5 ? 'BPSK' : 'QPSK')
    all.cfo.push((r() - 0.5) * 0.02); all.n_checks.push(checks)
    const pos = Math.floor(checks * (0.5 + (r() - 0.5) * 0.2)); all.n_positive.push(pos)
    all.log10_p.push(-Math.abs(r() * r() * 4))
  }
  const decoded = s.status === 'DECODED'
  const hyp = (code: string, dims: number[], lp: number, rej: string | null): Hyp => ({
    code, interleaver: dims, sps: s.sps ?? 6, cfo: s.cfo ?? 0, modulation: s.modulation ?? 'QPSK', rotation: 0, phase: 0.3,
    symbol_snr_db: 6 + r() * 10, n_checks: dims[0] * dims[1] / 2 - 6, n_positive: dims[0] * dims[1] / 2 - 6 - (rej ? 6 : 0),
    log10_p: lp, syndrome_z: 3 + r() * 5, covered_bits: dims[0] * dims[1], total_observed_bits: dims[0] * dims[1] + 20,
    coverage_ratio: s.coverage ?? 0.7, consistency: decoded ? 0.99 : 0.9, path_metric: decoded ? 0.97 : 0.88,
    mdl_savings_bits: decoded ? 40 : -5, active_symbols: dims[0] * dims[1], covered_symbols: dims[0] * dims[1] - (rej ? 30 : 0),
    bpsk_presence_log10p: s.modulation === 'BPSK' ? -12 : -0.4, bpsk_contradiction_log10p: s.modulation === 'BPSK' ? -0.1 : -9,
    structural_rejection: rej,
  })
  const top: Hyp[] = []
  if (decoded && s.code && s.interleaver) top.push(hyp(s.code, s.interleaver, s.log10p ?? thr - 3, null))
  for (let k = 0; k < 7; k++) {
    const d = DIMS[(k * 3 + 1) % DIMS.length]
    top.push(hyp(CODES[k % 3], d, thr + 0.4 + k * 0.5 + r(), k === 0 && !decoded ? 'block length: covers 112 of ~192 transmitted symbols' : null))
  }
  const sps = s.sps ?? 6
  const specT = 90, specF = 64
  const db: number[][] = Array.from({ length: specF }, (_, fi) => Array.from({ length: specT }, (_, ti) => {
    const center = specF / 2 + (s.cfo ?? 0) * specF * 20
    const inBand = Math.abs(fi - center) < specF / (sps * 1.6)
    return -62 + r() * 6 + (s.status !== 'UNKNOWN' && inBand && ti > 4 && ti < specT - 6 ? 18 + r() * 4 : 0)
  }))
  const pts: number[][] = []
  for (let k = 0; k < 360; k++) {
    const noise = s.status === 'UNKNOWN' ? 0.8 : s.status === 'SIGNAL_NO_CODE' ? 0.35 : 0.22
    const g = () => (r() + r() + r() - 1.5) * noise
    if (s.modulation === 'BPSK') pts.push([(r() < 0.5 ? -1 : 1) + g(), g()])
    else pts.push([(r() < 0.5 ? -0.707 : 0.707) + g(), (r() < 0.5 ? -0.707 : 0.707) + g()])
  }
  return {
    id: s.id, analysed_at: new Date(s.observedAt).toISOString(),
    source: { kind: 'SIMULATED', note: 'Simulated record for demonstration. Values are not measurements.' },
    capture: { samples: 4096, fs_hz: 1e6, fs_source: 'declared', duration_s: 0.004096, format: 'iq', station: s.stationId },
    engine: { version: '0.3.0', commit: 'simulated', alpha: 0.01, accept_search: 20, bl_delta_symbols: 1.7, pm_floor: 0.926,
      sps_range: [2, 20], min_symbols: 16, cfo_max: 0.0125, rx_beta: 0.3, modulations: ['BPSK', 'QPSK'], codes: CODES,
      interleaver_domain: 'single block, rows 2-16, cols 4-24 (<=384 bits)' },
    result: { status: s.status, code: s.code, interleaver: s.interleaver, modulation: s.modulation, sps: s.sps,
      symbol_rate_est: s.sps ? 1e6 / s.sps : null, cfo: s.cfo, beta: 0.3, phase: 0.3, rotation: 0, runtime: 0.4 + r(),
      payload_bits: decoded ? Array.from({ length: 96 }, () => (r() < 0.5 ? 0 : 1)) : [], payload_len: decoded ? 96 : 0 },
    accept: { log10_p: top[0]?.log10_p ?? 0, log10_threshold: thr, n_hypotheses: M, alpha: 0.01,
      accepted_hypothesis: decoded ? top[0] : null,
      significant_but_rejected: decoded ? [] : top.filter((h) => h.structural_rejection).map((h) => ({
        code: h.code, interleaver: h.interleaver, modulation: h.modulation, sps: h.sps, log10_p: thr - 0.3,
        structural_rejection: h.structural_rejection as string })),
      rules: { bl_delta_symbols: 1.7, pm_floor: 0.926 } },
    diagnostics: {
      cfo_candidates: [0, 1, 2].map((k) => ({ cfo: (s.cfo ?? 0) + k * 0.003, order: k ? 2 : 4, peak_to_floor_db: 22 - k * 7, log10_p: -18 + k * 7 })),
      detection_log10_p: s.status === 'UNKNOWN' ? -0.5 : -14, raw_sps_estimate: sps + (r() - 0.5),
      sps_table: Array.from({ length: 12 }, (_, k) => ({ sps: k + 2, n_symbols: 400, q4: k + 2 === sps ? 0.82 : 0.1 + r() * 0.3 * ((k + 2) % sps === 0 ? 2 : 1), q2: 0.1 })),
      sps_candidates: [sps, sps * 2, 2], modulation_stats: [{ sps, q2: 0.1, q4: 0.8, bpsk_ratio: s.modulation === 'BPSK' ? 0.94 : 0.07, decision: s.modulation ?? 'QPSK', margin: 0.4 }],
      top_hypotheses: top, runner_up_margin_log10: 3.2, n_front_ends: 36, front_ends_rejected_serial_dependence: 48,
      timers_s: { cfo: 0.004, sps: 0.03, matched_filter: 0.03, syndrome_search: 0.42, viterbi: 0.04, scoring: 0.02 },
      all_hypotheses: all,
    },
    views: {
      spectrogram: { f_hz: Array.from({ length: specF }, (_, k) => (k - specF / 2) * 1e6 / specF), t_s: Array.from({ length: specT }, (_, k) => k * 4.5e-5), db },
      psd: { f_hz: Array.from({ length: 128 }, (_, k) => (k - 64) * 1e6 / 128), db: Array.from({ length: 128 }, (_, k) => -60 + (Math.abs(k - 64) < 128 / (sps * 1.6) && s.status !== 'UNKNOWN' ? 17 : 0) + r() * 4) },
      constellation: pts,
      timeseries: { i: Array.from({ length: 300 }, (_, k) => Math.sin(k / sps) * 0.8 + (r() - 0.5) * 0.3), q: Array.from({ length: 300 }, (_, k) => Math.cos(k / sps) * 0.8 + (r() - 0.5) * 0.3) },
    },
  }
}
