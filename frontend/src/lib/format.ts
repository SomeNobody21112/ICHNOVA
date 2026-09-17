import type { Status } from './types'

export const STATUS_LABEL: Record<Status, string> = {
  DECODED: 'DECODED',
  SIGNAL_NO_CODE: 'SIGNAL · NO CODE',
  UNKNOWN: 'UNKNOWN',
}

export const STATUS_MEANING: Record<Status, string> = {
  DECODED: 'Evidence passed. Code, interleaver and payload established.',
  SIGNAL_NO_CODE: 'Signal detected. No catalogue code could be verified.',
  UNKNOWN: 'Insufficient evidence. No interpretation is asserted.',
}

export const CODE_SHORT = (c: string | null | undefined) =>
  !c ? '—' : c.includes('k7') || c === 'K7' ? 'K=7' : c.includes('k5') || c === 'K5' ? 'K=5' : c.includes('k3') || c === 'K3' ? 'K=3' : c

export const CODE_FULL: Record<string, string> = {
  conv_k7_r12_171_133: 'Convolutional K=7, r=1/2, (171,133)',
  conv_k5_r12_23_35: 'Convolutional K=5, r=1/2, (23,35)',
  conv_k3_r12_7_5: 'Convolutional K=3, r=1/2, (7,5)',
}

export function fmtFreq(hz: number | null | undefined) {
  if (hz == null) return 'Not recorded'
  if (hz >= 1e9) return `${(hz / 1e9).toFixed(4)} GHz`
  if (hz >= 1e6) return `${(hz / 1e6).toFixed(4)} MHz`
  if (hz >= 1e3) return `${(hz / 1e3).toFixed(2)} kHz`
  return `${hz.toFixed(0)} Hz`
}

export function fmtBw(hz: number | null | undefined) {
  if (hz == null) return 'Not recorded'
  return hz >= 1e6 ? `${(hz / 1e6).toFixed(2)} MHz` : `${(hz / 1e3).toFixed(1)} kHz`
}

export function fmtRate(hz: number | null | undefined) {
  if (hz == null) return '—'
  return hz >= 1e6 ? `${(hz / 1e6).toFixed(3)} Msym/s` : `${(hz / 1e3).toFixed(2)} ksym/s`
}

const IST: Intl.DateTimeFormatOptions = { timeZone: 'Asia/Kolkata', hour12: false }

export function fmtTime(ms: number) {
  return new Date(ms).toLocaleTimeString('en-GB', { ...IST, hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function fmtDate(ms: number) {
  return new Date(ms).toLocaleDateString('en-GB', { ...IST, day: '2-digit', month: 'short', year: 'numeric' })
}

export function fmtDateTime(ms: number) {
  return `${fmtDate(ms)} ${fmtTime(ms)} IST`
}

export function fmtAgo(ms: number, now = Date.now()) {
  const s = Math.max(0, Math.round((now - ms) / 1000))
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.round(s / 60)} min ago`
  if (s < 86400) return `${Math.round(s / 3600)} h ago`
  return `${Math.round(s / 86400)} d ago`
}

export function fmtP(log10p: number | null | undefined) {
  if (log10p == null) return '—'
  if (log10p > -3) return Math.pow(10, log10p).toFixed(4)
  const exp = Math.floor(log10p)
  const mant = Math.pow(10, log10p - exp)
  return `${mant.toFixed(2)}×10${sup(exp)}`
}

function sup(n: number) {
  const map: Record<string, string> = { '-': '⁻', '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹' }
  return String(n).split('').map((c) => map[c] ?? c).join('')
}

export const fmtInt = (n: number | null | undefined) => (n == null ? '—' : n.toLocaleString('en-IN'))
export const pct = (x: number | null | undefined, d = 0) => (x == null ? '—' : `${(x * 100).toFixed(d)}%`)
