import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
import '@fontsource/ibm-plex-sans/600.css'
import '@fontsource/ibm-plex-sans-condensed/500.css'
import '@fontsource/ibm-plex-sans-condensed/600.css'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'
import './styles.css'
import { MotionConfig } from 'framer-motion'
import { lazy, StrictMode, Suspense, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AppProvider, useApp } from './lib/store'
import { ThemeProvider } from './lib/theme'
import Landing from './pages/Landing'

// Each screen is its own chunk, so the first visit downloads only the landing page. Once the
// browser is idle the remaining chunks are prefetched (see below), so later navigation is instant.
const load = {
  Shell: () => import('./app/Shell'), SignIn: () => import('./pages/SignIn'), Command: () => import('./pages/Command'),
  Monitor: () => import('./pages/Monitor'), Analysis: () => import('./pages/Analysis'), Signals: () => import('./pages/Signals'),
  Review: () => import('./pages/Review'), Incidents: () => import('./pages/Incidents'), Spectrum: () => import('./pages/Spectrum'),
  Genome: () => import('./pages/Genome'), Intelligence: () => import('./pages/Intelligence'), Reports: () => import('./pages/Reports'),
  System: () => import('./pages/System'), Lab: () => import('./pages/Lab'),
}
const Shell = lazy(load.Shell)
const SignIn = lazy(load.SignIn)
const Command = lazy(load.Command)
const Monitor = lazy(load.Monitor)
const Analysis = lazy(load.Analysis)
const SignalLibrary = lazy(() => load.Signals().then((m) => ({ default: m.SignalLibrary })))
const SignalDetail = lazy(() => load.Signals().then((m) => ({ default: m.SignalDetail })))
const Review = lazy(load.Review)
const IncidentList = lazy(() => load.Incidents().then((m) => ({ default: m.IncidentList })))
const IncidentDetail = lazy(() => load.Incidents().then((m) => ({ default: m.IncidentDetail })))
const Spectrum = lazy(load.Spectrum)
const Genome = lazy(load.Genome)
const Intelligence = lazy(load.Intelligence)
const Reports = lazy(load.Reports)
const System = lazy(load.System)
const Lab = lazy(load.Lab)

function prefetchAll() {
  const run = () => Object.values(load).forEach((f) => { f().catch(() => { /* retried on navigation */ }) })
  const w = window as Window & { requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number }
  if (w.requestIdleCallback) w.requestIdleCallback(run, { timeout: 4000 })
  else setTimeout(run, 1500)
}
if (document.readyState === 'complete') prefetchAll()
else window.addEventListener('load', prefetchAll, { once: true })

/** Shown for the moment a screen's chunk is still arriving (normally never, after prefetch). */
function Pending() {
  return <div className="route-pending" role="status" aria-live="polite"><span className="spinner" /> Loading…</div>
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { session } = useApp()
  const loc = useLocation()
  if (!session) return <Navigate to="/signin" state={{ from: loc.pathname + loc.search }} replace />
  return <>{children}</>
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* framer-motion does not read the CSS media query: this makes every motion component honour
        the operating system's reduced-motion setting (opacity stays, movement goes). */}
    <MotionConfig reducedMotion="user">
    <ThemeProvider>
    <BrowserRouter>
      <AppProvider>
        <Suspense fallback={<Pending />}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/signin" element={<SignIn />} />
          <Route path="/app" element={<RequireAuth><Shell /></RequireAuth>}>
            <Route index element={<Navigate to="command" replace />} />
            <Route path="command" element={<Command />} />
            <Route path="monitor" element={<Monitor />} />
            <Route path="analysis" element={<Analysis />} />
            <Route path="signals" element={<SignalLibrary />} />
            <Route path="signals/:id" element={<SignalDetail />} />
            <Route path="review" element={<Review />} />
            <Route path="incidents" element={<IncidentList />} />
            <Route path="incidents/:id" element={<IncidentDetail />} />
            <Route path="spectrum" element={<Spectrum />} />
            <Route path="genome" element={<Genome />} />
            <Route path="intelligence" element={<Intelligence />} />
            <Route path="reports" element={<Reports />} />
            <Route path="system" element={<System />} />
            <Route path="lab" element={<Lab />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </Suspense>
      </AppProvider>
    </BrowserRouter>
    </ThemeProvider>
    </MotionConfig>
  </StrictMode>,
)
