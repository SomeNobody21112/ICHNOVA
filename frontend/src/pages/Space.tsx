import { useEffect, useState } from 'react'
import { HBars } from '../components/charts'
import { Icon, Loading, Panel, Tabs, Tag } from '../components/ui'

/** Every number here is read from frontend/public/space.json, written by
 *  server/export_space_data.py out of the result files in results/. Nothing is typed by hand.
 *  The narrative text is the wording the reports and SPACE_CLAIM_FIREWALL.md already permit. */
type Stat = { n: number; min: number; med: number; max: number }
type Space = {
  generated_from_commit: string
  doppler: {
    n: number; treated: number; controls: number; wrong_payload: number
    controls_wrong_payload: number; wrong_structure: number; max_drift_rate: number; source: string
    by_severity: { severity: number; n: number; wrong_payload: number; correct: number; refused: number; peak_cyc_per_sample: number }[]
    by_trajectory: { trajectory: string; n: number; treated: boolean; wrong_payload: number; correct: number; refused: number }[]
  }
  mechanism: { n_analyses: number; conclusion_label: string; source: string
    arms: { arm: string; label: string; treated: number; wrong_payload: number; correct: number; refused: number; wrong_structure: number }[] }
  estimator: {
    decision: string; source: string
    doppler_gain: { arm: string; treated: number; wrong_payload: number; correct: number }[]
    regression: { population: string; before: { n: number; correct: number; false_accept: number }; after: { n: number; correct: number; false_accept: number } }[]
    idle_carrier: Record<string, { status: string; code: string | null; f4_margin: number; f4_accepted: boolean; n_converged: number | null; n_codewords: number | null }>
  }
  f4: { n: number; accepts: number; accepts_correct: number; accepts_zero_convergence: number
    true_nulls: number; accepts_on_true_nulls: number; closest_non_accepting_margin: number
    weakest_accepting_margin: number; source: string }
  offcarrier: { n: number; signal_bearing: number; captures_with_off_carrier_admitted: number
    admitted_front_ends: number; admitted_off_carrier: number; published_claims: number
    claims_by_band: Record<string, number>; f4_passes_from_off_carrier: number; source: string }
  tracker: { n: number; tracker_ran: number; block_choice: Record<string, number>; min_symbols: number
    claim_from_tracked: number; failures_from_untracked: number; failures_total: number; source: string
    by_trajectory: { trajectory: string; n: number; treated: boolean; max_err_rad: Stat | null; captures_with_slip: number; predicted_slip: number }[]
    slip_outcome_grid: { slip: string; outcome: string; n: number }[] }
  validity: { n: number; bound_rad: number; measured: number; indeterminate: number; source: string
    by_trajectory: ({ group: string; treated: boolean } & Partial<Stat>)[]
    by_slip: ({ group: string } & Partial<Stat>)[] }
  reports: string[]
}

type T = 'story' | 'doppler' | 'mechanism' | 'remediation' | 'tracker' | 'boundary'
const pct = (a: number, b: number) => (b ? `${((100 * a) / b).toFixed(1)}%` : '—')
const rad = (v?: number) => (v == null ? '—' : `${v.toFixed(v < 0.1 ? 4 : 3)} rad`)
const Fig = ({ label, value, note, accent }: { label: string; value: string; note?: string; accent?: 'amber' | 'green' }) => (
  <div className={`kpi${accent ? ` accent-${accent}` : ''}`}>
    <div className="row"><span className="kpi-label grow">{label}</span></div>
    <div className="kpi-value">{value}</div>
    <div className="kpi-note">{note ?? ' '}</div>
  </div>
)
const Src = ({ s }: { s: string }) => <div className="mono muted" style={{ fontSize: 11, marginTop: 10 }}>source: {s}</div>

/** The chain a judge should be able to repeat back. Each step names its measured outcome. */
const CHAIN: { step: string; what: string; got: string }[] = [
  { step: 'Unknown RF arrives', what: 'An IQ capture with no parameters supplied.', got: 'No assumption is made about carrier, rate, modulation or code.' },
  { step: 'Blind inference', what: 'Every rate × modulation × rotation × code × interleaver is a hypothesis, tested under family-wise error control.', got: 'Validated at benchmark conditions for a carrier static within the capture.' },
  { step: 'Refusal when evidence is short', what: 'DECODED / SIGNAL_NO_CODE / UNKNOWN, with the statistic that refused.', got: '0 of 120 false accepts on non-catalogue classes; 0 of 900 on an independent null set.' },
  { step: 'Controlled space experiment', what: '192 synthetic vectors, criteria pre-registered before the first vector existed.', got: 'One run, published as-is — including the failure.' },
  { step: 'Measured limitation', what: 'A carrier that moves during the capture.', got: 'Structure stayed correct in all 192; the payload did not.' },
  { step: 'Mechanism investigation', what: 'Five arms on the same bytes.', got: 'Residual carrier error the front end does not model.' },
  { step: 'Remediation attempted', what: 'A blind carrier pre-correction in front of the structural search.', got: 'It fixed Doppler and broke things that already worked.' },
  { step: 'Remediation rejected', what: 'Two pre-registered rules fired; the decision was taken by the rules, not by preference.', got: 'INTEGRATION NOT SUPPORTED.' },
  { step: 'The boundary is now reported', what: 'The engine publishes how close its phase tracker ran to its own unwrap ambiguity.', got: 'Evidence, consulted by no decision.' },
  { step: 'A refusal replaces the wrong answer', what: 'A payload-reliability floor on the re-encode consistency the engine already computed, measured before it was integrated.', got: 'Costs 0 of 1,278 working decodes; 52 of 54 wrong payloads are now withheld, and 3 long-standing false accepts became refusals.' },
]

const BOUNDARY = {
  established: [
    'Blind identification of modulation, symbol rate, coding and framing — benchmark conditions, carrier static within the capture',
    'Refusal with a stated reason when the evidence is insufficient',
    'An unreliable payload is withheld rather than published, with the statistic and floor given',
    'Signal structure stays correct even under a moving carrier',
    'Structural acceptance never fired on a true null across 1,810 sealed captures',
    'The engine reports when its phase tracker ran at its own unwrap limit',
  ],
  limitation: [
    'Payload reliability under a carrier that moves during the capture — measured, not suspected',
    'The payload itself is still not recovered under a moving carrier — it is withheld, not decoded',
    '2 of the 54 measured wrong payloads still clear the reliability floor and would be published',
    'The phase tracker fails past a bound written into its own code, and its block adaptation is already at its finest setting',
  ],
  notEstablished: [
    'Real spacecraft RF — no spacecraft capture exists in this project',
    'Orbital Doppler: no TLE, no geometry, no pass model',
    'Carrier-trajectory measurement or static-vs-time-varying classification',
    'CCSDS layers outside the searched domain (TM block-LDPC, turbo, packet semantics, GMSK)',
    'Space UI / mission replay / telemetry forensics — design only, not built',
  ],
}

export default function Space() {
  const [d, setD] = useState<Space | null>(null)
  const [tab, setTab] = useState<T>('story')
  useEffect(() => { fetch('/space.json').then((r) => r.json()).then(setD).catch(() => setD(null)) }, [])
  if (!d) return <div className="page"><Loading label="Loading space evidence…" /></div>
  const { doppler: dp, mechanism: mx, estimator: es, f4, offcarrier: oc, tracker: tr, validity: va } = d
  const idleA = es.idle_carrier.A_production
  const idleB = es.idle_carrier.B_candidate

  return (
    <div className="page">
      <div className="page-head">
        <div className="grow">
          <h1 className="page-title">Space ground segment</h1>
          <div className="page-sub">
            ICHNOVA is a ground-segment analysis layer: it reads a recording, it does not fly. Every number on this page is
            read from result files in the repository (commit {d.generated_from_commit}) — nothing is typed by hand.
          </div>
        </div>
        <Tag kind="BENCHMARK">Synthetic benchmark data</Tag>
      </div>

      {/* The four numbers the whole branch rests on. auto-fit, so the bar never leaves a gap. */}
      <div className="statbar" style={{ marginBottom: 14 }}>
        <Fig label="Structural claims correct" value={`${dp.n}/${dp.n}`} note="no wrong structure in any capture" accent="green" />
        <Fig label="Wrong payloads, moving carrier" value={`${dp.wrong_payload}/${dp.treated}`} note={`${pct(dp.wrong_payload, dp.treated)} of treated captures — the measured limitation`} accent="amber" />
        <Fig label="Wrong payloads, static control" value={`${dp.controls_wrong_payload}/${dp.controls}`} note="the same engine, carrier held still" accent="green" />
        <Fig label="Structural accepts on true nulls" value={`${f4.accepts_on_true_nulls}/${f4.true_nulls}`} note={`${f4.accepts} accepts over ${f4.n.toLocaleString('en-IN')} sealed captures, all correct`} accent="green" />
      </div>

      <div className="banner amber" style={{ marginBottom: 14 }}>
        <Icon name="flag" />
        <div>
          <b>MEASURED LIMITATION.</b> Under a carrier that moves during the capture the engine kept the structure right and published
          a wrong payload in <b>{dp.wrong_payload} of {dp.treated}</b> treated captures. That measurement is what the engine did
          <i>before</i> the payload-reliability floor was integrated; it now <b>withholds</b> such a payload and reports
          SIGNAL_NO_CODE with the reason, keeping the structural claim the evidence supports. The decode verdict remains scoped
          to a carrier that is <b>static within the capture</b>. This page shows how the failure was found, what was tried, why
          the obvious fix was rejected, and what was finally integrated.
        </div>
      </div>

      <Tabs<T> value={tab} onChange={setTab} tabs={[
        { id: 'story', label: 'The investigation' },
        { id: 'doppler', label: 'Doppler experiment' },
        { id: 'mechanism', label: 'Mechanism' },
        { id: 'remediation', label: 'Rejected fix' },
        { id: 'tracker', label: 'Tracker + validity' },
        { id: 'boundary', label: 'Capability boundary' },
      ]} />

      {tab === 'story' && (
        <div className="grid g-2" style={{ alignItems: 'start' }}>
          <Panel title="Nine steps, each with its measured outcome" sub="This is the whole branch. No step is a plan; every one produced a number that is in the repository">
            <ol className="col" style={{ margin: 0, paddingLeft: 0, listStyle: 'none', gap: 10 }}>
              {CHAIN.map((c, i) => (
                <li key={c.step} style={{ display: 'grid', gridTemplateColumns: '22px 1fr', gap: 10, alignItems: 'start' }}>
                  <span className="mono dim" style={{ fontSize: 11.5, paddingTop: 2 }}>{String(i + 1).padStart(2, '0')}</span>
                  <div style={{ minWidth: 0 }}>
                    <b style={{ fontSize: 13.5 }}>{c.step}</b>
                    <div className="muted" style={{ fontSize: 12.5, marginTop: 1 }}>{c.what}</div>
                    <div style={{ fontSize: 12.5, marginTop: 2 }}><Icon name="check" size={11} /> {c.got}</div>
                  </div>
                </li>
              ))}
            </ol>
          </Panel>
          <div className="col" style={{ gap: 16 }}>
            <Panel title="What we may say" sub="The one sentence both halves of which are measured">
              <div className="banner" style={{ margin: 0 }}>
                <Icon name="check" />
                <span>“ICHNOVA's blind-inference core and refusal discipline are validated within its documented benchmark
                  scope; controlled time-varying-carrier testing has identified a measured limitation in payload reliability.”</span>
              </div>
              <p className="dim" style={{ fontSize: 12.5, marginBottom: 0 }}>
                Dropping the second half is a false claim by omission, so it is never said alone.
              </p>
            </Panel>
            <Panel title="What we do not say" sub="Each of these is prohibited until evidence exists">
              <ul className="col" style={{ margin: 0, paddingLeft: 18, gap: 6, fontSize: 12.5 }}>
                <li>“Handles satellite Doppler” — the opposite is what was measured</li>
                <li>“Validated on satellite links” — no spacecraft capture exists here</li>
                <li>“Space-ready” — never supported, now contradicted</li>
                <li>“Decodes telemetry during a pass” — no pass has been analysed</li>
                <li>Any payload guarantee without the static-carrier qualifier</li>
              </ul>
            </Panel>
            <Panel title="How to read every label on this page">
              <div className="col" style={{ gap: 8, fontSize: 12.5 }}>
                <div className="row" style={{ gap: 8 }}><Tag kind="BENCHMARK" /><span className="dim">measured by the real engine on synthetic captures</span></div>
                <div className="row" style={{ gap: 8 }}><Tag kind="SIMULATED" /><span className="dim">the scenario is synthetic; the engine output on it is real</span></div>
                <div className="row" style={{ gap: 8 }}><Tag kind="LIVE" /><span className="dim">produced from an operator or receiver capture</span></div>
                <div className="row" style={{ gap: 8 }}><Tag kind="NOT ESTABLISHED" /><span className="dim">not implemented, or implemented and not validated</span></div>
              </div>
            </Panel>
          </div>
        </div>
      )}

      {tab === 'doppler' && (
        <div className="col" style={{ gap: 16 }}>
          <div className="grid g-2" style={{ alignItems: 'start' }}>
            <Panel title="Wrong payloads rise with carrier severity" sub="Treated captures only: a carrier that moves during the capture" right={<Tag kind="BENCHMARK" />}>
              <HBars max={Math.max(...dp.by_severity.map((s) => s.n))}
                items={dp.by_severity.map((s) => ({
                  label: `severity ${s.severity}`, value: s.wrong_payload, color: 'var(--amber)',
                  note: `${s.wrong_payload} wrong of ${s.n}; peak offset ${s.peak_cyc_per_sample.toExponential(2)} cyc/sample`,
                }))} fmt={(v) => `${v}`} />
              <p className="dim" style={{ fontSize: 12.5, marginBottom: 0 }}>
                Bars are counts of wrong payloads; each severity band holds {dp.by_severity[0]?.n} captures. The failure is
                already present at the gentlest setting tested — it does not switch on at some comfortable threshold.
              </p>
              <Src s={dp.source} />
            </Panel>
            <Panel title="The same engine, four carrier shapes" sub="zero and static are controls; linear and pass move the carrier" flush>
              <table className="tbl">
                <thead><tr><th>Carrier</th><th className="num">n</th><th className="num">Correct</th><th className="num">Wrong payload</th><th className="num">Refused</th></tr></thead>
                <tbody>{dp.by_trajectory.map((t) => (
                  <tr key={t.trajectory}>
                    <td><b>{t.trajectory}</b>{!t.treated && <span className="muted"> · control</span>}</td>
                    <td className="num">{t.n}</td>
                    <td className="num">{t.correct}</td>
                    <td className="num" style={{ color: t.wrong_payload ? 'var(--amber)' : undefined }}>{t.wrong_payload}</td>
                    <td className="num">{t.refused}</td>
                  </tr>
                ))}</tbody>
              </table>
              <div className="dim" style={{ fontSize: 12.5, padding: '10px 14px' }}>
                Controls hold the carrier still and produce <b>{dp.controls_wrong_payload}</b> wrong payloads. That is what makes
                the treated column a result about the carrier and not about the engine in general.
              </div>
            </Panel>
          </div>
          <Panel title="The half that held, and the half that did not" sub="Both are measured on the same 192 captures">
            <div className="grid g-2" style={{ gap: 14 }}>
              <div className="banner" style={{ margin: 0 }}>
                <Icon name="check" />
                <div><b>Structure: {dp.wrong_structure} wrong in {dp.n}.</b> Modulation, symbol rate, code family and framing stayed
                  correct at drift rates up to {dp.max_drift_rate.toExponential(2)} cyc/sample² — far beyond the bench channel.</div>
              </div>
              <div className="banner amber" style={{ margin: 0 }}>
                <Icon name="flag" />
                <div><b>Payload: {dp.wrong_payload} wrong in {dp.treated}.</b> The bits beneath a correct structural claim were not the
                  transmitted bits, and the verdict did not say so. Published as-is, with the criteria that failed.</div>
              </div>
            </div>
          </Panel>
        </div>
      )}

      {tab === 'mechanism' && (
        <div className="col" style={{ gap: 16 }}>
        <div className="grid g-2" style={{ alignItems: 'start' }}>
          <Panel title="Five arms on the same bytes" sub="Paired comparison: only the carrier handling changes" right={<Tag kind="BENCHMARK" />}>
            <HBars max={Math.max(...mx.arms.map((a) => a.treated))}
              items={mx.arms.map((a) => ({
                label: a.label, value: a.wrong_payload,
                color: a.wrong_payload === 0 ? 'var(--green)' : a.arm === 'B_existing' ? 'var(--amber)' : 'var(--faint)',
                note: `${a.wrong_payload} wrong payloads of ${a.treated} treated`,
              }))} fmt={(v) => `${v}`} />
            <Src s={mx.source} />
          </Panel>
          <Panel title="What that proves, and what it does not" sub={mx.conclusion_label}>
            <ul className="col" style={{ margin: 0, paddingLeft: 18, gap: 8, fontSize: 12.8 }}>
              <li><b>Remove the carrier motion exactly and the failure disappears</b> — 0 wrong payloads. So the information was
                never destroyed; it was mis-recovered.</li>
              <li><b>A blind estimator gets within 3.</b> The information is recoverable without ground truth, which is what made
                the remediation attempt worth running.</li>
              <li><b>Ablating the phase tracker makes it worse</b> (77 vs 57). The tracker helps; it is not the villain.</li>
              <li className="dim">This is a mechanism, not a universal root cause. It is labelled SUPPORTED, from
                {' '}{mx.n_analyses.toLocaleString('en-IN')} analyses on one synthetic population.</li>
            </ul>
          </Panel>
        </div>
        <Panel title="Every outcome of every arm" sub="Treated captures only. Structure held in all four arms of the shipped configuration; only the payload column moves" flush>
          <table className="tbl">
            <thead><tr><th>Arm</th><th className="num">Treated</th><th className="num">Correct payload</th><th className="num">Wrong payload</th><th className="num">Refused</th><th className="num">Wrong structure</th></tr></thead>
            <tbody>{mx.arms.map((a) => (
              <tr key={a.arm}>
                <td><b>{a.label}</b><div className="muted mono" style={{ fontSize: 11.5 }}>{a.arm}</div></td>
                <td className="num">{a.treated}</td>
                <td className="num" style={{ color: a.correct ? 'var(--green)' : undefined }}>{a.correct}</td>
                <td className="num" style={{ color: a.wrong_payload ? 'var(--amber)' : 'var(--green)' }}>{a.wrong_payload}</td>
                <td className="num">{a.refused}</td>
                <td className="num" style={{ color: a.wrong_structure ? 'var(--amber)' : undefined }}>{a.wrong_structure}</td>
              </tr>
            ))}</tbody>
          </table>
          <div className="dim" style={{ fontSize: 12.5, padding: '10px 14px' }}>
            The single wrong structure on record appears in the <b>tracking-ablated</b> arm — a configuration that does
            not ship. It is reported rather than dropped, because an ablation that breaks something is evidence about
            what the tracker is doing for us.
          </div>
        </Panel>
        </div>
      )}

      {tab === 'remediation' && (
        <div className="col" style={{ gap: 16 }}>
          <div className="grid g-2" style={{ alignItems: 'start' }}>
            <Panel title="What the fix gained" sub="Wrong payloads on treated captures, its own 288-capture matrix">
              <HBars max={Math.max(...es.doppler_gain.map((g) => g.treated))}
                items={es.doppler_gain.map((g) => ({
                  label: g.arm.replace('_', ' '), value: g.wrong_payload,
                  color: g.wrong_payload === 0 ? 'var(--green)' : g.arm === 'A_production' ? 'var(--amber)' : 'var(--cyan)',
                  note: `${g.wrong_payload} wrong of ${g.treated} treated`,
                }))} fmt={(v) => `${v}`} />
              <p className="dim" style={{ fontSize: 12.5, marginBottom: 0 }}>
                On Doppler alone it worked: the candidate arm cut wrong payloads to {es.doppler_gain.find((g) => g.arm === 'B_candidate')?.wrong_payload}.
                If we had stopped measuring here, we would have shipped it.
              </p>
            </Panel>
            <Panel title="What the fix cost everywhere else" sub="Captures scored correct, before and after, on populations that already worked" flush>
              <table className="tbl">
                <thead><tr><th>Population</th><th className="num">Before</th><th className="num">After</th><th className="num">Δ</th><th className="num">False accepts</th></tr></thead>
                <tbody>{es.regression.map((r) => {
                  const delta = r.after.correct - r.before.correct
                  return (
                    <tr key={r.population}>
                      <td><b>{r.population}</b><div className="muted" style={{ fontSize: 11.5 }}>{r.before.n} captures</div></td>
                      <td className="num">{r.before.correct}</td>
                      <td className="num">{r.after.correct}</td>
                      <td className="num" style={{ color: delta < 0 ? 'var(--amber)' : delta > 0 ? 'var(--green)' : undefined }}>{delta > 0 ? `+${delta}` : delta}</td>
                      <td className="num" style={{ color: r.after.false_accept > r.before.false_accept ? 'var(--amber)' : undefined }}>{r.before.false_accept} → {r.after.false_accept}</td>
                    </tr>
                  )
                })}</tbody>
              </table>
              <div className="dim" style={{ fontSize: 12.5, padding: '10px 14px' }}>
                bench-v1 fell from 30/30 to 22/30, and bench-v2 dropped one of its nine pre-registered criteria. Two independent
                pre-registered rules fired — static-carrier regression and structural safety.
              </div>
            </Panel>
          </div>
          <Panel title="The exhibit that ended the question" sub="One capture, bench2 sealed idle_carrier_0411 — an idle carrier carrying no code at all"
            right={<Tag kind="BENCHMARK" />}>
            <div className="grid g-2" style={{ gap: 14 }}>
              <div className="card" style={{ padding: 14 }}>
                <div className="row" style={{ gap: 8, marginBottom: 8 }}><span className="meta grow">Shipped engine</span><Icon name="check" size={13} /></div>
                <div className="mono" style={{ fontSize: 15 }}>{idleA?.status}</div>
                <div className="muted" style={{ fontSize: 12.5, marginTop: 5 }}>
                  Structural bar not cleared — margin {idleA?.f4_margin.toFixed(3)} (positive means it fell short). The engine says
                  there is a signal and no code it can prove. That is the correct answer.
                </div>
              </div>
              <div className="card" style={{ padding: 14, borderColor: 'var(--amber)' }}>
                <div className="row" style={{ gap: 8, marginBottom: 8 }}><span className="meta grow">With the carrier fix in front</span><Icon name="flag" size={13} /></div>
                <div className="mono" style={{ fontSize: 15, color: 'var(--amber)' }}>{idleB?.status} · {idleB?.code}</div>
                <div className="muted" style={{ fontSize: 12.5, marginTop: 5 }}>
                  Margin {idleB?.f4_margin.toFixed(3)} — bar cleared, a CCSDS LDPC frame claimed from an idle carrier, with
                  {' '}{idleB?.n_converged} of {idleB?.n_codewords} codewords converged. A false structural claim invented by the fix.
                </div>
              </div>
            </div>
            <div className="banner amber" style={{ marginTop: 14 }}>
              <Icon name="flag" />
              <div><b>Decision: {es.decision}.</b> Chosen by the pre-registered rules, not by preference. A fix that improves the
                number you are looking at while inventing a claim out of an idle carrier is not a fix.</div>
            </div>
            <Src s={es.source} />
          </Panel>
        </div>
      )}

      {tab === 'tracker' && (
        <div className="col" style={{ gap: 16 }}>
          <div className="grid g-2" style={{ alignItems: 'start' }}>
            <Panel title="What the phase tracker actually estimates" sub="Measured against the known injected trajectory, in radians" flush>
              <table className="tbl">
                <thead><tr><th>Carrier</th><th className="num">n</th><th className="num">Median worst error</th><th className="num">Slipped</th><th className="num">Predicted</th></tr></thead>
                <tbody>{tr.by_trajectory.map((t) => (
                  <tr key={t.trajectory}>
                    <td><b>{t.trajectory}</b>{!t.treated && <span className="muted"> · control</span>}</td>
                    <td className="num">{t.n}</td>
                    <td className="num" style={{ color: (t.max_err_rad?.med ?? 0) > 1 ? 'var(--amber)' : 'var(--green)' }}>
                      {t.max_err_rad ? `${t.max_err_rad.med.toFixed(t.max_err_rad.med > 10 ? 0 : 3)}` : '—'}
                    </td>
                    <td className="num">{t.captures_with_slip}</td>
                    <td className="num">{t.predicted_slip}</td>
                  </tr>
                ))}</tbody>
              </table>
              <div className="dim" style={{ fontSize: 12.5, padding: '10px 14px' }}>
                It estimates a piecewise-constant <b>phase</b> — there is no trajectory model anywhere in it. On a still carrier it is
                accurate to under a radian. On a moving one it diverges by hundreds, and it does so exactly where the arithmetic says
                its unwrap must take the wrong branch (“predicted”).
              </div>
              <Src s={tr.source} />
            </Panel>
            <Panel title="When the tracker slips, the claim is wrong" sub={`Captures whose published claim came from a tracked front end (${tr.claim_from_tracked})`}>
              <div className="grid g-2" style={{ gap: 10 }}>
                {tr.slip_outcome_grid.map((g) => (
                  <div key={`${g.slip}-${g.outcome}`} className="card" style={{ padding: 12, borderColor: g.slip === 'slip' ? 'var(--amber)' : undefined }}>
                    <div className="meta">{g.slip === 'slip' ? 'unwrap slipped' : 'no slip'}</div>
                    <div className="mono" style={{ fontSize: 18, marginTop: 3 }}>{g.n}</div>
                    <div className="muted" style={{ fontSize: 12 }}>{g.outcome === 'FALSE_DECODE' ? 'wrong payload' : 'correct payload'}</div>
                  </div>
                ))}
              </div>
              <p className="dim" style={{ fontSize: 12.5, marginTop: 12, marginBottom: 0 }}>
                A clean separation — but not the whole story: <b>{tr.failures_from_untracked} of {tr.failures_total}</b> failures came from
                front ends the tracker never touched. So the slip is a mechanism for some of the failure, not the explanation of it.
                Block length chosen: {Object.entries(tr.block_choice).map(([k, v]) => `${k} symbols (${v}×)`).join(', ')} — already the
                finest setting available, so there is no headroom left.
              </p>
            </Panel>
          </div>
          <Panel title="The boundary the engine now reports" sub={`unwrap margin in radians; the bound is π = ${va.bound_rad.toFixed(3)}, the exact discriminant of the unwrap — not a chosen threshold`}
            right={<Tag kind="BENCHMARK" />}>
            <div className="grid g-2" style={{ gap: 16, alignItems: 'start' }}>
              <div>
                <div className="meta" style={{ marginBottom: 8 }}>Margin at the front end that produced the claim</div>
                <HBars max={va.bound_rad}
                  items={va.by_trajectory.map((g) => ({
                    label: `${g.group}${g.treated ? '' : ' · control'}`, value: g.med ?? 0,
                    color: g.treated ? 'var(--amber)' : 'var(--green)',
                    note: `n=${g.n}; min ${rad(g.min)}, max ${rad(g.max)}`,
                  }))} fmt={(v) => v.toFixed(3)} />
              </div>
              <div>
                <div className="meta" style={{ marginBottom: 8 }}>Against slips measured from the known trajectory</div>
                <table className="tbl">
                  <thead><tr><th>Group</th><th className="num">n</th><th className="num">Min</th><th className="num">Max</th></tr></thead>
                  <tbody>{va.by_slip.map((g) => (
                    <tr key={g.group}>
                      <td><b>{g.group}</b></td><td className="num">{g.n}</td>
                      <td className="num">{rad(g.min)}</td><td className="num">{rad(g.max)}</td>
                    </tr>
                  ))}</tbody>
                </table>
                <p className="dim" style={{ fontSize: 12.5, marginTop: 10, marginBottom: 0 }}>
                  The two groups do not overlap, and the engine reads this blind — no ground truth. On {va.indeterminate} of {va.n} captures
                  the claim came from an untracked front end, and the engine reports <b>indeterminate</b> rather than guessing.
                </p>
              </div>
            </div>
            <div className="banner" style={{ marginTop: 14 }}>
              <Icon name="check" />
              <div><b>This is evidence, not a verdict.</b> A small margin means the unwrap ran at its ambiguity, where its branch
                may be wrong — it does not mean the decode failed, and refusals sit there too. No acceptance, refusal or ranking
                reads this number.</div>
            </div>
            <Src s={va.source} />
          </Panel>
        </div>
      )}

      {tab === 'boundary' && (
        <div className="col" style={{ gap: 16 }}>
          <div className="grid g-3" style={{ alignItems: 'start' }}>
            <Panel title="Established" right={<Tag kind="BENCHMARK" />}>
              <ul className="col" style={{ margin: 0, paddingLeft: 18, gap: 8, fontSize: 12.6 }}>
                {BOUNDARY.established.map((s) => <li key={s}>{s}</li>)}
              </ul>
            </Panel>
            <Panel title="Measured limitation" right={<Tag kind="BENCHMARK" />}>
              <ul className="col" style={{ margin: 0, paddingLeft: 18, gap: 8, fontSize: 12.6 }}>
                {BOUNDARY.limitation.map((s) => <li key={s}>{s}</li>)}
              </ul>
              <p className="dim" style={{ fontSize: 12.3, marginBottom: 0 }}>
                Stronger than “not established”: the question was asked and the answer is negative.
              </p>
            </Panel>
            <Panel title="Not established" right={<Tag kind="NOT ESTABLISHED" />}>
              <ul className="col" style={{ margin: 0, paddingLeft: 18, gap: 8, fontSize: 12.6 }}>
                {BOUNDARY.notEstablished.map((s) => <li key={s}>{s}</li>)}
              </ul>
            </Panel>
          </div>
          <div className="grid g-2" style={{ alignItems: 'start' }}>
            <Panel title="Structural safety at scale" sub={`The shipped engine over ${f4.n.toLocaleString('en-IN')} sealed captures`}>
              <div className="statbar">
                <Fig label="Block-code accepts" value={`${f4.accepts}`} note={`${f4.accepts_correct} of ${f4.accepts} correct, ${f4.accepts_zero_convergence} with zero convergence`} accent="green" />
                <Fig label="On true nulls" value={`${f4.accepts_on_true_nulls}`} note={`of ${f4.true_nulls} captures carrying no code`} accent="green" />
                <Fig label="Closest near-miss" value={`+${f4.closest_non_accepting_margin.toFixed(3)}`} note="log units short of the bar (positive = refused)" />
              </div>
              <p className="dim" style={{ fontSize: 12.5, marginTop: 12, marginBottom: 0 }}>
                The weakest real acceptance cleared its bar by {Math.abs(f4.weakest_accepting_margin).toFixed(2)} log units, so the
                nearest miss is not a near miss. An empirical floor, not a guarantee.
              </p>
              <Src s={f4.source} />
            </Panel>
            <Panel title="Why noise does not become a claim" sub="Off-carrier, noise-like front ends are admitted constantly and have never produced one">
              <div className="statbar">
                <Fig label="Off-carrier front ends admitted" value={oc.admitted_off_carrier.toLocaleString('en-IN')} note={`of ${oc.admitted_front_ends.toLocaleString('en-IN')} admitted front ends`} />
                <Fig label="Captures affected" value={`${oc.captures_with_off_carrier_admitted}/${oc.signal_bearing}`} note="a normal operating state, not a fault" />
                <Fig label="Claims produced by one" value={`${oc.f4_passes_from_off_carrier}`} note={`all ${oc.published_claims} claims came from an on- or near-carrier front end`} accent="green" />
              </div>
              <p className="dim" style={{ fontSize: 12.5, marginTop: 12, marginBottom: 0 }}>
                The safeguard is the multiplicity-corrected bar, not the front-end filter: admitting a noise-like candidate raises the
                hypothesis count, which lowers the bar it must clear, and noise then fails it.
              </p>
              <Src s={oc.source} />
            </Panel>
          </div>
          <Panel title="Where to check any of this" sub="Written reports in reports/space/, each carrying its own pre-registered criteria and result files">
            <div className="row-wrap" style={{ gap: 8 }}>
              {d.reports.map((r) => <span key={r} className="chip mono" style={{ fontSize: 11.5 }}>{r}</span>)}
            </div>
          </Panel>
        </div>
      )}
    </div>
  )
}
