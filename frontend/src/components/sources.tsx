import { useCallback, useEffect, useState } from 'react'
import { apiJson } from '../lib/api'
import { Icon, Panel, Tag } from './ui'

/** Mirrors server/sources.py. `feeds` is the honesty label: what a verdict may be built from. */
export interface SourceStatus {
  key: string
  name: string
  kind: string
  operator: string
  feeds: 'ENGINE' | 'REFERENCE ONLY' | 'METADATA ONLY'
  licence: string
  licence_note: string
  references: { title: string; url: string }[]
  needs_network: boolean
  health: {
    state: 'AVAILABLE' | 'DEGRADED' | 'UNAVAILABLE' | 'NOT CONFIGURED'
    detail: string
    checked_utc: string
    last_data_utc: string | null
    age_s: number | null
  }
}

const STATE_TONE: Record<SourceStatus['health']['state'], string> = {
  AVAILABLE: 'dot-ok', DEGRADED: 'dot-warn', UNAVAILABLE: 'dot-bad', 'NOT CONFIGURED': 'dot-off',
}

/** "Last received" in the units an operator reads at a glance. Never received and received-at-an-
 *  unreadable-time are different facts, so they read differently. */
function ago(when: string | null, seconds: number | null): string {
  if (!when) return 'never on this machine'
  if (seconds == null) return `at ${when}`
  if (seconds < 90) return `${seconds} seconds ago`
  if (seconds < 5400) return `${Math.round(seconds / 60)} minutes ago`
  if (seconds < 172800) return `${Math.round(seconds / 3600)} hours ago`
  return `${Math.round(seconds / 86400)} days ago`
}

export function SignalSources() {
  const [rows, setRows] = useState<SourceStatus[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async (network: boolean) => {
    setBusy(true); setError(null)
    try {
      const r = await apiJson<{ sources: SourceStatus[] }>(`/api/sources?network=${network ? 1 : 0}`)
      setRows(r.sources)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not reach the analysis server.')
      setRows(null)
    } finally { setBusy(false) }
  }, [])

  // Offline first, so the panel is populated immediately; the network check is a deliberate action.
  useEffect(() => { void load(false) }, [load])

  return (
    <Panel
      title="Signal sources"
      sub="Where data may come from, what may be done with it, and whether it is reachable now"
      right={
        <button className="btn btn-sm" onClick={() => void load(true)} disabled={busy} data-loading={busy}>
          {busy ? 'Checking…' : 'Check now'}
        </button>
      }
    >
      {error && <div className="banner amber" role="alert"><Icon name="info" /><span>{error}</span></div>}
      {!rows && !error && <div className="empty">Reading the source registry…</div>}
      {rows && (
        <div className="col" style={{ gap: 10 }}>
          {rows.map((s) => (
            <div key={s.key} className="card col" style={{ gap: 6 }}>
              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
                <b>{s.name}</b>
                <Tag kind={s.feeds === 'ENGINE' ? 'LIVE' : 'NOT ESTABLISHED'}>{s.feeds}</Tag>
              </div>
              <div className="row" style={{ gap: 8, alignItems: 'center' }}>
                <i className={`dot ${STATE_TONE[s.health.state]}`} />
                <span className="mono" style={{ fontSize: 12 }}>{s.health.state}</span>
                <span className="muted" style={{ fontSize: 12.5 }}>{s.health.detail}</span>
              </div>
              <div className="col" style={{ gap: 4 }}>
                <div className="muted" style={{ fontSize: 12.5 }}>
                  <b style={{ fontWeight: 500 }}>{s.operator}</b> · {s.licence} · last received {ago(s.health.last_data_utc, s.health.age_s)}
                </div>
                <div className="muted" style={{ fontSize: 12.5 }}>{s.licence_note}</div>
              </div>
              {s.references.length > 0 && (
                <div className="row" style={{ gap: 10, flexWrap: 'wrap' }}>
                  {s.references.slice(0, 3).map((r) => (
                    <a key={r.url} href={r.url} target="_blank" rel="noreferrer noopener"
                      className="muted" style={{ fontSize: 12 }}>{r.title}</a>
                  ))}
                </div>
              )}
            </div>
          ))}
          <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>
            Only <b>ENGINE</b> sources can produce a verdict. <b>REFERENCE ONLY</b> data is used to
            check a decode the engine already reached, never to reach one, and <b>METADATA ONLY</b>
            {' '}sources carry no samples at all. Nothing here is a restricted, encrypted or private
            service: every source is publicly offered and openly documented.
          </p>
        </div>
      )}
    </Panel>
  )
}
