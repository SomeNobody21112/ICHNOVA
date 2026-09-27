import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useMemo, useState } from 'react'
import { EvidenceSteps, PathCard, progressSteps, RealWaterfall } from '../components/liveviz'
import { Icon, Loading, Panel, Stamp, Tag } from '../components/ui'
import { api } from '../lib/api'
import { useLiveFeed, type ReplayDoc, type ReplayIndexEntry, type StationInfo, type StationsDoc } from '../lib/live'
import { bearingDeg, branches, deriveStage, greatCircleKm, lightMs, PROVENANCE_NOTE, provenanceOf, STAGE_LABEL, STAGES, type Provenance } from '../lib/observatory'

/** The Observatory: a location-first way into the live pipeline.
 *
 *  Four acts — LOCATION → RECEIVER → RF → CAPTURE/DECISION — over the real station registry
 *  (`server/stations.py`, served as /live/stations.json). No location or receiver is hard-coded: the
 *  view is built from whatever the registry holds, so it grows when a verified receiver is added.
 *
 *  Every animated state is derived from real application state via `lib/observatory.ts`. A LIVE badge
 *  appears only for an actual server session; a recorded capture is always labelled RECORDED. There is
 *  no code path that animates a successful analysis the engine did not produce.
 */

type Act = 'location' | 'source' | 'rf' | 'capture'
type Source = { kind: 'live'; session: string; key: string } | { kind: 'replay'; id: string; key: string }
type Entry = { key: string; station: StationInfo }
const ACTS: Act[] = ['location', 'source', 'rf', 'capture']

const fmtKhz = (k: number) => (k >= 1000 ? `${(k / 1000).toFixed(3)} MHz` : `${k} kHz`)
const COMPASS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
const compassOf = (b: number) => COMPASS[Math.round(b / 45) % 8]

/** The instrument dial: transmitters placed by true bearing and great-circle distance from the
 *  selected location. Real geometry, which is why it is a dial and not a map clone. */
function Dial({ from, entries, onPick, active }: {
  from: StationInfo; entries: Entry[]; onPick: (e: Entry) => void; active?: string
}) {
  const R = 132
  const marks = entries.map((e) => {
    const km = greatCircleKm(from.site, e.station.site)
    const b = bearingDeg(from.site, e.station.site)
    // log radius: a 200 km hop and a 12,000 km hop both have to be legible on one dial
    const r = km < 1 ? 14 : Math.min(R - 16, 16 + (Math.log10(km) / Math.log10(20000)) * (R - 30))
    const th = ((b - 90) * Math.PI) / 180
    return { e, km, x: Math.cos(th) * r, y: Math.sin(th) * r }
  })
  return (
    <svg viewBox={`${-R} ${-R} ${R * 2} ${R * 2}`} className="obs-dial" role="group"
      aria-label="Transmitters by bearing and distance from the selected location">
      {[0.34, 0.62, 0.9].map((f) => <circle key={f} r={R * f} className="obs-ring" />)}
      {[0, 45, 90, 135].map((a) => (
        <line key={a} x1={-R * 0.9} y1={0} x2={R * 0.9} y2={0} className="obs-cross"
          transform={`rotate(${a})`} />
      ))}
      {COMPASS.map((c, i) => {
        const th = ((i * 45 - 90) * Math.PI) / 180
        return <text key={c} x={Math.cos(th) * (R - 5)} y={Math.sin(th) * (R - 5)}
          className="obs-tick" textAnchor="middle" dominantBaseline="middle">{c}</text>
      })}
      <circle r={5} className="obs-here" />
      <circle r={5} className="obs-pulse" />
      {marks.map(({ e, x, y, km }) => (
        <g key={e.key} className={`obs-mark${active === e.key ? ' on' : ''}`} tabIndex={0} role="button"
          aria-label={`${e.station.name}, ${Math.round(km)} kilometres`}
          onClick={() => onPick(e)} onKeyDown={(ev) => { if (ev.key === 'Enter') onPick(e) }}>
          <line x1={0} y1={0} x2={x} y2={y} className="obs-arc" />
          <circle cx={x} cy={y} r={4.5} className="obs-node" />
          <text x={x} y={y - 9} textAnchor="middle" className="obs-label">{e.station.name}</text>
        </g>
      ))}
    </svg>
  )
}

export default function Observatory() {
  const [doc, setDoc] = useState<StationsDoc | null>(null)
  const [replays, setReplays] = useState<ReplayIndexEntry[]>([])
  const [act, setAct] = useState<Act>('location')
  const [country, setCountry] = useState<string | null>(null)
  const [picked, setPicked] = useState<Entry | null>(null)
  const [source, setSource] = useState<Source | null>(null)
  const [replayDoc, setReplayDoc] = useState<ReplayDoc | null>(null)
  const [starting, setStarting] = useState(false)
  const [startErr, setStartErr] = useState<string | null>(null)
  // one piece of state, not a ref: the stage memo must re-run when a row lands, and a ref read
  // during render would not trigger that.
  const [feedRows, setFeedRows] = useState({ n: 0, at: 0 })
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    fetch('/live/stations.json').then((r) => r.json()).then(setDoc).catch(() => setDoc(null))
    fetch('/live/index.json').then((r) => r.json()).then(setReplays).catch(() => setReplays([]))
  }, [])

  const feed = useLiveFeed(source?.kind === 'live'
    ? { kind: 'live', session: source.session }
    : { kind: 'replay', doc: replayDoc, speed: 1, playing: true })
  const st = feed.state

  // count real rows; the capture counter and the STALE test are facts about the transport
  useEffect(() => feed.subscribe(() => {
    setFeedRows((r) => ({ n: r.n + 1, at: Date.now() }))
  }), [feed])
  // 1 Hz is enough to notice staleness; no animation frame is burned on it
  useEffect(() => {
    if (act !== 'capture') return
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [act])

  const entries: Entry[] = useMemo(
    () => Object.entries(doc?.stations ?? {}).map(([key, station]) => ({ key, station })), [doc])
  const byCountry = useMemo(() => {
    const m = new Map<string, Entry[]>()
    for (const e of entries) {
      const list = m.get(e.station.country) ?? []
      list.push(e)
      m.set(e.station.country, list)
    }
    return [...m.entries()].sort((a, b) => (a[0] === 'India' ? -1 : b[0] === 'India' ? 1
      : a[0].localeCompare(b[0])))
  }, [entries])

  const anchor = useMemo(
    () => (country ? byCountry.find(([c]) => c === country)?.[1][0]?.station ?? null : null),
    [country, byCountry])

  const provenance: Provenance | null = provenanceOf(source?.kind ?? null)
  const stage = useMemo(() => deriveStage(st, feedRows.n, feedRows.at, now), [st, feedRows, now])
  const answer = st.result?.answer
  const replayFor = (key: string) => replays.find((r) => r.station_key === key) ?? null
  const actIdx = ACTS.indexOf(act)

  async function startLive(e: Entry) {
    setStarting(true); setStartErr(null); setFeedRows({ n: 0, at: 0 })
    try {
      const r = await api(`/api/live/start?station=${encodeURIComponent(e.key)}&mode=iq`,
        { method: 'POST' })
      const j = await r.json()
      if (!j?.session) throw new Error('the server did not open a session')
      setSource({ kind: 'live', session: j.session, key: e.key }); setReplayDoc(null); setAct('capture')
    } catch (err) {
      // a failed start is reported as a failed start; it never becomes a fake LIVE session
      setStartErr(err instanceof Error ? err.message : 'could not reach the receiver')
    } finally { setStarting(false) }
  }

  function startReplay(e: Entry) {
    const r = replayFor(e.key)
    if (!r) return
    setFeedRows({ n: 0, at: 0 }); setStartErr(null)
    fetch(`/live/${r.id}.json`).then((x) => x.json()).then((d: ReplayDoc) => {
      setReplayDoc(d); setSource({ kind: 'replay', id: r.id, key: e.key }); setAct('capture')
    }).catch(() => setStartErr('the recording could not be loaded'))
  }

  async function back(to: Act) {
    if (source?.kind === 'live') {
      await api(`/api/live/stop?session=${source.session}`, { method: 'POST' }).catch(() => undefined)
    }
    setSource(null); setReplayDoc(null); setFeedRows({ n: 0, at: 0 }); setStartErr(null); setAct(to)
  }

  if (!doc) return <div className="page"><Loading label="Loading the receiver registry…" /></div>

  return (
    <div className="page obs">
      <div className="page-head">
        <div className="grow">
          <h1 className="page-title">Observatory</h1>
          <div className="page-sub">
            Pick a location, see which verified transmitters are reachable from it, and watch a capture
            arrive. Everything here is the real registry and the real link state.
          </div>
        </div>
        {provenance
          ? <Tag kind={provenance === 'LIVE' ? 'LIVE' : 'BENCHMARK'}>{provenance === 'LIVE' ? 'Live reception' : 'Recorded real capture'}</Tag>
          : <Tag kind="LIVE">Real receivers</Tag>}
      </div>

      <nav className="obs-rail" aria-label="Observatory steps">
        {ACTS.map((a, i) => (
          <button key={a} className={`obs-step${act === a ? ' on' : ''}${i < actIdx ? ' past' : ''}`}
            disabled={i > actIdx}
            onClick={() => { if (a === 'location' || a === 'source') void back(a); else setAct(a) }}>
            <span className="obs-step-n">{i + 1}</span>
            {a === 'location' ? 'Location' : a === 'source' ? 'Receiver' : a === 'rf' ? 'RF' : 'Capture'}
          </button>
        ))}
      </nav>

      <AnimatePresence mode="wait">
        {/* ----------------------------------------------------------- ACT 1 · LOCATION */}
        {act === 'location' && (
          <motion.div key="loc" className="grid g-2" style={{ alignItems: 'start' }}
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
            <Panel title="Where are we listening from?" sub={`${entries.length} verified transmitters across ${byCountry.length} countries, from the station registry`}>
              <div className="obs-locs">
                {byCountry.map(([c, list]) => (
                  <button key={c} className={`obs-loc${country === c ? ' on' : ''}`}
                    onClick={() => { setCountry(c); setAct('source') }}>
                    <span className="obs-loc-name">{c}</span>
                    <span className="obs-loc-n">{list.length} source{list.length > 1 ? 's' : ''}</span>
                    <span className="obs-loc-sites">{list.map((e) => e.station.site.name.split('(')[0].trim()).join(' · ')}</span>
                  </button>
                ))}
              </div>
              <p className="dim" style={{ fontSize: 12.5, marginBottom: 0 }}>
                India has one verified source today — All India Radio Chennai. This list <i>is</i> the
                registry, so it grows the moment another verified receiver is added; nothing is hard-coded.
              </p>
            </Panel>
            <Panel title="What this is" sub="A receiver, not a satellite">
              <ul className="col" style={{ margin: 0, paddingLeft: 18, gap: 9, fontSize: 12.8 }}>
                <li>Each entry is a <b>real transmitter</b> with an official reference, received through a public receiver.</li>
                <li>The engine is told only <b>where to listen</b>. Carrier, symbol timing, protocol and payload are established from the signal.</li>
                <li><b>LIVE</b> means a session is open right now. <b>RECORDED</b> means a real capture replayed with its own timestamps. The badge is never decorative.</li>
                <li>If the receiver drops, this screen says <b>DISCONNECTED</b>. If the engine refuses, it shows the refusal.</li>
              </ul>
            </Panel>
          </motion.div>
        )}

        {/* ----------------------------------------------------------- ACT 2 · RECEIVER */}
        {act === 'source' && anchor && (
          <motion.div key="src" className="grid g-2" style={{ alignItems: 'start' }}
            initial={{ opacity: 0, scale: 0.985 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}>
            <Panel title={`Reachable from ${country}`} sub="Bearing and great-circle distance from the first site in this region — real geometry, not a map" flush>
              <div className="obs-dial-wrap">
                <Dial from={anchor} entries={entries} active={picked?.key}
                  onPick={(e) => { setPicked(e); setAct('rf') }} />
              </div>
            </Panel>
            <Panel title="Sources" sub="Select one to open the RF view" flush>
              <div className="list">
                {entries.map((e) => {
                  const km = greatCircleKm(anchor.site, e.station.site)
                  const rep = replayFor(e.key)
                  return (
                    <div key={e.key} className="list-item" role="link" tabIndex={0}
                      onClick={() => { setPicked(e); setAct('rf') }}
                      onKeyDown={(ev) => { if (ev.key === 'Enter') { setPicked(e); setAct('rf') } }}>
                      <span className="mono obs-freq">{fmtKhz(e.station.frequency_khz)}</span>
                      <div className="grow" style={{ minWidth: 0 }}>
                        <div style={{ fontSize: 13 }}>{e.station.name}</div>
                        <div className="muted" style={{ fontSize: 12 }}>
                          {e.station.site.name} · {Math.round(km).toLocaleString('en-IN')} km {compassOf(bearingDeg(anchor.site, e.station.site))}
                        </div>
                      </div>
                      {rep ? <Tag kind="BENCHMARK">RECORDED</Tag>
                        : <span className="muted mono" style={{ fontSize: 11 }}>live only</span>}
                    </div>
                  )
                })}
              </div>
            </Panel>
          </motion.div>
        )}

        {/* ----------------------------------------------------------- ACT 3 · RF */}
        {act === 'rf' && picked && (
          <motion.div key="rf" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}>
            <div className="obs-rf">
              <div className="obs-rf-freq mono">{fmtKhz(picked.station.frequency_khz)}</div>
              <div className="obs-rf-sub">{picked.station.name} · {picked.station.operator}</div>
              <div className="obs-rf-meta mono">
                <span>{picked.station.service}</span>
                <span>{picked.station.site.name}</span>
                {anchor && <span>{Math.round(greatCircleKm(anchor.site, picked.station.site)).toLocaleString('en-IN')} km · {lightMs(greatCircleKm(anchor.site, picked.station.site)).toFixed(1)} ms light time</span>}
              </div>
            </div>
            <div className="grid g-2" style={{ alignItems: 'start', marginTop: 14 }}>
              <Panel title="Open a capture" sub="Live needs the receiver reachable now; a recording is a real capture replayed">
                <div className="row-wrap" style={{ gap: 10 }}>
                  <button className="btn btn-primary" disabled={starting}
                    onClick={() => void startLive(picked)}>
                    <Icon name="play" size={12} /> {starting ? 'Opening receiver…' : 'Start live analysis'}
                  </button>
                  {replayFor(picked.key)
                    ? <button className="btn" onClick={() => startReplay(picked)}>Replay recorded capture</button>
                    : <span className="muted" style={{ fontSize: 12.5, alignSelf: 'center' }}>No recorded capture for this source yet</span>}
                </div>
                {startErr && (
                  <div className="banner amber" style={{ marginTop: 12 }}>
                    <Icon name="flag" />
                    <div><b>DISCONNECTED.</b> {startErr}. Nothing is shown as received, because nothing was.</div>
                  </div>
                )}
                <p className="dim" style={{ fontSize: 12.5, marginBottom: 0 }}>
                  Live reception needs outbound access to a public receiver. Where that is unavailable the
                  recorded capture carries the same evidence and is labelled <b>RECORDED</b>.
                </p>
              </Panel>
              <Panel title="Reference" sub="Every source is checkable">
                <ul className="col" style={{ margin: 0, paddingLeft: 18, gap: 7, fontSize: 12.5 }}>
                  {picked.station.references.map((r) => (
                    <li key={r.url}><a href={r.url} target="_blank" rel="noreferrer">{r.title}</a></li>
                  ))}
                </ul>
              </Panel>
            </div>
          </motion.div>
        )}

        {/* ----------------------------------------------------------- ACT 4 · CAPTURE */}
        {act === 'capture' && picked && (
          <motion.div key="cap" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            {provenance && (
              <div className={`banner${provenance === 'LIVE' ? '' : ' amber'}`} style={{ marginBottom: 12 }}>
                <Icon name={provenance === 'LIVE' ? 'monitor' : 'play'} />
                <div><b>{provenance === 'LIVE' ? 'LIVE' : 'RECORDED REAL CAPTURE'}.</b> {PROVENANCE_NOTE[provenance]}</div>
              </div>
            )}

            <div className="obs-stages">
              {STAGES.map((s, i) => (
                <div key={s} className={`obs-stage${i < stage.reached ? ' past' : ''}${i === stage.reached ? ' on' : ''}`}>
                  <span className="obs-stage-dot" />
                  <span className="obs-stage-t">{STAGE_LABEL[s]}</span>
                </div>
              ))}
            </div>
            {stage.blocked && (
              <div className="banner amber" style={{ marginBottom: 12 }}>
                <Icon name="flag" />
                <div><b>{stage.blocked}.</b> {stage.blocked === 'STALE'
                  ? 'No spectrum row has arrived recently; the link is not delivering.'
                  : stage.blocked === 'DISCONNECTED'
                    ? (st.error ?? 'The receiver dropped the session.')
                    : 'The capture ended before the engine reached a verdict. No answer is asserted.'}</div>
              </div>
            )}

            <div className="grid g-2" style={{ alignItems: 'start' }}>
              <Panel title="Spectrum as it arrives" sub={`${feedRows.n.toLocaleString('en-IN')} rows received${st.span ? ` · ${(st.span[1] - st.span[0]).toFixed(0)} Hz span` : ''}`} flush>
                <RealWaterfall subscribe={feed.subscribe} height={260}
                  idle={feedRows.n ? undefined : 'waiting for the first spectrum row'} />
              </Panel>
              <div className="col" style={{ gap: 14 }}>
                <Panel title="Link" sub="The receiver the server actually chose">
                  <PathCard station={picked.station} receiver={st.receiver} />
                </Panel>
                <Panel title="Competing readings" sub={answer ? 'Resolved by the engine’s own answer' : 'Open until the engine answers'}>
                  <div className="obs-branches">
                    {branches(st, picked.station).map((b) => (
                      <div key={b.label} className={`obs-branch ${b.state}`}>
                        <span className="obs-branch-m">{b.state === 'won' ? '✓' : b.state === 'lost' ? '✕' : '·'}</span>
                        <span>{b.label}</span>
                      </div>
                    ))}
                  </div>
                  <p className="dim" style={{ fontSize: 12.3, margin: '10px 0 0' }}>
                    Nothing is marked until the analysis finishes. A reading that loses is still shown — the
                    alternatives are part of the evidence.
                  </p>
                </Panel>
              </div>
            </div>

            <AnimatePresence>
              {answer && (
                <motion.div key="verdict" className="obs-verdict"
                  initial={{ opacity: 0, y: 18, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}>
                  <div className="obs-verdict-head">
                    <Stamp status={answer.status} size="xl" />
                    <div className="grow">
                      <div style={{ fontSize: 13.5 }}>
                        {answer.protocol ? <b>{answer.protocol}</b> : <b>No catalogue code established</b>}
                        {answer.operator ? <span className="muted"> · {answer.operator}</span> : null}
                      </div>
                      <div className="muted" style={{ fontSize: 12.5 }}>
                        {answer.status === 'DECODED' ? 'The evidence supports this reading.'
                          : answer.status === 'SIGNAL_NO_CODE' ? 'A signal is established; no payload is asserted.'
                            : 'The evidence does not support any reading.'}
                      </div>
                    </div>
                  </div>
                  {answer.status === 'SIGNAL_NO_CODE' && (
                    <div className="obs-split">
                      <div className="obs-half ok"><span className="obs-half-k">STRUCTURE</span><span className="obs-half-v">✓ ESTABLISHED</span></div>
                      <div className="obs-half no"><span className="obs-half-k">PAYLOAD</span><span className="obs-half-v">✕ WITHHELD</span></div>
                    </div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>

            <Panel title="Evidence behind the answer" sub="Assembled from the run, in the order it arrived"
              style={{ marginTop: 14 }}>
              <EvidenceSteps steps={progressSteps(picked.station.analysis ?? 'timecode', st, picked.station)} />
            </Panel>

            <div className="row-wrap" style={{ gap: 10, marginTop: 14 }}>
              <button className="btn" onClick={() => void back('source')}>
                <Icon name="chevron" size={12} /> Another source
              </button>
              <button className="btn btn-ghost" onClick={() => void back('location')}>Another location</button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
