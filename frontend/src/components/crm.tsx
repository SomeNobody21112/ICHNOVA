import { useCallback, useEffect, useState } from 'react'
import { apiJson } from '../lib/api'
import { useApp, useCan, whyNot } from '../lib/store'
import type { EvidencePack } from '../lib/types'
import { Icon, Panel } from './ui'

/** Mirrors server/crm.py. A queued case is local until Salesforce returns a record id. */
export interface OutboxItem {
  id: string
  kind: string
  state: 'PENDING' | 'SENT' | 'DEAD'
  attempts: number
  created_utc: string
  next_attempt_utc: string
  sent_utc: string | null
  remote_id: string | null
  last_error: string | null
}

export interface CrmStatus {
  crm: { state: 'CONFIGURED' | 'NOT CONFIGURED'; login_url: string; object: string; missing_env: string[]; detail: string }
  outbox: { pending: number; sent: number; dead: number; total: number }
  items: OutboxItem[]
  never_synchronised: string[]
}

interface FlushReport { sent: number; retry: number; dead: number; attempted: number; detail: string }

/** Raise a case from a signal record. Writes locally; delivery is a separate, visible step. */
export function RaiseCase({ pack, station }: { pack: EvidencePack; station?: string }) {
  const { session } = useApp()
  const mayReview = useCan('review')
  const cannotReview = whyNot(session?.authRole, 'review')
  const [state, setState] = useState<{ busy: boolean; message: string | null; tone: 'ok' | 'warn' }>(
    { busy: false, message: null, tone: 'ok' })

  const raiseCase = async () => {
    setState({ busy: true, message: null, tone: 'ok' })
    try {
      const body = {
        // Only the decision travels. The pack's views and payload bits stay on this machine, and
        // the server rebuilds the record from its own field list regardless of what is sent.
        pack: {
          id: pack.id, analysed_at: pack.analysed_at, source: { kind: pack.source.kind },
          result: {
            status: pack.result.status, code: pack.result.code, modulation: pack.result.modulation,
            sps: pack.result.sps, interleaver: pack.result.interleaver,
          },
          accept: {
            log10_p: pack.accept.log10_p, log10_threshold: pack.accept.log10_threshold,
            n_hypotheses: pack.accept.n_hypotheses,
          },
          receipt: pack.receipt ? { hash: pack.receipt.hash, capture: { sha256: pack.receipt.capture.sha256 } } : undefined,
          data_quality: pack.data_quality ? { status: pack.data_quality.status } : undefined,
          sufficiency: pack.sufficiency ? { verdict: pack.sufficiency.verdict } : undefined,
        },
        summary: `${pack.result.status} on ${pack.id}`,
        station,
      }
      const r = await apiJson<{ queued: boolean; crm: CrmStatus['crm']; outbox: CrmStatus['outbox'] }>(
        '/api/crm/queue', { method: 'POST', body: JSON.stringify(body) })
      const where = r.crm.state === 'CONFIGURED'
        ? 'queued for Salesforce; delivery is reported on the System page.'
        : 'queued locally. Salesforce is not configured here, so nothing has been sent.'
      setState({
        busy: false, tone: r.crm.state === 'CONFIGURED' ? 'ok' : 'warn',
        message: `${r.queued ? 'Case raised and' : 'Already raised;'} ${where} ${r.outbox.pending} pending.`,
      })
    } catch (e) {
      setState({ busy: false, tone: 'warn', message: e instanceof Error ? e.message : 'Could not reach the server.' })
    }
  }

  return (
    <>
      <button className="btn btn-sm" onClick={() => void raiseCase()} disabled={state.busy || !pack.receipt || !mayReview}
        data-loading={state.busy}
        title={!mayReview ? cannotReview : pack.receipt ? undefined : 'This record has no receipt to reference'}>
        <Icon name="flag" size={13} /> {state.busy ? 'Raising…' : 'Raise case'}
      </button>
      {state.message && (
        <span className="muted" style={{ fontSize: 12, color: state.tone === 'warn' ? 'var(--amber)' : undefined }}>
          {state.message}
        </span>
      )}
    </>
  )
}

/** The queue itself: what is waiting, what was delivered, and what needs a human. */
export function CaseOutbox() {
  const { session } = useApp()
  const mayReview = useCan('review')
  const cannotReview = whyNot(session?.authRole, 'review')
  const [data, setData] = useState<CrmStatus | null>(null)
  const [report, setReport] = useState<FlushReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try { setData(await apiJson<CrmStatus>('/api/crm/status')); setError(null) } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not reach the analysis server.')
    }
  }, [])
  useEffect(() => { void load() }, [load])

  const deliver = async () => {
    setBusy(true); setReport(null)
    try {
      setReport(await apiJson<FlushReport>('/api/crm/flush', { method: 'POST' }))
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Delivery could not be attempted.')
    } finally { setBusy(false) }
  }

  const configured = data?.crm.state === 'CONFIGURED'
  return (
    <Panel
      title="Case hand-off"
      sub="Cases are written here first, so a flat network never loses one. Delivery is a separate step."
      right={
        <button className="btn btn-sm" onClick={() => void deliver()} disabled={busy || !data?.outbox.pending || !mayReview}
          data-loading={busy} title={mayReview ? undefined : cannotReview}>{busy ? 'Attempting…' : 'Attempt delivery'}</button>
      }
    >
      {error && <div className="banner amber" role="alert"><Icon name="info" /><span>{error}</span></div>}
      {!data && !error && <div className="empty">Reading the outbox…</div>}
      {data && (
        <div className="col" style={{ gap: 12 }}>
          <div className="statbar">
            <div><span className="kpi-label">Salesforce</span><b className={configured ? 'ok' : 'warn'}>{data.crm.state}</b></div>
            <div><span className="kpi-label">Pending</span><b className="mono">{data.outbox.pending}</b></div>
            <div><span className="kpi-label">Delivered</span><b className="mono">{data.outbox.sent}</b></div>
            <div><span className="kpi-label">Dead letter</span><b className="mono">{data.outbox.dead}</b></div>
          </div>
          <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>
            {data.crm.detail}
            {data.crm.missing_env.length > 0 && <> Set {data.crm.missing_env.join(', ')} in the environment to enable it.</>}
          </p>
          {report && <div className="banner muted"><Icon name="info" /><span>{report.detail}</span></div>}
          {data.items.length > 0 ? (
            <div className="list">
              {data.items.slice(0, 8).map((i) => (
                <div key={i.id} className="list-item" style={{ gridTemplateColumns: '90px minmax(0, 1fr) auto', cursor: 'default' }}>
                  <span className={`mono ${i.state === 'SENT' ? 'ok' : i.state === 'DEAD' ? 'no' : 'warn'}`} style={{ fontSize: 12 }}>{i.state}</span>
                  <span className="muted" style={{ fontSize: 12.5 }}>
                    {i.remote_id ? `Salesforce ${i.remote_id}` : i.last_error ?? `queued ${i.created_utc}`}
                  </span>
                  <span className="mono muted" style={{ fontSize: 11.5 }}>{i.attempts} attempt{i.attempts === 1 ? '' : 's'}</span>
                </div>
              ))}
            </div>
          ) : <div className="empty">No cases have been raised on this workstation.</div>}
          <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>
            A case carries the decision, the statistics behind it and the receipt hash. Captures,
            audio and the analyst views are never synchronised: exporting a recording is a separate,
            deliberate action.
          </p>
        </div>
      )}
    </Panel>
  )
}
