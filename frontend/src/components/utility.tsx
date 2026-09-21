import { PRODUCT } from '../brand'
import { TEXT_SCALES, useTheme, type ThemePref } from '../lib/theme'
import { Icon } from './ui'

const THEMES: { id: ThemePref; label: string; icon: string }[] = [
  { id: 'light', label: 'Light', icon: 'sun' },
  { id: 'dark', label: 'Dark', icon: 'moon' },
  { id: 'system', label: 'System', icon: 'auto' },
]

/** Accessibility bar: skip link, text size and colour theme, as on DoT's Tarang Sanchar portal. */
export function UtilityBar({ target = 'main' }: { target?: string }) {
  const { pref, setPref, scale, setScale } = useTheme()
  const i = (TEXT_SCALES as readonly number[]).indexOf(scale)
  return (
    <div className="util-bar" role="region" aria-label="Accessibility options">
      <a className="skip" href={`#${target}`}>Skip to main content</a>
      <span className="hide-sm util-id">{PRODUCT.name} · Independent SIH prototype</span>
      <span className="spacer" />
      <div className="util-group" role="group" aria-label="Text size">
        <span className="hide-sm">Text size</span>
        <button className="util-btn" aria-label="Decrease text size" disabled={i <= 0} onClick={() => setScale(TEXT_SCALES[Math.max(0, i - 1)])}>A−</button>
        <button className={`util-btn${scale === 1 ? ' on' : ''}`} aria-label="Reset text size" aria-pressed={scale === 1} onClick={() => setScale(1)}>A</button>
        <button className="util-btn" aria-label="Increase text size" disabled={i >= TEXT_SCALES.length - 1} onClick={() => setScale(TEXT_SCALES[Math.min(TEXT_SCALES.length - 1, i + 1)])}>A+</button>
      </div>
      <i className="util-sep" aria-hidden="true" />
      {/* Colour theme, not the Field/Regional/National view: that selector lives in the top bar. */}
      <div className="util-group" role="group" aria-label="Colour theme">
        <span className="hide-sm">Theme</span>
        {THEMES.map((t) => (
          <button key={t.id} className={`util-btn${pref === t.id ? ' on' : ''}`} aria-pressed={pref === t.id}
            aria-label={`${t.label} theme`} title={t.id === 'system' ? 'Follow the operating system' : `${t.label} theme`} onClick={() => setPref(t.id)}>
            <Icon name={t.icon} size={13} /><span className="hide-sm">{t.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
