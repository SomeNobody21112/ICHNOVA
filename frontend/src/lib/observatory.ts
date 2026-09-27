/** Observatory: the stage machine and geometry behind the live-capture experience.
 *
 *  Every value here is derived from real application state — the phases the server actually emits
 *  (`connecting`, `directory`, `carrier`, `epoch`, `analysing`, `closed`, `receiver_failed`), the
 *  spectrum rows that actually arrived, and the engine's own verdict. Nothing is invented to make an
 *  animation look busy: if the receiver drops, the stage is DISCONNECTED; if rows stop, STALE; if the
 *  capture ends with no verdict, INSUFFICIENT CAPTURE. That is why it lives in one pure module rather
 *  than inside the view.
 */
import type { LiveState, StationInfo } from './live'

/** The visual progression. Each stage is entered only on evidence that it has actually happened. */
export const STAGES = ['CONNECTING', 'RECEIVING', 'CAPTURING', 'QUALIFYING', 'SEARCHING',
  'TESTING', 'DECISION'] as const
export type Stage = typeof STAGES[number]

/** A stage cannot advance: the reason is the link's or the engine's, never decoration. */
export type Blocked = 'DISCONNECTED' | 'STALE' | 'INSUFFICIENT CAPTURE'

export const STAGE_LABEL: Record<Stage, string> = {
  CONNECTING: 'Connecting to receiver',
  RECEIVING: 'Receiving spectrum',
  CAPTURING: 'Capturing carrier',
  QUALIFYING: 'Qualifying the capture',
  SEARCHING: 'Hypothesis search',
  TESTING: 'Evidence test',
  DECISION: 'Decision',
}

/** How long without a spectrum row before the link is called stale rather than merely quiet. */
export const STALE_MS = 8000

export interface StageView { stage: Stage; blocked: Blocked | null; reached: number }

/**
 * Derive the stage from live state. `rows` is how many spectrum rows have arrived and `lastRowAt`
 * when the last one did — both facts about the transport, not guesses.
 */
export function deriveStage(st: LiveState, rows: number, lastRowAt: number, now: number): StageView {
  const has = (phase: string) => st.statuses.some((s) => s.phase === phase)
  const at = (stage: Stage, blocked: Blocked | null = null): StageView =>
    ({ stage, blocked, reached: STAGES.indexOf(stage) })

  // the link itself failed: the server said so, or the feed reported an error
  if (st.error || has('receiver_failed')) return at('CONNECTING', 'DISCONNECTED')
  // a verdict exists — the only path to DECISION
  if (st.result) return at('DECISION')
  // the session ended without the engine reaching a verdict
  if (st.closed || has('closed')) {
    return at(rows ? 'QUALIFYING' : 'CONNECTING', 'INSUFFICIENT CAPTURE')
  }
  // the engine is working on the capture
  if (has('analysing')) {
    // TESTING once family-level evidence exists; SEARCHING while hypotheses are still forming
    const evidence = Boolean(st.decode || st.fsk || st.am || st.census)
    return at(evidence ? 'TESTING' : 'SEARCHING')
  }
  // rows were flowing and stopped
  if (rows > 0 && now - lastRowAt > STALE_MS) return at('RECEIVING', 'STALE')
  // qualifying: something protocol-specific has been measured from the samples
  if (st.symbols.length > 0 || st.am || st.census || st.epochMs != null) return at('QUALIFYING')
  if (st.carrierDb != null) return at('CAPTURING')
  if (rows > 0) return at('RECEIVING')
  return at('CONNECTING')
}

/** Provenance is a property of the source, never of the animation. */
export type Provenance = 'LIVE' | 'RECORDED' | 'SIMULATED'

export function provenanceOf(kind: 'live' | 'replay' | null): Provenance | null {
  return kind === 'live' ? 'LIVE' : kind === 'replay' ? 'RECORDED' : null
}

export const PROVENANCE_NOTE: Record<Provenance, string> = {
  LIVE: 'Received now, from a public receiver. The link state shown is the real one.',
  RECORDED: 'A real capture, recorded earlier and replayed with its own timestamps. Not live.',
  SIMULATED: 'Synthetic scenario. The engine output on it is real; the timeline is not.',
}

/* --------------------------------------------------------- geometry (real, not decorative) */

const R_KM = 6371.0088
const rad = (d: number) => (d * Math.PI) / 180
const deg = (r: number) => (r * 180) / Math.PI

export interface Site { lat: number; lon: number }

/** Great-circle distance: how far the signal travels along the ground. */
export function greatCircleKm(a: Site, b: Site): number {
  const dLat = rad(b.lat - a.lat)
  const dLon = rad(b.lon - a.lon)
  const h = Math.sin(dLat / 2) ** 2
    + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2
  return 2 * R_KM * Math.asin(Math.min(1, Math.sqrt(h)))
}

/** Initial great-circle bearing from a to b, degrees clockwise from true north. */
export function bearingDeg(a: Site, b: Site): number {
  const dLon = rad(b.lon - a.lon)
  const y = Math.sin(dLon) * Math.cos(rad(b.lat))
  const x = Math.cos(rad(a.lat)) * Math.sin(rad(b.lat))
    - Math.sin(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.cos(dLon)
  return (deg(Math.atan2(y, x)) + 360) % 360
}

/** One-way propagation delay at c, for the light-time readout. */
export function lightMs(km: number): number {
  return km / 299.792458
}

/* --------------------------------------------------------- hypotheses, from the real run */

export interface Branch { label: string; state: 'won' | 'lost' | 'open' }

/**
 * The competing readings the engine actually ran, resolved by its actual answer. Before a verdict
 * every branch is `open`: nothing is marked won until the engine says so.
 */
export function branches(st: LiveState, station: StationInfo): Branch[] {
  const runs = st.result?.runs
  const answer = st.result?.answer
  const kinds = [
    { label: 'Time code', ran: Boolean(runs?.timecode), ok: runs?.timecode?.status === 'DECODED' },
    { label: 'FSK telegraphy', ran: Boolean(runs?.fsk), ok: runs?.fsk?.status === 'DECODED' },
    { label: 'AM carrier', ran: Boolean(st.am), ok: Boolean(st.am) },
    { label: 'Band census', ran: Boolean(st.census), ok: Boolean(st.census) },
  ]
  const ran = kinds.filter((k) => k.ran)
  const fallback = station.analysis === 'am' ? 'AM carrier'
    : station.analysis === 'fsk' ? 'FSK telegraphy' : 'Time code'
  const pool = ran.length ? ran : [{ label: fallback, ran: false, ok: false }]
  return pool.map((k) => ({
    label: k.label,
    state: (!answer ? 'open' : k.ok && answer.status === 'DECODED' ? 'won' : 'lost') as Branch['state'],
  }))
}
