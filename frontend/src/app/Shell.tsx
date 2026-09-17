import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useMemo, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { PRODUCT } from '../brand'
import { BrandMark, Icon, Seg, Tag } from '../components/ui'
import { useApp } from '../lib/store'
import type { Level } from '../lib/types'

const NAV: { sec: string; items: { to: string; label: string; icon: string; badge?: 'review' | 'incidents' | 'dev' }[] }[] = [
  { sec: 'Operations', items: [
    { to: 'command', label: 'Command Center', icon: 'command' },
    { to: 'monitor', label: 'Live Monitor', icon: 'monitor' },
    { to: 'analysis', label: 'Analysis', icon: 'analysis' },
  ] },
  { sec: 'Signals', items: [
    { to: 'signals', label: 'Signals', icon: 'signals' },
    { to: 'review', label: 'Review Queue', icon: 'review', badge: 'review' },
    { to: 'incidents', label: 'Incidents', icon: 'incidents', badge: 'incidents' },
  ] },
  { sec: 'Intelligence', items: [
    { to: 'spectrum', label: 'Spectrum Map', icon: 'spectrum' },
    { to: 'genome', label: 'Signal Genome', icon: 'genome' },
    { to: 'intelligence', label: 'Intelligence', icon: 'intel' },
  ] },
  { sec: 'Records', items: [
    { to: 'reports', label: 'Reports', icon: 'reports' },
    { to: 'system', label: 'System', icon: 'system' },
    { to: 'lab', label: 'Experiment Lab', icon: 'lab', badge: 'dev' },
  ] },
]

const TITLES: Record<string, [string, string]> = {
  command: ['Command Center', 'RF observability'], monitor: ['Live Monitor', 'Real transmissions'],
  analysis: ['Analysis', 'Field capture workflow'], signals: ['Signals', 'Library & evidence'], review: ['Review Queue', 'Human in the loop'],
  incidents: ['Incidents', 'Investigations'], spectrum: ['Spectrum Map', 'Spectrum intelligence'], genome: ['Signal Genome', 'Fingerprints & similarity'],
  intelligence: ['Intelligence', 'Cross-signal patterns'], reports: ['Reports', 'Evidence packages'], system: ['System', 'Architecture, quality, audit'],
  lab: ['Experiment Lab', 'Research & benchmark'],
}

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
      <motion.div key={tour.scene} className="tour" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 10 }}>
        <div className="tour-head">
          <span className="eyebrow grow">Scene {tour.scene + 1} of {SCENES.length}</span>
          <button className="btn btn-ghost btn-sm" onClick={() => setTour({ active: false, scene: 0 })}><Icon name="cross" size={13} /></button>
        </div>
        <div className="tour-body"><h3>{s.title}</h3><p>{s.text}</p></div>
        <div className="tour-foot">
          <div className="tour-dots">{SCENES.map((_, i) => <i key={i} className={i <= tour.scene ? 'on' : ''} />)}</div>
          <span className="spacer" />
          <button className="btn btn-sm" disabled={tour.scene === 0} onClick={() => setTour({ active: true, scene: tour.scene - 1 })}>Back</button>
          {tour.scene < SCENES.length - 1
            ? <button className="btn btn-primary btn-sm" onClick={() => setTour({ active: true, scene: tour.scene + 1 })}>Next scene <Icon name="chevron" size={12} /></button>
            : <button className="btn btn-primary btn-sm" onClick={() => setTour({ active: false, scene: 0 })}>Finish</button>}
        </div>
      </motion.div>
    </AnimatePresence>
  )
}

function Clock() {
  const [now, setNow] = useState(Date.now())
  useEffect(() => { const id = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(id) }, [])
  return <span className="mono dim nowrap" style={{ fontSize: 12 }}>{new Date(now).toLocaleTimeString('en-GB', { timeZone: 'Asia/Kolkata', hour12: false })} IST</span>
}

export default function Shell() {
  const { session, signOut, level, setLevel, engine, signals, world, reviews, setTour, tour } = useApp()
  const [collapsed, setCollapsed] = useState(false)
  const [menu, setMenu] = useState(false)
  const loc = useLocation()
  const nav = useNavigate()
  const section = loc.pathname.split('/')[2] ?? 'command'
  const [title, sub] = TITLES[section] ?? ['', '']
  const reviewCount = useMemo(() => signals.filter((s) => (s.status !== 'DECODED' || s.investigate) && !reviews[s.id]).length, [signals, reviews])
  const openIncidents = world.incidents.filter((i) => i.status !== 'CLOSED').length

  return (
    <div className={`shell${collapsed ? ' collapsed' : ''}`}>
      <aside className="sidebar">
        <div className="brand">
          <BrandMark />
          <div className="brand-text"><div className="brand-name">{PRODUCT.name}</div><div className="brand-sub">RF evidence platform</div></div>
        </div>
        <nav className="nav" aria-label="Primary">
          {NAV.map((g) => (
            <div key={g.sec}>
              <div className="nav-sec">{g.sec}</div>
              {g.items.map((it) => (
                <NavLink key={it.to} to={`/app/${it.to}`} className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`} title={it.label} onClick={() => { if (window.innerWidth <= 760) setCollapsed(false) }}>
                  <Icon name={it.icon} /><span className="nav-label">{it.label}</span>
                  {it.badge === 'review' && reviewCount > 0 && <span className="nav-badge">{reviewCount}</span>}
                  {it.badge === 'incidents' && <span className="nav-badge">{openIncidents}</span>}
                  {it.badge === 'dev' && <span className="nav-badge dev">DEV</span>}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">
          <q>{PRODUCT.philosophy}</q>
          <span>{PRODUCT.context}</span>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <button className="btn btn-ghost btn-sm" onClick={() => setCollapsed(!collapsed)} aria-label="Toggle navigation"><Icon name="menu" size={16} /></button>
          <div className="crumb">{title}<small>{sub}</small></div>
          <span className="spacer" />
          <Seg<Level> options={[{ id: 'FIELD', label: 'Field' }, { id: 'REGIONAL', label: 'Regional' }, { id: 'NATIONAL', label: 'National' }]} value={level} onChange={setLevel} />
          <span className="row nowrap" title={engine.online ? `Local engine ${engine.version} · ${engine.commit}` : 'Local analysis server not reachable: benchmark evidence and replay only'}>
            <i className={`dot ${engine.online ? 'dot-ok' : 'dot-warn'}`} />
            <span className="mono" style={{ fontSize: 11.5, color: engine.online ? 'var(--green)' : 'var(--amber)' }}>{engine.online ? `ENGINE READY v${engine.version}` : 'ENGINE OFFLINE · REPLAY'}</span>
          </span>
          <Clock />
          {!tour.active && <button className="btn btn-sm" onClick={() => setTour({ active: true, scene: 0 })}><Icon name="play" size={12} /> Walkthrough</button>}
          <div style={{ position: 'relative' }}>
            <button className="btn btn-ghost btn-sm" onClick={() => setMenu(!menu)} aria-haspopup="menu">
              {session?.picture ? <img src={session.picture} alt="" width={22} height={22} style={{ borderRadius: '50%' }} referrerPolicy="no-referrer" /> : <span className="center" style={{ width: 22, height: 22, borderRadius: '50%', background: 'var(--panel-3)', fontSize: 11 }}>{session?.name.slice(0, 1)}</span>}
              <span className="nowrap" style={{ maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis' }}>{session?.name}</span>
            </button>
            {menu && (
              <div className="panel" style={{ position: 'absolute', right: 0, top: 38, width: 280, zIndex: 50, padding: 12 }} onMouseLeave={() => setMenu(false)}>
                <div style={{ fontWeight: 600 }}>{session?.name}</div>
                <div className="muted" style={{ fontSize: 12 }}>{session?.email}</div>
                <div className="hr" />
                <dl className="kv" style={{ fontSize: 12 }}>
                  <dt>Sign-in</dt><dd>{session?.method === 'google' ? 'Google' : 'Operator credentials'}</dd>
                  <dt>Role</dt><dd>{session?.role}</dd>
                  <dt>Station</dt><dd>{session?.stationId}</dd>
                </dl>
                <div className="hr" />
                <div className="col" style={{ gap: 6 }}>
                  <span className="muted" style={{ fontSize: 11 }}>Data provenance</span>
                  <div className="row-wrap"><Tag kind="SIMULATED" /><Tag kind="BENCHMARK" /><Tag kind="LIVE" /><Tag kind="EXPERIMENTAL" /><Tag kind="NOT ESTABLISHED" /></div>
                </div>
                <div className="hr" />
                <button className="btn btn-sm" style={{ width: '100%' }} onClick={() => { signOut(); nav('/') }}><Icon name="logout" size={13} /> Sign out</button>
              </div>
            )}
          </div>
        </header>
        <main className="content">
          <AnimatePresence mode="wait">
            <motion.div key={loc.pathname} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}>
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
      <Tour />
    </div>
  )
}
