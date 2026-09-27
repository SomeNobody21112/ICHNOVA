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

/** EventSource fires `onerror` whenever the stream closes — including the normal close the server
 *  performs after sending the verdict (`live.ts` closes the source itself on the `closed` phase, which
 *  immediately re-enters onerror with readyState CLOSED). So this exact message is a transport
 *  lifecycle event, NOT a failure, and it must never outrank a verdict. Treating it as a failure was
 *  why a successful capture reported DISCONNECTED. */
export const BENIGN_STREAM_END = 'event stream closed'

export interface StageView { stage: Stage; blocked: Blocked | null; reached: number }

/**
 * Derive the stage from live state. `rows` is how many spectrum rows have arrived and `lastRowAt`
 * when the last one did — both facts about the transport, not guesses.
 *
 * Order matters and is deliberate: a real link failure first, then a verdict (which always wins, even
 * if the stream has since closed), then an ended stream, then progress.
 */
export function deriveStage(st: LiveState, rows: number, lastRowAt: number, now: number): StageView {
  const has = (phase: string) => st.statuses.some((s) => s.phase === phase)
  const at = (stage: Stage, blocked: Blocked | null = null): StageView =>
    ({ stage, blocked, reached: STAGES.indexOf(stage) })

  // a real failure: the server said the receiver failed, or the feed reported something other than
  // the ordinary end of stream
  const hardError = Boolean(st.error) && st.error !== BENIGN_STREAM_END
  if (has('receiver_failed') || hardError) return at('CONNECTING', 'DISCONNECTED')

  // a verdict exists — the only path to DECISION, and it outranks any later stream close
  if (st.result) return at('DECISION')

  // the stream ended without a verdict
  const ended = st.closed || has('closed') || st.error === BENIGN_STREAM_END
  if (ended) {
    // rows arrived but the engine never answered; or nothing ever arrived at all
    return rows > 0 ? at('QUALIFYING', 'INSUFFICIENT CAPTURE') : at('CONNECTING', 'DISCONNECTED')
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

/* ------------------------------------------- globe helpers (pure, so they can be checked alone) */

/** Natural Earth spells a few countries differently from the station registry. */
const NE_ALIAS: Record<string, string> = { 'United States': 'United States of America' }
export const neName = (c: string) => NE_ALIAS[c] ?? c

/** Shortest signed way round the sphere: -170 to +170 is 20 degrees, not 340. */
export function shortestTurn(from: number, to: number): number {
  let d = (to - from) % 360
  if (d > 180) d -= 360
  if (d < -180) d += 360
  return d
}

/**
 * What clicking a pin on the globe means.
 *
 * A pin **is** a transmitter, so clicking one always opens it. The first version spent that click on
 * choosing the listening site instead, so the very first pin click appeared to do nothing: the globe
 * re-centred and you were left on the same screen with no way to tell the click had registered. If no
 * listening site has been chosen yet, the place clicked becomes it too, in the same click.
 */
export function pinClick(anchorKey: string | null, key: string): { anchor: string; open: string } {
  return { anchor: anchorKey ?? key, open: key }
}

export interface LabelMark { x: number; y: number; visible: boolean }
export interface LabelPlaced { ly: number; side: 1 | -1 }

/**
 * Place labels after projection, then push them apart vertically so they never overlap — the reason
 * the first attempt at this view was unreadable. Each column (left of centre, right of centre) is
 * spaced independently, then nudged back inside the frame.
 */
export function placeLabels<T extends LabelMark>(marks: T[], cx: number, minGap: number,
  top = 10, bottom = Infinity): (T & LabelPlaced)[] {
  const out = marks.map((m) => ({ ...m, ly: m.y, side: (m.x >= cx ? 1 : -1) as 1 | -1 }))
  for (const side of [1, -1] as const) {
    const col = out.filter((m) => m.visible && m.side === side).sort((a, b) => a.y - b.y)
    for (let i = 1; i < col.length; i++) {
      if (col[i].ly - col[i - 1].ly < minGap) col[i].ly = col[i - 1].ly + minGap
    }
    const over = col.length ? col[col.length - 1].ly - bottom : 0
    if (over > 0) for (const m of col) m.ly -= over
    for (let i = col.length - 1; i > 0; i--) {
      if (col[i].ly - col[i - 1].ly < minGap) col[i - 1].ly = col[i].ly - minGap
    }
    if (col.length && col[0].ly < top) {
      const up = top - col[0].ly
      for (const m of col) m.ly += up
    }
  }
  return out
}

/* --------------------------------------------- day/night and interaction maths (pure, checkable) */

/** Sub-solar point for a UTC instant: where the Sun is directly overhead. Good to a fraction of a
 *  degree, which is far finer than a 1-pixel terminator needs, and it means the night side on the
 *  globe is the real one for the user's clock rather than an ornament. */
export function subsolar(d: Date): { lat: number; lon: number } {
  const day = (Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate())
    - Date.UTC(d.getUTCFullYear(), 0, 1)) / 86400000 + 1
  const secs = d.getUTCHours() * 3600 + d.getUTCMinutes() * 60 + d.getUTCSeconds()
  // declination: the tilt term, peaking at ±23.44° at the solstices
  const gamma = (2 * Math.PI / 365) * (day - 1 + (secs / 86400 - 0.5))
  const decl = 0.006918 - 0.399912 * Math.cos(gamma) + 0.070257 * Math.sin(gamma)
    - 0.006758 * Math.cos(2 * gamma) + 0.000907 * Math.sin(2 * gamma)
    - 0.002697 * Math.cos(3 * gamma) + 0.00148 * Math.sin(3 * gamma)
  // equation of time, in minutes, then longitude of the sub-solar meridian
  const eqt = 229.18 * (0.000075 + 0.001868 * Math.cos(gamma) - 0.032077 * Math.sin(gamma)
    - 0.014615 * Math.cos(2 * gamma) - 0.040849 * Math.sin(2 * gamma))
  let lon = -15 * (secs / 3600 + eqt / 60 - 12)
  lon = ((lon + 180) % 360 + 360) % 360 - 180
  return { lat: (decl * 180) / Math.PI, lon }
}

/** Antipode — the terminator is drawn as a 90° cap around the anti-solar point. */
export function antipode(p: { lat: number; lon: number }) {
  return { lat: -p.lat, lon: ((p.lon + 360) % 360) - 180 }
}

export const ZOOM_MIN = 0.85
export const ZOOM_MAX = 4
export const clampZoom = (z: number) => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z))

/** Latitude is clamped so a drag can never flip the globe upside-down. */
export const clampTilt = (deg: number) => Math.min(89, Math.max(-89, deg))

/** Per-frame inertia decay after a drag ends: multiplicative, so it always settles. */
export const SPIN_FRICTION = 0.94
/** Below this the drift is invisible, so it is dropped rather than ticking forever. */
export const SPIN_EPSILON = 0.02
