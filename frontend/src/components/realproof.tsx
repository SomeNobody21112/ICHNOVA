import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import type { ReplayIndexEntry } from '../lib/live'
import { Stamp } from './ui'

const FLAG: Record<string, string> = { India: 'IN', 'United States': 'US', Germany: 'DE', 'United Kingdom': 'GB', Japan: 'JP', Canada: 'CA' }

function headline(e: ReplayIndexEntry) {
  const a = e.answer
  if (a.receiver === 'timecode' && a.status === 'DECODED') {
    const m = /(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(a.summary ?? '')
    return { big: m ? `${m[2]} UTC` : 'decoded', small: m ? `${m[1]} · ${a.protocol} time code` : a.protocol ?? '' }
  }
  if (a.receiver === 'fsk') {
    const line = (a.summary ?? '').split('\n').find((l) => /DE\s+\w+/.test(l)) ?? (a.summary ?? '').split('\n')[1] ?? ''
    return { big: `“${line.trim().slice(0, 28)}”`, small: `${a.protocol}` }
  }
  if (a.receiver === 'census') return { big: (a.summary ?? '').split(';')[1]?.trim().split(' ')[0] ?? '—', small: 'AIR carriers matched to the official list' }
  if (a.receiver === 'timecode') return { big: 'time refused', small: 'station detected, digits not established' }
  if (a.receiver === 'am') return { big: 'AM carrier', small: (a.summary ?? '').split(',')[1]?.trim() ?? '' }
  return { big: a.status, small: a.summary ?? '' }
}

/** Cards summarising real transmissions the engine has analysed; each opens its replay in the Live Monitor. */
export function RealProof({ compact }: { compact?: boolean }) {
  const [items, setItems] = useState<ReplayIndexEntry[]>([])
  useEffect(() => { fetch('/live/index.json').then((r) => r.json()).then(setItems).catch(() => setItems([])) }, [])
  const order = ['AIR-MW', 'JJY', 'DCF77', 'MSF', 'WWV', 'DDH47', 'WWVB']
  const sorted = [...items].sort((x, y) => order.indexOf(x.station_key) - order.indexOf(y.station_key) || (x.mode === 'band' ? -1 : 1))
  return (
    <div className={`proof${compact ? ' compact' : ''}`}>
      {sorted.map((e, i) => {
        const h = headline(e)
        const v = e.answer.verification
        return (
          <motion.div key={e.id} initial={{ opacity: 0, y: 10 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.06 }}>
            <Link to={`/app/monitor?rec=${e.id}`} className="proof-card">
              <div className="row" style={{ gap: 8, minWidth: 0 }}>
                <span className="flag mono">{FLAG[e.country] ?? '··'}</span>
                <b className="proof-name">{e.mode === 'band' ? 'AIR medium-wave band' : e.station_key === 'AIR-MW' ? 'AIR Chennai 720 kHz' : e.station.replace(' (40 kHz)', ' 40 kHz')}</b>
              </div>
              <div><Stamp status={e.answer.status} /></div>
              <div className="proof-big mono">{h.big}</div>
              <div className="proof-small">{h.small}</div>
              <div className="proof-foot mono">
                <span>{e.operator.split(' — ')[0]}</span>
                {v ? <span className="ok">GPS check {v.arrival_minus_decoded_ms > 0 ? '+' : ''}{v.arrival_minus_decoded_ms.toFixed(1)} ms</span> : <span>{e.receiver}</span>}
              </div>
            </Link>
          </motion.div>
        )
      })}
    </div>
  )
}
