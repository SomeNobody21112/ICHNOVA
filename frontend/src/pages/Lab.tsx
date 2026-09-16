import { useState } from 'react'
import { HBars, LinePlot } from '../components/charts'
import { Icon, Loading, Panel, Tabs, Tag } from '../components/ui'
import { useApp } from '../lib/store'

type T = 'bench' | 'ladder' | 'null' | 'accept' | 'scoring' | 'fec' | 'runtime'
const STAGE_NOTE: Record<string, string> = {
  O0: 'blind', O1: '+ true modulation', O2: '+ true samples/symbol', O3: '+ true carrier offset', O4: '+ true roll-off',
  O5: '+ true timing', O6: '+ true phase', O7: '+ true interleaver',
}
const COLORS = ['#5fd0f0', '#a393ff', '#3ec28f']

const Src = ({ s }: { s: string }) => <div className="mono muted" style={{ fontSize: 11, marginTop: 10 }}>source: {s}</div>

export default function Lab() {
  const { benchmark: b } = useApp()
  const [tab, setTab] = useState<T>('bench')
  if (!b) return <div className="page"><Loading label="Loading benchmark results…" /></div>
  const labels = ['K7', 'K5', 'K3', 'SIGNAL_NO_CODE', 'UNKNOWN']
  const classes = Object.keys(b.nullset.confusion)
  return (
    <div className="page">
      <div className="page-head">
        <div className="grow">
          <div className="eyebrow">Evidence about the evidence engine</div>
          <h1 className="page-title">Experiment Lab</h1>
          <div className="page-sub">Every number on this page is read from result files in the repository (commit {b.generated_from_commit}). Nothing is typed by hand.</div>
        </div>
        <Tag kind="BENCHMARK">Synthetic benchmark data</Tag>
      </div>
      <div className="banner amber" style={{ marginBottom: 14 }}><Icon name="flag" /><div><b>ACTIVE RESEARCH ISSUE.</b> {b.research_issue}</div></div>
      <Tabs<T> value={tab} onChange={setTab} tabs={[
        { id: 'bench', label: 'Benchmark' }, { id: 'ladder', label: 'Oracle ladder' }, { id: 'null', label: 'Null test' },
        { id: 'accept', label: 'Acceptance rules' }, { id: 'scoring', label: 'Scoring' }, { id: 'fec', label: 'FEC vs Es/N0' }, { id: 'runtime', label: 'Runtime' },
      ]} />

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
                <HBars items={[...Object.entries(l.stages).map(([s, n]) => ({ label: `${s} ${STAGE_NOTE[s]}`, value: n, color: s === 'O0' ? '#3ec28f' : '#5fd0f0' })), { label: 'never', value: l.never, color: '#e9b949' }]} max={l.n} />
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
        <Panel title="Acceptance rules · held-out split" sub={`Constants calibrated on even-indexed files: block-length tolerance ${b.acceptance.params.delta.toFixed(2)} symbols, path-metric floor ${b.acceptance.params.t.toFixed(3)}`}>
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
