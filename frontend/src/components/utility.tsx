import { PRODUCT } from '../brand'
import { TEXT_SCALES, useTheme } from '../lib/theme'
import { Icon } from './ui'

/** Accessibility bar: skip link, text size and light/dark, as on DoT's Tarang Sanchar portal. */
export function UtilityBar({ target = 'main' }: { target?: string }) {
  const { theme, setTheme, scale, setScale } = useTheme()
  const i = (TEXT_SCALES as readonly number[]).indexOf(scale)
  return (
    <div className="util-bar" role="region" aria-label="Accessibility options">
      <a className="skip" href={`#${target}`}>Skip to main content</a>
      <span className="hide-sm" style={{ opacity: 0.8 }}>{PRODUCT.name} · {PRODUCT.context} · prototype</span>
      <span className="spacer" />
      <div className="util-group" aria-label="Text size">
        <span className="hide-sm">Text size</span>
        <button className="util-btn" aria-label="Decrease text size" disabled={i <= 0} onClick={() => setScale(TEXT_SCALES[Math.max(0, i - 1)])}>A−</button>
        <button className={`util-btn${scale === 1 ? ' on' : ''}`} aria-label="Reset text size" onClick={() => setScale(1)}>A</button>
        <button className="util-btn" aria-label="Increase text size" disabled={i >= TEXT_SCALES.length - 1} onClick={() => setScale(TEXT_SCALES[Math.min(TEXT_SCALES.length - 1, i + 1)])}>A+</button>
      </div>
      <i className="util-sep" />
      <div className="util-group" role="group" aria-label="Colour theme">
        <button className={`util-btn${theme === 'light' ? ' on' : ''}`} aria-pressed={theme === 'light'} onClick={() => setTheme('light')}>
          <Icon name="sun" size={13} /> <span className="hide-sm" style={{ opacity: 1, margin: 0 }}>Light</span>
        </button>
        <button className={`util-btn${theme === 'dark' ? ' on' : ''}`} aria-pressed={theme === 'dark'} onClick={() => setTheme('dark')}>
          <Icon name="moon" size={13} /> <span className="hide-sm" style={{ opacity: 1, margin: 0 }}>Dark</span>
        </button>
      </div>
    </div>
  )
}
