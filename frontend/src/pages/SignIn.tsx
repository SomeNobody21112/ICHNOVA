import { GoogleLogin, GoogleOAuthProvider } from '@react-oauth/google'
import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { PRODUCT } from '../brand'
import { Link } from 'react-router-dom'
import { BrandMark, Lockup, Wordmark } from '../components/brand'
import { Icon, Tag } from '../components/ui'
import { UtilityBar } from '../components/utility'
import { ApiError, authInfo, login, loginDemo, ROLE_LABEL, type AuthInfo, type AuthUser } from '../lib/api'
import { STATIONS } from '../lib/sim'
import { useApp } from '../lib/store'
import { useTheme } from '../lib/theme'
import type { Level, Session } from '../lib/types'

const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined

function decodeJwt(token: string): { name?: string; email?: string; picture?: string } {
  try {
    const part = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    return JSON.parse(decodeURIComponent(atob(part).split('').map((c) => '%' + c.charCodeAt(0).toString(16).padStart(2, '0')).join('')))
  } catch {
    return {}
  }
}

export default function SignIn() {
  const { signIn, setTour } = useApp()
  const { theme } = useTheme()
  const nav = useNavigate()
  const loc = useLocation() as { state?: { from?: string; tour?: boolean } }
  const [role, setRole] = useState<Level>('FIELD')
  const [station, setStation] = useState('MS-07')
  const [officer, setOfficer] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [info, setInfo] = useState<AuthInfo | null>(null)

  // What the server offers: whether authentication is required and which demo accounts exist.
  useEffect(() => { authInfo().then(setInfo).catch(() => setInfo(null)) }, [])

  const finish = (s: Omit<Session, 'role' | 'stationId' | 'signedInAt'>, user?: AuthUser) => {
    signIn({
      ...s, role, stationId: user?.station ?? station, signedInAt: Date.now(),
      authRole: user?.role, username: user?.username, demo: user?.demo,
    })
    if (loc.state?.tour) { setTour({ active: true, scene: 0 }); nav('/app/monitor') } else nav(loc.state?.from ?? '/app/command')
  }

  const fail = (e: unknown) => {
    setError(e instanceof ApiError ? e.message : 'Could not reach the analysis server. Is it running?')
    setBusy(null)
  }

  const signInWithPassword = async () => {
    setError(null); setBusy('password')
    try {
      const { user } = await login(officer.trim(), code)
      finish({ name: user.name, email: `${user.username}@station.local`, method: 'operator' }, user)
    } catch (e) { fail(e) }
  }

  const signInAsDemo = async (username: string, name: string) => {
    setError(null); setBusy(username)
    try {
      const { user } = await loginDemo(username)
      finish({ name: user.name || name, email: `${user.username}@demo.local`, method: 'demo' }, user)
    } catch (e) { fail(e) }
  }

  return (
    <>
    <UtilityBar />
    <div className="signin">
      <div className="signin-art">
        <Link to="/" className="row" style={{ gap: 10, color: 'var(--text)', textDecoration: 'none' }} aria-label={`${PRODUCT.name} home`}>
          <BrandMark size={32} /><Wordmark height={11} />
        </Link>
        <div style={{ margin: 'auto 0', maxWidth: 560 }}>
          <Lockup width={340} animate />
          <h1 className="land-h1" style={{ fontSize: 'clamp(26px, 2.6vw, 38px)', marginTop: 34 }}>Every signal decision, with the evidence behind it.</h1>
          <ul className="why-list" style={{ marginTop: 18 }}>
            <li><span className="ok"><Icon name="check" size={16} /></span><span>Blind analysis of .IQ and .wav recordings: modulation, symbol rate, code and interleaver.</span></li>
            <li><span className="ok"><Icon name="check" size={16} /></span><span>Verified on real government transmissions against receiver GPS time.</span></li>
            <li><span className="ok"><Icon name="check" size={16} /></span><span>{PRODUCT.restraint}</span></li>
          </ul>
        </div>
        <div className="muted" style={{ fontSize: 12 }}>{PRODUCT.disclaimer}</div>
      </div>
      <div className="signin-form">
        <motion.div className="signin-card" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
          <div>
            <h2 className="page-title" style={{ fontSize: 26 }}>Sign in</h2>
            <p className="dim" style={{ margin: '4px 0 0' }}>Choose your role and station. They set your default view and can be changed later.</p>
          </div>
          <div className="form-grid">
            <div className="field"><label htmlFor="role">Role</label>
              <select id="role" className="select" value={role} onChange={(e) => setRole(e.target.value as Level)}>
                <option value="FIELD">Field station</option><option value="REGIONAL">Regional / zonal</option><option value="NATIONAL">National / policy</option>
              </select></div>
            <div className="field"><label htmlFor="station">Station</label>
              <select id="station" className="select" value={station} onChange={(e) => setStation(e.target.value)}>
                {STATIONS.map((s) => <option key={s.id} value={s.id}>{s.id} · {s.name}</option>)}
              </select></div>
          </div>

          {CLIENT_ID ? (
            <GoogleOAuthProvider clientId={CLIENT_ID}>
              <div className="center" style={{ minHeight: 44 }}>
                <GoogleLogin theme={theme === 'dark' ? 'filled_black' : 'outline'} size="large" width="400" text="signin_with" shape="rectangular"
                  onSuccess={(cred) => {
                    const p = decodeJwt(cred.credential ?? '')
                    if (!p.email) { setError('Google did not return an identity token.'); return }
                    finish({ name: p.name ?? p.email, email: p.email, picture: p.picture, method: 'google' })
                  }}
                  onError={() => setError('Google sign-in was cancelled or failed. Check the OAuth client origins.')} />
              </div>
            </GoogleOAuthProvider>
          ) : (
            <div className="col" style={{ gap: 6 }}>
              <button className="gbtn" disabled title="Set VITE_GOOGLE_CLIENT_ID to enable">
                <svg width="18" height="18" viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" /><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" /><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.3 0-9.7-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" /><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 38.2 44 33 44 24c0-1.3-.1-2.4-.4-3.5z" /></svg>
                Sign in with Google
              </button>
              <span className="muted" style={{ fontSize: 11.5 }}>Google sign-in needs <span className="mono">VITE_GOOGLE_CLIENT_ID</span> (see <span className="mono">frontend/.env.example</span>).</span>
            </div>
          )}

          <div className="divider">operator account</div>
          <form className="col" style={{ gap: 10 }} onSubmit={(e) => {
            e.preventDefault()
            if (!officer.trim() || code.length < 8) { setError('Enter your username and a password of at least 8 characters.'); return }
            void signInWithPassword()
          }}>
            <div className="field"><label htmlFor="officer">Username</label>
              <input id="officer" className="input" value={officer} onChange={(e) => setOfficer(e.target.value)} placeholder="e.g. a.rao" autoComplete="username" /></div>
            <div className="field"><label htmlFor="code">Password</label>
              <input id="code" className="input" type="password" value={code} onChange={(e) => setCode(e.target.value)} autoComplete="current-password" /></div>
            {error && <div className="banner amber" role="alert"><Icon name="info" /><span>{error}</span></div>}
            <button className="btn btn-primary btn-lg" type="submit" style={{ justifyContent: 'center' }}
              data-loading={busy === 'password'} disabled={busy !== null}>Sign in</button>
          </form>

          {!!info?.demo_accounts?.length && (
            <div className="col" style={{ gap: 8 }}>
              <div className="divider">demo accounts</div>
              <div className="picker" role="group" aria-label="Demo accounts">
                {info.demo_accounts.map((a) => (
                  <button key={a.username} type="button" className="pick" disabled={busy !== null}
                    data-loading={busy === a.username} onClick={() => void signInAsDemo(a.username, a.name)}>
                    <span className="pick-name">{a.name}</span>
                    <span className="mono muted" style={{ fontSize: 'var(--t-xs)' }}>{ROLE_LABEL[a.role]}</span>
                    <span className="pick-note">Can {a.permissions.join(', ')}{a.station ? ` \u00b7 station ${a.station}` : ''}</span>
                  </button>
                ))}
              </div>
              <p className="muted" style={{ fontSize: 'var(--t-sm)', margin: 0 }}>
                Demo accounts are issued by the server for this demonstration. They carry exactly the
                permissions listed above, and no password reaches the browser.
              </p>
            </div>
          )}
          <div className="banner muted" style={{ fontSize: 12 }}>
            <Icon name="shield" />
            <span>
              Passwords are verified on the server with scrypt, and the session is a signed token that
              expires{info ? ` after ${Math.round(info.session_ttl_s / 3600)} h` : ''}. Google sign-in
              remains a prototype path: its token is decoded in the browser and is not verified
              server-side. <Tag kind="EXPERIMENTAL" />
            </span>
          </div>
        </motion.div>
      </div>
    </div>
    </>
  )
}
