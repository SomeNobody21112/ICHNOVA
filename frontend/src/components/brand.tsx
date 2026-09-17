import { useId } from 'react'
import { PRODUCT } from '../brand'

/**
 * ICHNOVA identity, drawn from the brand sheet so it follows the theme:
 * a signal that grows out of noise (wave), is discovered (star on the vertical axis) and resolves into a
 * clean line (harmony). Dark theme: gold on warm black. Light theme: ink on ivory.
 */

function Defs({ id }: { id: string }) {
  return (
    <defs>
      <linearGradient id={`${id}-wave`} x1="0" x2="1" y1="0" y2="0">
        <stop offset="0" style={{ stopColor: 'var(--logo-wave-0)', stopOpacity: 0.35 }} />
        <stop offset="0.55" style={{ stopColor: 'var(--logo-wave-1)' }} />
        <stop offset="1" style={{ stopColor: 'var(--logo-gold-1)' }} />
      </linearGradient>
      <linearGradient id={`${id}-gold`} x1="0" x2="1" y1="0" y2="1">
        <stop offset="0" style={{ stopColor: 'var(--logo-gold-0)' }} />
        <stop offset="1" style={{ stopColor: 'var(--logo-gold-1)' }} />
      </linearGradient>
      <radialGradient id={`${id}-glow`}>
        <stop offset="0" style={{ stopColor: 'var(--logo-glow)', stopOpacity: 0.55 }} />
        <stop offset="1" style={{ stopColor: 'var(--logo-glow)', stopOpacity: 0 }} />
      </radialGradient>
    </defs>
  )
}

function Star({ cx, cy, r, id }: { cx: number; cy: number; r: number; id: string }) {
  const h = r * 0.12
  const w = r * 0.78
  return (
    <>
      <circle cx={cx} cy={cy} r={r * 1.1} fill={`url(#${id}-glow)`} className="logo-glow" />
      <path fill={`url(#${id}-gold)`}
        d={`M${cx} ${cy - r} Q${cx + h} ${cy - h} ${cx + w} ${cy} Q${cx + h} ${cy + h} ${cx} ${cy + r} Q${cx - h} ${cy + h} ${cx - w} ${cy} Q${cx - h} ${cy - h} ${cx} ${cy - r} Z`} />
    </>
  )
}

/** Square mark (app icon, sidebar, favicon). */
export function BrandMark({ size = 32, tile = false, title }: { size?: number; tile?: boolean; title?: string }) {
  const id = useId().replace(/:/g, '')
  return (
    <svg viewBox="0 0 64 64" width={size} height={size} className={`brand-mark${tile ? ' tile' : ''}`} role={title ? 'img' : undefined} aria-hidden={title ? undefined : true}>
      {title && <title>{title}</title>}
      <Defs id={id} />
      {tile && <rect x="1" y="1" width="62" height="62" rx="14" className="logo-tile" />}
      <path d="M5 44 C10 37 14 37 18 41 C22 45 26 50 32 46" fill="none" stroke={`url(#${id}-wave)`} strokeWidth="1.8" strokeLinecap="round" />
      <path d="M32 7 V58" stroke={`url(#${id}-gold)`} strokeWidth="1.5" strokeLinecap="round" />
      <path d="M32 9 C46 11 53 21 53 33 C53 45 46 55 32 57 C41 53 47 44 47 33 C47 22 41 13 32 9 Z" fill={`url(#${id}-gold)`} />
      <path d="M50 32.3 L62 33 L50 33.7 Z" fill={`url(#${id}-gold)`} />
      <Star cx={32.5} cy={33} r={9} id={id} />
    </svg>
  )
}

const GLYPHS: [string, number][] = [
  ['M0 0V14', 0],                                        // I
  ['M12 2.4A7 7 0 1 0 12 11.6', 12],                     // C
  ['M0 0V14M11 0V14M0 7H11', 11],                        // H
  ['M0 14V0L11 14V0', 11],                               // N
  ['M14 7A7 7 0 1 0 0 7A7 7 0 1 0 14 7', 14],            // O
  ['M0 0L6.5 14L13 0', 13],                              // V
  ['M0 14L6.5 0L13 14', 13],                             // Λ (the brand A has no crossbar)
]
const GAP = 13
const WORD_W = GLYPHS.reduce((a, [, w]) => a + w, 0) + GAP * (GLYPHS.length - 1)

/** Spaced ICHNOVA wordmark drawn as strokes (no font dependency). */
export function Wordmark({ height = 14, tagline = false }: { height?: number; tagline?: boolean }) {
  const h = tagline ? 26 : 14
  let x = 0
  return (
    <svg viewBox={`-1 -1 ${WORD_W + 2} ${h + 2}`} height={height * (h + 2) / 16} className="wordmark" role="img" aria-label={PRODUCT.name}>
      {GLYPHS.map(([d, w], i) => {
        const g = <path key={i} d={d} transform={`translate(${x} 0)`} fill="none" strokeWidth="1.15" strokeLinecap="square" />
        x += w + GAP
        return g
      })}
      {tagline && <text x={WORD_W / 2} y={25.5} textAnchor="middle" className="wordmark-tag">{PRODUCT.tagline.toUpperCase()}</text>}
    </svg>
  )
}

/** Full horizontal lockup: noise -> discovery -> harmony, with the wordmark beneath. */
export function Lockup({ width = 360, animate = false }: { width?: number; animate?: boolean }) {
  const id = useId().replace(/:/g, '')
  return (
    <div className={`lockup${animate ? ' animate' : ''}`} style={{ width }}>
      <svg viewBox="0 0 240 76" width="100%" aria-hidden>
        <Defs id={id} />
        <path className="lockup-wave" d="M4 40 C9 36 12 36 15 40 S21 44 25 40 S33 30 39 40 S51 56 59 42 S73 16 85 40 C91 52 98 60 107 60"
          fill="none" stroke={`url(#${id}-wave)`} strokeWidth="1.7" strokeLinecap="round" />
        <path d="M108 8 V70" stroke={`url(#${id}-gold)`} strokeWidth="1.4" strokeLinecap="round" />
        <path d="M108 11 C125 13 134 25 134 39 C134 53 125 65 108 67 C119 62 127 52 127 39 C127 26 119 16 108 11 Z" fill={`url(#${id}-gold)`} />
        <path className="lockup-tail" d="M130 38.3 L236 39 L130 39.7 Z" fill={`url(#${id}-gold)`} />
        <Star cx={108.5} cy={39} r={11} id={id} />
      </svg>
      <Wordmark height={Math.max(12, width / 22)} tagline />
    </div>
  )
}
