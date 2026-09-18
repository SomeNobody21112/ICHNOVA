/**
 * The one way the console talks to the API.
 *
 * Every request goes through `api()`, so a call site cannot forget the bearer token, and a 401 is
 * handled in one place instead of thirteen. The token lives in sessionStorage: it is gone when the
 * tab closes, it is never written to localStorage (which survives indefinitely) and it never travels
 * in a URL, where it would end up in history and logs.
 */

export interface AuthUser {
  username: string
  name: string
  role: 'ADMIN' | 'ANALYST' | 'REVIEWER' | 'VIEWER'
  station: string | null
  demo: boolean
}

export interface DemoAccount extends Omit<AuthUser, 'demo'> { permissions: string[] }

const TOKEN_KEY = 'ichnova.token'
const listeners = new Set<() => void>()

export function getToken(): string | null {
  try { return sessionStorage.getItem(TOKEN_KEY) } catch { return null }
}

export function setToken(token: string | null) {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token)
    else sessionStorage.removeItem(TOKEN_KEY)
  } catch { /* private mode: the session simply does not persist across reloads */ }
  listeners.forEach((fn) => fn())
}

/** Notifies the app when the session ends (logout, expiry, or a 401 from any call). */
export function onAuthChange(fn: () => void) {
  listeners.add(fn)
  return () => { listeners.delete(fn) }
}

export class ApiError extends Error {
  status: number
  retryAfter?: number
  constructor(status: number, message: string, retryAfter?: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.retryAfter = retryAfter
  }
}

/** Fetch with the bearer token attached. Throws ApiError carrying the server's message. */
export async function api(path: string, init: RequestInit = {}): Promise<Response> {
  const token = getToken()
  const headers = new Headers(init.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const res = await fetch(path, { ...init, headers, cache: init.cache ?? 'no-store' })
  if (res.status === 401 && token) {
    // We sent a token and it was refused: expired or revoked. Drop it so the UI returns to sign-in.
    // A 401 with no token is a failed sign-in attempt, which keeps the server's own message below.
    setToken(null)
    throw new ApiError(401, 'Your session has ended. Sign in again.')
  }
  if (!res.ok) {
    let message = `Request failed (${res.status})`
    let retryAfter: number | undefined
    try {
      const body = await res.clone().json()
      if (body?.error) message = body.error
      if (typeof body?.retry_after_s === 'number') retryAfter = body.retry_after_s
    } catch { /* not JSON: keep the generic message rather than dumping HTML into the UI */ }
    throw new ApiError(res.status, message, retryAfter)
  }
  return res
}

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  return (await api(path, init)).json() as Promise<T>
}

export interface AuthState { token: string; expires_at: number; user: AuthUser }

export async function login(username: string, password: string) {
  const body = await apiJson<AuthState>('/api/auth/login', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  setToken(body.token)
  return body
}

/** Signs in a demo account. The console never holds a demo password; the server issues the token. */
export async function loginDemo(username: string) {
  const body = await apiJson<AuthState>('/api/auth/demo', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username }),
  })
  setToken(body.token)
  return body
}

export async function logout() {
  try { await api('/api/auth/logout', { method: 'POST' }) } catch { /* already invalid; clear anyway */ }
  setToken(null)
}

export async function me() {
  return apiJson<{ user: AuthUser & { exp: number } }>('/api/auth/me')
}

export interface AuthInfo {
  demo_accounts: DemoAccount[]
  auth_required: boolean
  session_ttl_s: number
  ephemeral_signing_key: boolean
}

/** Public: what sign-in options exist. Never includes a password. */
export async function authInfo() {
  return apiJson<AuthInfo>('/api/auth/accounts')
}

export const ROLE_LABEL: Record<AuthUser['role'], string> = {
  ADMIN: 'Administrator', ANALYST: 'Analyst', REVIEWER: 'Reviewer', VIEWER: 'Viewer',
}

/** Mirrors the server's PERMISSIONS table; the server remains the authority. */
export const ROLE_CAN: Record<AuthUser['role'], string[]> = {
  ADMIN: ['analyse', 'live', 'review', 'read', 'admin'],
  ANALYST: ['analyse', 'live', 'review', 'read'],
  REVIEWER: ['review', 'read'],
  VIEWER: ['read'],
}

export function can(role: AuthUser['role'] | undefined | null, permission: string) {
  return !!role && ROLE_CAN[role]?.includes(permission)
}
