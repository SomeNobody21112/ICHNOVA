import { useState } from 'react'
import { Link } from 'react-router-dom'
import { APPROACHES, DIFFERENTIATORS } from '../lib/landscape'
import { HBars, LinePlot } from '../components/charts'
import { Icon, Loading, Panel, Stamp, Tabs, Tag } from '../components/ui'
import { useApp } from '../lib/store'

type T = 'real' | 'bench' | 'ladder' | 'null' | 'accept' | 'scoring' | 'fec' | 'runtime' | 'perf' | 'landscape'
const STAGE_NOTE: Record<string, string> = {
  O0: 'blind', O1: '+ true modulation', O2: '+ true samples/symbol', O3: '+ true carrier offset', O4: '+ true roll-off',
  O5: '+ true timing', O6: '+ true phase', O7: '+ true interleaver',
}
const COLORS = ['var(--cyan)', 'var(--violet)', 'var(--green)']

const Src = ({ s }: { s: string }) => <div className="mono muted" style={{ fontSize: 11, marginTop: 10 }}>source: {s}</div>

export default function Lab() {
  const { benchmark: b } = useApp()
  const [tab, setTab] = useState<T>('real')
  if (!b) return <div className="page"><Loading label="Loading benchmark results…" /></div>
  const labels = ['K7', 'K5', 'K3', 'SIGNAL_NO_CODE', 'UNKNOWN']
  const classes = Object.keys(b.nullset.confusion)
  return (
    <div className="page">
      <div className="page-head">
        <div className="grow">
          <h1 className="page-title">Experiment Lab</h1>
          <div className="page-sub">Every number on this page is read from result files in the repository (commit {b.generated_from_commit}). Nothing is typed by hand.</div>
        </div>
        <Tag kind="BENCHMARK">Synthetic benchmark data</Tag>
      </div>
      <div className="banner amber" style={{ marginBottom: 14 }}><Icon name="flag" /><div><b>ACTIVE RESEARCH ISSUE.</b> {b.research_issue}</div></div>
      <Tabs<T> value={tab} onChange={setTab} tabs={[
        { id: 'real', label: 'Real transmissions', count: b.real_signals?.length }, { id: 'bench', label: 'Benchmark' }, { id: 'ladder', label: 'Oracle ladder' }, { id: 'null', label: 'Null test' },
        { id: 'accept', label: 'Acceptance rules' }, { id: 'scoring', label: 'Scoring' }, { id: 'fec', label: 'FEC vs Es/N0' }, { id: 'runtime', label: 'Runtime' },
        { id: 'perf', label: 'Performance' }, { id: 'landscape', label: 'Landscape' },
      ]} />

      {tab === 'real' && (
        <Panel title="Real government transmissions, received blind" sub="Captured through public KiwiSDR receivers; each answer is checked against an independent reference (receiver GPS time, the transmission's own content, or the operator's official list)" flush right={<Tag kind="LIVE">Real signals</Tag>}>
          <div style={{ overflowX: 'auto' }}>
            <table className="tbl">
              <thead><tr><th>Transmitter</th><th>Received</th><th>Engine answer</th><th className="num">log₁₀ p</th><th className="num">vs GPS clock</th><th /></tr></thead>
              <tbody>{(b.real_signals ?? []).map((r) => (
                <tr key={r.id}>
                  <td><b>{r.station}</b><div className="muted" style={{ fontSize: 11.5 }}>{r.operator}</div></td>
                  <td className="mono" style={{ fontSize: 12 }}>{r.t0_utc.slice(0, 16).replace('T', ' ')} UTC<div className="muted">{r.receiver}</div></td>
                  <td style={{ maxWidth: 420 }}><Stamp status={r.answer.status} /><div className="muted" style={{ fontSize: 12, marginTop: 4, overflowWrap: 'anywhere' }}>{(r.answer.summary ?? '').replace(/\s+/g, ' ').slice(0, 140)}</div></td>
                  <td className="num">{r.answer.log10_p != null ? r.answer.log10_p.toFixed(1) : '—'}</td>
                  <td className="num">{r.answer.verification ? `${r.answer.verification.arrival_minus_decoded_ms > 0 ? '+' : ''}${r.answer.verification.arrival_minus_decoded_ms.toFixed(1)} ms` : '—'}</td>
                  <td><Link className="btn btn-sm" to={`/app/monitor?rec=${r.id}`}><Icon name="play" size={11} /> Replay</Link></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          <div className="dim" style={{ fontSize: 12.5, padding: '10px 14px' }}>
            The weak WWVB capture is kept on purpose: the frame structure is significant, but no time digit beats its alternatives by 100:1, so the engine names the station and refuses to state the time.
            Recordings and their GPS start times are committed under recordings/real and re-decoded in CI (tests/test_realsig.py).
          </div>
        </Panel>
      )}

      {tab === 'perf' && b.performance && (
        <div className="grid g-2" style={{ alignItems: 'start' }}>
          <Panel title="Same decisions, less time" sub="Wall-clock seconds on the development workstation, before and after the vectorised hypothesis search">
            <HBars items={[
              { label: 'sealed 30 · before', value: b.performance.sealed_s[0], color: 'var(--faint)' }, { label: 'sealed 30 · after', value: b.performance.sealed_s[1], color: 'var(--green)' },
              { label: 'train 100 · before', value: b.performance.train_s[0], color: 'var(--faint)' }, { label: 'train 100 · after', value: b.performance.train_s[1], color: 'var(--green)' },
              { label: 'null set 1350 · before', value: b.performance.nullset_s[0], color: 'var(--faint)' }, { label: 'null set 1350 · after', value: b.performance.nullset_s[1], color: 'var(--green)' },
            ]} fmt={(v) => `${v.toFixed(1)} s`} />
            <p className="dim" style={{ fontSize: 12.5 }}>{(b.performance.nullset_s[0] / b.performance.nullset_s[1]).toFixed(1)}× on the null set, {(b.performance.train_s[0] / b.performance.train_s[1]).toFixed(1)}× on train. {b.performance.note}</p>
            <Src s={b.performance.source} />
          </Panel>
          <Panel title="What changed">
            <ul style={{ margin: 0, paddingLeft: 18, display: 'grid', gap: 8 }}>{b.performance.changes.map((c) => <li key={c}>{c}</li>)}</ul>
            <div className="banner" style={{ marginTop: 14 }}><Icon name="check" /><span>Decision differences across 1,480 files: <b>{b.performance.decision_differences}</b>. Speed was not bought with accuracy.</span></div>
          </Panel>
        </div>
      )}

      {tab === 'landscape' && (
        <div className="col" style={{ gap: 14 }}>
          <div className="grid g-4">{DIFFERENTIATORS.map(([t, d]) => (
            <div key={t} className="card col" style={{ gap: 6 }}><b style={{ fontFamily: 'var(--cond)', fontSize: 15 }}>{t}</b><span className="dim" style={{ fontSize: 12.5 }}>{d}</span></div>
          ))}</div>
          <Panel title="Existing tools and published methods" sub="Claims about other products are limited to their public descriptions" flush>
            <div style={{ overflowX: 'auto' }}>
              <table className="tbl">
                <thead><tr><th>Approach</th><th>What it does</th><th>Strength</th><th>Gap this platform addresses</th></tr></thead>
                <tbody>{APPROACHES.map((a) => (
                  <tr key={a.name}>
                    <td style={{ minWidth: 180 }}><div className="section-label" style={{ fontSize: 9.5 }}>{a.group}</div><b>{a.name}</b><div className="col" style={{ gap: 2, marginTop: 4 }}>{a.sources.map((s) => <a key={s.url} href={s.url} target="_blank" rel="noreferrer" style={{ fontSize: 11 }}>{s.title}</a>)}</div></td>
                    <td className="dim" style={{ fontSize: 12.5 }}>{a.what}</td>
                    <td className="dim" style={{ fontSize: 12.5 }}>{a.strength}</td>
                    <td style={{ fontSize: 12.5 }}>{a.gap}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </Panel>
        </div>
      )}

      {tab === 'bench' && (
        <Panel title="bench-v1 · versions" sub="Pass = decoded with bit error rate < 1%. A false accept is a decode claimed with the wrong payload.">
          <table className="tbl"><thead><tr><th>Version</th><th className="num">Sealed</th><th className="num">Train</th><th className="num">False accepts</th><th className="num">Train runtime</th></tr></thead>
            <tbody>{Object.entries(b.bench_v1).map(([v, e]) => (
              <tr key={v}><td className="mono">{v}</td><td className="num">{e.sealed.pass}/{e.sealed.n}</td><td className="num">{e.train.pass}/{e.train.n}</td>
                <td className="num">{e.sealed.false_accepts == null ? 'not measured' : e.sealed.false_accepts + (e.train.false_accepts ?? 0)}</td><td className="num">{e.train.runtime_s} s</td></tr>
            ))}</tbody></table>
          <p className="dim" style={{ fontSize: 12.5 }}>The baseline used dataset-specific constants (fixed samples/symbol and a score bonus). The hardened receiver removed them; train recall is limited mostly by 32-bit blocks that cannot be proven.</p>
          <Src s={Object.values(b.bench_v1).flatMap((e) => [e.sealed.source, e.train.source]).join(', ')} />
        </Panel>
      )}

      {tab === 'ladder' && (
        <div className="grid g-2">
          {(['sealed', 'train'] as const).map((ds) => {
            const l = b.oracle_ladder[ds]
            return (
              <Panel key={ds} title={`${ds} · first stage at which each file passes`} sub="Oracle stages reveal one true parameter at a time">
                <HBars items={[...Object.entries(l.stages).map(([s, n]) => ({ label: `${s} ${STAGE_NOTE[s]}`, value: n, color: s === 'O0' ? 'var(--green)' : 'var(--cyan)' })), { label: 'never', value: l.never, color: 'var(--amber)' }]} max={l.n} />
                {ds === 'train' && <p className="dim" style={{ fontSize: 12.5 }}>{l.o7_first_pass_32bit} of the {l.stages.O7} files needing the true interleaver have 32-bit blocks: too few parity checks to single out one hypothesis.</p>}
                <Src s={l.source} />
              </Panel>
            )
          })}
        </div>
      )}

      {tab === 'null' && (
        <Panel title={`Null set · ${b.nullset.n} files · outcome by true class`} sub="Only coded classes may decode; any decode of noise, uncoded or off-catalogue signals is a false accept">
          <table className="tbl"><thead><tr><th>True class</th>{labels.map((l) => <th key={l} className="num">{l}</th>)}</tr></thead>
            <tbody>{classes.map((c) => (
              <tr key={c}><td className="mono">{c}</td>{labels.map((l) => {
                const n = b.nullset.confusion[c][l.toLowerCase()] ?? b.nullset.confusion[c][l] ?? 0
                const right = l.toLowerCase() === c
                const wrong = n > 0 && ['K7', 'K5', 'K3'].includes(l) && !right
                return <td key={l} className="num" style={{ color: wrong ? 'var(--red)' : right && n ? 'var(--green)' : n ? undefined : 'var(--muted)' }}>{n}</td>
              })}</tr>
            ))}</tbody></table>
          <p className="dim" style={{ fontSize: 12.5 }}>Mean {b.nullset.hypotheses_mean.toLocaleString('en-IN')} hypotheses and {b.nullset.runtime_mean_s} s per file.</p>
          <Src s={b.nullset.source} />
        </Panel>
      )}

      {tab === 'accept' && (
        <Panel title="Acceptance rules · evaluation split" sub={`Constants calibrated on even-indexed files: block-length tolerance ${b.acceptance.params.delta.toFixed(2)} symbols, path-metric floor ${b.acceptance.params.t.toFixed(3)}`}>
          <table className="tbl"><thead><tr><th>Rule</th><th className="num">Recall</th><th className="num">Wrong hypothesis</th><th className="num">Null false accepts</th><th className="num">Wrong-structure accepts</th></tr></thead>
            <tbody>{b.acceptance.evaluation_split.map((r) => (
              <tr key={r.rule} className={r.rule === b.acceptance.adopted ? 'sel' : ''}>
                <td className="mono">{r.rule}{r.rule === b.acceptance.adopted && <span className="tag tag-LIVE" style={{ marginLeft: 8 }}>Adopted</span>}</td>
                <td className="num">{r.recall.toFixed(3)}</td><td className="num">{r.wrong_hyp}/{r.n_coded}</td><td className="num">{r.null_fa}/{r.n_null}</td><td className="num">{r.wrongnull_fa}/{r.n_wrong}</td>
              </tr>
            ))}</tbody></table>
          <p className="dim" style={{ fontSize: 12.5 }}>MC = modulation consistency, BL = block length, RM = runner-up margin, PM = path-metric floor. Wrong-structure runs remove the true interleaver, so any accept is wrong.</p>
          <Src s={b.acceptance.source} />
        </Panel>
      )}

      {tab === 'scoring' && (
        <Panel title="Hypothesis scoring methods" sub="How well each score separates true from wrong hypotheses">
          <table className="tbl"><thead><tr><th>Method</th><th className="num">AUC</th><th className="num">True-positive rate at 0 false positives</th><th className="num">Identification</th><th>Null range</th></tr></thead>
            <tbody>{b.scoring.map((s) => <tr key={s.method}><td className="mono">{s.method}</td><td className="num">{s.auc.toFixed(3)}</td><td className="num">{s.tpr_at_zero_fp.toFixed(3)}</td><td className="num">{s.identification.toFixed(3)}</td><td className="mono">{s.null_range}</td></tr>)}</tbody></table>
          <Src s="reports/data/scoring_compare.md" />
        </Panel>
      )}

      {tab === 'fec' && (
        <Panel title="Correct decodes vs symbol Es/N0" sub="Fraction of null-set coded files decoded with the right code, interleaver and payload">
          <LinePlot height={300} yMin={0} yMax={1} yLabel="correct" xLabel="Es/N0 (dB)" series={Object.values(b.nullset.correct_by_esn0).map((v, i) => {
            const pts = Object.entries(v).map(([e, c]) => [Number(e), c.correct / Math.max(1, c.n)]).sort((a, z) => a[0] - z[0])
            return { x: pts.map((p) => p[0]), y: pts.map((p) => p[1]), color: COLORS[i % 3], width: 2 }
          })} />
          <div className="legend">{Object.keys(b.nullset.correct_by_esn0).map((k, i) => <span key={k}><i style={{ background: COLORS[i % 3] }} />{k.toUpperCase()}</span>)}</div>
          <Src s={b.nullset.source} />
        </Panel>
      )}

      {tab === 'runtime' && (
        <Panel title="Where the time goes" sub="Share of analysis time by stage, 100 train files">
          <HBars items={Object.entries(b.runtime.stage_share).sort((a, z) => z[1] - a[1]).map(([k, v]) => ({ label: k.replace('_', ' '), value: v }))} max={1} fmt={(v) => `${(v * 100).toFixed(1)}%`} />
          <p className="dim" style={{ fontSize: 12.5 }}>The syndrome search over code × interleaver hypotheses dominates; it is embarrassingly parallel across hypotheses.</p>
          <Src s={b.runtime.source} />
        </Panel>
      )}
    </div>
  )
}
