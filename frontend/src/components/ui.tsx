import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { STATUS_LABEL } from '../lib/format'
import type { Provenance, Status } from '../lib/types'

const P = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.6, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }

const ICONS: Record<string, ReactNode> = {
  command: <><rect x="3" y="3" width="7" height="9" rx="1" {...P} /><rect x="14" y="3" width="7" height="5" rx="1" {...P} /><rect x="14" y="12" width="7" height="9" rx="1" {...P} /><rect x="3" y="16" width="7" height="5" rx="1" {...P} /></>,
  monitor: <><path d="M3 17c2 0 2-10 4.5-10S10 19 12.5 19 15 5 17.5 5 20 13 21 13" {...P} /></>,
  analysis: <><circle cx="11" cy="11" r="6.5" {...P} /><path d="M16 16l5 5M8 11h1.5l1-3 1.5 6 1-3H15" {...P} /></>,
  signals: <><path d="M4 12a8 8 0 0 1 16 0M7.5 12a4.5 4.5 0 0 1 9 0" {...P} /><circle cx="12" cy="12" r="1.6" fill="currentColor" /><path d="M12 14v7" {...P} /></>,
  review: <><path d="M4 5h16v11H9l-5 4z" {...P} /><path d="M9 10l2 2 4-4" {...P} /></>,
  incidents: <><path d="M12 3l9 16H3z" {...P} /><path d="M12 10v4M12 17v.5" {...P} /></>,
  spectrum: <><path d="M3 20V9M7 20V4M11 20v-9M15 20V7M19 20v-6" {...P} /></>,
  genome: <><circle cx="12" cy="12" r="8.5" {...P} /><path d="M12 3.5v17M3.5 12h17M6 6l12 12M18 6L6 18" {...P} opacity="0.5" /><path d="M12 7l3.5 5-3.5 4.5L8 13z" {...P} /></>,
  intel: <><circle cx="12" cy="12" r="8.5" {...P} /><path d="M3.5 12h17M12 3.5c2.5 2.3 3.6 5.2 3.6 8.5S14.5 18.2 12 20.5C9.5 18.2 8.4 15.3 8.4 12S9.5 5.8 12 3.5z" {...P} /></>,
  reports: <><path d="M6 3h9l4 4v14H6z" {...P} /><path d="M9 11h7M9 15h7M9 7h4" {...P} /></>,
  system: <><circle cx="12" cy="12" r="3" {...P} /><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1" {...P} /></>,
  lab: <><path d="M9 3h6M10 3v6L4.5 19a1.5 1.5 0 0 0 1.3 2h12.4a1.5 1.5 0 0 0 1.3-2L14 9V3" {...P} /><path d="M7 15h10" {...P} /></>,
  check: <path d="M4 12.5l5 5L20 6.5" {...P} strokeWidth={2} />,
  cross: <path d="M6 6l12 12M18 6L6 18" {...P} strokeWidth={2} />,
  dash: <path d="M6 12h12" {...P} strokeWidth={2} />,
  chevron: <path d="M9 6l6 6-6 6" {...P} />,
  back: <path d="M15 6l-6 6 6 6" {...P} />,
  play: <path d="M8 5v14l11-7z" {...P} />,
  pause: <path d="M8 5v14M16 5v14" {...P} strokeWidth={2.2} />,
  upload: <><path d="M12 16V4M7 9l5-5 5 5" {...P} /><path d="M4 16v4h16v-4" {...P} /></>,
  download: <><path d="M12 4v12M7 11l5 5 5-5" {...P} /><path d="M4 16v4h16v-4" {...P} /></>,
  eye: <><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" {...P} /><circle cx="12" cy="12" r="3" {...P} /></>,
  menu: <path d="M4 7h16M4 12h16M4 17h16" {...P} />,
  logout: <><path d="M14 4h5v16h-5M10 8l-4 4 4 4M6 12h10" {...P} /></>,
  raw: <path d="M3 12h2l1.5-6 2 12 2-9 1.5 5 1.5-3 1.5 4 1.5-6 1.5 3H21" {...P} />,
  detect: <><circle cx="12" cy="12" r="3" {...P} /><path d="M5.6 5.6a9 9 0 0 0 0 12.8M18.4 5.6a9 9 0 0 1 0 12.8" {...P} /></>,
  structure: <><circle cx="7" cy="7" r="2" {...P} /><circle cx="17" cy="7" r="2" {...P} /><circle cx="7" cy="17" r="2" {...P} /><circle cx="17" cy="17" r="2" {...P} /></>,
  fec: <><rect x="3" y="6" width="18" height="12" rx="1.5" {...P} /><path d="M7 10h2v4H7zM11 10h2M11 14h2M15 10h2v4h-2z" {...P} /></>,
  stats: <><path d="M3 20h18" {...P} /><path d="M5 20c3-1 4-14 7-14s4 13 7 14" {...P} /><path d="M15.5 6v14" {...P} strokeDasharray="2 2" /></>,
  decision: <><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" {...P} /><path d="M8.5 12l2.5 2.5 4.5-5" {...P} /></>,
  station: <><path d="M12 10v11M8 21h8" {...P} /><path d="M7.5 6.5a6 6 0 0 1 9 0M5 4a9.5 9.5 0 0 1 14 0" {...P} /><circle cx="12" cy="10" r="1.5" fill="currentColor" /></>,
  link: <><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1" {...P} /><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" {...P} /></>,
  shield: <path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" {...P} />,
  clock: <><circle cx="12" cy="12" r="8.5" {...P} /><path d="M12 7v5l3 2" {...P} /></>,
  info: <><circle cx="12" cy="12" r="8.5" {...P} /><path d="M12 11v5M12 8v.5" {...P} /></>,
  cpu: <><rect x="6" y="6" width="12" height="12" rx="1.5" {...P} /><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4" {...P} /></>,
  layers: <><path d="M12 3l9 5-9 5-9-5z" {...P} /><path d="M3 13l9 5 9-5" {...P} /></>,
  search: <><circle cx="11" cy="11" r="6.5" {...P} /><path d="M16 16l5 5" {...P} /></>,
  map: <><path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2z" {...P} /><path d="M9 4v14M15 6v14" {...P} /></>,
  flag: <><path d="M5 21V4M5 4h11l-2 4 2 4H5" {...P} /></>,
}

export function Icon({ name, size = 18, className }: { name: string; size?: number; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} className={className} aria-hidden="true">
      {ICONS[name] ?? ICONS.info}
    </svg>
  )
}

export function BrandMark({ size = 30 }: { size?: number }) {
  return (
    <svg viewBox="0 0 32 32" width={size} height={size} className="brand-mark" aria-hidden="true">
      <rect width="32" height="32" rx="7" fill="#0f1820" stroke="#1f3242" />
      <circle cx="16" cy="16" r="10.5" fill="none" stroke="#2b4a63" strokeWidth="1.2" strokeDasharray="2 2.2" />
      <path d="M5.5 16c2.2 0 2.9-6 5.2-6s2.9 12 5.3 12 3-12 5.3-12 3 6 5.2 6" fill="none" stroke="#5fd0f0" strokeWidth="1.9" strokeLinecap="round" />
      <circle cx="16" cy="16" r="2" fill="#e9b949" />
    </svg>
  )
}

const TAG_TEXT: Record<Provenance, string> = {
  SIMULATED: 'Simulated', BENCHMARK: 'Benchmark', LIVE: 'Live engine', EXPERIMENTAL: 'Experimental', 'NOT ESTABLISHED': 'Not established',
}
const TAG_TITLE: Record<Provenance, string> = {
  SIMULATED: 'Demonstration data generated for the prototype. Not a measurement.',
  BENCHMARK: 'Measured by the real engine on synthetic benchmark captures.',
  LIVE: 'Produced by the local analysis engine from an operator capture.',
  EXPERIMENTAL: 'Research feature; results are not operationally validated.',
  'NOT ESTABLISHED': 'Capability not implemented or not validated.',
}

export function Tag({ kind, children }: { kind: Provenance; children?: ReactNode }) {
  const cls = kind === 'NOT ESTABLISHED' ? 'tag tag-NOT' : `tag tag-${kind}`
  return <span className={cls} title={TAG_TITLE[kind]}>{children ?? TAG_TEXT[kind]}</span>
}

export function Stamp({ status, size, investigate }: { status: Status; size?: 'lg' | 'xl'; investigate?: boolean }) {
  return (
    <span className="row" style={{ gap: 6 }}>
      <span className={`stamp stamp-${status}${size ? ` stamp-${size}` : ''}`}>{STATUS_LABEL[status]}</span>
      {investigate && <span className={`stamp stamp-INVESTIGATE${size ? ` stamp-${size}` : ''}`}>INVESTIGATE</span>}
    </span>
  )
}

export function Panel({ title, sub, right, children, flush, className, style, id }: {
  title?: ReactNode; sub?: ReactNode; right?: ReactNode; children: ReactNode; flush?: boolean; className?: string
  style?: React.CSSProperties; id?: string
}) {
  return (
    <section className={`panel ${className ?? ''}`} style={style} id={id}>
      {(title || right) && (
        <header className="panel-head">
          <div className="grow">
            {title && <div className="panel-title">{title}</div>}
            {sub && <div className="panel-sub">{sub}</div>}
          </div>
          {right}
        </header>
      )}
      <div className={`panel-body${flush ? ' flush' : ''}`}>{children}</div>
    </section>
  )
}

export function CountUp({ value, duration = 900, format = (n: number) => Math.round(n).toLocaleString('en-IN') }: {
  value: number; duration?: number; format?: (n: number) => string
}) {
  const [v, setV] = useState(0)
  const from = useRef(0)
  useEffect(() => {
    const start = performance.now()
    const a = from.current
    let raf = 0
    const step = (t: number) => {
      const k = Math.min(1, (t - start) / duration)
      const e = 1 - Math.pow(1 - k, 3)
      setV(a + (value - a) * e)
      if (k < 1) raf = requestAnimationFrame(step)
      else from.current = value
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [value, duration])
  return <>{format(v)}</>
}

export function Kpi({ label, value, note, accent, tag, spark }: {
  label: string; value: number; note?: ReactNode; accent?: 'amber' | 'orange' | 'green'; tag?: Provenance; spark?: ReactNode
}) {
  return (
    <div className={`panel kpi${accent ? ` accent-${accent}` : ''}`}>
      <div className="row"><span className="kpi-label grow">{label}</span>{tag && <Tag kind={tag} />}</div>
      <div className="kpi-value"><CountUp value={value} /></div>
      {note && <div className="kpi-note">{note}</div>}
      {spark && <div className="kpi-spark">{spark}</div>}
    </div>
  )
}

export function Tabs<T extends string>({ tabs, value, onChange }: {
  tabs: { id: T; label: ReactNode; count?: number }[]; value: T; onChange: (t: T) => void
}) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} className={`tab${value === t.id ? ' on' : ''}`} onClick={() => onChange(t.id)}>
          {t.label}{t.count != null && <span className="count">{t.count}</span>}
        </button>
      ))}
    </div>
  )
}

export function Seg<T extends string>({ options, value, onChange }: { options: { id: T; label: string }[]; value: T; onChange: (v: T) => void }) {
  return (
    <div className="seg">
      {options.map((o) => (
        <button key={o.id} className={value === o.id ? 'on' : ''} onClick={() => onChange(o.id)}>{o.label}</button>
      ))}
    </div>
  )
}

export function Drawer({ open, onClose, title, children, right }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; right?: ReactNode }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [onClose])
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div className="scrim" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
          <motion.aside className="drawer" initial={{ x: 60, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: 60, opacity: 0 }} transition={{ type: 'spring', stiffness: 380, damping: 36 }} role="dialog" aria-modal="true">
            <div className="drawer-head">
              <div className="grow">{title}</div>
              {right}
              <button className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close"><Icon name="cross" size={14} /></button>
            </div>
            <div className="drawer-body">{children}</div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}

export function Meter({ value, tone, title }: { value: number; tone?: 'amber' | 'green' | 'orange' | 'segs'; title?: string }) {
  return <div className={`meter${tone ? ` ${tone}` : ''}`} title={title}><i style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} /></div>
}

export function Philosophy({ compact }: { compact?: boolean }) {
  return (
    <div className="philosophy">
      <Icon name="shield" size={15} />
      {!compact && <s>What does the AI think this signal is?</s>}
      <span>What evidence supports this signal interpretation?</span>
    </div>
  )
}

export function FadeIn({ children, delay = 0, y = 8 }: { children: ReactNode; delay?: number; y?: number }) {
  return <motion.div initial={{ opacity: 0, y }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay, ease: 'easeOut' }}>{children}</motion.div>
}

export function Loading({ label = 'Loading evidence…' }: { label?: string }) {
  return <div className="empty row" style={{ justifyContent: 'center' }}><div className="spinner" /> {label}</div>
}
