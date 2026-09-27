import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useMemo, useState } from 'react'
import { Globe, type GlobePoint } from '../components/Globe'
import { EvidenceSteps, PathCard, progressSteps, RealWaterfall } from '../components/liveviz'
import { Icon, Loading, Panel, Stamp, Tag } from '../components/ui'
import { api } from '../lib/api'
import { useLiveFeed, type ReplayDoc, type ReplayIndexEntry, type StationInfo, type StationsDoc } from '../lib/live'
import { bearingDeg, branches, deriveStage, greatCircleKm, lightMs, PROVENANCE_NOTE, provenanceOf, STAGE_LABEL, STAGES, type Provenance } from '../lib/observatory'

/** The Observatory: a location-first way into the live pipeline.
 *
 *  Three acts — WORLD → RF → CAPTURE/DECISION — over the real station registry (`server/stations.py`,
 *  served as /live/stations.json). No location or receiver is hard-coded: the view is built from
 *  whatever the registry holds, so it grows the moment a verified receiver is added.
 *
 *  Every animated state is derived from real application state via `lib/observatory.ts`. A LIVE badge
 *  appears only for an actual server session; a recorded capture is always labelled RECORDED. There is
 *  no code path that animates a successful analysis the engine did not produce.
 */

type Act = 'world' | 'rf' | 'capture'
type Source = { kind: 'live'; session: string; key: string } | { kind: 'replay'; id: string; key: string }
type Entry = { key: string; station: StationInfo }
const ACTS: Act[] = ['world', 'rf', 'capture']
const ACT_LABEL: Record<Act, string> = { world: 'World', rf: 'RF', capture: 'Capture' }

const fmtKhz = (k: number) => (k >= 1000 ? `${(k / 1000).toFixed(3)} MHz` : `${k} kHz`)
const COMPASS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
const compassOf = (b: number) => COMPASS[Math.round(b / 45) % 8]
const shortSite = (s: string) => s.split('(')[0].trim()

export default function Observatory() {
  const [doc, setDoc] = useState<StationsDoc | null>(null)
  const [replays, setReplays] = useState<ReplayIndexEntry[]>([])
  const [act, setAct] = useState<Act>('world')
  const [anchorKey, setAnchorKey] = useState<string | null>(null)
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

  /** India first: it is the problem statement's country, and it holds one verified source today. */
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

  const points: GlobePoint[] = useMemo(() => entries.map(({ key, station }) => ({
    key, name: station.name, lat: station.site.lat, lon: station.site.lon, country: station.country,
  })), [entries])

  const anchorEntry = useMemo(
    () => entries.find((e) => e.key === anchorKey) ?? null, [entries, anchorKey])
  const anchorPoint = useMemo(
    () => points.find((p) => p.key === anchorKey) ?? null, [points, anchorKey])
  const anchor = anchorEntry?.station ?? null

  const provenance: Provenance | null = provenanceOf(source?.kind ?? null)
  const stage = useMemo(() => deriveStage(st, feedRows.n, feedRows.at, now), [st, feedRows, now])
  const answer = st.result?.answer
  const replayFor = (key: string) => replays.find((r) => r.station_key === key) ?? null
  const actIdx = ACTS.indexOf(act)

  /** Ranked by how far the signal has to travel from where we are listening. */
  const reachable = useMemo(() => {
    if (!anchor) return []
    return entries.map((e) => ({
      e,
      km: greatCircleKm(anchor.site, e.station.site),
      bearing: bearingDeg(anchor.site, e.station.site),
    })).sort((a, b) => a.km - b.km)
  }, [entries, anchor])

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

  function chooseCountry(list: Entry[]) {
    setAnchorKey(list[0].key)
    setPicked(null)
  }

  if (!doc) return <div className="page"><Loading label="Loading the receiver registry…" /></div>

  return (
    <div className="page obs">
      <div className="page-head">
        <div className="grow">
          <h1 className="page-title">Observatory</h1>
          <div className="page-sub">
            Choose where to listen from, see which transmitters that place can actually hear, and watch
            a capture arrive. The geography, the receivers and the link state are all real.
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
            onClick={() => { if (a === 'world') void back(a); else setAct(a) }}>
            <span className="obs-step-n">{i + 1}</span>{ACT_LABEL[a]}
          </button>
        ))}
      </nav>

      <AnimatePresence mode="wait">
        {/* ------------------------------------------------- ACT 1 · WORLD (location + receiver) */}
        {act === 'world' && (
          <motion.div key="world" className="obs-world"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="obs-globe-pane">
              <Globe points={points} anchor={anchorPoint} selected={picked?.key ?? null}
                height={560}
                onPick={(p) => {
                  const e = entries.find((x) => x.key === p.key)
                  if (!e) return
                  if (!anchorKey) { setAnchorKey(p.key); setPicked(null); return }
                  setPicked(e); setAct('rf')
                }} />
              <div className="obs-globe-cap">
                {anchor
                  ? <>Listening from <b>{shortSite(anchor.site.name)}</b>. Each arc is a great-circle path to a transmitter this place can hear — click one to open it.</>
                  : <>Earth, with every verified transmitter in the registry. Pick a region to listen from.</>}
                {' '}<span className="obs-globe-hint">Drag to spin · scroll to zoom · double-click to re-centre. The night side is the real one, for your clock.</span>
              </div>
            </div>

            <div className="obs-side">
              <Panel title="Listen from" sub={`${entries.length} transmitters · ${byCountry.length} countries`} flush>
                <div className="obs-locs">
                  {byCountry.map(([c, list]) => (
                    <button key={c}
                      className={`obs-loc${anchor?.country === c ? ' on' : ''}`}
                      onClick={() => chooseCountry(list)}>
                      <span className="obs-loc-name">{c}</span>
                      <span className="obs-loc-n">{list.length} source{list.length > 1 ? 's' : ''}</span>
                      <span className="obs-loc-sites">{list.map((e) => shortSite(e.station.site.name)).join(' · ')}</span>
                    </button>
                  ))}
                </div>
              </Panel>

              <AnimatePresence>
                {anchor && (
                  <motion.div key="reach" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }} transition={{ duration: 0.3 }}>
                    <Panel title="Reachable from here" sub="Nearest first, by great-circle distance" flush>
                      <div className="list">
                        {reachable.map(({ e, km, bearing }, i) => (
                          <motion.div key={e.key} className="list-item" role="link" tabIndex={0}
                            initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: Math.min(i * 0.05, 0.4), duration: 0.24 }}
                            onClick={() => { setPicked(e); setAct('rf') }}
                            onKeyDown={(ev) => { if (ev.key === 'Enter') { setPicked(e); setAct('rf') } }}>
                            <span className="mono obs-freq">{fmtKhz(e.station.frequency_khz)}</span>
                            <div className="grow" style={{ minWidth: 0 }}>
                              <div style={{ fontSize: 13 }}>{e.station.name}</div>
                              <div className="muted" style={{ fontSize: 12 }}>
                                {e.key === anchorKey
                                  ? 'here · this is the listening site'
                                  : `${shortSite(e.station.site.name)} · ${Math.round(km).toLocaleString('en-IN')} km ${compassOf(bearing)}`}
                              </div>
                            </div>
                            {replayFor(e.key)
                              ? <Tag kind="BENCHMARK">RECORDED</Tag>
                              : <span className="muted mono" style={{ fontSize: 11 }}>live only</span>}
                          </motion.div>
                        ))}
                      </div>
                    </Panel>
                  </motion.div>
                )}
              </AnimatePresence>

              {!anchor && (
                <Panel title="What this is" sub="A receiver, not a satellite">
                  <ul className="col" style={{ margin: 0, paddingLeft: 18, gap: 9, fontSize: 12.8 }}>
                    <li>Every mark is a <b>real transmitter</b> with an official reference, received through a public receiver.</li>
                    <li>The engine is told only <b>where to listen</b>. Carrier, timing, protocol and payload are established from the signal.</li>
                    <li><b>LIVE</b> means a session is open now; <b>RECORDED</b> is a real capture replayed. The badge is never decorative.</li>
                    <li>If the receiver drops, this screen says <b>DISCONNECTED</b>. If the engine refuses, it shows the refusal.</li>
                  </ul>
                  <p className="dim" style={{ fontSize: 12.3, marginBottom: 0 }}>
                    India holds one verified source today. This list <i>is</i> the registry, so it grows the
                    moment another verified receiver is added — nothing here is hard-coded.
                  </p>
                </Panel>
              )}
            </div>
          </motion.div>
        )}

        {/* ------------------------------------------------------------------ ACT 2 · RF */}
        {act === 'rf' && picked && (
          <motion.div key="rf" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}>
            <div className="obs-rf">
              <div className="obs-rf-freq mono">{fmtKhz(picked.station.frequency_khz)}</div>
              <div className="obs-rf-sub">{picked.station.name} · {picked.station.operator}</div>
              <div className="obs-rf-meta mono">
                <span>{picked.station.service}</span>
                <span>{picked.station.site.name}</span>
                {anchor && picked.key !== anchorKey && (
                  <span>{Math.round(greatCircleKm(anchor.site, picked.station.site)).toLocaleString('en-IN')} km · {lightMs(greatCircleKm(anchor.site, picked.station.site)).toFixed(1)} ms light time</span>
                )}
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
                  <button className="btn btn-ghost" onClick={() => setAct('world')}>Back to the globe</button>
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

        {/* ------------------------------------------------------------------ ACT 3 · CAPTURE */}
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
              <button className="btn" onClick={() => void back('world')}>
                <Icon name="chevron" size={12} /> Back to the globe
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
