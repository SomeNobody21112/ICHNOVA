import { motion } from 'framer-motion'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { TimelineStrip } from '../components/charts'
import { Icon, Panel, Stamp, Tag } from '../components/ui'
import { fmtAgo, fmtDate, fmtDateTime } from '../lib/format'
import { stationName, useApp } from '../lib/store'

export function IncidentList() {
  const { world } = useApp()
  const nav = useNavigate()
  return (
    <div className="page">
      <div className="page-head">
        <div className="grow">
          <div className="eyebrow">Workflow objects</div>
          <h1 className="page-title">Incidents</h1>
          <div className="page-sub">An incident is opened when observations form a pattern worth investigating, not for every signal.</div>
        </div>
        <Tag kind="SIMULATED" />
      </div>
      <Panel flush>
        <table className="tbl">
          <thead><tr><th>Incident</th><th>Priority</th><th>Title</th><th>Status</th><th className="num">Observations</th><th className="num">Stations</th><th className="num">First observed</th><th className="num">Last observed</th></tr></thead>
          <tbody>{world.incidents.map((i) => (
            <tr key={i.id} className="click" onClick={() => nav(`/app/incidents/${i.id}`)}>
              <td className="mono">{i.id}</td><td><span className={`pri pri-${i.priority}`}>{i.priority}</span></td><td>{i.title}</td>
              <td className="mono" style={{ fontSize: 11.5, color: i.status === 'UNDER INVESTIGATION' ? 'var(--orange)' : i.status === 'CLOSED' ? 'var(--muted)' : 'var(--text-2)' }}>{i.status}</td>
              <td className="num">{i.events.length}</td><td className="num">{i.stationIds.length}</td><td className="num">{fmtDate(i.firstSeen)}</td><td className="num">{fmtAgo(i.lastSeen)}</td>
            </tr>
          ))}</tbody>
        </table>
      </Panel>
    </div>
  )
}

export function IncidentDetail() {
  const { id } = useParams()
  const { world, signals, notes, addNote, log } = useApp()
  const nav = useNavigate()
  const inc = world.incidents.find((i) => i.id === id)
  const [text, setText] = useState('')
  const [status, setStatus] = useState(inc?.status)
  if (!inc) return <div className="page"><div className="empty">Incident not found.</div></div>
  const related = signals.filter((s) => inc.signalIds.includes(s.id))
  const lanes = inc.stationIds.map((s) => ({ id: s, label: stationName(s) }))
  return (
    <div className="page">
      <div className="row" style={{ marginBottom: 10 }}><button className="btn btn-ghost btn-sm" onClick={() => nav('/app/incidents')}><Icon name="back" size={13} /> Incidents</button></div>
      <motion.div className="panel" style={{ padding: '16px 18px', marginBottom: 14 }} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
        <div className="row-wrap" style={{ gap: 28, alignItems: 'flex-start' }}>
          <div><div className="eyebrow">Incident #{inc.id}</div><div className="page-title">{inc.kind}</div><div className="muted">{inc.title}</div></div>
          <div><div className="kpi-label">First observed</div><div className="mono">{fmtDateTime(inc.firstSeen)}</div><div className="kpi-label" style={{ marginTop: 8 }}>Last observed</div><div className="mono">{fmtDateTime(inc.lastSeen)}</div></div>
          <div><div className="kpi-label">Occurrences</div><div className="kpi-value">{inc.events.length}</div></div>
          <div><div className="kpi-label">Locations</div><div className="kpi-value">{inc.stationIds.length}</div></div>
          <span className="spacer" />
          <div className="col" style={{ gap: 6, alignItems: 'flex-end' }}>
            <span className={`pri pri-${inc.priority}`}>{inc.priority} PRIORITY</span>
            <select className="select" style={{ width: 220 }} value={status} onChange={(e) => { setStatus(e.target.value as typeof inc.status); log(`Incident status → ${e.target.value}`, inc.id) }}>
              {['OPEN', 'UNDER INVESTIGATION', 'MONITORING', 'CLOSED'].map((s) => <option key={s}>{s}</option>)}
            </select>
            <Tag kind="SIMULATED" />
          </div>
        </div>
      </motion.div>
      <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1.4fr) minmax(0, 0.6fr)', alignItems: 'start' }}>
        <div className="col" style={{ gap: 14 }}>
          <Panel title="Observation timeline" sub="Each mark is one observation; click to open the signal record">
            <TimelineStrip lanes={lanes} from={inc.firstSeen - 3600e3} to={inc.lastSeen + 3600e3}
              events={inc.events.map((e) => ({ t: e.t, lane: e.stationId, id: e.signalId, tone: 'var(--amber)' }))} onPick={(sid) => nav(`/app/signals/${sid}`)} />
          </Panel>
          <Panel title="Related signals" flush>
            <div className="list">{related.map((s) => (
              <div key={s.id} className="list-item" onClick={() => nav(`/app/signals/${s.id}`)}>
                <span className="mono">{s.id}</span><span className="muted" style={{ fontSize: 12 }}>{stationName(s.stationId)} · {fmtAgo(s.observedAt)}</span><Stamp status={s.status} investigate={s.investigate} />
              </div>
            ))}</div>
          </Panel>
        </div>
        <div className="col" style={{ gap: 14 }}>
          <Panel title="Summary"><p className="dim" style={{ margin: 0 }}>{inc.summary}</p></Panel>
          <Panel title="Attachments" flush>
            <div className="list">
              {related.slice(0, 3).map((s) => <Link key={s.id} to={`/app/signals/${s.id}?tab=chain`} className="list-item" style={{ gridTemplateColumns: 'auto 1fr' }}><Icon name="decision" size={15} /><span>Evidence chain · {s.id}</span></Link>)}
              <Link to={`/app/reports?incident=${inc.id}`} className="list-item" style={{ gridTemplateColumns: 'auto 1fr' }}><Icon name="reports" size={15} /><span>Incident report</span></Link>
            </div>
          </Panel>
          <Panel title="Analyst notes">
            <div className="col" style={{ gap: 8 }}>
              {(notes[inc.id] ?? []).map((n, i) => <div key={i} className="banner" style={{ padding: '8px 10px' }}><div><div style={{ fontSize: 12.5 }}>{n.text}</div><div className="muted" style={{ fontSize: 11 }}>{n.by} · {fmtAgo(n.t)}</div></div></div>)}
              <textarea className="textarea" value={text} onChange={(e) => setText(e.target.value)} placeholder="Add an observation, hypothesis or next step" />
              <button className="btn btn-primary btn-sm" disabled={!text.trim()} onClick={() => { addNote(inc.id, text.trim()); setText('') }}>Add note</button>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  )
}
