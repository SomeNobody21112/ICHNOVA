import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useState, type ReactNode } from 'react'

export type Theme = 'light' | 'dark'
/** What the operator chose. 'system' follows the operating system and keeps following it. */
export type ThemePref = Theme | 'system'
export const TEXT_SCALES = [0.9, 1, 1.12, 1.25] as const
const THEME_COLOR: Record<Theme, string> = { light: '#f7f8f6', dark: '#0b0c0d' }

interface ThemeCtx {
  /** The theme actually applied (system resolved). Canvases redraw on this. */
  theme: Theme
  pref: ThemePref
  setPref: (p: ThemePref) => void
  scale: number
  setScale: (s: number) => void
}

const Ctx = createContext<ThemeCtx | null>(null)

function read<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key)
    return v == null ? fallback : (JSON.parse(v) as T)
  } catch {
    return fallback
  }
}

function write(key: string, value: unknown) {
  try { localStorage.setItem(key, JSON.stringify(value)) } catch { /* private mode: session only */ }
}

const systemDark = () => typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-color-scheme: dark)').matches

export function initialPref(): ThemePref {
  const saved = read<ThemePref | null>('ichnova.theme', null)
  return saved === 'light' || saved === 'dark' || saved === 'system' ? saved : 'system'
}

/** Theme and text size, remembered per browser; mirrors the accessibility bars of DoT portals. */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [pref, setPrefState] = useState<ThemePref>(initialPref)
  const [sysDark, setSysDark] = useState(systemDark)
  const [scale, setScaleState] = useState<number>(() => {
    const s = read<number>('ichnova.textScale', 1)
    return (TEXT_SCALES as readonly number[]).includes(s) ? s : 1
  })
  useEffect(() => {
    const mq = window.matchMedia?.('(prefers-color-scheme: dark)')
    if (!mq) return
    const on = () => setSysDark(mq.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [])
  const theme: Theme = pref === 'system' ? (sysDark ? 'dark' : 'light') : pref
  useLayoutEffect(() => {
    const root = document.documentElement
    root.dataset.theme = theme
    root.style.colorScheme = theme
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', THEME_COLOR[theme])
  }, [theme])
  useLayoutEffect(() => { document.documentElement.style.setProperty('--ui-scale', String(scale)) }, [scale])
  const setPref = useCallback((p: ThemePref) => { setPrefState(p); write('ichnova.theme', p) }, [])
  const setScale = useCallback((s: number) => { setScaleState(s); write('ichnova.textScale', s) }, [])
  const value = useMemo(() => ({ theme, pref, setPref, scale, setScale }), [theme, pref, setPref, scale, setScale])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useTheme() {
  const c = useContext(Ctx)
  if (!c) throw new Error('useTheme outside ThemeProvider')
  return c
}

/** Resolved value of a CSS custom property (for canvas drawing, which cannot use var()). */
export function cssVar(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

export function parseColor(c: string): [number, number, number] {
  const m = c.trim()
  if (m.startsWith('#')) {
    const h = m.length === 4 ? m.slice(1).split('').map((x) => x + x).join('') : m.slice(1, 7)
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]
  }
  const nums = m.match(/[\d.]+/g)?.map(Number) ?? [0, 0, 0]
  return [nums[0], nums[1], nums[2]]
}

/** Colour ramp stops (RGB) for spectra, read from the theme so instrument views follow light/dark. */
export function rampStops(kind: 'spec' | 'occ'): number[][] {
  const names = kind === 'spec'
    ? ['--ramp-0', '--ramp-1', '--ramp-2', '--ramp-3', '--ramp-4', '--ramp-5']
    : ['--occ-0', '--occ-1', '--occ-2', '--occ-3', '--occ-4']
  return names.map((n) => parseColor(cssVar(n) || '#000000'))
}
