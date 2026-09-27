import { useEffect, type RefObject } from 'react'

/** Blocks that ease in the first time they scroll into view. Only top-level blocks: a panel inside
 *  a revealed panel arrives with its parent. */
const SEL = '.panel, .card, .verdict, .tasks, .statbar, .section-head, .proof-card, .stats, .flow-step, .hero-card'

/** Debounce for the rescan after new nodes appear: long enough that a live view updating many times
 *  a second costs one scan rather than sixty, short enough to be imperceptible on a route change. */
const SCAN_MS = 120

/** Scroll reveal for everything under `ref`, including content rendered later (route changes, data
 *  arriving). Nothing already on screen is ever hidden: only blocks that start below the fold are
 *  marked, so there is no flash on load. With reduced motion, or without IntersectionObserver, the
 *  hook does nothing and every block is simply visible. */
export function useScrollReveal(ref: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const root = ref.current
    if (!root || typeof IntersectionObserver === 'undefined') return
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (!e.isIntersecting) continue
        const el = e.target as HTMLElement
        el.classList.add('in')
        io.unobserve(el)
        window.setTimeout(() => el.classList.remove('reveal', 'in'), 700)
      }
    }, { rootMargin: '0px 0px -6% 0px', threshold: 0.04 })
    const scan = () => {
      root.querySelectorAll<HTMLElement>(SEL).forEach((el) => {
        if (el.dataset.rv) return
        el.dataset.rv = '1'
        if (el.parentElement?.closest(SEL)) return
        if (el.getBoundingClientRect().top < window.innerHeight) return
        el.classList.add('reveal')
        io.observe(el)
      })
    }
    scan()
    // Coalesce bursts of DOM changes into one scan, and only for changes that could have added a
    // block worth revealing.
    //
    // This used to scan once per animation frame. A live view mutates on every frame, and each scan
    // walks the whole subtree and measures every unseen element, which forces layout — so on the
    // Live Monitor the reveal pass ran ~60 times a second over a large DOM and helped starve the
    // main thread until the window lost focus. Reacting only to added nodes, and no more often than
    // SCAN_MS, costs nothing on a live page and is still immediate for a route change.
    let timer = 0
    const mo = new MutationObserver((records) => {
      if (timer) return
      if (!records.some((r) => r.addedNodes.length)) return
      timer = window.setTimeout(() => { timer = 0; scan() }, SCAN_MS)
    })
    mo.observe(root, { childList: true, subtree: true })
    return () => { io.disconnect(); mo.disconnect(); clearTimeout(timer) }
  }, [ref])
}
