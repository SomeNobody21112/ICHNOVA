/**
 * Receipt verification, done in the browser.
 *
 * The point of a receipt is that you do not have to take our word for it, so this recomputes every
 * hash locally with the Web Crypto API rather than asking the server whether it is honest.
 *
 * A stored receipt is canonical JSON: keys sorted, no whitespace. Its hash was taken over exactly
 * that text with the `hash` field removed. Rather than re-serialising the parsed object — where a
 * float that Python writes as `1.0` and JavaScript writes as `1` would produce a false mismatch —
 * we cut the `"hash":"..."` pair out of the stored line and hash the remaining text. That is byte
 * for byte what the writer hashed.
 */

import { getToken } from './api'

export const GENESIS = '0'.repeat(64)

export interface Receipt {
  ledger_version: number
  created_utc: string
  capture: { sha256: string; samples?: number; fs_hz?: number | null }
  engine: Record<string, unknown>
  decision: { pack_id?: string | null; status?: string | null; code?: string | null; payload_bits?: number }
  statistics: { log10_p?: number | null; log10_threshold?: number | null; n_hypotheses?: number | null }
  source: Record<string, unknown> | null
  prev_hash: string
  hash: string
}

export interface ChainResult {
  ok: boolean
  checked: number
  head: string
  problems: { index: number; receipt: string; problem: string }[]
}

const HASH_FIELD = /"hash":"[0-9a-f]{64}"/

/** The text a receipt's hash was taken over: the stored line without its own `hash` field. */
export function bodyText(line: string): string | null {
  const m = HASH_FIELD.exec(line)
  if (!m) return null
  const start = m.index, end = m.index + m[0].length
  // Remove the pair and exactly one adjacent comma, whichever side it sits on.
  if (line[start - 1] === ',') return line.slice(0, start - 1) + line.slice(end)
  if (line[end] === ',') return line.slice(0, start) + line.slice(end + 1)
  return line.slice(0, start) + line.slice(end)
}

export async function sha256Hex(text: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text))
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, '0')).join('')
}

/** Recompute one stored line's hash. */
export async function verifyLine(line: string): Promise<{ ok: boolean; recomputed: string; stored: string }> {
  const stored = (JSON.parse(line) as Receipt).hash
  const body = bodyText(line)
  if (body === null) return { ok: false, recomputed: '', stored }
  const recomputed = await sha256Hex(body)
  return { ok: recomputed === stored, recomputed, stored }
}

/** Verify a whole ledger: every receipt's own hash, and every link to the one before it. */
export async function verifyChain(lines: string[]): Promise<ChainResult> {
  const problems: ChainResult['problems'] = []
  let prev = GENESIS
  for (let i = 0; i < lines.length; i++) {
    let r: Receipt
    try { r = JSON.parse(lines[i]) as Receipt } catch {
      problems.push({ index: i, receipt: '', problem: 'line is not valid JSON' })
      continue
    }
    const { ok, recomputed } = await verifyLine(lines[i])
    if (!ok) problems.push({ index: i, receipt: r.hash, problem: `content does not match its hash (recomputed ${recomputed.slice(0, 12)}…, stored ${String(r.hash).slice(0, 12)}…)` })
    if (r.prev_hash !== prev) problems.push({ index: i, receipt: r.hash, problem: `broken link: prev_hash ${String(r.prev_hash).slice(0, 12)}… does not follow the previous receipt ${prev.slice(0, 12)}…` })
    prev = r.hash ?? prev
  }
  return { ok: problems.length === 0, checked: lines.length, head: prev, problems }
}

export interface Ledger { lines: string[]; source: string; total: number }

/**
 * The ledgers this deployment can reach, as stored.
 *
 * There are two, and a record may sit in either: the server writes one for every capture it
 * analyses, and the build ships another covering the packs bundled with it. A static deployment has
 * only the second. Both are returned so a caller can find the receipt it is looking for rather than
 * reporting a record missing because it looked in the wrong place.
 */
export async function loadLedgers(): Promise<Ledger[]> {
  const found: Ledger[] = []
  // `no-store` on both requests, deliberately: verifying a cached copy would report a ledger intact
  // after it had been altered on disk, which is the one answer this workflow must never give.
  try {
    const token = getToken()
    const res = await fetch('/api/ledger?limit=2000', { cache: 'no-store', headers: token ? { Authorization: `Bearer ${token}` } : {} })
    if (res.ok) {
      const j = await res.json() as { lines: string[]; total: number; path: string }
      found.push({ lines: j.lines, source: j.path, total: j.total })
    }
  } catch { /* no server behind this build */ }
  try {
    const res = await fetch('/evidence/ledger.jsonl', { cache: 'no-store' })
    if (res.ok) {
      const lines = (await res.text()).split('\n').map((l) => l.trim()).filter(Boolean)
      found.push({ lines, source: 'evidence/ledger.jsonl, shipped with this build', total: lines.length })
    }
  } catch { /* nothing shipped */ }
  if (!found.length) throw new Error('No receipt ledger is reachable from this deployment.')
  return found
}
