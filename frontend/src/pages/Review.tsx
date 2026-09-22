import { AnimatePresence, motion } from 'framer-motion'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { GenomeGlyph } from '../components/charts'
import { Icon, Panel, Seg, Stamp, Tag } from '../components/ui'
import { fmtAgo, fmtFreq } from '../lib/format'
import { stationName, useApp, useCan, whyNot } from '../lib/store'

type Filter = 'OPEN' | 'DONE'

export default function Review() {
  const { signals, reviews, review, session } = useApp()
  const mayReview = useCan('review')
  const cannotReview = whyNot(session?.authRole, 'review')
  const [filter, setFilter] = useState<Filter>('OPEN')
  const queue = useMemo(() => signals.filter((s) => s.status !== 'DECODED' || s.investigate), [signals])
  const open = queue.filter((s) => !reviews[s.id])
  const done = queue.filter((s) => reviews[s.id])
  const list = (filter === 'OPEN' ? open : done).slice(0, 60)
  return (
    <div className="page">
      <div className="page-head">
        <div className="grow">
          <div className="section-label">Human + machine loop</div>
          <h1 className="page-title"><span style={{ color: 'var(--amber)' }}>{open.length}</span> signals require review</h1>
          <div className="page-sub">Unknowns and anomalies are routed to an analyst, never silently labelled. Validated decisions are logged and can later become reference data.</div>
        </div>
        <Seg<Filter> options={[{ id: 'OPEN', label: `Open ${open.length}` }, { id: 'DONE', label: `Reviewed ${done.length}` }]} value={filter} onChange={setFilter} />
      </div>
      <div className="grid g-3">
        <AnimatePresence>
          {list.map((s) => (
            <motion.div key={s.id} layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.97 }}>
              {/* The whole card opens the record: the ID link's hit area is stretched over the card
                  (.card-link-target::after), and the review buttons sit above it, so each click
                  still does exactly one thing and there is no button nested in a link. */}
              <div className="card card-link col" style={{ gap: 10, height: '100%' }}>
                <div className="row">
                  <Link to={`/app/signals/${s.id}`} className="mono grow card-link-target" aria-label={`Open signal record ${s.id}`} style={{ fontSize: 13.5, minHeight: 24, display: 'flex', alignItems: 'center' }}>{s.id}</Link>
                  <Tag kind={s.provenance} />
                </div>
                <div className="row" style={{ gap: 12 }}>
                  <GenomeGlyph values={s.genome} size={52} color={s.status === 'UNKNOWN' ? 'var(--amber)' : 'var(--cyan)'} />
                  {/* min-width 0: without it this column refuses to shrink and the badges are
                      clipped by the card edge instead of wrapping. */}
                  <div className="col" style={{ gap: 4, minWidth: 0 }}>
                    <Stamp status={s.status} investigate={s.investigate} />
                    <span className="muted" style={{ fontSize: 12 }}>{stationName(s.stationId)} · {fmtFreq(s.centerHz)} · {fmtAgo(s.observedAt)}</span>
                  </div>
                </div>
                <div><div className="kpi-label">Reason</div><div style={{ fontSize: 12.5 }}>{s.reason}</div></div>
                {s.candidates.length > 0 && <div><div className="kpi-label">Best candidates</div><div className="mono dim" style={{ fontSize: 12 }}>{s.candidates.join(' · ')}</div></div>}
                <span className="spacer" />
                {reviews[s.id] ? (
                  <div className="banner" style={{ padding: '8px 10px' }}><Icon name="check" className="ok" /><span>{reviews[s.id].action} · {reviews[s.id].by}</span></div>
                ) : (
                  <div className="row-wrap" title={mayReview ? undefined : cannotReview}>
                    <button className="btn btn-good btn-sm" disabled={!mayReview} onClick={() => review(s.id, 'Marked known')}>Mark known</button>
                    <button className="btn btn-sm" disabled={!mayReview} onClick={() => review(s.id, 'Added to library')}>Add to library</button>
                    <button className="btn btn-warn btn-sm" disabled={!mayReview} onClick={() => review(s.id, 'Deep analysis requested')}>Request deep analysis</button>
                    <button className="btn btn-ghost btn-sm" disabled={!mayReview} onClick={() => review(s.id, 'Dismissed')}>Dismiss</button>
                  </div>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
      {!list.length && <Panel><div className="empty">Nothing in this view.</div></Panel>}
    </div>
  )
}
