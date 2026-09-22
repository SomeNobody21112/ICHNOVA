import { AnimatePresence, motion } from 'framer-motion'
import { Suspense, useMemo, useRef, useState, useEffect } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { PRODUCT } from '../brand'
import { BrandMark, Wordmark } from '../components/brand'
import { Icon, Tag } from '../components/ui'
import { UtilityBar } from '../components/utility'
import { useApp } from '../lib/store'
import type { Level } from '../lib/types'

type Item = { to: string; label: string; icon: string; badge?: 'review' | 'incidents' }
const NAV: { sec: string; items: Item[] }[] = [
  { sec: 'Overview', items: [{ to: 'command', label: 'Home', icon: 'command' }] },
  { sec: 'Work', items: [
    { to: 'analysis', label: 'Analyse a capture', icon: 'analysis' },
    { to: 'monitor', label: 'Live signals', icon: 'monitor' },
    { to: 'review', label: 'Review queue', icon: 'review', badge: 'review' },
  ] },
  { sec: 'Records', items: [
    { to: 'signals', label: 'Signal library', icon: 'signals' },
    { to: 'incidents', label: 'Incidents', icon: 'incidents', badge: 'incidents' },
    { to: 'reports', label: 'Reports', icon: 'reports' },
  ] },
  { sec: 'Insights', items: [
    { to: 'spectrum', label: 'Spectrum map', icon: 'spectrum' },
    { to: 'intelligence', label: 'Intelligence', icon: 'intel' },
    { to: 'genome', label: 'Signal genome', icon: 'genome' },
  ] },
  { sec: 'About the engine', items: [
    { to: 'lab', label: 'Evidence lab', icon: 'lab' },
    { to: 'system', label: 'System', icon: 'system' },
  ] },
]
const LOOKUP: Record<string, { sec: string; label: string }> = Object.fromEntries(NAV.flatMap((g) => g.items.map((i) => [i.to, { sec: g.sec, label: i.label }])))

export const SCENES = [
  { title: 'Real signals, not a demo loop', route: '/app/monitor?rec=jjy40-japan-2026-09-17', text: 'A government time signal from Japan, received through a public receiver. The engine is told only where to listen: carrier, second timing, symbols and protocol are established from the signal, then the decoded minute is checked against the receiver’s GPS clock.' },
  { title: 'The platform observes', route: '/app/analysis', text: 'An operator brings in a .IQ or .wav capture with its metadata. The engine runs detection, symbol-structure search, CFO estimation and a structured FEC hypothesis search.' },
  { title: 'It does not guess', route: '/app/signals/BENCH-QPSK-K7?tab=hypotheses', text: 'Every combination of rate, modulation, rotation, code and interleaver is a hypothesis. Tens of thousands are tested; each point here is one of them.' },
  { title: 'Evidence', route: '/app/signals/BENCH-QPSK-K7?tab=chain', text: 'The decision is a chain of evidence: presence, structure, parity checks, multiple-testing correction and structural consistency. Every stage is inspectable.' },
  { title: 'Decision — or restraint', route: '/app/signals/BENCH-SHORT-K7', text: 'This capture is a real K=7 transmission that is too short to prove. The system refuses to manufacture an answer and says UNKNOWN.' },
  { title: 'From one signal to national intelligence', route: '/app/intelligence?view=scale', text: 'Each evidence record becomes a fingerprint. Fingerprints correlate across captures, stations and regions into patterns an analyst can act on.' },
]

function Tour() {
  const { tour, setTour } = useApp()
  const nav = useNavigate()
  const loc = useLocation()
  useEffect(() => {
    if (!tour.active) return
    const target = SCENES[tour.scene].route
    if (loc.pathname + loc.search !== target) nav(target)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tour.active, tour.scene])
  if (!tour.active) return null
  const s = SCENES[tour.scene]
  return (
    <AnimatePresence mode="wait">
      <motion.div key={tour.scene} className="tour" role="dialog" aria-label="Guided tour" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 10 }}>
        <div className="tour-head">
          <span className="meta grow">Guided tour · {tour.scene + 1} of {SCENES.length}</span>
          <button className="btn btn-ghost btn-sm" aria-label="Close tour" onClick={() => setTour({ active: false, scene: 0 })}><Icon name="cross" size={13} /></button>
        </div>
        <div className="tour-body"><h3>{s.title}</h3><p>{s.text}</p></div>
        <div className="tour-foot">
          <div className="tour-dots">{SCENES.map((_, i) => <i key={i} className={i <= tour.scene ? 'on' : ''} />)}</div>
          <span className="spacer" />
          <button className="btn btn-sm" disabled={tour.scene === 0} onClick={() => setTour({ active: true, scene: tour.scene - 1 })}>Back</button>
          {tour.scene < SCENES.length - 1
            ? <button className="btn btn-primary btn-sm" onClick={() => setTour({ active: true, scene: tour.scene + 1 })}>Next <Icon name="chevron" size={12} /></button>
            : <button className="btn btn-primary btn-sm" onClick={() => setTour({ active: false, scene: 0 })}>Finish</button>}
        </div>
      </motion.div>
    </AnimatePresence>
  )
}

export default function Shell() {
  const { session, signOut, level, setLevel, engine, signals, world, reviews, setTour, tour } = useApp()
  const [collapsed, setCollapsed] = useState(false)
  const [menu, setMenu] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  // The account panel is a disclosure: it closes on Escape or a click outside, not on mouse-out,
  // which dropped it the moment a keyboard or touch user moved toward it.
  useEffect(() => {
    if (!menu) return
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') setMenu(false) }
    const down = (e: PointerEvent) => { if (!menuRef.current?.contains(e.target as Node)) setMenu(false) }
    window.addEventListener('keydown', key)
    window.addEventListener('pointerdown', down)
    return () => { window.removeEventListener('keydown', key); window.removeEventListener('pointerdown', down) }
  }, [menu])
  const loc = useLocation()
  const nav = useNavigate()
  const parts = loc.pathname.split('/')
  const section = parts[2] ?? 'command'
  const detail = parts[3]
  const here = LOOKUP[section]
  const reviewCount = useMemo(() => signals.filter((s) => (s.status !== 'DECODED' || s.investigate) && !reviews[s.id]).length, [signals, reviews])
  const openIncidents = world.incidents.filter((i) => i.status !== 'CLOSED').length

  return (
    <div className={`shell${collapsed ? ' collapsed' : ''}`}>
      <UtilityBar />
      <aside className="sidebar" aria-label="Main navigation">
        <Link to="/app/command" className="brand" aria-label={`${PRODUCT.name} home`}>
          <BrandMark size={34} title={PRODUCT.name} />
          {/* The rail is 236px: the wordmark alone reads cleanly there. The tagline stays on the
              landing page and in the app footer, where it has room to be set properly. */}
          <div className="brand-text"><Wordmark height={14} /><span className="brand-sub">Independent SIH prototype</span></div>
        </Link>
        <nav className="nav">
          {NAV.map((g) => (
            <div key={g.sec}>
              <div className="nav-sec">{g.sec}</div>
              {g.items.map((it) => (
                <NavLink key={it.to} to={`/app/${it.to}`} className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`} title={it.label}
                  onClick={() => { if (window.innerWidth <= 760) setCollapsed(false) }}>
                  <Icon name={it.icon} /><span className="nav-label">{it.label}</span>
                  {it.badge === 'review' && reviewCount > 0 && <span className="nav-badge" aria-label={`${reviewCount} awaiting review`}>{reviewCount}</span>}
                  {it.badge === 'incidents' && openIncidents > 0 && <span className="nav-badge" aria-label={`${openIncidents} open`}>{openIncidents}</span>}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">{PRODUCT.context}<br />Sponsor: NTRO</div>
      </aside>
      <div className="main">
        <header className="topbar">
          <button className="btn btn-ghost btn-sm" onClick={() => setCollapsed(!collapsed)} aria-label="Toggle navigation" aria-expanded={!collapsed}><Icon name="menu" size={17} /></button>
          <nav className="crumbs" aria-label="Breadcrumb">
            <Link to="/app/command">Home</Link>
            {here && section !== 'command' && <><span className="sep">/</span><span className="hide-sm">{here.sec}</span><span className="sep hide-sm">/</span>{detail ? <Link to={`/app/${section}`}>{here.label}</Link> : <b>{here.label}</b>}</>}
            {detail && <><span className="sep">/</span><b className="mono">{decodeURIComponent(detail)}</b></>}
          </nav>
          <span className="spacer" />
          <label className="row hide-sm" style={{ gap: 6, fontSize: 12.5 }}>
            <span className="muted">View</span>
            <select className="select" style={{ width: 'auto', height: 30, padding: '2px 8px' }} value={level} onChange={(e) => setLevel(e.target.value as Level)}>
              <option value="FIELD">Field station</option><option value="REGIONAL">Regional</option><option value="NATIONAL">National</option>
            </select>
          </label>
          <span className="engine-pill hide-sm" title={engine.online ? `Local engine ${engine.version} · ${engine.commit}` : 'Local analysis server not reachable: recorded results only'}>
            <i className={`dot ${engine.online ? 'dot-ok' : 'dot-warn'}`} aria-hidden="true" />Engine <b>{engine.online ? 'ready' : 'offline'}</b>
          </span>
          {!tour.active && <button className="btn btn-sm hide-sm" onClick={() => setTour({ active: true, scene: 0 })}><Icon name="play" size={12} /> Guided tour</button>}
          <div style={{ position: 'relative' }} ref={menuRef}>
            <button className="btn btn-ghost btn-sm" onClick={() => setMenu(!menu)} aria-expanded={menu} aria-controls="user-panel" aria-label={`Account: ${session?.name ?? ''}`}>
              {session?.picture ? <img src={session.picture} alt="" width={24} height={24} style={{ borderRadius: '50%' }} referrerPolicy="no-referrer" /> : <span className="center" style={{ width: 24, height: 24, borderRadius: '50%', background: 'var(--accent-soft)', color: 'var(--accent)', fontSize: 11, fontWeight: 600 }}>{session?.name.slice(0, 1)}</span>}
              <span className="nowrap hide-sm" style={{ maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis' }}>{session?.name}</span>
            </button>
            {menu && (
              <div className="panel raised" id="user-panel" role="region" aria-label="Account" style={{ position: 'absolute', right: 0, top: 40, width: 290, maxWidth: 'calc(100vw - 24px)', zIndex: 50, padding: 14 }}>
                <div style={{ fontWeight: 600 }}>{session?.name}</div>
                <div className="muted" style={{ fontSize: 12.5 }}>{session?.email}</div>
                <div className="hr" />
                <dl className="kv" style={{ fontSize: 12.5 }}>
                  <dt>Sign-in</dt><dd>{session?.method === 'google' ? 'Google' : 'Operator credentials'}</dd>
                  <dt>Role</dt><dd>{session?.role}</dd>
                  <dt>Station</dt><dd>{session?.stationId}</dd>
                </dl>
                <div className="hr" />
                <div className="col" style={{ gap: 6 }}>
                  <span className="muted" style={{ fontSize: 11.5 }}>Data labels used across the console</span>
                  <div className="row-wrap"><Tag kind="LIVE" /><Tag kind="BENCHMARK" /><Tag kind="SIMULATED" /><Tag kind="EXPERIMENTAL" /><Tag kind="NOT ESTABLISHED" /></div>
                </div>
                <div className="hr" />
                <button className="btn btn-sm" style={{ width: '100%', justifyContent: 'center' }} onClick={() => { signOut(); nav('/') }}><Icon name="logout" size={13} /> Sign out</button>
              </div>
            )}
          </div>
        </header>
        <main className="content" id="main" tabIndex={-1}>
          <AnimatePresence mode="wait">
            <motion.div key={loc.pathname} className="route" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}>
              <Suspense fallback={<div className="route-pending" role="status" aria-live="polite"><span className="spinner" /> Loading…</div>}>
                <Outlet />
              </Suspense>
            </motion.div>
          </AnimatePresence>
          <footer className="app-foot">
            <span>{PRODUCT.name} · {PRODUCT.tagline}</span>
            <span>{PRODUCT.disclaimer}</span>
          </footer>
        </main>
      </div>
      <Tour />
    </div>
  )
}
