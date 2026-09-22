import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { GenomeGlyph } from '../components/charts'
import { Panel, Stamp, Tag } from '../components/ui'
import { fmtFreq, pct, STATUS_LABEL } from '../lib/format'
import { cosine, GENOME_AXES } from '../lib/sim'
import { stationName, useApp } from '../lib/store'
import type { SignalRecord } from '../lib/types'

const MODULES = [
  { phase: 'Phase 1', name: 'Deterministic DSP + statistical validation', status: 'OPERATIONAL', desc: 'Blind search, exact parity tests, multiple-testing correction, structural checks. Every decision in this prototype.' },
  { phase: 'Phase 2', name: 'Signal fingerprints & similarity search', status: 'EXPERIMENTAL', desc: 'A fingerprint of what the engine measured (presence, spectral lines, symbol structure, code evidence, verdict) and nearest-neighbour search over it, to find recurrences of a signal. Never part of a decision.' },
  { phase: 'Phase 3', name: 'Anomaly detection', status: 'NOT ESTABLISHED', desc: 'Learn normal spectrum behaviour per station; flag deviation for review, never as a threat.' },
  { phase: 'Phase 4', name: 'Learned hypothesis prioritisation', status: 'NOT ESTABLISHED', desc: 'Rank which hypotheses to test first. Reduces search cost; statistical verification still decides.' },
  { phase: 'Phase 5', name: 'Code-aided adaptive inference', status: 'NOT ESTABLISHED', desc: 'Decode → residual error → parameter refinement → re-decode. Research module, not enabled until experimentally validated.' },
]

/** The fields of results/similarity.json the roadmap reads (written by eval/similarity.py). */
interface Similarity {
  n_queries: number; top1: number; baseline_random: number; baseline_verdict_only: number
  signal_classes_only: { top1: number; baseline_random: number }
}

// ---------------------------------------------------------------- genome map
type Status = SignalRecord['status']
const TONE: Record<Status, string> = { DECODED: 'var(--green)', SIGNAL_NO_CODE: 'var(--cyan)', UNKNOWN: 'var(--amber)' }

/** Status by shape as well as colour, the same vocabulary as the verdict stamps:
 *  filled dot = decoded, ring = signal without code, diamond = unknown. */
function StatusMark({ status, x, y, r }: { status: Status; x: number; y: number; r: number }) {
  const c = TONE[status]
  if (status === 'UNKNOWN') return <path d={`M${x},${y - r * 1.3}L${x + r * 1.3},${y}L${x},${y + r * 1.3}L${x - r * 1.3},${y}Z`} fill={c} />
  if (status === 'SIGNAL_NO_CODE') return <circle cx={x} cy={y} r={r * 0.95} fill="var(--panel)" stroke={c} strokeWidth={1.6} />
  return <circle cx={x} cy={y} r={r} fill={c} />
}

/** Top two principal components of the genome vectors (power iteration with deflation). A real
 *  projection: distance on screen tracks distance between fingerprints, which the old average-of-
 *  fields layout did not, and the axes can say how much of the variation they show. */
export function pca2(rows: number[][]) {
  const n = rows.length, d = rows[0]?.length ?? 0
  const mean = Array.from({ length: d }, (_, j) => rows.reduce((a, r) => a + r[j], 0) / Math.max(1, n))
  const X = rows.map((r) => r.map((v, j) => v - mean[j]))
  const C = Array.from({ length: d }, (_, i) => Array.from({ length: d }, (_, j) => X.reduce((a, r) => a + r[i] * r[j], 0) / Math.max(1, n - 1)))
  const total = C.reduce((a, row, i) => a + row[i], 0) || 1
  const comps: { v: number[]; lambda: number }[] = []
  for (let c = 0; c < 2; c++) {
    let v = Array.from({ length: d }, (_, j) => (j === c ? 1 : 0.5 / d))
    for (let it = 0; it < 120; it++) {
      const w = C.map((row) => row.reduce((a, x, j) => a + x * v[j], 0))
      const norm = Math.hypot(...w) || 1
      v = w.map((x) => x / norm)
    }
    const lambda = v.reduce((a, x, i) => a + x * C[i].reduce((b, y, j) => b + y * v[j], 0), 0)
    comps.push({ v, lambda })
    for (let i = 0; i < d; i++) for (let j = 0; j < d; j++) C[i][j] -= lambda * v[i] * v[j]
  }
  return { proj: X.map((r) => comps.map((p) => r.reduce((a, x, j) => a + x * p.v[j], 0))), explained: comps.map((p) => p.lambda / total) }
}

/** 2-sigma ellipse of a point cloud: centre, radii and rotation from the 2x2 covariance. */
function ellipse(pts: number[][]) {
  const n = pts.length
  const mx = pts.reduce((a, p) => a + p[0], 0) / n, my = pts.reduce((a, p) => a + p[1], 0) / n
  let sxx = 0, syy = 0, sxy = 0
  pts.forEach(([x, y]) => { sxx += (x - mx) ** 2; syy += (y - my) ** 2; sxy += (x - mx) * (y - my) })
  sxx /= n; syy /= n; sxy /= n
  const tr = sxx + syy, det = sxx * syy - sxy * sxy
  const disc = Math.sqrt(Math.max(0, (tr * tr) / 4 - det))
  const l1 = tr / 2 + disc, l2 = tr / 2 - disc
  // Major axis direction: the eigenvector of the larger eigenvalue.
  const angle = Math.abs(sxy) < 1e-12 ? (sxx >= syy ? 0 : 90) : (Math.atan2(l1 - sxx, sxy) * 180) / Math.PI
  return { cx: mx, cy: my, rx: 2 * Math.sqrt(Math.max(l1, 1e-6)), ry: 2 * Math.sqrt(Math.max(l2, 1e-6)), angle }
}

function GenomeMap({ signals, selected, neighbours, onSelect }: { signals: SignalRecord[]; selected: SignalRecord; neighbours: string[]; onSelect: (id: string) => void }) {
  const W = 640, H = 440, pad = { l: 40, r: 16, t: 16, b: 34 }
  const [hover, setHover] = useState<{ x: number; y: number; s: SignalRecord } | null>(null)
  const layout = useMemo(() => {
    const { proj, explained } = pca2(signals.map((s) => s.genome))
    const xs = proj.map((p) => p[0]), ys = proj.map((p) => p[1])
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)]
    const sx = (v: number) => pad.l + 14 + ((v - x0) / (x1 - x0 || 1)) * (W - pad.l - pad.r - 28)
    const sy = (v: number) => pad.t + 24 + (1 - (v - y0) / (y1 - y0 || 1)) * (H - pad.t - pad.b - 38)
    const at = new Map(signals.map((s, i) => [s.id, [sx(proj[i][0]), sy(proj[i][1])] as [number, number]]))
    const byFam = new Map<number, SignalRecord[]>()
    signals.forEach((s) => byFam.set(s.family, [...(byFam.get(s.family) ?? []), s]))
    const fams = [...byFam.entries()].filter(([, ss]) => ss.length >= 5).sort((a, b) => b[1].length - a[1].length)
      .map(([f, ss], k) => {
        const e = ellipse(ss.map((s) => at.get(s.id)!))
        const decoded = ss.filter((s) => s.status === 'DECODED').length
        return { f, name: `Family ${String.fromCharCode(65 + k)}`, n: ss.length, share: decoded / ss.length, e }
      })
    return { at, fams, explained }
  }, [signals]) // eslint-disable-line react-hooks/exhaustive-deps
  const [px, py] = layout.at.get(selected.id) ?? [0, 0]
  return (
    <div className="gmap" onMouseLeave={() => setHover(null)}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Genome map of ${signals.length} signals projected on their two main components; ${selected.id} selected with ${neighbours.length} nearest fingerprints linked.`}>
        {/* a light grid: position, not value, is what the reader compares */}
        {[0, 1, 2, 3, 4].map((i) => {
          const x = pad.l + (i / 4) * (W - pad.l - pad.r), y = pad.t + (i / 4) * (H - pad.t - pad.b)
          return <g key={i}><line x1={x} x2={x} y1={pad.t} y2={H - pad.b} stroke="var(--line)" /><line x1={pad.l} x2={W - pad.r} y1={y} y2={y} stroke="var(--line)" /></g>
        })}
        <text className="axis-t" x={W - pad.r} y={H - 10} textAnchor="end">Component 1 · {Math.round(layout.explained[0] * 100)}% of variation →</text>
        <text className="axis-t" x={16} y={H - pad.b} transform={`rotate(-90 16 ${H - pad.b})`}>Component 2 · {Math.round(layout.explained[1] * 100)}% →</text>

        {/* Only the selected signal's family is outlined and named. Drawing all of them put twenty
            labels on top of each other; the family of the thing you are looking at is the one that
            matters, and selecting another signal moves the outline with it. */}
        {layout.fams.filter((x) => x.f === selected.family).map(({ f, name, n, share, e }) => {
          const top = e.cy - Math.max(e.rx, e.ry) - 16
          const below = top < pad.t + 12
          return (
            <g key={f}>
              <ellipse className="fam on" cx={e.cx} cy={e.cy} rx={e.rx + 8} ry={e.ry + 8} transform={`rotate(${e.angle} ${e.cx} ${e.cy})`} />
              <text className="fam-label" x={Math.min(W - pad.r - 100, Math.max(pad.l + 100, e.cx))} y={below ? Math.min(H - pad.b - 8, e.cy + Math.max(e.rx, e.ry) + 24) : top} textAnchor="middle">
                {name} <tspan className="n">· {n} signals · {Math.round(share * 100)}% decoded</tspan>
              </text>
            </g>
          )
        })}

        {/* neighbours: thin rules from the selection, drawn under the points */}
        {neighbours.map((id) => { const p = layout.at.get(id); return p && <line key={id} x1={px} y1={py} x2={p[0]} y2={p[1]} stroke="var(--accent)" strokeOpacity={0.55} strokeWidth={1} /> })}

        {signals.map((s) => {
          const [x, y] = layout.at.get(s.id)!
          const isSel = s.id === selected.id, near = neighbours.includes(s.id)
          return (
            <g key={s.id} className="pt" opacity={isSel || near ? 1 : 0.8} onClick={() => onSelect(s.id)}
              onMouseEnter={() => setHover({ x, y, s })}>
              <circle className="hit" cx={x} cy={y} r={7} />
              {near && <circle cx={x} cy={y} r={6.5} fill="none" stroke="var(--accent)" strokeWidth={1.2} />}
              <StatusMark status={s.status} x={x} y={y} r={isSel ? 4.5 : 3} />
            </g>
          )
        })}
        {/* the selection: crosshair to both axes and a ring, drawn last so nothing covers it */}
        <line x1={pad.l} x2={px - 10} y1={py} y2={py} stroke="var(--text-2)" strokeDasharray="2 3" pointerEvents="none" />
        <line x1={px} x2={px} y1={py + 10} y2={H - pad.b} stroke="var(--text-2)" strokeDasharray="2 3" pointerEvents="none" />
        <circle cx={px} cy={py} r={9} fill="none" stroke="var(--text)" strokeWidth={1.6} pointerEvents="none" />
      </svg>
      {hover && (
        <div className="gmap-tip" style={{ left: `${(hover.x / W) * 100}%`, top: `${(hover.y / H) * 100}%`, transform: `translate(${hover.x > W * 0.65 ? 'calc(-100% - 12px)' : '12px'}, -50%)` }}>
          <div className="mono">{hover.s.id}</div>
          <div className="muted" style={{ fontSize: 11.5 }}>{STATUS_LABEL[hover.s.status]} · {stationName(hover.s.stationId)} · {fmtFreq(hover.s.centerHz)}</div>
        </div>
      )}
      <div className="gmap-legend">
        {(['DECODED', 'SIGNAL_NO_CODE', 'UNKNOWN'] as Status[]).map((st) => (
          <span key={st}><svg width={12} height={12} viewBox="-6 -6 12 12" aria-hidden="true"><StatusMark status={st} x={0} y={0} r={3.4} /></svg>{STATUS_LABEL[st]}</span>
        ))}
        <span><svg width={14} height={12} viewBox="-7 -6 14 12" aria-hidden="true"><circle r={5} fill="none" stroke="var(--accent)" strokeWidth={1.2} /></svg>nearest fingerprints</span>
        <span className="muted">Outline: the selected signal's family (two standard deviations).</span>
      </div>
    </div>
  )
}

export default function Genome() {
  const { signals, engine } = useApp()
  // Phase 2's measured result (eval/similarity.py). Absent file: the step says so instead of a number.
  const [sim, setSim] = useState<Similarity | null>(null)
  useEffect(() => { fetch('/similarity.json').then((r) => (r.ok ? r.json() : null)).then(setSim).catch(() => setSim(null)) }, [])
  const [sel, setSel] = useState(signals.find((s) => s.provenance === 'SIMULATED' && s.status === 'UNKNOWN')?.id ?? signals[0]?.id)
  const rec = signals.find((s) => s.id === sel) ?? signals[0]
  const sims = useMemo(() => rec ? signals.filter((s) => s.id !== rec.id).map((s) => ({ s, score: cosine(rec.genome, s.genome) })).sort((a, b) => b.score - a.score).slice(0, 8) : [], [signals, rec])
  if (!rec) return null
  return (
    <div className="page">
      <div className="page-head">
        <div className="grow">
          <h1 className="page-title">Signal Genome</h1>
          <div className="page-sub">Every observation becomes a structured fingerprint: what was established about its frequency, structure, code and behaviour. Fingerprints make recurrence and similarity searchable.</div>
        </div>
      </div>
      <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1.1fr) minmax(0, 0.9fr)', alignItems: 'start' }}>
        <Panel title="Genome map" sub="Each mark is a signal, placed by its fingerprint: close marks have similar fingerprints. Select one to see its nearest neighbours." right={<Tag kind="SIMULATED">Mostly simulated records</Tag>}>
          <GenomeMap signals={signals} selected={rec} neighbours={sims.map((m) => m.s.id)} onSelect={setSel} />
        </Panel>
        <div className="col" style={{ gap: 14 }}>
          <Panel title={<span className="mono">{rec.id}</span>} right={<><Stamp status={rec.status} /><Tag kind={rec.provenance} /></>}>
            {/* Stacked, not side by side: the axis names need the full width of the card. */}
            <div className="col" style={{ gap: 10 }}>
              <div className="center"><GenomeGlyph values={rec.genome} size={380} labels={GENOME_AXES} /></div>
              <div className="row-wrap" style={{ gap: 10, alignItems: 'center', fontSize: 12.5 }}>
                <span className="muted">{stationName(rec.stationId)}</span>
                <span className="mono">{fmtFreq(rec.centerHz)}</span>
                <span className="spacer" />
                <Link to={`/app/signals/${rec.id}`} className="btn btn-sm">Open record</Link>
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
      <Panel title="Machine-learning roadmap" sub="Where learned models may enter, in order. None of them decides: every result still passes the same statistical acceptance." style={{ marginTop: 14 }}>
        {/* A track, not five identical cards: filled = running today, half = experimental,
            hollow = planned. Model details appear only where a model or engine actually exists. */}
        <ol className="roadmap">
          {MODULES.map((m) => {
            const st = m.status === 'OPERATIONAL' ? 'now' : m.status === 'EXPERIMENTAL' ? 'exp' : 'plan'
            return (
              <li key={m.phase} className={`roadmap-step ${st}`}>
                <span className="roadmap-dot" aria-hidden="true" />
                <div className="roadmap-meta"><span>{m.phase}</span><b>{st === 'now' ? 'Running today' : st === 'exp' ? 'Experimental' : 'Planned · not established'}</b></div>
                <h3 className="roadmap-name">{m.name}</h3>
                <p className="roadmap-desc">{m.desc}</p>
                <p className="roadmap-model">{st === 'now'
                  ? <>No learned model: deterministic DSP{engine.version ? <> · engine <span className="mono">{engine.version}</span></> : null}</>
                  : st === 'exp' ? (sim
                    ? <>No trained model. Measured on {sim.n_queries} held-out synthetic captures: the nearest fingerprint is the same kind of signal <b className="mono">{pct(sim.top1)}</b> of the time (random {pct(sim.baseline_random)}, verdict alone {pct(sim.baseline_verdict_only)}); {pct(sim.signal_classes_only.top1)} vs {pct(sim.signal_classes_only.baseline_random)} with noise excluded.</>
                    : 'No trained model: measured fingerprints and nearest-neighbour search (evaluation not found)')
                  : 'No model, version or training data yet'}</p>
              </li>
            )
          })}
        </ol>
        <div className="roadmap-flow" aria-label="Analysis path with the planned ML step">
          <span className="section-label">Analysis path</span>
          <ol>
            <li>Raw signal</li>
            <li className="planned" title="Phase 4: planned, not enabled">ML prioritiser <small>planned</small></li>
            <li>Top hypotheses</li>
            <li>Deterministic DSP</li>
            <li className="decides">Statistical validation</li>
            <li>Decision</li>
          </ol>
        </div>
      </Panel>
    </div>
  )
}
