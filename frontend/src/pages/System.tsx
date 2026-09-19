import { Link } from 'react-router-dom'
import { CaseOutbox } from '../components/crm'
import { SignalSources } from '../components/sources'
import { Icon, Panel, Tag } from '../components/ui'
import { fmtDateTime } from '../lib/format'
import { STATIONS } from '../lib/sim'
import { useApp, usePack } from '../lib/store'
import { COVERAGE } from './Landing'

const EDGE = [
  { icon: 'raw', t: 'Capture', d: 'SDR front end writes .IQ / .wav with sample rate and tuning metadata' },
  { icon: 'detect', t: 'Detection & characterisation', d: 'Carrier lines, symbol rate, modulation; runs on the station computer' },
  { icon: 'fec', t: 'Blind decode', d: 'Code × interleaver search with exact parity tests' },
  { icon: 'stats', t: 'Evidence pack', d: 'Decision + statistics + views, ~1 MB JSON per capture' },
]
const CENTRAL = [
  { icon: 'layers', t: 'Signal library', d: 'Evidence records, genome fingerprints, review state' },
  { icon: 'link', t: 'Correlation', d: 'Recurrence across captures, stations and zones' },
  { icon: 'flag', t: 'Incidents & review', d: 'Analyst queue, notes, audit trail' },
  { icon: 'map', t: 'Regional & national views', d: 'Aggregates only: no waveforms leave the edge unless requested' },
]

function Flow({ items, label, tone }: { items: typeof EDGE; label: string; tone: string }) {
  return (
    <div className="card col" style={{ gap: 8, borderColor: tone }}>
      <div className="section-label" style={{ color: tone }}>{label}</div>
      {items.map((s, i) => (
        <div key={s.t} className="row" style={{ alignItems: 'flex-start', gap: 10 }}>
          <span className="mono muted" style={{ width: 16 }}>{i + 1}</span><Icon name={s.icon} size={16} />
          <div><b style={{ fontSize: 13 }}>{s.t}</b><div className="muted" style={{ fontSize: 12 }}>{s.d}</div></div>
        </div>
      ))}
    </div>
  )
}

export default function System() {
  const { engine, audit } = useApp()
  const { pack } = usePack('BENCH-QPSK-K7')
  const cfg = pack?.engine
  return (
    <div className="page">
      <div className="page-head">
        <div className="grow">
          <div className="section-label">Platform</div>
          <h1 className="page-title">System</h1>
          <div className="page-sub">Architecture, engine configuration, problem-statement coverage, data quality and the complete audit trail.</div>
        </div>
        <span className="row"><i className={`dot ${engine.online ? 'dot-ok' : 'dot-warn'}`} />{engine.online ? `Engine online · v${engine.version} · ${engine.commit}` : 'Engine offline (replaying stored evidence)'}</span>
      </div>

      <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1.2fr) minmax(0, 0.8fr)', alignItems: 'start' }}>
        <Panel title="Data flow" sub="Heavy DSP runs at the edge; the centre receives evidence, not raw spectrum">
          <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1fr) auto minmax(0, 1fr)', alignItems: 'stretch' }}>
            <Flow items={EDGE} label="Edge · monitoring station" tone="var(--accent)" />
            <div className="col" style={{ alignItems: 'center', justifyContent: 'center', gap: 4 }}><Icon name="chevron" size={22} /><span className="mono muted" style={{ fontSize: 11 }}>evidence<br />packs</span></div>
            <Flow items={CENTRAL} label="Central · regional / national" tone="var(--violet)" />
          </div>
        </Panel>
        <Panel title="Engine configuration" right={<Tag kind="BENCHMARK">From evidence pack</Tag>}>
          {cfg ? (
            <dl className="kv">
              <dt>Version / commit</dt><dd>{cfg.version} · {cfg.commit}</dd>
              <dt>Significance α</dt><dd>{cfg.alpha} (Bonferroni)</dd>
              <dt>Samples / symbol search</dt><dd>{cfg.sps_range.join('–')}</dd>
              <dt>Max carrier offset</dt><dd>±{cfg.cfo_max} cyc/sample</dd>
              <dt>Receive roll-off</dt><dd>{cfg.rx_beta}</dd>
              <dt>Modulations</dt><dd>{cfg.modulations.join(', ')}</dd>
              <dt>Code catalogue</dt><dd>{cfg.codes.map((c) => c.split('_')[1].toUpperCase()).join(', ')}</dd>
              <dt>Interleaver domain</dt><dd>{cfg.interleaver_domain}</dd>
              <dt>Block-length tolerance</dt><dd>{cfg.bl_delta_symbols} symbols</dd>
              <dt>Path-metric floor</dt><dd>{cfg.pm_floor}</dd>
              <dt>Acceptance search depth</dt><dd>{cfg.accept_search}</dd>
            </dl>
          ) : <div className="muted">Loading…</div>}
        </Panel>
      </div>

      <div className="grid g-2" style={{ marginTop: 14, alignItems: 'start' }}>
        <Panel title="Problem statement SIH26147 · coverage" flush>
          <table className="tbl"><tbody>{COVERAGE.map((c) => (
            <tr key={c.req}><td>{c.req}<div className="muted" style={{ fontSize: 11.5 }}>{c.detail}</div></td>
              <td style={{ textAlign: 'right' }}>{c.status === 'ESTABLISHED' ? <span className="tag tag-LIVE">Established</span> : <Tag kind={c.status} />}</td></tr>
          ))}</tbody></table>
        </Panel>
        <div className="col" style={{ gap: 14 }}>
          <Panel title="Adaptive analysis" right={<Tag kind="NOT ESTABLISHED">Research module — not enabled</Tag>}>
            <div className="banner muted"><Icon name="cpu" /><div>
              <b>Decode → measure residual errors → refine timing / carrier / phase → re-decode.</b>
              <div className="dim" style={{ marginTop: 4 }}>Code-aided refinement could lift low-SNR recall (today K=7 is 3/34 correct at 3 dB Es/N0). It stays disabled until an experiment shows it does not raise false accepts. See <Link to="/app/lab">Experiment Lab</Link>.</div>
            </div></div>
          </Panel>
          <Panel title="Station data quality" flush right={<Tag kind="SIMULATED" />}>
            <table className="tbl"><thead><tr><th>Station</th><th>Receiver</th><th>Clock</th><th>Bands</th></tr></thead>
              <tbody>{STATIONS.map((s) => (
                <tr key={s.id}><td>{s.id} · {s.name}</td><td><span className="row"><i className={`dot ${s.health === 'NOMINAL' ? 'dot-ok' : 'dot-warn'}`} />{s.health}</span></td>
                  <td style={{ color: s.clock === 'DRIFT' ? 'var(--amber)' : undefined }}>{s.clock}</td><td className="mono">{s.bands.join(' ')}</td></tr>
              ))}</tbody></table>
          </Panel>
        </div>
      </div>

      <div className="grid g-2" style={{ marginTop: 14, alignItems: 'start' }}>
        <SignalSources />
        <CaseOutbox />
      </div>

      <Panel title="Audit trail" sub="Every sign-in, analysis, review and export on this workstation" style={{ marginTop: 14 }} flush right={<span className="muted mono" style={{ fontSize: 11 }}>{audit.length} events · stored locally</span>}>
        {audit.length ? (
          <table className="tbl"><thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Subject</th><th>Detail</th></tr></thead>
            <tbody>{audit.slice(0, 100).map((e, i) => <tr key={i}><td className="mono">{fmtDateTime(e.t)}</td><td>{e.actor}</td><td>{e.action}</td><td className="mono">{e.subject}</td><td className="muted">{e.detail}</td></tr>)}</tbody></table>
        ) : <div className="empty">No events yet.</div>}
      </Panel>
    </div>
  )
}
