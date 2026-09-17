import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { GenomeGlyph } from '../components/charts'
import { Icon, Panel, Stamp, Tag } from '../components/ui'
import { fmtFreq } from '../lib/format'
import { cosine, GENOME_AXES } from '../lib/sim'
import { stationName, useApp } from '../lib/store'

const MODULES = [
  { phase: 'Phase 1', name: 'Deterministic DSP + statistical validation', status: 'OPERATIONAL', desc: 'Blind search, exact parity tests, multiple-testing correction, structural checks. Every decision in this prototype.' },
  { phase: 'Phase 2', name: 'Signal embeddings & similarity search', status: 'EXPERIMENTAL', desc: 'Feature-vector fingerprints for similarity, clustering and recurring-emitter discovery. Today: cosine similarity on engineered genome fields.' },
  { phase: 'Phase 3', name: 'Anomaly detection', status: 'NOT ESTABLISHED', desc: 'Learn normal spectrum behaviour per station; flag deviation for review, never as a threat.' },
  { phase: 'Phase 4', name: 'Learned hypothesis prioritisation', status: 'NOT ESTABLISHED', desc: 'Rank which hypotheses to test first. Reduces search cost; statistical verification still decides.' },
  { phase: 'Phase 5', name: 'Code-aided adaptive inference', status: 'NOT ESTABLISHED', desc: 'Decode → residual error → parameter refinement → re-decode. Research module, not enabled until experimentally validated.' },
]

export default function Genome() {
  const { signals } = useApp()
  const [sel, setSel] = useState(signals.find((s) => s.provenance === 'SIMULATED' && s.status === 'UNKNOWN')?.id ?? signals[0]?.id)
  const rec = signals.find((s) => s.id === sel) ?? signals[0]
  const sims = useMemo(() => rec ? signals.filter((s) => s.id !== rec.id).map((s) => ({ s, score: cosine(rec.genome, s.genome) })).sort((a, b) => b.score - a.score).slice(0, 8) : [], [signals, rec])
  const W = 520, H = 360
  const raw = (g: number[]) => [(g[0] + g[2] + g[5] + g[6]) / 4, (g[1] + g[3] + g[7] + g[8]) / 4]
  const ext = useMemo(() => {
    const pts = signals.map((s) => raw(s.genome))
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1])
    return [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)]
  }, [signals])
  const pos = (g: number[]) => { const [x, y] = raw(g); return [30 + ((x - ext[0]) / (ext[1] - ext[0] || 1)) * (W - 60), 20 + (1 - (y - ext[2]) / (ext[3] - ext[2] || 1)) * (H - 40)] }
  if (!rec) return null
  return (
    <div className="page">
      <div className="page-head">
        <div className="grow">
          <div className="eyebrow">Beyond decoding</div>
          <h1 className="page-title">Signal Genome</h1>
          <div className="page-sub">Every observation becomes a structured fingerprint: what was established about its frequency, structure, code and behaviour. Fingerprints make recurrence and similarity searchable.</div>
        </div>
      </div>
      <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1.1fr) minmax(0, 0.9fr)', alignItems: 'start' }}>
        <Panel title="Genome map" sub="Each point is a signal; nearby points have similar fingerprints. Click to inspect." right={<Tag kind="SIMULATED" />}>
          <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 400 }}>
            <rect width={W} height={H} fill="none" stroke="var(--line)" />
            {signals.map((s) => {
              const [x, y] = pos(s.genome)
              const c = s.status === 'DECODED' ? 'var(--green)' : s.status === 'UNKNOWN' ? 'var(--amber)' : 'var(--cyan)'
              const on = s.id === rec.id
              const near = sims.some((m) => m.s.id === s.id)
              return <circle key={s.id} cx={x} cy={y} r={on ? 7 : near ? 5 : 3.2} fill={c} opacity={on || near ? 1 : 0.55} stroke={on ? 'var(--text)' : near ? 'var(--amber)' : 'none'} strokeWidth={1.5} style={{ cursor: 'pointer', transition: 'r 0.2s' }} onClick={() => setSel(s.id)}><title>{s.id}</title></circle>
            })}
            {sims.map(({ s }) => { const [x1, y1] = pos(rec.genome); const [x2, y2] = pos(s.genome); return <line key={s.id} x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--amber)" strokeOpacity="0.35" strokeDasharray="3 3" /> })}
          </svg>
          <div className="legend"><span><i style={{ background: 'var(--green)' }} />Decoded</span><span><i style={{ background: 'var(--cyan)' }} />Signal, no code</span><span><i style={{ background: 'var(--amber)' }} />Unknown</span></div>
        </Panel>
        <div className="col" style={{ gap: 14 }}>
          <Panel title={<span className="mono">{rec.id}</span>} right={<><Stamp status={rec.status} /><Tag kind={rec.provenance} /></>}>
            <div className="row" style={{ gap: 16, alignItems: 'center' }}>
              <GenomeGlyph values={rec.genome} size={230} labels={GENOME_AXES} />
              <div className="col" style={{ gap: 4, fontSize: 12.5 }}>
                <span className="muted">{stationName(rec.stationId)}</span><span className="mono">{fmtFreq(rec.centerHz)}</span>
                <Link to={`/app/signals/${rec.id}`} className="btn btn-sm" style={{ marginTop: 8 }}>Open record</Link>
              </div>
            </div>
          </Panel>
          <Panel title="Find similar signals" sub="Cosine similarity on genome fields" right={<Tag kind="EXPERIMENTAL" />} flush>
            <div className="list">{sims.map(({ s, score }) => (
              <div key={s.id} className="list-item" onClick={() => setSel(s.id)} style={{ gridTemplateColumns: 'auto 1fr auto auto' }}>
                <GenomeGlyph values={s.genome} compare={rec.genome} size={32} />
                <div><div className="mono" style={{ fontSize: 12 }}>{s.id}</div><div className="muted" style={{ fontSize: 11 }}>{stationName(s.stationId)}</div></div>
                <Stamp status={s.status} /><span className="mono" style={{ color: 'var(--cyan)' }}>{(score * 100).toFixed(0)}%</span>
              </div>
            ))}</div>
          </Panel>
        </div>
      </div>
      <Panel title="Machine-learning roadmap" sub="ML is introduced only where it adds value, and never replaces statistical verification" style={{ marginTop: 14 }}>
        <div className="grid g-5">
          {MODULES.map((m) => (
            <div key={m.phase} className="card col" style={{ gap: 8 }}>
              <div className="row"><span className="eyebrow grow">{m.phase}</span>{m.status === 'OPERATIONAL' ? <span className="tag tag-LIVE">Operational</span> : <Tag kind={m.status as 'EXPERIMENTAL' | 'NOT ESTABLISHED'} />}</div>
              <b style={{ fontFamily: 'var(--cond)', fontSize: 15 }}>{m.name}</b>
              <p className="dim" style={{ margin: 0, fontSize: 12.5 }}>{m.desc}</p>
              <dl className="kv" style={{ fontSize: 11.5, marginTop: 'auto' }}>
                <dt>Model</dt><dd>{m.status === 'OPERATIONAL' ? 'none (DSP)' : '—'}</dd><dt>Version</dt><dd>{m.status === 'OPERATIONAL' ? 'engine 0.3.0' : '—'}</dd>
                <dt>Training data</dt><dd>{m.status === 'OPERATIONAL' ? 'n/a' : '—'}</dd>
              </dl>
            </div>
          ))}
        </div>
        <div className="banner" style={{ marginTop: 14 }}>
          <Icon name="layers" />
          <div className="row-wrap mono" style={{ fontSize: 12, gap: 6 }}>
            <span>RAW SIGNAL</span><Icon name="chevron" size={12} /><span style={{ color: 'var(--violet)' }}>ML PRIORITISER (Phase 4)</span><Icon name="chevron" size={12} /><span>TOP HYPOTHESES</span><Icon name="chevron" size={12} /><span>DETERMINISTIC DSP</span><Icon name="chevron" size={12} /><span style={{ color: 'var(--green)' }}>STATISTICAL VALIDATION</span><Icon name="chevron" size={12} /><span>DECISION</span>
          </div>
        </div>
      </Panel>
    </div>
  )
}
