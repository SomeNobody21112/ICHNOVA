import { motion } from 'framer-motion'
import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { GenomeGlyph } from '../components/charts'
import { AuditTrail, CaptureGate, Characteristics, DataQuality, DecisionRecord, EvidenceChain, HypothesisExplorer, provOf, ReceiptPanel, ViewsPanel, WhatWouldProveIt, WhyPanel } from '../components/evidence'
import { Icon, Loading, Panel, Stamp, Tabs, Tag } from '../components/ui'
import { CODE_SHORT, fmtAgo, fmtBw, fmtDateTime, fmtFreq, fmtInt, STATUS_MEANING } from '../lib/format'
import { cosine, GENOME_AXES, STATIONS } from '../lib/sim'
import { stationName, useApp, usePack } from '../lib/store'
import type { SignalRecord } from '../lib/types'

type LibTab = 'all' | 'known' | 'unknown' | 'recurrent' | 'archived' | 'reference' | 'benchmark'

export function SignalLibrary() {
  const { signals, reviews } = useApp()
  const nav = useNavigate()
  const [params] = useSearchParams()
  const [tab, setTab] = useState<LibTab>('all')
  const [q, setQ] = useState('')
  const station = params.get('station')
  const now = Date.now()
  const rows = useMemo(() => signals.filter((s) => {
    if (station && s.stationId !== station) return false
    if (tab === 'benchmark') return s.provenance !== 'SIMULATED'
    if (tab !== 'all' && s.library !== tab) return false
    if (q && !`${s.id} ${s.modulation ?? ''} ${s.code ?? ''} ${stationName(s.stationId)}`.toLowerCase().includes(q.toLowerCase())) return false
    return true
  }), [signals, tab, q, station])
  const count = (t: LibTab) => signals.filter((s) => (t === 'all' ? true : t === 'benchmark' ? s.provenance !== 'SIMULATED' : s.library === t)).length
  return (
    <div className="page">
      <div className="page-head">
        <div className="grow">
          <div className="section-label">Signal library</div>
          <h1 className="page-title">Signals</h1>
          <div className="page-sub">Every observation is an evidence record. Benchmark and live records carry real engine output; the monitoring world is simulated.</div>
        </div>
        {station && <Link className="chip on" to="/app/signals">{stationName(station)} <Icon name="cross" size={11} /></Link>}
        <input className="input" style={{ width: 260 }} placeholder="Search ID, modulation, code, station" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <Tabs<LibTab> value={tab} onChange={setTab} tabs={[
        { id: 'all', label: 'All', count: count('all') }, { id: 'known', label: 'Known', count: count('known') },
        { id: 'unknown', label: 'Unknown', count: count('unknown') }, { id: 'recurrent', label: 'Recurrent', count: count('recurrent') },
        { id: 'archived', label: 'Archived', count: count('archived') }, { id: 'reference', label: 'Reference', count: count('reference') },
        { id: 'benchmark', label: 'Engine evidence', count: count('benchmark') },
      ]} />
      <Panel flush>
        <div className="table-wrap" style={{ maxHeight: 'calc(100vh - 250px)' }}>
          <table className="tbl">
            <thead><tr><th>Signal</th><th>Status</th><th>Fingerprint</th><th>Station</th><th className="num">Frequency</th><th className="num">Bandwidth</th><th>Modulation</th><th>Structure</th><th className="num">Hypotheses</th><th className="num">Seen</th><th className="num">Last seen</th><th>Data</th></tr></thead>
            <tbody>{rows.slice(0, 400).map((s) => (
              <tr key={s.id} className="click" onClick={() => nav(`/app/signals/${s.id}`)}>
                <td className="mono nowrap">{s.id}</td>
                <td className="nowrap"><Stamp status={s.status} investigate={s.investigate} />{reviews[s.id] && <div className="muted" style={{ fontSize: 11 }}>reviewed: {reviews[s.id].action}</div>}</td>
                <td><GenomeGlyph values={s.genome} size={34} color={s.status === 'DECODED' ? 'var(--green)' : s.status === 'UNKNOWN' ? 'var(--amber)' : 'var(--cyan)'} /></td>
                <td className="dim nowrap">{stationName(s.stationId)}</td>
                <td className="num nowrap">{s.centerHz == null ? <span className="muted">—</span> : fmtFreq(s.centerHz)}</td>
                <td className="num nowrap">{s.bandwidthHz == null ? <span className="muted">—</span> : fmtBw(s.bandwidthHz)}</td>
                <td className="mono">{s.modulation ?? '—'}</td>
                <td className="mono nowrap">{s.code ? `${CODE_SHORT(s.code)} · ${s.interleaver?.[0]}×${s.interleaver?.[1]}` : '—'}</td>
                <td className="num">{fmtInt(s.hypotheses)}</td>
                <td className="num">{s.occurrences}</td>
                <td className="num nowrap">{fmtAgo(s.lastSeen, now)}</td>
                <td><Tag kind={s.provenance} /></td>
              </tr>
            ))}</tbody>
          </table>
          {!rows.length && <div className="empty">No signals match.</div>}
        </div>
      </Panel>
    </div>
  )
}

type DetailTab = 'overview' | 'chain' | 'hypotheses' | 'views' | 'genome' | 'audit'

function Similar({ rec }: { rec: SignalRecord }) {
  const { signals } = useApp()
  const nav = useNavigate()
  const sims = useMemo(() => signals.filter((s) => s.id !== rec.id).map((s) => ({ s, score: cosine(rec.genome, s.genome) })).sort((a, b) => b.score - a.score).slice(0, 6), [signals, rec])
  return (
    <div className="list">
      {sims.map(({ s, score }) => (
        <div key={s.id} className="list-item" onClick={() => nav(`/app/signals/${s.id}`)} style={{ gridTemplateColumns: 'auto 1fr auto auto' }}>
          <GenomeGlyph values={s.genome} compare={rec.genome} size={34} />
          <div><div className="mono" style={{ fontSize: 12 }}>{s.id}</div><div className="muted" style={{ fontSize: 11.5 }}>{stationName(s.stationId)} · {fmtFreq(s.centerHz)}</div></div>
          <Stamp status={s.status} />
          <span className="mono" style={{ color: 'var(--cyan)' }}>{(score * 100).toFixed(0)}%</span>
        </div>
      ))}
    </div>
  )
}

export function SignalDetail() {
  const { id } = useParams()
  const { signals, reviews, review, audit, world, log } = useApp()
  const [params, setParams] = useSearchParams()
  const nav = useNavigate()
  const rec = signals.find((s) => s.id === id)
  const { pack, error } = usePack(rec?.evidenceId ?? id)
  const tab = (params.get('tab') as DetailTab) ?? 'overview'
  const setTab = (t: DetailTab) => setParams(t === 'overview' ? {} : { tab: t }, { replace: true })
  if (!rec) return <div className="page"><div className="empty">Signal {id} not found. <Link to="/app/signals">Back to library</Link></div></div>
  const station = STATIONS.find((s) => s.id === rec.stationId)
  const incident = world.incidents.find((i) => i.id === rec.incidentId)
  const extraAudit = audit.filter((a) => a.subject === rec.id)
  return (
    <div className="page">
      <motion.div className="panel detail-head" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
        <div className="detail-top">
          <div style={{ minWidth: 0 }}>
            <div className="section-label">Signal record</div>
            <h1 className="page-title mono" style={{ fontSize: 22 }}>{rec.id}</h1>
            <div className="row-wrap" style={{ marginTop: 6 }}><Tag kind={rec.provenance} />{rec.description && <span className="dim" style={{ fontSize: 13 }}>{rec.description}</span>}</div>
          </div>
          <div className="col" style={{ gap: 6, alignItems: 'flex-end' }}>
            <div className="row-wrap" style={{ justifyContent: 'flex-end' }}>
              <button className="btn btn-good btn-sm" onClick={() => review(rec.id, 'Confirmed by analyst')}><Icon name="check" size={13} /> Confirm</button>
              <button className="btn btn-sm" onClick={() => review(rec.id, 'Added to library')}>Add to library</button>
              <button className="btn btn-sm" onClick={() => { log('Incident created from signal', rec.id); nav(incident ? `/app/incidents/${incident.id}` : '/app/incidents') }}><Icon name="incidents" size={13} /> {incident ? 'Open incident' : 'Create incident'}</button>
              <Link className="btn btn-sm" to={`/app/reports?signal=${rec.id}`}><Icon name="reports" size={13} /> Report</Link>
            </div>
            {reviews[rec.id] && <span className="muted" style={{ fontSize: 12 }}>{reviews[rec.id].action} · {reviews[rec.id].by} · {fmtAgo(reviews[rec.id].t)}</span>}
          </div>
        </div>
        <div className="facts">
          <div><span className="kpi-label">Status</span><Stamp status={rec.status} size="lg" investigate={rec.investigate} /><span className="muted fact-note">{STATUS_MEANING[rec.status]}</span></div>
          <div><span className="kpi-label">Observed</span><b className="mono">{fmtDateTime(rec.observedAt)}</b></div>
          <div><span className="kpi-label">Location</span><b>{station ? `Station ${station.id.slice(3)} · ${station.name}` : stationName(rec.stationId)}</b></div>
          <div><span className="kpi-label">Frequency · bandwidth</span><b className="mono">{fmtFreq(rec.centerHz)} · {fmtBw(rec.bandwidthHz)}</b></div>
        </div>
      </motion.div>

      <Tabs<DetailTab> value={tab} onChange={setTab} tabs={[
        { id: 'overview', label: 'Overview' }, { id: 'chain', label: 'Evidence chain' }, { id: 'hypotheses', label: 'Hypothesis explorer' },
        { id: 'views', label: 'Waterfall · constellation · spectrum' }, { id: 'genome', label: 'Signal genome' }, { id: 'audit', label: 'Audit & decision record' },
      ]} />
      {error && <div className="banner amber"><Icon name="info" /><span>{error}</span></div>}
      {!pack ? <Loading /> : (
        <motion.div key={tab} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
          {pack.source.kind === 'SIMULATED' && tab !== 'genome' && (
            <div className="banner muted" style={{ marginBottom: 12 }}><Icon name="info" /><span>This record is <b>simulated</b> for the monitoring demonstration; its evidence is illustrative. Open an <Link to="/app/signals/BENCH-QPSK-K7">engine evidence record</Link> for real receiver output.</span></div>
          )}
          {tab === 'overview' && (
            <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1.1fr) minmax(0, 0.9fr)', alignItems: 'start' }}>
              <div className="col" style={{ gap: 14 }}>
                <Characteristics pack={pack} />
                <Panel title="Capture quality" sub="Whether the recording can be trusted as a measurement. Reported beside the verdict, never part of it." right={<Tag kind={provOf(pack)} />}>
                  <CaptureGate pack={pack} />
                  <div className="hr" />
                  <DataQuality pack={pack} stationClock={station?.clock} />
                </Panel>
              </div>
              <div className="col" style={{ gap: 14 }}>
                <WhyPanel pack={pack} />
                {pack.result.status !== 'DECODED' && (
                  <Panel title="What would prove it?" sub="Derived from the test that refused this capture" right={<Tag kind={provOf(pack)} />}>
                    <WhatWouldProveIt pack={pack} />
                  </Panel>
                )}
                {incident && <Panel title="Linked incident"><Link to={`/app/incidents/${incident.id}`} className="row"><span className={`pri pri-${incident.priority}`}>{incident.priority}</span><span>{incident.id} · {incident.title}</span></Link></Panel>}
                <Panel title="Similar signals" sub="Fingerprint cosine similarity" right={<Tag kind="EXPERIMENTAL" />} flush><Similar rec={rec} /></Panel>
              </div>
            </div>
          )}
          {tab === 'chain' && <EvidenceChain pack={pack} />}
          {tab === 'hypotheses' && <HypothesisExplorer pack={pack} />}
          {tab === 'views' && <Panel title="Analyst views" right={<Tag kind={provOf(pack)} />}><ViewsPanel pack={pack} /></Panel>}
          {tab === 'genome' && (
            <div className="grid g-2" style={{ alignItems: 'start' }}>
              <Panel title="Signal genome" sub="Structured fingerprint of what was established about this observation" right={<Tag kind={rec.provenance === 'SIMULATED' ? 'SIMULATED' : 'EXPERIMENTAL'} />}>
                <div className="center"><GenomeGlyph values={rec.genome} size={360} labels={GENOME_AXES} color={rec.status === 'DECODED' ? 'var(--green)' : 'var(--cyan)'} /></div>
              </Panel>
              <div className="col" style={{ gap: 14 }}>
                <Panel title="Genome fields" flush>
                  <div className="list">{GENOME_AXES.map((a, i) => (
                    <div key={a} className="list-item" style={{ gridTemplateColumns: '180px 1fr 50px', cursor: 'default' }}>
                      <span className="muted" style={{ fontSize: 12.5 }}>{a}</span>
                      <div className="meter"><i style={{ width: `${rec.genome[i] * 100}%` }} /></div>
                      <span className="mono" style={{ textAlign: 'right' }}>{rec.genome[i].toFixed(2)}</span>
                    </div>
                  ))}</div>
                </Panel>
                <Panel title="Find similar signals" right={<Tag kind="EXPERIMENTAL" />} flush><Similar rec={rec} /></Panel>
              </div>
            </div>
          )}
          {tab === 'audit' && (
            <div className="grid g-2" style={{ alignItems: 'start' }}>
              <Panel title="Audit trail" right={<Tag kind={provOf(pack)} />} flush><AuditTrail pack={pack} extra={extraAudit} /></Panel>
              <div className="col" style={{ gap: 14 }}>
                <Panel title="Decision record"><DecisionRecord pack={pack} operatorAction={reviews[rec.id]?.action} /></Panel>
                <Panel title="Evidence receipt" sub="Hash-chained record of this decision, verifiable without trusting this system">
                  <ReceiptPanel pack={pack} />
                </Panel>
              </div>
            </div>
          )}
        </motion.div>
      )}
    </div>
  )
}
