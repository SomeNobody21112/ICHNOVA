/** Runnable checks for the Observatory's pure logic: the live-stage machine and the globe geometry.
 *
 *  This file exists because of a real defect. `EventSource` fires `onerror` whenever the stream
 *  closes — including the normal close that follows the verdict — so the first version of
 *  `deriveStage` read every successful capture as DISCONNECTED and hid the answer. That is a
 *  one-line ordering mistake with no stack trace, which is exactly the kind of thing a check has to
 *  hold down permanently.
 *
 *  There is no JS test runner in this project and adding one is not worth it for a pure module:
 *  `node:assert` plus Node's own TypeScript type-stripping runs the real source directly.
 *
 *      npm run check        (from frontend/)
 */
import assert from 'node:assert/strict'
import {
  antipode, bearingDeg, BENIGN_STREAM_END, clampTilt, clampZoom, deriveStage, greatCircleKm,
  lightMs, placeLabels, provenanceOf, shortestTurn, SPIN_EPSILON, SPIN_FRICTION, STAGES, STALE_MS,
  subsolar, ZOOM_MAX, ZOOM_MIN,
} from '../src/lib/observatory.ts'

let n = 0
const ok = (name, fn) => {
  fn()
  n++
  console.log(`ok  ${name}`)
}
const near = (got, want, tol, what) =>
  assert.ok(Math.abs(got - want) <= tol, `${what}: got ${got}, want ${want} +/- ${tol}`)

/** A LiveState carrying only the fields the stage machine reads. */
const state = (over = {}) => ({
  statuses: [], symbols: [], result: null, error: null, closed: false,
  carrierDb: null, epochMs: null, decode: null, fsk: null, am: null, census: null, ...over,
})
const phases = (...p) => p.map((phase) => ({ phase }))
const NOW = 1_000_000

/* ------------------------------------------------------- the stage machine, including the defect */

ok('a capture with a verdict reaches DECISION', () => {
  const s = deriveStage(state({ statuses: phases('analysing'), result: { answer: {} } }), 40, NOW, NOW)
  assert.equal(s.stage, 'DECISION')
  assert.equal(s.blocked, null)
})

ok('THE DEFECT: a verdict survives the stream close that always follows it', () => {
  // this is the exact shape the server and live.ts produce on every successful run
  const s = deriveStage(state({
    statuses: phases('connecting', 'carrier', 'analysing', 'closed'),
    result: { answer: { status: 'DECODED' } }, error: BENIGN_STREAM_END, closed: true,
  }), 120, NOW, NOW)
  assert.equal(s.stage, 'DECISION')
  assert.equal(s.blocked, null, 'a completed capture must never report a link failure')
})

ok('a refusal is also a verdict, and also survives the close', () => {
  const s = deriveStage(state({
    statuses: phases('analysing', 'closed'), result: { answer: { status: 'UNKNOWN' } },
    error: BENIGN_STREAM_END, closed: true,
  }), 120, NOW, NOW)
  assert.equal(s.stage, 'DECISION')
  assert.equal(s.blocked, null)
})

ok('a real receiver failure is still DISCONNECTED', () => {
  const s = deriveStage(state({ statuses: phases('connecting', 'receiver_failed') }), 0, 0, NOW)
  assert.equal(s.blocked, 'DISCONNECTED')
})

ok('an unexpected error outranks everything, verdict or not', () => {
  const s = deriveStage(state({ error: 'TypeError: boom', result: { answer: {} } }), 10, NOW, NOW)
  assert.equal(s.blocked, 'DISCONNECTED', 'only the benign end-of-stream is forgiven')
})

ok('a stream that closed with rows but no verdict is INSUFFICIENT CAPTURE', () => {
  const s = deriveStage(state({ statuses: phases('closed'), closed: true }), 30, NOW, NOW)
  assert.equal(s.blocked, 'INSUFFICIENT CAPTURE')
})

ok('a stream that closed with nothing at all is DISCONNECTED', () => {
  const s = deriveStage(state({ statuses: phases('closed'), closed: true }), 0, 0, NOW)
  assert.equal(s.blocked, 'DISCONNECTED')
})

ok('rows that stop flowing go STALE, and only after the threshold', () => {
  const live = state({ statuses: phases('connecting') })
  assert.equal(deriveStage(live, 5, NOW - STALE_MS + 500, NOW).blocked, null)
  assert.equal(deriveStage(live, 5, NOW - STALE_MS - 1, NOW).blocked, 'STALE')
})

ok('the progression only advances on real evidence', () => {
  const seen = (st, rows) => deriveStage(st, rows, NOW, NOW).stage
  assert.equal(seen(state(), 0), 'CONNECTING')
  assert.equal(seen(state(), 3), 'RECEIVING')
  assert.equal(seen(state({ carrierDb: -42 }), 3), 'CAPTURING')
  assert.equal(seen(state({ carrierDb: -42, epochMs: 5 }), 3), 'QUALIFYING')
  // analysing with nothing measured yet is a search; family evidence makes it a test
  assert.equal(seen(state({ statuses: phases('analysing') }), 3), 'SEARCHING')
  assert.equal(seen(state({ statuses: phases('analysing'), am: { depth: 0.3 } }), 3), 'TESTING')
})

ok('reached is a real index into STAGES, so the rail can never mis-highlight', () => {
  for (const st of [state(), state({ carrierDb: -1 }), state({ result: { answer: {} } })]) {
    const v = deriveStage(st, 1, NOW, NOW)
    assert.equal(STAGES[v.reached], v.stage)
  }
})

ok('provenance follows the source, never the animation', () => {
  assert.equal(provenanceOf('live'), 'LIVE')
  assert.equal(provenanceOf('replay'), 'RECORDED')
  assert.equal(provenanceOf(null), null)
})

/* ------------------------------------------------------------- day/night, against real astronomy */

ok('the sub-solar latitude tracks the real declination through the year', () => {
  near(subsolar(new Date('2026-03-20T12:00:00Z')).lat, 0, 0.6, 'March equinox')
  near(subsolar(new Date('2026-06-21T12:00:00Z')).lat, 23.44, 0.3, 'June solstice')
  near(subsolar(new Date('2026-12-21T12:00:00Z')).lat, -23.44, 0.3, 'December solstice')
})

ok('the sub-solar longitude tracks UTC: noon over Greenwich, midnight over the dateline', () => {
  // Noon UTC does NOT put the Sun exactly on the prime meridian: the equation of time shifts it by
  // up to about +/-16.5 minutes of solar time, i.e. +/-4.1 degrees. Mid-April is one of the four
  // dates a year where that correction passes through zero, so this is where the Sun really is
  // overhead at 12:00 UTC.
  near(subsolar(new Date('2026-04-15T12:00:00Z')).lon, 0, 0.7, 'noon UTC in mid-April')
  // and on every other day of the year the offset stays inside the equation-of-time bound
  for (let d = 0; d < 365; d += 5) {
    const lon = subsolar(new Date(Date.UTC(2026, 0, 1 + d, 12))).lon
    assert.ok(Math.abs(lon) <= 4.3, `noon UTC on day ${d} put the Sun at ${lon}, beyond the EoT bound`)
  }
  const mid = subsolar(new Date('2026-03-20T00:00:00Z')).lon
  assert.ok(Math.abs(mid) > 175, `midnight UTC should sit on the dateline, got ${mid}`)
})

ok('the sub-solar point stays inside the projection domain all day', () => {
  for (let h = 0; h < 24; h++) {
    const { lat, lon } = subsolar(new Date(Date.UTC(2026, 6, 4, h)))
    assert.ok(lon >= -180 && lon <= 180, `lon out of range at ${h}h: ${lon}`)
    assert.ok(Math.abs(lat) <= 23.5, `lat out of range at ${h}h: ${lat}`)
  }
})

ok('the night cap is centred opposite the Sun', () => {
  const sun = subsolar(new Date('2026-06-21T12:00:00Z'))
  const dark = antipode(sun)
  near(dark.lat, -sun.lat, 1e-9, 'antipodal latitude')
  assert.ok(Math.abs(Math.abs(shortestTurn(sun.lon, dark.lon)) - 180) < 1e-6, 'antipodal longitude')
})

/* ------------------------------------------------------------------------- interaction maths */

ok('zoom is clamped both ways', () => {
  assert.equal(clampZoom(0.01), ZOOM_MIN)
  assert.equal(clampZoom(99), ZOOM_MAX)
  assert.equal(clampZoom(2), 2)
})

ok('tilt can never flip the globe over a pole', () => {
  assert.equal(clampTilt(400), 89)
  assert.equal(clampTilt(-400), -89)
  for (let i = 0; i < 400; i++) assert.ok(Math.abs(clampTilt(clampTilt(i * 7) + 30)) <= 89)
})

ok('drag inertia always settles, and is neither instant nor endless', () => {
  let v = 6
  let frames = 0
  while (Math.abs(v) > SPIN_EPSILON) { v *= SPIN_FRICTION; frames++; assert.ok(frames < 10000) }
  assert.ok(frames > 20 && frames < 300, `inertia settled in ${frames} frames`)
})

ok('a turn takes the short way round the sphere', () => {
  assert.equal(shortestTurn(-170, 170), -20)
  assert.equal(shortestTurn(170, -170), 20)
  assert.equal(shortestTurn(0, 90), 90)
  assert.equal(shortestTurn(10, 10), 0)
  for (let a = -360; a <= 360; a += 13) {
    for (let b = -360; b <= 360; b += 17) {
      assert.ok(Math.abs(shortestTurn(a, b)) <= 180.0000001)
    }
  }
})

/* -------------------------------------------------------------------- labels and real distances */

ok('labels never overlap, at any layout', () => {
  const MIN = 15
  let seed = 7
  const rnd = () => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff)
  for (let t = 0; t < 200; t++) {
    const marks = Array.from({ length: 2 + Math.floor(rnd() * 18) }, () => ({
      x: rnd() * 600, y: rnd() * 500, visible: rnd() > 0.15,
    }))
    const out = placeLabels(marks, 300, MIN, 12, 488)
    for (const side of [1, -1]) {
      const col = out.filter((m) => m.visible && m.side === side).sort((a, b) => a.ly - b.ly)
      for (let i = 1; i < col.length; i++) {
        assert.ok(col[i].ly - col[i - 1].ly >= MIN - 1e-6,
          `overlap on side ${side}: ${col[i - 1].ly} then ${col[i].ly}`)
      }
    }
  }
})

ok('great-circle distance and bearing match known geography', () => {
  const delhi = { lat: 28.6139, lon: 77.209 }
  const london = { lat: 51.5072, lon: -0.1276 }
  near(greatCircleKm(delhi, london), 6708, 40, 'Delhi to London')
  near(bearingDeg(delhi, london), 313, 3, 'initial bearing, Delhi to London')
  assert.equal(Math.round(greatCircleKm(delhi, delhi)), 0)
  // light time is the distance, not a decorative number
  near(lightMs(299.792458), 1, 1e-9, 'one light-millisecond')
})

console.log(`\nALL ${n} CHECKS PASS`)
