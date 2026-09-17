import { createContext, useCallback, useContext, useLayoutEffect, useMemo, useState, type ReactNode } from 'react'

export type Theme = 'light' | 'dark'
export const TEXT_SCALES = [0.9, 1, 1.12, 1.25] as const

interface ThemeCtx {
  theme: Theme
  setTheme: (t: Theme) => void
  toggle: () => void
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

export function initialTheme(): Theme {
  const saved = read<Theme | null>('ichnova.theme', null)
  if (saved === 'light' || saved === 'dark') return saved
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

/** Theme and text size, remembered per browser; mirrors the accessibility bars of DoT portals. */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(initialTheme)
  const [scale, setScaleState] = useState<number>(() => {
    const s = read<number>('ichnova.textScale', 1)
    return (TEXT_SCALES as readonly number[]).includes(s) ? s : 1
  })
  useLayoutEffect(() => {
    const root = document.documentElement
    root.dataset.theme = theme
    root.style.colorScheme = theme
    const meta = document.querySelector('meta[name="theme-color"]')
    if (meta) meta.setAttribute('content', theme === 'dark' ? '#0c0b0a' : '#f5f2eb')
  }, [theme])
  useLayoutEffect(() => { document.documentElement.style.setProperty('--ui-scale', String(scale)) }, [scale])
  const setTheme = useCallback((t: Theme) => { setThemeState(t); write('ichnova.theme', t) }, [])
  const setScale = useCallback((s: number) => { setScaleState(s); write('ichnova.textScale', s) }, [])
  const value = useMemo(() => ({ theme, setTheme, toggle: () => setTheme(theme === 'dark' ? 'light' : 'dark'), scale, setScale }), [theme, setTheme, scale, setScale])
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
