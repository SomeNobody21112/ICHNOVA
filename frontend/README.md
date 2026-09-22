# ICHNOVA — operator console

ICHNOVA (*From noise to harmony*). Prototype for SIH 2026 problem statement SIH26147 (sponsor: NTRO). Not an official Government of India system.

React 19 + TypeScript + Vite. The console asks one question of every capture: *what evidence supports this signal interpretation?*

## Run

```bash
pip install -r ../requirements.txt
npm install
npm run build
python ../server/app.py          # http://127.0.0.1:8765 — engine API + built console
```

Development with hot reload: keep `server/app.py` running and use `npm run dev` (http://localhost:5173, `/api` is proxied to 8765). Without the server the console still works, replaying stored benchmark evidence (the top bar shows ENGINE OFFLINE · REPLAY).

## Look, themes and accessibility

- **Light, dark and system themes.** Every colour is a CSS token in `src/styles.css` (`:root[data-theme='light'|'dark']`); canvases read the same tokens (`src/lib/theme.tsx`). Light is its own palette (paper, ink, one bronze accent), not an inversion of dark. *System* follows the operating system and keeps following it while the page is open. The choice (`light`, `dark` or `system`) and text size are remembered in `localStorage` (`ichnova.theme`, `ichnova.textScale`) and applied before first paint (`index.html`).
- **Contrast.** Every text token was computed against `--bg`, `--panel` and `--panel-2` in both themes and clears 4.5:1; `--field` (input boundaries) clears 3:1. These are computed ratios, not a formal WCAG audit.
- **Accessibility bar** on every screen (`src/components/utility.tsx`): skip to content, text size A−/A/A+, theme Light/Dark/System. Controls are at least 24 px; pressed state is announced (`aria-pressed`).
- **Outcomes never rely on colour.** DECODED, SIGNAL · NO CODE and UNKNOWN each carry a shape as well as a word and a colour (check, waveform, dashed question mark; `STATUS_GLYPH` in `src/components/ui.tsx`). Provenance tags likewise: dot = live, square = benchmark, hollow diamond on hatching = simulated, triangle = experimental, dashed ring = not established. Evidence-chain stages state their result in words (PASS, BAR NOT MET, …).
- **Result hierarchy.** A signal record opens on the verdict, then why (hypotheses tested, observed p, corrected threshold α/M, acceptance), then evidence, then technical detail (`Verdict` in `src/components/evidence.tsx`). For a refusal the explanation and "what would prove it" are the engine's own sufficiency text, not UI copy. The receipt panel lays the decision out as a receipt and reports RECEIPT VERIFIED or VERIFICATION FAILED in a live region.
- **Tags are rare and quiet.** Provenance is stated once per page (or record header) as a small glyph and word, not as a coloured box on every panel; a panel carries its own mark only when it differs from the page. Priority is a fixed-width signal-strength mark plus a word (`Priority` in `src/components/ui.tsx`), so mixed High/Medium/Low rows stay aligned. No coloured side stripes on cards.
- **Station map** (`src/components/IndiaMap.tsx`): drag to pan; zoom with the + / − buttons, Ctrl/⌘ + scroll, trackpad or touch pinch, double-click or the keyboard (arrows, + / −, 0 resets). A plain scroll still scrolls the page. Markers keep their screen size while geography scales, and use shape as well as colour (circle = station, diamond = unresolved, ringed = open incident). The legend is a small corner control that opens on hover, keyboard focus or tap.
- **Genome map** (`src/pages/Genome.tsx`): signals projected on the top two principal components of their fingerprints (axes state the share of variation shown); families of five or more drawn as 2σ outlines with counts; status by shape; the selection is ringed with its nearest fingerprints linked.
- **Loading.** The library is built from per-pack summaries in `public/evidence/index.json`; a full evidence pack loads only when its record is opened (`loadPack`). Screens are separate chunks (`React.lazy` in `src/main.tsx`), prefetched when the browser is idle. `server/app.py` serves the build gzip-compressed with ETags.
- **Motion** carries data arriving, once: line plots draw in, bars and meters grow, blocks below the fold rise in on scroll (`src/lib/reveal.ts`). Reduced motion and print show end states.
- **Keyboard and motion.** Tabs move with the arrow keys; the evidence drawer takes focus, traps Tab and returns focus on close; clickable table rows and lists accept Enter; the account panel closes on Escape or outside click. Reduced motion is honoured by CSS and by framer-motion (`MotionConfig reducedMotion="user"`), and count-up numbers jump straight to their value.
- **Brand** (`src/components/brand.tsx`): the ICHNOVA mark, wordmark and lockup are drawn as SVG from the brand sheet, so they follow the theme (gold on dark, ink on light).
- **Layout** follows Indian spectrum-administration portals doing similar work: DoT [Tarang Sanchar](https://tarangsanchar.gov.in/emfportal) (accessibility bar, one primary action, headline statistics, footer with last-updated) and [Saral Sanchar](https://saralsanchar.gov.in/) (WPC licensing: short service cards, grouped menus), plus NTIA ITS spectrum monitoring pages (breadcrumbs). Hence: grouped sidebar, breadcrumbs, four task cards on Home, secondary charts folded under "Show spectrum trends", and long lists behind tabs. Design reference only; ICHNOVA is not affiliated with these portals.

## Live Monitor (real transmissions)

With `server/app.py` running, the Live Monitor starts real reception sessions through public KiwiSDR receivers (`POST /api/live/start`, events over `GET /api/live/events`): NIST WWV/WWVB, PTB DCF77, NPL MSF, NICT JJY, DWD DDH47 and All India Radio (IQ or medium-wave waterfall). Without the server it replays recorded sessions from `public/live/`, generated by `python ../server/export_live_replays.py` from `recordings/real/` with the same processing code. Deep link: `/app/monitor?rec=<recording id>`.

## Sign in with Google

1. Google Cloud console → APIs & Services → Credentials → OAuth client ID (Web application).
2. Authorised JavaScript origins: `http://localhost:5173` and `http://127.0.0.1:8765`.
3. `cp .env.example .env.local`, set `VITE_GOOGLE_CLIENT_ID`, rebuild.

Without a client ID the Google button is disabled and operator credentials / demo analyst work offline. Identity is kept in the browser only; the ID token is decoded, not verified server-side (prototype).

## Data honesty

Every figure carries a label:

| Label | Meaning |
|---|---|
| BENCHMARK | Real engine output on synthetic benchmark captures (`public/evidence`, `public/benchmark.json`) |
| LIVE | Real engine output on a capture analysed in this session, or on a real over-the-air recording (Live Monitor, Lab) |
| SIMULATED | Monitoring network, stations, incidents, occupancy (`src/lib/sim.ts`) |
| EXPERIMENTAL | Implemented but not validated (e.g. genome similarity) |
| NOT ESTABLISHED | Not built or not validated (ML models, FSK/QAM, RS/LDPC, …) |

Regenerate the real-data layer after changing the receiver: `python ../server/export_frontend_data.py` (needs generated datasets and evaluation results; see the root README).

## Map

`src/assets/india-*.topo.json`: DataMeet India boundaries, Survey of India depiction (CC BY 4.0).
