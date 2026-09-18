import { useSearchParams } from 'react-router-dom'
import { provOf } from '../components/evidence'
import { Icon, Loading, Panel, Seg, Tag } from '../components/ui'
import { CODE_FULL, STATUS_LABEL, STATUS_MEANING, fmtDateTime, fmtFreq, fmtFs, fmtInt, fmtInterleaver, fmtP } from '../lib/format'
import { stationName, useApp, usePack } from '../lib/store'
import { PRODUCT } from '../brand'

function save(name: string, text: string, type: string) {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([text], { type }))
  a.download = name
  a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 1000)
}

function SignalReport({ id }: { id: string }) {
  const { signals, audit, reviews, session, log } = useApp()
  const rec = signals.find((s) => s.id === id)
  const { pack, error } = usePack(rec?.evidenceId ?? id)
  if (error) return <div className="empty">{error}</div>
  if (!pack || !rec) return <Loading />
  const acc = pack.accept.accepted_hypothesis
  const r = pack.result
  const trail = audit.filter((e) => e.subject === id)
  return (
    <>
      <div className="row no-print" style={{ marginBottom: 12 }}>
        <button className="btn btn-primary" onClick={() => { log('Report printed', id); window.print() }}><Icon name="download" size={14} /> Print / save PDF</button>
        <button className="btn" onClick={() => { log('Evidence exported', id, 'JSON'); save(`${id}.evidence.json`, JSON.stringify(pack, null, 1), 'application/json') }}>Evidence pack (JSON)</button>
        <button className="btn" onClick={() => save(`${id}.audit.csv`, ['time,actor,action,subject,detail', ...trail.map((e) => [new Date(e.t).toISOString(), e.actor, e.action, e.subject, e.detail ?? ''].map((v) => `"${String(v).replace(/"/g, '""')}"`).join(','))].join('\n'), 'text/csv')}>Audit trail (CSV)</button>
        <span className="grow" />
        <Tag kind={provOf(pack)} />
      </div>
      <article className="print-report">
        <div style={{ fontSize: 11, color: '#666', letterSpacing: '0.1em', textTransform: 'uppercase' }}>{PRODUCT.name} · Signal evidence report · {provOf(pack)} data</div>
        <h1 style={{ margin: '4px 0 2px' }}>{rec.id} — {STATUS_LABEL[r.status]}</h1>
        <p style={{ margin: 0, color: '#444' }}>{STATUS_MEANING[r.status]}</p>
        <h2>1. Capture</h2>
        <table><tbody>
          <tr><th>Station</th><td>{stationName(rec.stationId)}</td><th>Centre frequency</th><td>{fmtFreq(rec.centerHz)}</td></tr>
          <tr><th>Samples</th><td>{fmtInt(pack.capture.samples)}</td><th>Sample rate</th><td>{fmtFs(pack.capture)}</td></tr>
          <tr><th>Source</th><td>{pack.source.kind}{pack.source.file ? ` · ${pack.source.file}` : ''}</td><th>Analysed</th><td>{pack.analysed_at}</td></tr>
        </tbody></table>
        <h2>2. Established characteristics</h2>
        <table><tbody>
          <tr><th>Modulation</th><td>{r.modulation ?? 'not established'}</td><th>Samples / symbol</th><td>{r.sps ?? 'not established'}</td></tr>
          <tr><th>Carrier offset (cycles/sample)</th><td>{r.cfo?.toFixed(6) ?? 'not established'}</td><th>Code</th><td>{r.code ? CODE_FULL[r.code] ?? r.code : 'not established'}</td></tr>
          <tr><th>Interleaver</th><td>{r.interleaver ? `block ${fmtInterleaver(r.interleaver, 'short')}` : 'not established'}</td><th>Payload</th><td>{r.payload_len ? `${r.payload_len} bits` : '—'}</td></tr>
        </tbody></table>
        <h2>3. Statistical validation</h2>
        <p>{fmtInt(pack.accept.n_hypotheses)} hypotheses were tested. Acceptance required log₁₀ p ≤ {pack.accept.log10_threshold.toFixed(2)} (α = {pack.accept.alpha}, Bonferroni over all hypotheses) and passing the modulation, block-length and path-metric consistency checks.</p>
        <table><tbody>
          <tr><th>Best evidence</th><td>{fmtP(pack.accept.log10_p)}</td><th>Accepted hypothesis</th><td>{acc ? `${acc.modulation} · ${acc.code} · ${fmtInterleaver(acc.interleaver, 'short')}` : 'none'}</td></tr>
          {acc && <tr><th>Parity checks satisfied</th><td>{acc.n_positive} / {acc.n_checks}</td><th>Path metric</th><td>{acc.path_metric.toFixed(3)} (floor {pack.accept.rules.pm_floor})</td></tr>}
        </tbody></table>
        {pack.accept.significant_but_rejected.length > 0 && <>
          <h2>4. Significant hypotheses rejected</h2>
          <table><thead><tr><th>Hypothesis</th><th>log₁₀ p</th><th>Reason</th></tr></thead><tbody>
            {pack.accept.significant_but_rejected.slice(0, 8).map((h, i) => <tr key={i}><td>{h.modulation} · {h.code} · {fmtInterleaver(h.interleaver, 'short')} · sps {h.sps}</td><td>{h.log10_p.toFixed(2)}</td><td>{h.structural_rejection}</td></tr>)}
          </tbody></table>
        </>}
        <h2>{pack.accept.significant_but_rejected.length ? 5 : 4}. Review & audit</h2>
        <table><tbody>
          <tr><th>Operator decision</th><td>{reviews[id] ? `${reviews[id].action} by ${reviews[id].by} at ${fmtDateTime(reviews[id].t)}` : 'not reviewed'}</td></tr>
          <tr><th>Engine</th><td>v{pack.engine.version} · commit {pack.engine.commit}</td></tr>
          <tr><th>Prepared by</th><td>{session?.name ?? '—'} · {fmtDateTime(Date.now())}</td></tr>
        </tbody></table>
        {trail.length > 0 && <ul style={{ fontSize: 12 }}>{trail.map((e, i) => <li key={i}>{fmtDateTime(e.t)} · {e.actor} · {e.action}{e.detail ? ` · ${e.detail}` : ''}</li>)}</ul>}
        <p style={{ fontSize: 11, color: '#777', marginTop: 18 }}>{PRODUCT.disclaimer}</p>
      </article>
    </>
  )
}

function IncidentReport({ id }: { id: string }) {
  const { world, notes } = useApp()
  const inc = world.incidents.find((i) => i.id === id)
  if (!inc) return <div className="empty">No incident {id}</div>
  return (
    <>
      <div className="row no-print" style={{ marginBottom: 12 }}><button className="btn btn-primary" onClick={() => window.print()}><Icon name="download" size={14} /> Print / save PDF</button><span className="grow" /><Tag kind="SIMULATED" /></div>
      <article className="print-report">
        <div style={{ fontSize: 11, color: '#666', letterSpacing: '0.1em', textTransform: 'uppercase' }}>{PRODUCT.name} · Incident report · SIMULATED data</div>
        <h1 style={{ margin: '4px 0' }}>{inc.id} — {inc.title}</h1>
        <p>{inc.summary}</p>
        <table><tbody>
          <tr><th>Priority</th><td>{inc.priority}</td><th>Status</th><td>{inc.status}</td></tr>
          <tr><th>First seen</th><td>{fmtDateTime(inc.firstSeen)}</td><th>Last seen</th><td>{fmtDateTime(inc.lastSeen)}</td></tr>
          <tr><th>Stations</th><td colSpan={3}>{inc.stationIds.map(stationName).join(', ')}</td></tr>
        </tbody></table>
        <h2>Timeline</h2>
        <table><thead><tr><th>Time</th><th>Station</th><th>Signal</th></tr></thead><tbody>
          {inc.events.map((e, i) => <tr key={i}><td>{fmtDateTime(e.t)}</td><td>{stationName(e.stationId)}</td><td>{e.signalId}</td></tr>)}
        </tbody></table>
        <h2>Analyst notes</h2>
        {(notes[id] ?? []).length ? <ul>{notes[id].map((n, i) => <li key={i}>{fmtDateTime(n.t)} · {n.by}: {n.text}</li>)}</ul> : <p>No notes.</p>}
        <p style={{ fontSize: 11, color: '#777', marginTop: 18 }}>{PRODUCT.disclaimer}</p>
      </article>
    </>
  )
}

export default function Reports() {
  const { signals, world } = useApp()
  const [params, setParams] = useSearchParams()
  const kind = params.get('incident') ? 'incident' : 'signal'
  const sid = params.get('signal') ?? signals.find((s) => s.provenance !== 'SIMULATED')?.id ?? signals[0]?.id
  const iid = params.get('incident') ?? world.incidents[0]?.id
  return (
    <div className="page">
      <div className="page-head no-print">
        <div className="grow">
          <div className="section-label">Reporting</div>
          <h1 className="page-title">Reports</h1>
          <div className="page-sub">A report is the evidence record in document form: what was established, how it was validated, what was rejected and who reviewed it.</div>
        </div>
        <Seg<'signal' | 'incident'> options={[{ id: 'signal', label: 'Signal' }, { id: 'incident', label: 'Incident' }]} value={kind} onChange={(k) => setParams(k === 'signal' ? { signal: sid } : { incident: iid })} />
        {kind === 'signal'
          ? <select className="select" style={{ width: 260 }} value={sid} onChange={(e) => setParams({ signal: e.target.value })}>{signals.slice(0, 80).map((s) => <option key={s.id} value={s.id}>{s.id} · {s.provenance}</option>)}</select>
          : <select className="select" style={{ width: 260 }} value={iid} onChange={(e) => setParams({ incident: e.target.value })}>{world.incidents.map((i) => <option key={i.id} value={i.id}>{i.id} · {i.title}</option>)}</select>}
      </div>
      <Panel>{kind === 'signal' && sid ? <SignalReport key={sid} id={sid} /> : iid ? <IncidentReport id={iid} /> : <div className="empty">Nothing to report.</div>}</Panel>
    </div>
  )
}
