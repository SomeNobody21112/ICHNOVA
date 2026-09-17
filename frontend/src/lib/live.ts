import { useCallback, useEffect, useReducer, useRef, useState } from 'react'

export interface Reference { title: string; url: string }
export interface StationInfo {
  name: string; operator: string; country: string; service: string; frequency_khz: number
  site: { name: string; lat: number; lon: number }; references: Reference[]
  analysis?: 'timecode' | 'fsk' | 'chu' | 'am'; capture_s?: number; protocol?: string | null
}
export interface LayoutPos { kind: string; field: string | null }
export interface StationsDoc {
  stations: Record<string, StationInfo>
  layouts: Record<string, { operator: string; zone: string; refers_to: string; positions: LayoutPos[] }>
}

export interface SpectrumEv { type: 'spectrum'; t: number; row: string; f0_hz: number; f1_hz: number; db_min: number; db_max: number }
export interface ReceiverEv {
  type: 'receiver'; t: number; url?: string; name?: string | null; location?: string | null; gps?: number[] | null
  distance_km?: number | null; gps_timed?: boolean | null; rssi_dbm?: number | null; fs_hz?: number; tuned_khz?: number
  timing?: string; t0_utc?: string; span_khz?: number[]
}
export interface StatusEv { type: 'status'; t: number; phase: string; message: string; carrier_db?: number; epoch_ms?: number; fixed?: boolean }
export interface SymbolEv { type: 'symbol'; t: number; k: number; symbol: string | null; confidence: number; utc_second: number | null }
export interface Digit { margin_symbols: number | null; log10_odds: number | null; established: boolean }
export interface Verification { timing: string; arrival_minus_decoded_ms: number; agrees: boolean }
export interface DecodeEv {
  type: 'decode'; t: number; protocol: string; frames: number; utc: string | null; digits: Record<string, Digit> | null
  established: boolean; detected: boolean; log10_p: number | null; mismatches: number | null; observed: number | null
  flags: Record<string, number> | null; verification: Verification | null
}
export interface Framing { baud: number; polarity: string; data_bits: number; parity: string | null; stop_bits: number; characters: number; stop_ok: number; stop_ok_fraction: number; log10_p: number }
export interface FskEv {
  type: 'fsk'; t: number; status: string; reason?: string; baud?: number | null; baud_estimate?: number; shift_hz?: number | null
  center_offset_hz?: number; framing?: Framing; code?: string; text?: string; log10_p?: number
}
export interface AmMetrics {
  modulation: string; carrier_offset_hz: number; carrier_offset_se_hz: number; carrier_to_noise_db: number
  modulation_depth_rms: number | null; modulation_depth_peak: number | null; audio_bandwidth_99_hz: number | null
  sideband_symmetry_db: number; receiver_passband: string; depth_is_approximate: boolean; status: string
}
export interface AmEv extends AmMetrics { type: 'am'; t: number }
export interface AirStation { station: string; state: string; power_kw: number; drm: boolean; frequency_khz: number }
export interface CensusChannel { khz: number; measured_khz: number; level_db: number; prominence_db?: number; stations: AirStation[] }
export interface Census { channels: CensusChannel[]; axis_fit: { scale: number; offset_khz: number }; reference: { title: string; url: string; retrieved: string; publisher?: string } }
export interface CensusEv extends Census { type: 'census'; t: number }
export interface TcResult {
  protocol: string; operator: string; reference: string; decoded: boolean; detected?: boolean; accepted: boolean
  log10_p: number; mismatches?: number; observed_symbols?: number; utc_first_frame?: string; unresolved_digits?: string[]
  complete_frames: number; epoch_s: number; verification?: Verification; search_space_log10: number; reason?: string
}
export interface Answer {
  status: 'DECODED' | 'SIGNAL_NO_CODE' | 'UNKNOWN'; receiver?: string; protocol?: string | null; operator?: string
  summary?: string; log10_p?: number; verification?: Verification | null
}
export interface Runs {
  timecode?: { status: string; protocol: string | null; utc: string | null; log10_threshold: number; carrier_offset_hz: number; carrier_peak_db: number | null; results: TcResult[]; reason?: string | null }
  fsk?: { status: string; reason?: string; baud?: number; baud_estimate?: number; measured_shift_hz?: number; code?: string; text?: string; framing?: Framing; framing_hypotheses?: (Framing & { screened_only?: boolean })[]; log10_threshold?: number; timing_coherence?: number; anticorrelation?: number }
  am?: AmMetrics
}
export interface ResultEv { type: 'result'; t: number; answer: Answer; runs?: Runs; census?: Census; recording_id: string | null; has_audio?: boolean }
export interface ErrorEv { type: 'error'; t: number; message: string }
export type LiveEvent = SpectrumEv | ReceiverEv | StatusEv | SymbolEv | DecodeEv | FskEv | AmEv | CensusEv | ResultEv | ErrorEv

export interface ReplayDoc {
  id: string; mode: 'iq' | 'band'; station_key: string; station: StationInfo
  recording: { receiver: Record<string, unknown>; capture: Record<string, unknown> }
  events: LiveEvent[]
}
export interface ReplayIndexEntry {
  id: string; mode: 'iq' | 'band'; station_key: string; station: string; operator: string; country: string
  frequency_khz: number; t0_utc: string; duration_s: number | null; receiver: string | null; answer: Answer
}

export interface LiveState {
  receiver?: ReceiverEv; statuses: StatusEv[]; carrierDb?: number; epochMs?: number; epochFixed?: boolean
  symbols: SymbolEv[]; decode?: DecodeEv; fsk?: FskEv; am?: AmEv; census?: CensusEv; result?: ResultEv
  error?: string; t: number; closed: boolean; span?: [number, number]
}

const EMPTY: LiveState = { statuses: [], symbols: [], t: 0, closed: false }

function reduce(s: LiveState, a: { kind: 'reset' } | { kind: 'events'; events: LiveEvent[] }): LiveState {
  if (a.kind === 'reset') return EMPTY
  let n = s
  for (const ev of a.events) {
    n = { ...n, t: Math.max(n.t, ev.t) }
    switch (ev.type) {
      case 'receiver': n.receiver = ev; break
      case 'status':
        n.statuses = [...n.statuses.slice(-40), ev]
        if (ev.phase === 'carrier') n.carrierDb = ev.carrier_db
        if (ev.phase === 'epoch') { n.epochMs = ev.epoch_ms; n.epochFixed = ev.fixed }
        if (ev.phase === 'closed') n.closed = true
        break
      case 'symbol': n.symbols = [...n.symbols.slice(-240), ev]; break
      case 'decode': n.decode = ev; break
      case 'fsk': if (ev.status === 'DECODED' || !n.fsk || n.fsk.status !== 'DECODED') n.fsk = ev; break
      case 'am': n.am = ev; break
      case 'census': n.census = ev; break
      case 'result': n.result = ev; n.closed = true; break
      case 'error': n.error = ev.message; break
      case 'spectrum': n.span = [ev.f0_hz, ev.f1_hz]; break
    }
  }
  return n
}

export type RowListener = (row: Uint8Array, f0: number, f1: number) => void

function decodeRow(b64: string) {
  const bin = atob(b64)
  const out = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i)
  return out
}

/** Plays a replay document (with its own timestamps) or follows a live server session. */
export function useLiveFeed(source: { kind: 'replay'; doc: ReplayDoc | null; speed: number; playing: boolean } | { kind: 'live'; session: string | null }) {
  const [state, dispatch] = useReducer(reduce, EMPTY)
  const listeners = useRef(new Set<RowListener>())
  const [clock, setClock] = useState(0)
  const clockRef = useRef(0)
  const idx = useRef(0)
  const subscribe = useCallback((fn: RowListener) => { listeners.current.add(fn); return () => { listeners.current.delete(fn) } }, [])

  const deliver = useCallback((events: LiveEvent[]) => {
    const rest: LiveEvent[] = []
    for (const ev of events) {
      if (ev.type === 'spectrum') {
        const row = decodeRow(ev.row)
        listeners.current.forEach((fn) => fn(row, ev.f0_hz, ev.f1_hz))
      }
      if (ev.type !== 'spectrum' || rest.length === 0) rest.push(ev)
    }
    if (rest.length) dispatch({ kind: 'events', events: rest })
  }, [])

  const doc = source.kind === 'replay' ? source.doc : null
  const speed = source.kind === 'replay' ? source.speed : 1
  const playing = source.kind === 'replay' ? source.playing : true
  const session = source.kind === 'live' ? source.session : null

  const restart = useCallback(() => {
    idx.current = 0
    clockRef.current = 0
    setClock(0)
    dispatch({ kind: 'reset' })
  }, [])

  useEffect(() => { restart() }, [doc, session, restart])

  useEffect(() => {
    if (!doc) return
    let raf = 0
    let last = performance.now()
    const step = (now: number) => {
      raf = requestAnimationFrame(step)
      const dt = Math.min(0.25, (now - last) / 1000)
      last = now
      const end = doc.events[doc.events.length - 1]?.t ?? 0
      if (!playing || clockRef.current > end) return
      clockRef.current = Math.min(end + 0.001, clockRef.current + dt * speed)
      const due: LiveEvent[] = []
      while (idx.current < doc.events.length && doc.events[idx.current].t <= clockRef.current) due.push(doc.events[idx.current++])
      if (due.length) deliver(due)
      setClock(clockRef.current)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [doc, speed, playing, deliver])

  useEffect(() => {
    if (!session) return
    const es = new EventSource(`/api/live/events?session=${encodeURIComponent(session)}`)
    es.onmessage = (m) => {
      try {
        const ev = JSON.parse(m.data) as LiveEvent
        deliver([ev])
        setClock(ev.t)
        if (ev.type === 'status' && ev.phase === 'closed') es.close()
      } catch { /* ignore malformed */ }
    }
    es.onerror = () => { if (es.readyState === EventSource.CLOSED) dispatch({ kind: 'events', events: [{ type: 'error', t: clockRef.current, message: 'event stream closed' }] }) }
    return () => es.close()
  }, [session, deliver])

  const duration = doc ? doc.events[doc.events.length - 1]?.t ?? 0 : 0
  return { state, subscribe, clock, duration, restart }
}

export const DIGIT_ORDER: Record<string, string[]> = {
  doy: ['year_tens', 'year_units', 'day_hundreds', 'day_tens', 'day_units', 'hour_tens', 'hour_units', 'minute_tens', 'minute_units'],
  mday: ['year_tens', 'year_units', 'month', 'day_tens', 'day_units', 'hour_tens', 'hour_units', 'minute_tens', 'minute_units'],
}

export const FIELD_LABEL: Record<string, string> = {
  min_u: 'minute units', min_t: 'minute tens', hour_u: 'hour units', hour_t: 'hour tens', day_u: 'day-of-year units',
  day_t: 'day-of-year tens', day_h: 'day-of-year hundreds', year_u: 'year units', year_t: 'year tens', mday_u: 'day units',
  mday_t: 'day tens', month_u: 'month units', month_t: 'month tens', dow: 'day of week', dut1: 'UT1−UTC', dut1_sign: 'UT1 sign',
  leap_warning: 'leap-second warning', dst1: 'DST', dst2: 'DST', cest: 'summer time', cet: 'winter time', dst_announce: 'DST change',
  leap_announce: 'leap second', year: 'year', month: 'month', mday: 'day of month', hour: 'hour', minute: 'minute',
  dut1_pos: 'DUT1 +', dut1_neg: 'DUT1 −', bst: 'British Summer Time', bst_warning: 'BST change', leap: 'leap second',
  leap_year: 'leap year', dst: 'DST',
}

export function lightTimeMs(km: number | null | undefined) {
  return km == null ? null : km / 299.792458
}
