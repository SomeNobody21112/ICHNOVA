import { motion } from 'framer-motion'
import { useCallback, useMemo, useState, type ReactNode } from 'react'
import { CODE_FULL, CODE_SHORT, fmtDateTime, fmtFs, fmtInt, fmtInterleaver, fmtP, fmtSymRate, interleaverBits, pct, STATUS_LABEL, STATUS_MEANING } from '../lib/format'
import { GENESIS, loadLedgers, verifyChain, verifyLine, type Receipt } from '../lib/receipt'
import type { AuditEvent, EvidencePack, Hyp, Provenance, QualityStatus } from '../lib/types'
import { Constellation, HBars, Landscape, LinePlot, Spectrogram } from './charts'
import { Drawer, Icon, Meter, Panel, Stamp, StatusGlyph, Tag } from './ui'

export const provOf = (p: EvidencePack): Provenance => (p.source.kind === 'UPLOAD' ? 'LIVE' : p.source.kind)
const LOG_ALPHA = (p: EvidencePack) => Math.log10(p.accept.alpha)
const codeKey = (c: string) => CODE_SHORT(c).replace('=', '')

export type Topic = 'detection' | 'sps' | 'modulation' | 'cfo' | 'fec' | 'interleaver' | 'validation'
const TOPIC_TITLE: Record<Topic, string> = {
  detection: 'Signal detection', sps: 'Symbol structure', modulation: 'Modulation', cfo: 'Carrier frequency offset',
  fec: 'FEC hypotheses', interleaver: 'Interleaver & coverage', validation: 'Statistical validation',
}

/** The three structural checks the acceptance rule applies to the first significant hypothesis.
 *  One source for the validation drawer, the receipt and the verdict, so they cannot disagree. */
export function structuralChecks(pack: EvidencePack) {
  const h = pack.accept.accepted_hypothesis ?? pack.diagnostics.top_hypotheses[0]
  if (!h) return []
  const rules = pack.accept.rules
  return [
    { label: 'Modulation consistency', ok: !h.structural_rejection?.startsWith('modulation'), detail: `exact binomial, α = ${pack.accept.alpha}` },
    { label: 'Block length', ok: h.covered_symbols >= h.active_symbols - rules.bl_delta_symbols, detail: `covers ${h.covered_symbols.toFixed(0)} of ~${h.active_symbols} symbols` },
    { label: 'Soft path metric', ok: h.path_metric >= rules.pm_floor, detail: `${h.path_metric.toFixed(3)} ${h.path_metric >= rules.pm_floor ? '≥' : '<'} floor ${rules.pm_floor}` },
  ]
}

function Check({ ok, children, na }: { ok: boolean; children: ReactNode; na?: boolean }) {
  return (
    <li>
      <span className={na ? 'na' : ok ? 'ok' : 'no'}><Icon name={na ? 'dash' : ok ? 'check' : 'cross'} size={15} /></span>
      <span>{children}</span>
    </li>
  )
}

// ---------------------------------------------------------------- topic renderers
export function TopicDetail({ pack, topic }: { pack: EvidencePack; topic: Topic }) {
  const d = pack.diagnostics
  const acc = pack.accept.accepted_hypothesis
  const best = acc ?? d.top_hypotheses[0]
  const la = LOG_ALPHA(pack)
  if (topic === 'detection') {
    return (
      <div className="col" style={{ gap: 12 }}>
        <p className="dim" style={{ margin: 0 }}>
          A PSK signal leaves a spectral line in x² (BPSK) or x⁴ (BPSK and QPSK). Each peak is tested against the
          exponential-periodogram null; the strongest line is the signal-presence test.
        </p>
        <dl className="kv">
          <dt>Strongest line p-value</dt><dd>{fmtP(d.detection_log10_p)}</dd>
          <dt>Presence threshold α</dt><dd>{pack.accept.alpha}</dd>
          <dt>Decision</dt><dd style={{ color: d.detection_log10_p <= la ? 'var(--green)' : 'var(--amber)' }}>{d.detection_log10_p <= la ? 'SIGNAL PRESENT' : 'NOT ESTABLISHED'}</dd>
        </dl>
        <table className="tbl"><thead><tr><th>Line</th><th className="num">CFO (cyc/sample)</th><th className="num">Peak/floor</th><th className="num">p-value</th></tr></thead>
          <tbody>{d.cfo_candidates.map((c, i) => (
            <tr key={i}><td className="mono">x{c.order === 2 ? '²' : '⁴'}</td><td className="num">{c.cfo.toFixed(5)}</td><td className="num">{c.peak_to_floor_db.toFixed(1)} dB</td><td className="num">{fmtP(c.log10_p)}</td></tr>
          ))}</tbody></table>
      </div>
    )
  }
  if (topic === 'sps' || topic === 'cfo') {
    if (topic === 'cfo') {
      return (
        <div className="col" style={{ gap: 12 }}>
          <p className="dim" style={{ margin: 0 }}>Every CFO candidate is carried forward; the code test, not the spectrum, decides which one explains the data.</p>
          <HBars items={d.cfo_candidates.map((c) => ({ label: `${c.cfo >= 0 ? '+' : ''}${c.cfo.toFixed(5)} (x${c.order === 2 ? '²' : '⁴'})`, value: Math.max(0, c.peak_to_floor_db), color: best && Math.abs(best.cfo - c.cfo) < 1e-9 ? 'var(--green)' : 'var(--cyan)' }))} fmt={(v) => `${v.toFixed(1)} dB`} />
          <dl className="kv"><dt>Chosen CFO</dt><dd>{best ? best.cfo.toFixed(5) : '—'}</dd><dt>Search bound</dt><dd>±{pack.engine.cfo_max} fs</dd></dl>
        </div>
      )
    }
    const cands = new Set(d.sps_candidates)
    return (
      <div className="col" style={{ gap: 12 }}>
        <p className="dim" style={{ margin: 0 }}>
          Lag-1 correlation of y⁴ at every samples-per-symbol in the search domain {pack.engine.sps_range.join('–')}. Integer multiples of the true
          rate also score high, so divisors are always tested; the code test resolves them.
        </p>
        <HBars items={d.sps_table.map((r) => ({ label: `sps ${r.sps}${cands.has(r.sps) ? '  · candidate' : ''}`, value: r.q4, color: best && r.sps === best.sps ? 'var(--green)' : cands.has(r.sps) ? 'var(--cyan)' : 'var(--line-3)' }))} max={1} fmt={(v) => v.toFixed(3)} />
        <dl className="kv">
          <dt>Raw spectral estimate</dt><dd>{d.raw_sps_estimate.toFixed(2)} sps</dd>
          <dt>Candidates tested</dt><dd>{d.sps_candidates.join(', ')}</dd>
          <dt>Front-ends searched / rejected (serial dependence)</dt><dd>{d.n_front_ends} / {d.front_ends_rejected_serial_dependence}</dd>
          <dt>Established</dt><dd>{acc ? `${acc.sps} sps · ${fmtSymRate(acc.sps, pack.capture.fs_hz)}` : 'NOT ESTABLISHED'}</dd>
        </dl>
      </div>
    )
  }
  if (topic === 'modulation') {
    return (
      <div className="col" style={{ gap: 12 }}>
        <p className="dim" style={{ margin: 0 }}>
          BPSK and QPSK are both tested at every candidate rate. y² is data-free for BPSK and random for QPSK, giving a
          per-candidate statistic and two exact binomial consistency tests on the accepted hypothesis.
        </p>
        <table className="tbl"><thead><tr><th>sps</th><th className="num">q2/q4</th><th>Statistic says</th><th className="num">Margin</th></tr></thead>
          <tbody>{d.modulation_stats.map((m) => (
            <tr key={m.sps}><td className="mono">{m.sps}</td><td className="num">{m.bpsk_ratio.toFixed(3)}</td><td className="mono">{m.decision}</td><td className="num">{m.margin.toFixed(2)}</td></tr>
          ))}</tbody></table>
        {best && (
          <dl className="kv">
            <dt>Hypothesis modulation</dt><dd>{best.modulation}</dd>
            <dt>BPSK signature present (p)</dt><dd>{fmtP(best.bpsk_presence_log10p)}</dd>
            <dt>Inconsistent with BPSK (p)</dt><dd>{fmtP(best.bpsk_contradiction_log10p)}</dd>
            <dt>Modulation check</dt><dd style={{ color: best.structural_rejection?.startsWith('modulation') ? 'var(--orange)' : 'var(--green)' }}>{best.structural_rejection?.startsWith('modulation') ? 'CONTRADICTED' : 'CONSISTENT'}</dd>
          </dl>
        )}
      </div>
    )
  }
  if (topic === 'fec') {
    return (
      <div className="col" style={{ gap: 12 }}>
        <p className="dim" style={{ margin: 0 }}>
          Each rate-½ convolutional code satisfies g₂(D)·c₁ + g₁(D)·c₂ = 0. Every trellis step gives one parity check; under
          noise or a wrong hypothesis each check's sign is a fair coin, so the count of satisfied checks has an exact binomial null.
        </p>
        <HypTable pack={pack} rows={d.top_hypotheses.slice(0, 12)} compact />
      </div>
    )
  }
  if (topic === 'interleaver') {
    const h = best
    return h ? (
      <div className="col" style={{ gap: 12 }}>
        <dl className="kv">
          <dt>Interleaver</dt><dd>{fmtInterleaver(h.interleaver)}</dd>
          <dt>Covered / observed bits</dt><dd>{h.covered_bits} / {h.total_observed_bits}</dd>
          <dt>Covered symbols vs transmission span</dt><dd>{h.covered_symbols.toFixed(0)} / {h.active_symbols}</dd>
          <dt>Block-length tolerance</dt><dd>{pack.accept.rules.bl_delta_symbols} symbols</dd>
          <dt>Search domain</dt><dd>{pack.engine.interleaver_domain}</dd>
        </dl>
        <div><div className="row muted" style={{ fontSize: 11.5, marginBottom: 4 }}><span className="grow">Coverage of transmission span</span><span className="mono">{pct(h.covered_symbols / Math.max(1, h.active_symbols))}</span></div>
          <Meter value={h.covered_symbols / Math.max(1, h.active_symbols)} tone={h.covered_symbols >= h.active_symbols - pack.accept.rules.bl_delta_symbols ? 'green' : 'orange'} /></div>
      </div>
    ) : <div className="empty">No interleaver hypothesis was examined.</div>
  }
  const M = pack.accept.n_hypotheses
  const thr = pack.accept.log10_threshold
  const bestLog = pack.accept.log10_p
  const checks = acc ?? d.top_hypotheses[0]
  return (
    <div className="col" style={{ gap: 12 }}>
      <p className="dim" style={{ margin: 0 }}>
        With M hypotheses tested, the best one must reach p ≤ α / M (Bonferroni). The first significant hypothesis must then pass three
        structural checks before anything is accepted.
      </p>
      <dl className="kv">
        <dt>Hypotheses tested (M)</dt><dd>{fmtInt(M)}</dd>
        <dt>Family-wise α</dt><dd>{pack.accept.alpha}</dd>
        <dt>Acceptance bar α / M</dt><dd>{fmtP(thr)}</dd>
        <dt>Best p-value</dt><dd>{fmtP(bestLog)}</dd>
        <dt>Adjusted p (p · M)</dt><dd>{fmtP(bestLog + Math.log10(M))}</dd>
        <dt>Significant?</dt><dd style={{ color: bestLog <= thr ? 'var(--green)' : 'var(--amber)' }}>{bestLog <= thr ? 'YES' : 'NO'}</dd>
      </dl>
      {checks && (
        <ul className="why-list">
          {structuralChecks(pack).map((c) => <Check key={c.label} ok={c.ok}>{c.label}: {c.detail}</Check>)}
        </ul>
      )}
      {pack.accept.significant_but_rejected.length > 0 && (
        <div className="banner amber">
          <Icon name="info" />
          <div><b>Significant but rejected</b>
            {pack.accept.significant_but_rejected.slice(0, 4).map((r, i) => (
              <div key={i} className="mono" style={{ fontSize: 12 }}>{CODE_SHORT(r.code)} {fmtInterleaver(r.interleaver, 'short')} {r.modulation} sps {r.sps} · p {fmtP(r.log10_p)} · {r.structural_rejection}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export function HypTable({ pack, rows, compact }: { pack: EvidencePack; rows: Hyp[]; compact?: boolean }) {
  const acc = pack.accept.accepted_hypothesis
  const same = (h: Hyp) => acc && h.code === acc.code && String(h.interleaver) === String(acc.interleaver)
  return (
    <div className="table-wrap" style={{ maxHeight: compact ? 360 : undefined }}>
      <table className="tbl">
        <thead><tr><th>#</th><th>Code</th><th>Interleaver</th><th>Mod</th><th className="num">sps</th><th className="num">Checks</th><th className="num">p-value</th><th>Status</th></tr></thead>
        <tbody>{rows.map((h, i) => {
          const sig = h.log10_p <= pack.accept.log10_threshold
          const status = same(h) && !h.structural_rejection ? 'ACCEPTED' : h.structural_rejection && sig ? 'REJECTED' : sig ? 'SIGNIFICANT' : 'NOT SIGNIFICANT'
          const color = status === 'ACCEPTED' ? 'var(--green)' : status === 'REJECTED' ? 'var(--orange)' : status === 'SIGNIFICANT' ? 'var(--amber)' : 'var(--muted)'
          return (
            <tr key={i} title={h.structural_rejection ?? undefined}>
              <td className="mono muted">{String(i + 1).padStart(2, '0')}</td>
              <td className="mono">{CODE_SHORT(h.code)}</td>
              <td className="mono">{fmtInterleaver(h.interleaver, 'short')}</td>
              <td className="mono">{h.modulation}</td>
              <td className="num">{h.sps}</td>
              <td className="num">{h.n_positive}/{h.n_checks}</td>
              <td className="num">{fmtP(h.log10_p)}</td>
              <td><span className="mono" style={{ color, fontSize: 11.5 }}>{status}</span>{status === 'REJECTED' && !compact && <div className="muted" style={{ fontSize: 11 }}>{h.structural_rejection}</div>}</td>
            </tr>
          )
        })}</tbody>
      </table>
    </div>
  )
}

export function EvidenceDrawer({ pack, topic, onClose }: { pack: EvidencePack; topic: Topic | null; onClose: () => void }) {
  return (
    <Drawer open={!!topic} onClose={onClose} right={<Tag kind={provOf(pack)} />}
      title={<><div className="meta mono">Evidence · {pack.id}</div><div className="panel-title" style={{ fontSize: 15 }}>{topic ? TOPIC_TITLE[topic] : ''}</div></>}>
      {topic && <TopicDetail pack={pack} topic={topic} />}
    </Drawer>
  )
}

// ---------------------------------------------------------------- characteristics
export function Characteristics({ pack }: { pack: EvidencePack }) {
  const [topic, setTopic] = useState<Topic | null>(null)
  const r = pack.result
  const acc = pack.accept.accepted_hypothesis
  const best = acc ?? pack.diagnostics.top_hypotheses[0]
  const rows: { label: string; value: string; topic: Topic; established: boolean }[] = [
    { label: 'Signal presence', value: pack.diagnostics.detection_log10_p <= LOG_ALPHA(pack) ? 'Detected' : 'Not established', topic: 'detection', established: pack.diagnostics.detection_log10_p <= LOG_ALPHA(pack) },
    { label: 'Modulation', value: r.modulation ?? (best ? `${best.modulation} (candidate)` : '—'), topic: 'modulation', established: !!r.modulation },
    { label: 'Sample rate', value: fmtFs(pack.capture), topic: 'sps', established: pack.capture.fs_hz != null },
    { label: 'Symbol rate', value: r.sps ? `${r.sps} sps · ${fmtSymRate(r.sps, pack.capture.fs_hz)}` : best ? `${best.sps} sps (candidate)` : '—', topic: 'sps', established: !!r.sps },
    { label: 'CFO', value: r.cfo != null ? `${r.cfo >= 0 ? '+' : ''}${r.cfo.toFixed(5)} cyc/sample` : '—', topic: 'cfo', established: r.cfo != null },
    { label: 'FEC', value: r.code ? CODE_FULL[r.code] ?? r.code : 'Not established', topic: 'fec', established: !!r.code },
    { label: 'Interleaver', value: r.interleaver ? `Block ${fmtInterleaver(r.interleaver)}` : 'Not established', topic: 'interleaver', established: !!r.interleaver },
    { label: 'Coverage', value: acc ? pct(acc.covered_symbols / Math.max(1, acc.active_symbols)) : '—', topic: 'interleaver', established: !!acc },
    { label: 'Hypotheses evaluated', value: fmtInt(pack.accept.n_hypotheses), topic: 'validation', established: true },
  ]
  return (
    <Panel title="Signal characteristics" right={<Tag kind={provOf(pack)} />} flush>
      <div className="list">
        {rows.map((row) => (
          <div key={row.label} className="list-item" style={{ gridTemplateColumns: '150px 1fr auto', cursor: 'default' }}>
            <span className="muted" style={{ fontSize: 12 }}>{row.label}</span>
            <span className="mono" style={{ color: row.established ? 'var(--text)' : 'var(--amber)' }}>{row.value}</span>
            <button className="btn btn-ghost btn-sm" onClick={() => setTopic(row.topic)}><Icon name="eye" size={13} /> View evidence</button>
          </div>
        ))}
      </div>
      <EvidenceDrawer pack={pack} topic={topic} onClose={() => setTopic(null)} />
    </Panel>
  )
}

// ---------------------------------------------------------------- why panel
/** `inVerdict`: the Verdict above already states the refusal, so the banner is not repeated. */
export function WhyPanel({ pack, inVerdict }: { pack: EvidencePack; inVerdict?: boolean }) {
  const r = pack.result, d = pack.diagnostics, a = pack.accept
  const la = LOG_ALPHA(pack)
  const acc = a.accepted_hypothesis
  const best = acc ?? d.top_hypotheses[0]
  const detected = d.detection_log10_p <= la
  const sig = a.log10_p <= a.log10_threshold
  const title = r.status === 'DECODED' ? 'Evidence behind the acceptance' : r.status === 'SIGNAL_NO_CODE' ? 'Evidence: signal, but no code' : 'Evidence behind UNKNOWN'
  return (
    <Panel title={title} right={<Tag kind={provOf(pack)} />}>
      <ul className="why-list">
        <Check ok={detected}>Signal presence {detected ? 'established' : 'not established'} (spectral line p {fmtP(d.detection_log10_p)})</Check>
        <Check ok={!!best} na={!best}>{best ? `Symbol structure candidates found (${d.sps_candidates.length} rates, ${d.n_front_ends} front-ends)` : 'No usable symbol structure'}</Check>
        {r.status === 'DECODED' && acc ? (
          <>
            <Check ok>Modulation hypothesis {acc.modulation} consistent with the symbols</Check>
            <Check ok>CFO candidate {acc.cfo.toFixed(5)} supports the decode</Check>
            <Check ok>{CODE_SHORT(acc.code)} parity evidence: {acc.n_positive} of {acc.n_checks} checks satisfied</Check>
            <Check ok>Multiple-hypothesis correction passed (p·M = {fmtP(acc.log10_p + Math.log10(a.n_hypotheses))} ≤ α = {a.alpha})</Check>
            <Check ok>Structural checks passed: modulation, block length, soft path metric</Check>
          </>
        ) : (
          <>
            <Check ok={!!best} na={!best}>{best ? `Best candidate ${CODE_SHORT(best.code)} / ${interleaverBits(best.interleaver) ? `${interleaverBits(best.interleaver)}-bit` : 'no interleaver'}, ${best.modulation}` : 'No candidate hypothesis'}</Check>
            <Check ok={false}>{sig ? 'A hypothesis was significant but failed a structural check' : 'No FEC hypothesis passed statistical acceptance after correcting for multiple testing'}</Check>
            {a.significant_but_rejected.slice(0, 2).map((x, i) => <Check key={i} ok={false}>Rejected {CODE_SHORT(x.code)} {fmtInterleaver(x.interleaver, 'short')}: {x.structural_rejection}</Check>)}
          </>
        )}
      </ul>
      <div className="hr" />
      <dl className="kv">
        <dt>Hypotheses tested</dt><dd>{fmtInt(a.n_hypotheses)}</dd>
        <dt>Best p-value</dt><dd>{fmtP(a.log10_p)}</dd>
        <dt>Adjusted p-value (p·M)</dt><dd>{fmtP(Math.min(0, a.log10_p + Math.log10(a.n_hypotheses)))}</dd>
        <dt>Acceptance threshold</dt><dd>{a.alpha.toFixed(4)}</dd>
        <dt>Coverage</dt><dd>{acc ? pct(acc.covered_symbols / Math.max(1, acc.active_symbols)) : '—'}</dd>
      </dl>
      {r.status !== 'DECODED' && !inVerdict && (
        <motion.div className="refusal" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.16 }}>
          <strong>THE SYSTEM REFUSED TO GUESS.</strong>
          <span className="dim">{r.status === 'SIGNAL_NO_CODE' ? 'A signal is present, but no code could be established. No payload is asserted.' : 'The evidence does not support any interpretation. No payload is asserted.'}</span>
        </motion.div>
      )}
    </Panel>
  )
}

// ---------------------------------------------------------------- verdict
/** Verdict first, then why, in the engine's own numbers. Every figure is read from the pack; nothing
 *  here is a demo constant. For a refusal the explanation is the sufficiency analysis, verbatim. */
export function Verdict({ pack }: { pack: EvidencePack }) {
  const r = pack.result, a = pack.accept, s = pack.sufficiency
  const acc = a.accepted_hypothesis
  const pass = r.status === 'DECODED'
  const sig = a.log10_p <= a.log10_threshold
  const structure = pass ? [
    r.modulation,
    r.code ? CODE_FULL[r.code] ?? r.code : null,
    r.interleaver ? `${fmtInterleaver(r.interleaver, 'short')} block interleaver` : null,
    r.sps ? `${r.sps} samples/symbol · ${fmtSymRate(r.sps, pack.capture.fs_hz)}` : null,
  ].filter(Boolean) as string[] : []
  const checks = structuralChecks(pack)
  return (
    <section className={`verdict verdict-${r.status}`} aria-labelledby={`verdict-${pack.id}`}>
      <div className="verdict-head">
        <div className="verdict-word" id={`verdict-${pack.id}`}>
          <StatusGlyph status={r.status} size={30} />
          <span>{STATUS_LABEL[r.status]}</span>
        </div>
        <Tag kind={provOf(pack)} />
      </div>
      <p className="verdict-meaning">{STATUS_MEANING[r.status]}</p>
      {structure.length > 0 && <ul className="verdict-structure">{structure.map((x) => <li key={x}>{x}</li>)}</ul>}
      {!pass && (
        <p className="verdict-lede">
          The system tested <b className="mono">{fmtInt(a.n_hypotheses)}</b> hypotheses, but{' '}
          {sig ? 'the candidate that reached significance failed a structural check.' : 'no candidate cleared the acceptance bar.'}{' '}
          No payload is asserted: it deliberately did not guess.
        </p>
      )}

      <div className="section-label verdict-q">{pass ? 'Why was this accepted?' : 'Why was nothing accepted?'}</div>
      <dl className="verdict-why">
        <div><dt>hypotheses tested</dt><dd className="mono">{fmtInt(a.n_hypotheses)}</dd></div>
        <div><dt>observed p-value (best)</dt><dd className="mono">{fmtP(a.log10_p)}</dd></div>
        <div><dt>corrected threshold α / M</dt><dd className="mono">{fmtP(a.log10_threshold)}</dd></div>
        <div><dt>acceptance</dt>
          <dd className={`verdict-pass ${pass ? 'ok' : 'no'}`}><Icon name={pass ? 'check' : 'dash'} size={14} />{pass ? 'PASS' : sig ? 'REJECTED ON STRUCTURE' : 'BAR NOT MET'}</dd></div>
      </dl>
      {pass && acc && checks.length > 0 && (
        <p className="verdict-foot muted">
          {CODE_SHORT(acc.code)} parity: {fmtInt(acc.n_positive)} of {fmtInt(acc.n_checks)} checks satisfied · structural checks passed: {checks.filter((c) => c.ok).map((c) => c.label.toLowerCase()).join(', ')}
        </p>
      )}

      {!pass && s && (s.reason || s.what_would_prove_it) && (
        <div className={`verdict-need${s.verdict === 'IMPOSSIBLE_IN_DOMAIN' ? ' impossible' : ''}`}>
          <div className="section-label">{SUFFICIENCY_TITLE[s.verdict] ?? s.verdict}</div>
          {s.reason && <p>{s.reason}</p>}
          {s.what_would_prove_it && <><div className="section-label" style={{ marginTop: 10 }}>What would prove it?</div><p>{s.what_would_prove_it}</p></>}
        </div>
      )}
    </section>
  )
}

// ---------------------------------------------------------------- evidence chain
type NodeId = 'raw' | 'detect' | 'structure' | 'fec' | 'validation' | 'decision'

export function EvidenceChain({ pack }: { pack: EvidencePack }) {
  const [sel, setSel] = useState<NodeId>('validation')
  const d = pack.diagnostics, a = pack.accept, r = pack.result
  const la = LOG_ALPHA(pack)
  const detected = d.detection_log10_p <= la
  const codeCounts = useMemo(() => {
    const c: Record<string, number> = { K7: 0, K5: 0, K3: 0 }
    d.all_hypotheses?.code.forEach((k) => (c[k] = (c[k] ?? 0) + 1))
    return c
  }, [d.all_hypotheses])
  // `state` says in words what the tone says in colour: the spine is readable without colour.
  const validationState = r.status === 'DECODED' ? 'PASS' : a.significant_but_rejected.length ? 'REJECTED' : 'BAR NOT MET'
  const nodes: { id: NodeId; icon: string; title: string; sum: string; tone: string; state: string }[] = [
    { id: 'raw', icon: 'raw', title: 'Raw IQ', sum: `${fmtInt(pack.capture.samples)} samples · ${fmtFs(pack.capture)} · ${(pack.capture.format ?? 'iq').toUpperCase()}`, tone: 'info', state: 'RECORDED' },
    { id: 'detect', icon: 'detect', title: 'Signal detected', sum: detected ? `Spectral line p ${fmtP(d.detection_log10_p)}` : 'Presence not established', tone: detected ? 'ok' : 'warn', state: detected ? 'ESTABLISHED' : 'NOT ESTABLISHED' },
    { id: 'structure', icon: 'structure', title: 'Symbol structure', sum: `${d.sps_candidates.length} rate · ${d.cfo_candidates.length} CFO · 2 modulation candidates`, tone: 'info', state: 'CANDIDATES' },
    { id: 'fec', icon: 'fec', title: 'FEC hypotheses', sum: `${fmtInt(a.n_hypotheses)} tested · K7 ${fmtInt(codeCounts.K7)} · K5 ${fmtInt(codeCounts.K5)} · K3 ${fmtInt(codeCounts.K3)}`, tone: 'info', state: 'TESTED' },
    { id: 'validation', icon: 'stats', title: 'Statistical validation', sum: `bar ${fmtP(a.log10_threshold)} · best ${fmtP(a.log10_p)}${a.significant_but_rejected.length ? ` · ${a.significant_but_rejected.length} rejected` : ''}`, tone: r.status === 'DECODED' ? 'ok' : a.significant_but_rejected.length ? 'fail' : 'warn', state: validationState },
    { id: 'decision', icon: 'decision', title: 'Decision', sum: r.status === 'DECODED' ? `${CODE_SHORT(r.code)} · ${r.interleaver?.join('×')} · ${r.modulation}` : r.status === 'SIGNAL_NO_CODE' ? 'Signal, no code established' : 'Unknown: no interpretation asserted', tone: r.status === 'DECODED' ? 'ok' : r.status === 'SIGNAL_NO_CODE' ? 'info' : 'warn', state: STATUS_LABEL[r.status] },
  ]
  const detail: Record<NodeId, ReactNode> = {
    raw: <ViewsPanel pack={pack} />,
    detect: <TopicDetail pack={pack} topic="detection" />,
    structure: <div className="grid g-2"><div><div className="panel-title" style={{ marginBottom: 8 }}>SPS candidates</div><TopicDetail pack={pack} topic="sps" /></div><div className="col" style={{ gap: 18 }}><div><div className="panel-title" style={{ marginBottom: 8 }}>Modulation candidates</div><TopicDetail pack={pack} topic="modulation" /></div><div><div className="panel-title" style={{ marginBottom: 8 }}>CFO candidates</div><TopicDetail pack={pack} topic="cfo" /></div></div></div>,
    fec: <TopicDetail pack={pack} topic="fec" />,
    validation: <TopicDetail pack={pack} topic="validation" />,
    decision: <WhyPanel pack={pack} />,
  }
  return (
    <div className="grid" style={{ gridTemplateColumns: 'minmax(300px, 380px) minmax(0, 1fr)', alignItems: 'start' }}>
      <div className="chain" role="group" aria-label="Evidence chain, in the order the engine applied it">
        {nodes.map((n, i) => (
          <motion.div key={n.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.16 }}>
            {i > 0 && <div className="chain-link" aria-hidden="true" />}
            {n.id === 'fec' && (
              <div className="chain-branches" style={{ marginBottom: 0 }}>
                {['K7', 'K5', 'K3'].map((k) => (
                  <div key={k} className="chain-branch mono dim" style={{ fontSize: 11.5 }}>{k} · {fmtInt(codeCounts[k])} hypotheses{r.code && codeKey(r.code) === k ? ' · accepted' : ''}</div>
                ))}
              </div>
            )}
            {n.id === 'fec' && <div className="chain-link" aria-hidden="true" />}
            <button className={`chain-node${sel === n.id ? ' on' : ''}`} aria-pressed={sel === n.id} onClick={() => setSel(n.id)}>
              <span className={`chain-icon ${n.tone}`}><Icon name={n.icon} /></span>
              <span style={{ minWidth: 0 }}>
                <span className="chain-top"><span className="chain-idx mono">{String(i + 1).padStart(2, '0')}</span><span className="chain-title">{n.title}</span></span>
                <span className="chain-sum">{n.sum}</span>
              </span>
              <span className={`chain-state ${n.tone}`}>{n.state}</span>
            </button>
            {n.id === 'structure' && (
              <div className="chain-branches">
                <div className="chain-branch mono dim" style={{ fontSize: 11.5 }}>SPS: {d.sps_candidates.join(', ')}</div>
                <div className="chain-branch mono dim" style={{ fontSize: 11.5 }}>Modulation: BPSK, QPSK</div>
                <div className="chain-branch mono dim" style={{ fontSize: 11.5 }}>CFO: {d.cfo_candidates.map((c) => c.cfo.toFixed(4)).join(', ')}</div>
              </div>
            )}
          </motion.div>
        ))}
      </div>
      <motion.div key={sel} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
        <Panel title={nodes.find((n) => n.id === sel)?.title} right={<Tag kind={provOf(pack)} />}>{detail[sel]}</Panel>
      </motion.div>
    </div>
  )
}

// ---------------------------------------------------------------- hypothesis explorer
type StatusFilter = 'ALL' | 'ACCEPTED' | 'REJECTED' | 'SIGNIFICANT' | 'NOT SIGNIFICANT'

export function HypothesisExplorer({ pack }: { pack: EvidencePack }) {
  const all = pack.diagnostics.all_hypotheses
  const a = pack.accept
  const [codes, setCodes] = useState<Record<string, boolean>>({ K7: true, K5: true, K3: true })
  const [mods, setMods] = useState<Record<string, boolean>>({ BPSK: true, QPSK: true })
  const [minBits, setMinBits] = useState(0)
  const [status, setStatus] = useState<StatusFilter>('ALL')
  const [page, setPage] = useState(0)
  const acc = a.accepted_hypothesis
  const accKey = acc ? `${codeKey(acc.code)}|${String(acc.interleaver)}|${acc.sps}|${acc.modulation}` : ''
  const rejKeys = useMemo(() => new Set(a.significant_but_rejected.map((x) => `${codeKey(x.code)}|${String(x.interleaver)}|${x.sps}|${x.modulation}`)), [a.significant_but_rejected])
  const keyOf = useCallback((i: number) => all ? `${all.code[i]}|${all.rows[i]}x${all.cols[i]}|${all.sps[i]}|${all.modulation[i]}` : '', [all])
  const statusOf = useCallback((i: number): StatusFilter => {
    if (!all) return 'NOT SIGNIFICANT'
    const k = keyOf(i)
    if (k === accKey && all.log10_p[i] <= a.log10_threshold) return 'ACCEPTED'
    if (rejKeys.has(k) && all.log10_p[i] <= a.log10_threshold) return 'REJECTED'
    return all.log10_p[i] <= a.log10_threshold ? 'SIGNIFICANT' : 'NOT SIGNIFICANT'
  }, [all, keyOf, accKey, rejKeys, a.log10_threshold])
  const filter = useCallback((i: number) => !!all && codes[all.code[i]] && mods[all.modulation[i]] && all.rows[i] * all.cols[i] >= minBits && (status === 'ALL' || statusOf(i) === status),
    [all, codes, mods, minBits, status, statusOf])
  const isAcc = useCallback((i: number) => statusOf(i) === 'ACCEPTED', [statusOf])
  const isRej = useCallback((i: number) => statusOf(i) === 'REJECTED', [statusOf])
  const ranked = useMemo(() => {
    if (!all) return []
    return Array.from({ length: all.log10_p.length }, (_, i) => i).filter(filter).sort((x, y) => all.log10_p[x] - all.log10_p[y])
  }, [all, filter])
  if (!all) return <div className="empty">Hypothesis list not recorded for this capture.</div>
  const PAGE = 50
  const counts = { K7: 0, K5: 0, K3: 0 } as Record<string, number>
  all.code.forEach((c) => (counts[c] = (counts[c] ?? 0) + 1))
  return (
    <div className="col" style={{ gap: 14 }}>
      <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1fr) 320px', alignItems: 'stretch' }}>
        <Panel title={<span><span className="mono" style={{ fontSize: 22, color: 'var(--cyan)', marginRight: 10 }}>{fmtInt(a.n_hypotheses)}</span>hypotheses evaluated</span>}
          sub="Each point is one (CFO × symbol rate × modulation × rotation × code × interleaver) hypothesis. Height = evidence (−log10 p)."
          right={<Tag kind={provOf(pack)} />}>
          <Landscape all={all} threshold={a.log10_threshold} isAccepted={isAcc} isRejected={isRej} filter={filter} height={270} />
          <div className="legend" style={{ marginTop: 8 }}>
            <span><i style={{ background: 'var(--cyan)' }} />K7</span><span><i style={{ background: 'var(--violet)' }} />K5</span><span><i style={{ background: 'var(--green)' }} />K3</span>
            <span><i style={{ background: 'var(--amber)' }} />Significant</span><span><i style={{ background: 'var(--orange)' }} />Rejected by structure check</span><span><i style={{ background: 'var(--green)', borderRadius: 5 }} />Accepted</span>
          </div>
        </Panel>
        <Panel title="Filters">
          <div className="col" style={{ gap: 12 }}>
            <div className="field"><label>Code</label><div className="row-wrap">{['K7', 'K5', 'K3'].map((c) => <button key={c} className={`chip${codes[c] ? ' on' : ''}`} onClick={() => { setCodes({ ...codes, [c]: !codes[c] }); setPage(0) }}>{c} · {fmtInt(counts[c])}</button>)}</div></div>
            <div className="field"><label>Modulation</label><div className="row-wrap">{['BPSK', 'QPSK'].map((m) => <button key={m} className={`chip${mods[m] ? ' on' : ''}`} onClick={() => { setMods({ ...mods, [m]: !mods[m] }); setPage(0) }}>{m}</button>)}</div></div>
            <div className="field"><label>Minimum interleaver coverage: {minBits} bits</label><input type="range" min={0} max={384} step={8} value={minBits} onChange={(e) => { setMinBits(Number(e.target.value)); setPage(0) }} /></div>
            <div className="field"><label>Status</label>
              <select className="select" value={status} onChange={(e) => { setStatus(e.target.value as StatusFilter); setPage(0) }}>
                {(['ALL', 'ACCEPTED', 'REJECTED', 'SIGNIFICANT', 'NOT SIGNIFICANT'] as StatusFilter[]).map((s) => <option key={s}>{s}</option>)}
              </select></div>
            <div className="banner muted" style={{ fontSize: 12 }}><Icon name="info" /><span>The system searches a structured hypothesis space and accepts only what the evidence supports; it never picks a single answer by default.</span></div>
          </div>
        </Panel>
      </div>
      <Panel title="Ranked hypotheses" sub={`${fmtInt(ranked.length)} match the filters`} flush
        right={<div className="row"><button className="btn btn-sm" disabled={page === 0} onClick={() => setPage(page - 1)}><Icon name="back" size={12} /></button><span className="mono muted" style={{ fontSize: 12 }}>{page * PAGE + 1}–{Math.min(ranked.length, (page + 1) * PAGE)}</span><button className="btn btn-sm" disabled={(page + 1) * PAGE >= ranked.length} onClick={() => setPage(page + 1)}><Icon name="chevron" size={12} /></button></div>}>
        <div className="table-wrap" style={{ maxHeight: 460 }}>
          <table className="tbl">
            <thead><tr><th>Rank</th><th>Code</th><th>Interleaver</th><th className="num">Coverage</th><th>Mod</th><th className="num">sps</th><th className="num">Checks</th><th className="num">p-value</th><th>Status</th></tr></thead>
            <tbody>{ranked.slice(page * PAGE, (page + 1) * PAGE).map((i, k) => {
              const st = statusOf(i)
              const color = st === 'ACCEPTED' ? 'var(--green)' : st === 'REJECTED' ? 'var(--orange)' : st === 'SIGNIFICANT' ? 'var(--amber)' : 'var(--muted)'
              const rej = st === 'REJECTED' ? a.significant_but_rejected.find((x) => `${codeKey(x.code)}|${String(x.interleaver)}|${x.sps}|${x.modulation}` === keyOf(i)) : undefined
              return (
                <tr key={i} className={st === 'ACCEPTED' ? 'sel' : ''}>
                  <td className="mono muted">{String(page * PAGE + k + 1).padStart(2, '0')}</td>
                  <td className="mono">{all.code[i]}</td>
                  <td className="mono">{all.rows[i]}×{all.cols[i]}</td>
                  <td className="num">{all.rows[i] * all.cols[i]} bits</td>
                  <td className="mono">{all.modulation[i]}</td>
                  <td className="num">{all.sps[i]}</td>
                  <td className="num">{all.n_positive[i]}/{all.n_checks[i]}</td>
                  <td className="num">{fmtP(all.log10_p[i])}</td>
                  <td><span className="mono" style={{ color, fontSize: 11.5 }}>{st}</span>{rej && <div className="muted" style={{ fontSize: 11 }}>{rej.structural_rejection}</div>}</td>
                </tr>
              )
            })}</tbody>
          </table>
        </div>
      </Panel>
    </div>
  )
}

// ---------------------------------------------------------------- views
export function ViewsPanel({ pack }: { pack: EvidencePack }) {
  const v = pack.views
  const r = pack.result
  const ideal = r.modulation ?? pack.diagnostics.top_hypotheses[0]?.modulation ?? null
  return (
    <div className="grid g-2">
      <div><div className="panel-title" style={{ marginBottom: 6 }}>Waterfall (time–frequency)</div><Spectrogram db={v.spectrogram.db} f={v.spectrogram.f_hz} t={v.spectrogram.t_s} height={200} /></div>
      <div><div className="panel-title" style={{ marginBottom: 6 }}>Constellation {r.status === 'DECODED' ? '(accepted front-end)' : '(best candidate front-end)'}</div><Constellation points={v.constellation} ideal={ideal} height={214} /></div>
      <div><div className="panel-title" style={{ marginBottom: 6 }}>Power spectral density</div><LinePlot series={[{ x: v.units === 'normalised' ? v.psd.f_hz : v.psd.f_hz.map((f) => f / 1e3), y: v.psd.db, color: 'var(--cyan)', fill: true }]} yLabel="dB" xLabel={v.units === 'normalised' ? 'cycles/sample' : 'kHz'} height={170} /></div>
      <div><div className="panel-title" style={{ marginBottom: 6 }}>IQ samples</div><LinePlot series={[{ x: v.timeseries.i.map((_, i) => i), y: v.timeseries.i, color: 'var(--cyan)', width: 1 }, { x: v.timeseries.q.map((_, i) => i), y: v.timeseries.q, color: 'var(--violet)', width: 1 }]} xLabel="sample" height={170} /></div>
      {r.payload_len > 0 && (
        <div style={{ gridColumn: '1 / -1' }}>
          <div className="row" style={{ marginBottom: 6 }}><span className="panel-title grow">{r.status === 'DECODED' ? 'Decoded payload bits' : 'Hard-decision bits (not decoded)'}</span><span className="mono muted" style={{ fontSize: 11.5 }}>{r.payload_len} bits · polarity unresolved without frame sync</span></div>
          <div className="bits">{r.payload_bits.map((b, i) => <span key={i}>{i % 8 === 0 && i ? ' ' : ''}{b ? <b>1</b> : '0'}</span>)}</div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- audit & decision record
/** What the engine did to this capture, in order, with the operator's own actions merged in.
 *
 *  Exported so the CSV on the report page carries the same rows the screen shows: exporting only
 *  the operator events produced a file with nothing but headers for any record nobody had acted on
 *  yet. */
export function auditRows(pack: EvidencePack, extra: AuditEvent[] = []) {
  const t0 = new Date(pack.analysed_at).getTime()
  const tm = pack.diagnostics.timers_s
  let acc = 0
  const step = (s: number) => (acc += s * 1000)
  const d = pack.diagnostics, a = pack.accept
  return [
    { t: t0, actor: 'engine', label: 'Capture received', detail: `${fmtInt(pack.capture.samples)} samples (${pack.source.kind})` },
    { t: t0 + step(tm.cfo ?? 0), actor: 'engine', label: d.detection_log10_p <= LOG_ALPHA(pack) ? 'Signal detected' : 'Signal presence not established', detail: `${d.cfo_candidates.length} spectral-line candidates` },
    { t: t0 + step(tm.sps ?? 0), actor: 'engine', label: `${d.sps_candidates.length} SPS candidates generated`, detail: d.sps_candidates.join(', ') },
    { t: t0 + step((tm.matched_filter ?? 0) + (tm.syndrome_search ?? 0)), actor: 'engine', label: `${fmtInt(a.n_hypotheses)} FEC hypotheses evaluated`, detail: `${d.n_front_ends} front-ends` },
    { t: t0 + step(tm.scoring ?? 0), actor: 'engine', label: a.log10_p <= a.log10_threshold ? 'Statistical test passed' : 'Statistical test not passed', detail: `best p ${fmtP(a.log10_p)} vs bar ${fmtP(a.log10_threshold)}` },
    { t: t0 + step(tm.viterbi ?? 0), actor: 'engine', label: pack.result.status.replace('_', ' '), detail: pack.result.code ? `${CODE_SHORT(pack.result.code)} ${pack.result.interleaver?.join('×')}` : 'no interpretation asserted' },
    ...extra.map((e) => ({ t: e.t, actor: e.actor, label: e.action, detail: e.detail ?? '' })),
  ].sort((x, y) => x.t - y.t)
}

export function AuditTrail({ pack, extra }: { pack: EvidencePack; extra: AuditEvent[] }) {
  const t0 = new Date(pack.analysed_at).getTime()
  const tm = pack.diagnostics.timers_s
  let acc = 0
  const step = (s: number) => (acc += s * 1000)
  const d = pack.diagnostics, a = pack.accept
  const events = [
    { t: t0, label: 'Capture received', detail: `${fmtInt(pack.capture.samples)} samples (${pack.source.kind})` },
    { t: t0 + step(tm.cfo ?? 0), label: d.detection_log10_p <= LOG_ALPHA(pack) ? 'Signal detected' : 'Signal presence not established', detail: `${d.cfo_candidates.length} spectral-line candidates` },
    { t: t0 + step(tm.sps ?? 0), label: `${d.sps_candidates.length} SPS candidates generated`, detail: d.sps_candidates.join(', ') },
    { t: t0 + step((tm.matched_filter ?? 0) + (tm.syndrome_search ?? 0)), label: `${fmtInt(a.n_hypotheses)} FEC hypotheses evaluated`, detail: `${d.n_front_ends} front-ends` },
    { t: t0 + step(tm.scoring ?? 0), label: a.log10_p <= a.log10_threshold ? 'Statistical test passed' : 'Statistical test not passed', detail: `best p ${fmtP(a.log10_p)} vs bar ${fmtP(a.log10_threshold)}` },
    { t: t0 + step(tm.viterbi ?? 0), label: pack.result.status.replace('_', ' '), detail: pack.result.code ? `${CODE_SHORT(pack.result.code)} ${pack.result.interleaver?.join('×')}` : 'no interpretation asserted' },
    ...extra.map((e) => ({ t: e.t, label: e.action, detail: e.actor })),
  ].sort((x, y) => x.t - y.t)
  return (
    <div className="list">
      {events.map((e, i) => (
        <div key={i} className="list-item" style={{ gridTemplateColumns: '170px 1fr auto', cursor: 'default' }}>
          <span className="mono muted" style={{ fontSize: 12 }}>{new Date(e.t).toLocaleTimeString('en-GB', { timeZone: 'Asia/Kolkata', hour12: false })}.{String(new Date(e.t).getMilliseconds()).padStart(3, '0')}</span>
          <span>{e.label}</span>
          <span className="muted" style={{ fontSize: 12 }}>{e.detail}</span>
        </div>
      ))}
    </div>
  )
}

export function DecisionRecord({ pack, operatorAction }: { pack: EvidencePack; operatorAction?: string }) {
  const e = pack.engine
  return (
    <dl className="kv">
      <dt>Signal ID</dt><dd>{pack.id}</dd>
      <dt>Analysed</dt><dd>{fmtDateTime(new Date(pack.analysed_at).getTime())}</dd>
      <dt>Software version</dt><dd>engine {e.version} · {e.commit}</dd>
      <dt>Model version</dt><dd>none: deterministic DSP + statistical test</dd>
      <dt>DSP configuration</dt><dd>α={e.alpha} · sps {e.sps_range.join('–')} · |CFO|≤{e.cfo_max} · β_rx={e.rx_beta} · BL Δ={e.bl_delta_symbols} · PM≥{e.pm_floor}</dd>
      <dt>Code catalogue</dt><dd>{e.codes.map((c) => CODE_SHORT(c)).join(', ')}</dd>
      <dt>Hypotheses tested</dt><dd>{fmtInt(pack.accept.n_hypotheses)}</dd>
      <dt>Decision</dt><dd>{pack.result.status}</dd>
      <dt>Evidence</dt><dd>p {fmtP(pack.accept.log10_p)} vs bar {fmtP(pack.accept.log10_threshold)}</dd>
      <dt>Operator action</dt><dd>{operatorAction ?? 'none recorded'}</dd>
    </dl>
  )
}

export function DataQuality({ pack, stationClock }: { pack: EvidencePack; stationClock?: string }) {
  const c = pack.capture
  const metaFields = ['station', 'center_freq_hz', 'bandwidth_hz', 'antenna', 'captured_at', 'format', 'name']
  const present = metaFields.filter((k) => (c as Record<string, unknown>)[k] != null && (c as Record<string, unknown>)[k] !== '').length
  const snr = (pack.accept.accepted_hypothesis ?? pack.diagnostics.top_hypotheses[0])?.symbol_snr_db
  const rows: { k: string; v: string; tag: Provenance; tone?: string }[] = [
    { k: 'Capture length', v: `${fmtInt(c.samples)} samples${c.duration_s != null ? ` · ${(c.duration_s * 1e3).toFixed(2)} ms` : ''}`, tag: provOf(pack) },
    { k: 'Sample rate', v: fmtFs(c), tag: c.fs_hz == null ? 'NOT ESTABLISHED' : provOf(pack) },
    { k: 'Signal quality (symbol SNR, M2M4)', v: snr != null ? `${snr.toFixed(1)} dB · ${snr > 10 ? 'GOOD' : snr > 5 ? 'FAIR' : 'POOR'}` : '—', tag: provOf(pack) },
    { k: 'Metadata completeness', v: `${Math.round((present / metaFields.length) * 100)}% (${present}/${metaFields.length} fields)`, tag: provOf(pack) },
    { k: 'Clock synchronisation', v: stationClock ?? 'NOT RECORDED', tag: stationClock ? 'SIMULATED' : 'NOT ESTABLISHED' },
    { k: 'Analysis confidence', v: pack.result.status === 'DECODED' ? 'VERIFIED (accepted)' : 'RESTRAINED (not asserted)', tag: provOf(pack) },
  ]
  return (
    <div className="list">
      {rows.map((r) => (
        <div key={r.k} className="list-item" style={{ gridTemplateColumns: '1fr auto auto', cursor: 'default' }}>
          <span className="muted" style={{ fontSize: 12.5 }}>{r.k}</span><span className="mono">{r.v}</span><Tag kind={r.tag} />
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------- capture gate
const QUALITY_TONE: Record<QualityStatus, string> = { GOOD: 'ok', DEGRADED: 'warn', FAILED: 'no' }
const CHECK_LABEL: Record<string, string> = {
  samples: 'Sample integrity', level: 'Signal level', clipping: 'Clipping', dc_offset: 'DC offset',
  gaps: 'Dropouts', iq_balance: 'I/Q balance', sample_rate: 'Declared sample rate',
}

/** The capture gate: can this recording be trusted as a measurement? Never part of the verdict. */
export function CaptureGate({ pack }: { pack: EvidencePack }) {
  const q = pack.data_quality
  if (!q) return <div className="empty">This record predates the capture gate; it was not assessed.</div>
  const m = q.metrics
  return (
    <div className="col" style={{ gap: 12 }}>
      <div className="statbar">
        <div><span className="kpi-label">Capture gate</span><b className={QUALITY_TONE[q.status]}>{q.status}</b></div>
        <div><span className="kpi-label">Decode verdict</span><b>{pack.result.status.replace(/_/g, ' ')}</b></div>
        <div><span className="kpi-label">Clipped</span><b className="mono">{pct(m.clipped_fraction)}</b></div>
        <div><span className="kpi-label">DC / RMS</span><b className="mono">{pct(m.dc_over_rms)}</b></div>
      </div>
      <div className="list">
        {q.checks.map((ch) => (
          <div key={ch.check} className="list-item" style={{ gridTemplateColumns: '180px minmax(0, 1fr) 90px', cursor: 'default' }}>
            <span className="muted" style={{ fontSize: 12.5 }}>{CHECK_LABEL[ch.check] ?? ch.check}</span>
            <span>{ch.detail}</span>
            <span className={`mono ${QUALITY_TONE[ch.status]}`} style={{ textAlign: 'right', fontSize: 12 }}>{ch.status}</span>
          </div>
        ))}
      </div>
      <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>{q.note}</p>
    </div>
  )
}

// ---------------------------------------------------------------- what would prove it
const SUFFICIENCY_TITLE: Record<string, string> = {
  ACHIEVABLE: 'More of this signal would settle it',
  IMPOSSIBLE_IN_DOMAIN: 'No capture length can settle this',
  STRUCTURALLY_REJECTED: 'The evidence was there and was refused on structure',
  NO_TREND: 'Nothing is trending towards an answer',
  NO_SIGNAL_EVIDENCE: 'No structure reached the code search',
  UNKNOWN_CAUSE: 'Cause not established',
}

/** What would turn this refusal into a decision, in the engine's own units. */
/** `detailOnly` drops the prose (the Verdict already states the reason and the requirement) and
 *  keeps the measurements behind them. */
export function WhatWouldProveIt({ pack, detailOnly }: { pack: EvidencePack; detailOnly?: boolean }) {
  const s = pack.sufficiency
  if (pack.result.status === 'DECODED') {
    return <div className="empty">This capture was accepted. Nothing further is required.</div>
  }
  if (!s) return <div className="empty">This record predates the sufficiency analysis.</div>
  const r = s.required, me = s.measured
  return (
    <div className="col" style={{ gap: 12 }}>
      {!detailOnly && <div>
        <div className="section-label">{SUFFICIENCY_TITLE[s.verdict] ?? s.verdict}</div>
        <p style={{ margin: '6px 0 0' }}>{s.reason}</p>
      </div>}
      {me.parity_checks != null && (
        <div className="statbar">
          <div><span className="kpi-label">Parity checks</span><b className="mono">{fmtInt(me.parity_checks)}</b></div>
          <div><span className="kpi-label">Agreeing</span><b className="mono">{fmtInt(me.checks_agreeing ?? 0)}{me.agreement_rate != null ? ` · ${pct(me.agreement_rate)}` : ''}</b></div>
          <div><span className="kpi-label">Evidence</span><b className="mono">{fmtP(s.best_log10_p ?? 0)}</b></div>
          <div><span className="kpi-label">Bar</span><b className="mono">{fmtP(s.bar_log10_p ?? 0)}</b></div>
        </div>
      )}
      {!detailOnly && <div>
        <div className="section-label">What would prove it</div>
        <p style={{ margin: '6px 0 0' }}>{s.what_would_prove_it}</p>
      </div>}
      {detailOnly && !me.parity_checks && !r?.achievable && <div className="empty">No further measurement is recorded for this refusal beyond the explanation above.</div>}
      {r?.achievable && (
        <dl className="kv">
          <dt>Parity checks now</dt><dd>{fmtInt(r.parity_checks_now ?? 0)}</dd>
          <dt>Parity checks needed</dt><dd>{fmtInt(r.parity_checks_needed ?? 0)}</dd>
          <dt>Additional coded bits</dt><dd>{fmtInt(r.extra_coded_bits ?? 0)}</dd>
          <dt>Additional capture</dt><dd>{r.extra_seconds != null ? `${r.extra_seconds.toFixed(3)} s` : r.extra_samples != null ? `${fmtInt(r.extra_samples)} samples (duration unknown: no absolute sample rate)` : 'duration unknown'}</dd>
          <dt>Assumption</dt><dd>{r.assumption}</dd>
        </dl>
      )}
      <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>
        These figures come from the sign test that refused this capture: the observed agreement rate of
        the best hypothesis measured against the acceptance bar, not a target chosen in advance.
      </p>
    </div>
  )
}

// ---------------------------------------------------------------- receipt verification
type VerifyStep = { label: string; ok: boolean | null; detail: string }

async function runVerification(pack: EvidencePack, rc: Receipt): Promise<VerifyStep[]> {
  const ledgers = await loadLedgers()
  const searched = ledgers.map((l) => ({ ...l, parsed: l.lines.map((s) => { try { return JSON.parse(s) as Receipt } catch { return null } }) }))
  const hit = searched.map((l) => ({ l, idx: l.parsed.findIndex((r) => r?.hash === rc.hash) })).find((x) => x.idx >= 0)
  if (!hit) {
    return [{ label: 'Receipt present in the ledger', ok: false,
      detail: `No receipt with hash ${rc.hash.slice(0, 12)}… appears in ${searched.map((l) => l.source).join(' or ')}. This decision is not recorded.` }]
  }
  const { lines, source, total, parsed } = hit.l
  const idx = hit.idx
  const one = await verifyLine(lines[idx])
  const chain = await verifyChain(lines)
  const stored = parsed[idx]!
  const matches = stored.decision.status === pack.result.status && stored.capture.sha256 === rc.capture.sha256
  const dupes = parsed.filter((r) => r?.capture?.sha256 === rc.capture.sha256).length
  return [
    { label: 'Receipt present in the ledger', ok: true, detail: `Entry ${idx + 1} of ${total} in ${source}.` },
    { label: 'Hash recomputed in this browser', ok: one.ok,
      detail: one.ok
        ? `SHA-256 over the receipt content gives ${one.recomputed.slice(0, 16)}…, which is the hash stored with it.`
        : `Recomputed ${one.recomputed.slice(0, 16)}…, stored ${one.stored.slice(0, 16)}…. The content has changed since it was written.` },
    { label: 'Chain links intact', ok: chain.ok,
      detail: chain.ok
        ? `${chain.checked} receipts checked, each carrying the hash of the one before it. Head ${chain.head.slice(0, 16)}….`
        : chain.problems.slice(0, 3).map((p) => `entry ${p.index + 1}: ${p.problem}`).join(' · ') },
    { label: 'Decision on screen matches the receipt', ok: matches,
      detail: matches
        ? `${stored.decision.status} on capture ${rc.capture.sha256.slice(0, 16)}…, as shown on this page.`
        : `The ledger records ${stored.decision.status} for a different capture or verdict than this page shows.` },
    { label: 'Capture seen before', ok: null,
      detail: dupes > 1
        ? `This exact capture appears in ${dupes} receipts: it has been analysed more than once.`
        : 'This capture appears once in the ledger.' },
  ]
}

export function ReceiptPanel({ pack }: { pack: EvidencePack }) {
  const rc = pack.receipt
  const [state, setState] = useState<{ busy: boolean; steps: VerifyStep[]; error: string | null }>(
    { busy: false, steps: [], error: null })
  if (!rc) return <div className="empty">No receipt was issued for this record.</div>
  const verify = async () => {
    setState({ busy: true, steps: [], error: null })
    try {
      setState({ busy: false, steps: await runVerification(pack, rc), error: null })
    } catch (e) {
      setState({ busy: false, steps: [], error: e instanceof Error ? e.message : 'Verification could not be completed.' })
    }
  }
  const failed = state.steps.some((s) => s.ok === false)
  const a = pack.accept
  const pass = pack.result.status === 'DECODED'
  const checks = structuralChecks(pack)
  // The receipt's own figures where it recorded them; the pack's where an older receipt did not.
  const stat = (k: keyof Receipt['statistics']) => rc.statistics[k] ?? null
  return (
    <div className="col" style={{ gap: 14 }}>
      <div className="receipt">
        <div className="receipt-head"><Icon name="shield" size={15} /><span>Verifiable decision receipt</span></div>
        <dl className="receipt-rows">
          <div><dt>Result</dt><dd><Stamp status={pack.result.status} /></dd></div>
          <div><dt>Capture</dt><dd className="mono" title={rc.capture.sha256}>sha256 {rc.capture.sha256.slice(0, 16)}…</dd></div>
          <div><dt>Hypotheses tested</dt><dd className="mono">{fmtInt(stat('n_hypotheses') ?? a.n_hypotheses)}</dd></div>
          <div><dt>Acceptance</dt><dd className={pass ? 'ok' : 'no'}><b>{pass ? 'PASS' : a.log10_p <= a.log10_threshold ? 'REJECTED ON STRUCTURE' : 'BAR NOT MET'}</b></dd></div>
          <div><dt>Threshold α / M</dt><dd className="mono">{fmtP(stat('log10_threshold') ?? a.log10_threshold)}</dd></div>
          <div><dt>Observed</dt><dd className="mono">{fmtP(stat('log10_p') ?? a.log10_p)}</dd></div>
          <div><dt>Structural checks</dt><dd>{checks.length ? checks.map((c) => (
            <span key={c.label} className={`receipt-check ${c.ok ? 'ok' : 'no'}`}><Icon name={c.ok ? 'check' : 'cross'} size={12} />{c.label}</span>
          )) : <span className="muted">not reached: no candidate hypothesis</span>}</dd></div>
          <div><dt>Receipt</dt><dd className="mono" title={rc.hash}>{rc.hash.slice(0, 32)}…</dd></div>
          <div><dt>Previous receipt</dt><dd className="mono">{rc.prev_hash === GENESIS ? 'none: first entry in the ledger' : `${rc.prev_hash.slice(0, 24)}…`}</dd></div>
          <div><dt>Written</dt><dd className="mono">{fmtDateTime(new Date(rc.created_utc).getTime())}</dd></div>
          {rc.decision.code && <div><dt>Recorded code</dt><dd className="mono">{CODE_SHORT(rc.decision.code)}</dd></div>}
        </dl>
      </div>
      <div className="row" style={{ gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <button className="btn btn-primary" onClick={() => void verify()} disabled={state.busy} data-loading={state.busy}>
          {state.busy ? 'Verifying…' : 'Verify receipt'}
        </button>
        <span className="muted" style={{ fontSize: 12.5 }}>
          Hashes are recomputed here, in your browser. The server is not asked whether it is honest.
        </span>
      </div>
      {state.error && <div className="banner amber" role="alert"><Icon name="info" /><span>Verification could not be completed: {state.error}</span></div>}
      <div role="status" aria-live="polite">
        {state.steps.length > 0 && (
          <div className="col" style={{ gap: 12 }}>
            <div className={`verify-result ${failed ? 'bad' : 'ok'}`}>
              <Icon name={failed ? 'cross' : 'check'} size={20} />
              <div>
                <b>{failed ? 'VERIFICATION FAILED' : 'RECEIPT VERIFIED'}</b>
                <span>{failed
                  ? 'Treat this decision as unproven: the record does not match what it claims. The failing step is marked below.'
                  : 'Every hash recomputed in this browser matches the stored ledger. The record has not been altered since it was written.'}</span>
              </div>
            </div>
            <ul className="why-list">
              {state.steps.map((s) => (
                <Check key={s.label} ok={s.ok === true} na={s.ok === null}>
                  {s.label}<div className="muted" style={{ fontSize: 12.5 }}>{s.detail}</div>
                </Check>
              ))}
            </ul>
          </div>
        )}
      </div>
      <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>
        A receipt proves that this decision belongs to this capture and this engine configuration, and
        that the ledger has not been edited since. It is not a signature, and it does not prove the
        decision is correct. <Tag kind="EXPERIMENTAL" />
      </p>
    </div>
  )
}
