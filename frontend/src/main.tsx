import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
import '@fontsource/ibm-plex-sans/600.css'
import '@fontsource/ibm-plex-sans-condensed/500.css'
import '@fontsource/ibm-plex-sans-condensed/600.css'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'
import './styles.css'
import { StrictMode, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AppProvider, useApp } from './lib/store'
import { ThemeProvider } from './lib/theme'
import Shell from './app/Shell'
import Landing from './pages/Landing'
import SignIn from './pages/SignIn'
import Command from './pages/Command'
import Monitor from './pages/Monitor'
import Analysis from './pages/Analysis'
import { SignalLibrary, SignalDetail } from './pages/Signals'
import Review from './pages/Review'
import { IncidentList, IncidentDetail } from './pages/Incidents'
import Spectrum from './pages/Spectrum'
import Genome from './pages/Genome'
import Intelligence from './pages/Intelligence'
import Reports from './pages/Reports'
import System from './pages/System'
import Lab from './pages/Lab'

function RequireAuth({ children }: { children: ReactNode }) {
  const { session } = useApp()
  const loc = useLocation()
  if (!session) return <Navigate to="/signin" state={{ from: loc.pathname + loc.search }} replace />
  return <>{children}</>
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
    <BrowserRouter>
      <AppProvider>
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
      </AppProvider>
    </BrowserRouter>
    </ThemeProvider>
  </StrictMode>,
)
