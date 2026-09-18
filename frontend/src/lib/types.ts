import type { Answer, ReplayIndexEntry, Runs } from './live'

export type Status = 'DECODED' | 'SIGNAL_NO_CODE' | 'UNKNOWN'
export type Provenance = 'SIMULATED' | 'BENCHMARK' | 'LIVE' | 'EXPERIMENTAL' | 'NOT ESTABLISHED'
export type Zone = 'NORTH' | 'WEST' | 'CENTRAL' | 'EAST' | 'NORTHEAST' | 'SOUTH'
export type Band = 'HF' | 'VHF' | 'UHF'
export type Level = 'FIELD' | 'REGIONAL' | 'NATIONAL'

export interface Hyp {
  code: string
  /** null for families that carry no interleaver (continuous stream code, frame-level block codes). */
  interleaver: number[] | null
  sps: number
  cfo: number
  modulation: string
  rotation: number
  phase: number
  symbol_snr_db: number
  n_checks: number
  n_positive: number
  log10_p: number
  syndrome_z: number
  covered_bits: number
  total_observed_bits: number
  coverage_ratio: number
  consistency: number
  path_metric: number
  mdl_savings_bits: number
  active_symbols: number
  covered_symbols: number
  bpsk_presence_log10p: number
  bpsk_contradiction_log10p: number
  structural_rejection: string | null
}

export interface RejectedHyp {
  code: string
  interleaver: number[] | null
  modulation: string
  sps: number
  log10_p: number
  structural_rejection: string
}

export interface AllHypotheses {
  code: string[]
  rows: number[]
  cols: number[]
  sps: number[]
  modulation: string[]
  cfo: number[]
  n_checks: number[]
  n_positive: number[]
  log10_p: number[]
}

/** Where the absolute sample rate came from (Constitution v2.5 §10). 'unavailable' means no rate in Hz is established. */
export type FsSource = 'declared' | 'wav_header' | 'inferred' | 'relative_only' | 'unavailable'

export interface EvidencePack {
  id: string
  analysed_at: string
  source: { kind: 'BENCHMARK' | 'UPLOAD' | 'SIMULATED'; file?: string; note?: string; dataset?: string }
  capture: {
    samples: number; fs_hz: number | null; duration_s: number | null; fs_source?: FsSource; fs_note?: string | null
    format?: string; name?: string; station?: string
    center_freq_hz?: string | number; bandwidth_hz?: string | number; antenna?: string; captured_at?: string; notes?: string
  }
  engine: {
    version: string; commit: string; alpha: number; accept_search: number; bl_delta_symbols: number; pm_floor: number
    sps_range: number[]; min_symbols: number; cfo_max: number; rx_beta: number; modulations: string[]; codes: string[]
    interleaver_domain: string
  }
  result: {
    status: Status; code: string | null; interleaver: number[] | null; modulation: string | null; sps: number | null
    symbol_rate_est: number | null; symbol_rate_norm?: number | null; cfo: number | null; beta: number; phase: number | null; rotation: number | null
    runtime: number; payload_bits: number[]; payload_len: number
  }
  accept: {
    log10_p: number; log10_threshold: number; n_hypotheses: number; alpha: number
    accepted_hypothesis: Hyp | null; significant_but_rejected: RejectedHyp[]
    rules: { bl_delta_symbols: number; pm_floor: number }
  }
  diagnostics: {
    cfo_candidates: { cfo: number; order: number; peak_to_floor_db: number; log10_p: number }[]
    detection_log10_p: number
    raw_sps_estimate: number
    sps_table: { sps: number; n_symbols: number; q4: number; q2: number }[]
    sps_candidates: number[]
    modulation_stats: { sps: number; q2: number; q4: number; bpsk_ratio: number; decision: string; margin: number }[]
    top_hypotheses: Hyp[]
    runner_up_margin_log10: number | null
    n_front_ends: number
    front_ends_rejected_serial_dependence: number
    timers_s: Record<string, number>
    all_hypotheses?: AllHypotheses
  }
  views: {
    units?: 'hz' | 'normalised'
    spectrogram: { f_hz: number[]; t_s: number[]; db: number[][] }
    psd: { f_hz: number[]; db: number[] }
    constellation: number[][]
    timeseries: { i: number[]; q: number[] }
  }
  benchmark_truth?: Record<string, unknown>
  real?: RealAnalysis
}

export interface RealAnalysis {
  samples: number; fs_hz: number; duration_s: number; timing: string | null; t0_unix: number | null
  runs: Runs; timers_s: Record<string, number>; answer: Answer
}

export interface Station {
  id: string; name: string; zone: Zone; lat: number; lon: number; bands: Band[]
  health: 'NOMINAL' | 'DEGRADED'; clock: 'SYNCED' | 'DRIFT'
}

export interface SignalRecord {
  id: string
  provenance: Provenance
  status: Status
  investigate: boolean
  library: 'known' | 'unknown' | 'recurrent' | 'archived' | 'reference'
  stationId: string
  band: Band | null
  centerHz: number | null
  bandwidthHz: number | null
  observedAt: number
  firstSeen: number
  lastSeen: number
  occurrences: number
  modulation: string | null
  sps: number | null
  cfo: number | null
  code: string | null
  interleaver: number[] | null
  coverage: number | null
  hypotheses: number
  log10p: number | null
  threshold: number | null
  genome: number[]
  family: number
  evidenceId: string
  reason: string
  candidates: string[]
  validations: number
  incidentId?: string
  description?: string
}

export interface Incident {
  id: string
  title: string
  kind: string
  priority: 'HIGH' | 'MEDIUM' | 'LOW'
  status: 'UNDER INVESTIGATION' | 'OPEN' | 'MONITORING' | 'CLOSED'
  firstSeen: number
  lastSeen: number
  stationIds: string[]
  signalIds: string[]
  events: { t: number; stationId: string; signalId: string }[]
  summary: string
}

export interface Anomaly {
  id: string; stationId: string; band: Band; score: number; reasons: string[]; signalId: string; detectedAt: number
  kind: string
}

export interface AuditEvent {
  t: number
  actor: string
  action: string
  subject: string
  detail?: string
}

export interface Session {
  name: string
  email: string
  picture?: string
  /** How the session was obtained. 'demo' is a server-issued demo account. */
  method: 'google' | 'operator' | 'demo'
  /** Operational view (Field / Regional / National). Not a permission. */
  role: Level
  stationId: string
  signedInAt: number
  /** Permission role issued by the server; the server remains the authority. */
  authRole?: 'ADMIN' | 'ANALYST' | 'REVIEWER' | 'VIEWER'
  username?: string
  demo?: boolean
  expiresAt?: number
}

export interface BenchmarkData {
  generated_from_commit: string
  bench_v1: Record<string, Record<'sealed' | 'train', { pass: number; n: number; false_accepts: number | null; outcomes: Record<string, number>; runtime_s: number; source: string }>>
  oracle_ladder: Record<'sealed' | 'train', { stages: Record<string, number>; never: number; n: number; o7_first_pass_32bit: number; source: string }>
  nullset: {
    n: number; confusion: Record<string, Record<string, number>>
    correct_by_esn0: Record<string, Record<string, { correct: number; n: number }>>
    runtime_mean_s: number; hypotheses_mean: number; source: string
  }
  acceptance: {
    params: { delta: number; t: number; m: number }
    evaluation_split: { rule: string; recall: number; wrong_hyp: number; n_coded: number; null_fa: number; n_null: number; wrongnull_fa: number; n_wrong: number }[]
    adopted: string; source: string
  }
  scoring: { method: string; auc: number; tpr_at_zero_fp: number; identification: number; null_range: string }[]
  runtime: { stage_share: Record<string, number>; source: string }
  research_issue: string
  performance?: { sealed_s: number[]; train_s: number[]; nullset_s: number[]; decision_differences: number; note: string; changes: string[]; source: string }
  real_signals?: ReplayIndexEntry[]
}
