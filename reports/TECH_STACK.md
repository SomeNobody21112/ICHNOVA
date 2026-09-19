# Tech Stack, User Flows & Workflows — Complete Brief

**Date:** 2026-09-17 · **Scope:** `src/` (engine), `server/` (web tier), `frontend/` (operator console), quality/delivery infrastructure, end-to-end user flows and development workflows

**Verdict:** a deliberately minimalist, two-language stack — Python + NumPy for all signal intelligence, a zero-framework Python web tier, and a modern React 19 SPA. Roughly **4,300 LOC of Python engine/server** and **5,200 LOC of TypeScript frontend**, with just **two Python dependencies total**.

---

## Part I — Tech Stack

### 1. Signal-processing engine (`src/` — Python 3.11)

| Layer | Detail |
|---|---|
| **Language** | Python 3.11 (pinned by CI) |
| **Dependencies** | **numpy 2.4.2, scipy 1.17.0 — that is the entire `requirements.txt`** |
| **DSP core** | `analyze.py` (symbol-rate spectrum, matched filter, M-power cumulants, LLRs), `fec.py` (vectorized soft-decision Viterbi K7/K5/K3, block interleaver), `blind_id.py` (code catalogue + dual-code syndrome sign test, Bonferroni-corrected), `pipeline.py` (blind search orchestrator) |
| **Real-signal receivers** | `timecodes.py` (WWV/WWVB/DCF77/MSF/JJY), `fsk.py` (RTTY/ITA2, CHU), `broadcast.py` (AM), `realsig.py` (one entry point over every receiver) |
| **Data layer** | No database — raw IQ `.wav`/`.npz` files + JSON sidecars; deterministic regeneration from seed via `generate.py` |

The interesting choice: no GNU Radio, no SDR framework, no machine learning. Everything is hand-derived estimation theory implemented directly on NumPy arrays — Viterbi, cumulant classifiers and CFO estimation are built from scratch and verified against exhaustive maximum likelihood (see `PROGRESS.md`, `reports/BASELINE_HARDENING_REPORT.md`).

### 2. Web tier (`server/` — no framework at all)

- **HTTP:** stdlib `http.server.ThreadingHTTPServer` with a hand-rolled router — REST endpoints, static serving of the built SPA with fallback. No Flask/FastAPI/Django anywhere in the import graph.
- **Live updates:** hand-implemented **Server-Sent Events** (queue + chunked streaming) for the Live Monitor; `live.py` processes KiwiSDR streams incrementally.
- **External RF I/O:** `kiwi.py` — a **stdlib websocket client** for public KiwiSDR receivers (no `websocket-client`/`aiohttp` dependency).
- **State:** in-memory queues + JSON files on disk; uploads go through `modem.load_wav` directly to the engine.

### 3. Frontend — ICHNOVA operator console (`frontend/` — React 19 + Vite 8)

- **Core:** React 19.2, TypeScript 6.0, Vite 8.3, react-router 7 — current-gen, all recent majors.
- **UI/UX:** framer-motion (animation), IBM Plex font family via `@fontsource`, hand-written CSS (no Tailwind or component library).
- **Visualization:** d3-geo + topojson-client (station/world maps), custom SVG/canvas components for waterfalls and evidence chains.
- **Auth:** `@react-oauth/google` (Google Identity) — client-side OIDC; operator-credential sign-in also supported. Setup in `frontend/README.md`.
- **Linting:** oxlint (not ESLint). Bundle: ~729 KB JS (232 KB gzipped).

### 4. Quality & delivery infrastructure

- **Tests:** pytest — 30 tests: engine round-trips plus **regression on committed real government-transmission recordings** (the fixtures double as demo data).
- **CI:** GitHub Actions — tests, deterministic dataset regeneration, sealed 30/30 benchmark gate, frontend build.
- **Ops surface:** zero external services, no Docker, no database, no server-side secrets. One Python process; the frontend is pre-built static files.

---

## Part II — User Flows

### Console page map (13 routes)

| Route | Page | Purpose |
|---|---|---|
| `/` | Landing | Public hero, evidence-instrument illustration, six-scene walkthrough entry, sign-in |
| `/app/command` | Command Center | RF observability overview |
| `/app/monitor` | Live Monitor | Real transmissions via KiwiSDR + offline replays |
| `/app/analysis` | Analysis | Field capture workflow (upload → decision) |
| `/app/signals` | Signals | Library & evidence (detail view with `?tab=hypotheses` / `?tab=chain`) |
| `/app/review` | Review Queue | Human-in-the-loop triage of non-decoded signals |
| `/app/incidents` | Incidents | Investigations |
| `/app/spectrum` | Spectrum Map | Spectrum intelligence |
| `/app/genome` | Signal Genome | Fingerprints & similarity |
| `/app/intelligence` | Intelligence | Cross-signal patterns (`?view=scale`) |
| `/app/reports` | Reports | Evidence packages |
| `/app/system` | System | Architecture, quality, audit |
| `/app/lab` | Experiment Lab | Research & benchmark (flagged DEV) |

A **Field / Regional / National** segmented control re-scales monitoring-network views. The top bar shows engine health (`ENGINE READY` vs `ENGINE OFFLINE · REPLAY`) and an IST clock.

### Flow A — First-time visitor → operator

1. Land on `/` (public). The pitch leads with the platform's question: *"What does the AI think this signal is?"* vs *"What evidence supports this signal interpretation?"*
2. **Six-scene walkthrough** (launchable any time from the top bar) drives the narrative by navigating to real pages, each a live view: JJY replay → Analysis upload → hypothesis scatter (tens of thousands tested) → evidence chain → an honest UNKNOWN (short capture, refusal to guess) → national-scale intelligence.
3. **Sign in** — Google OIDC or operator credentials. Session menu shows role, station, and the data-provenance legend.

### Flow B — Analyst: capture → decision (the core engine flow)

1. **Analysis** page: operator supplies a `.IQ`/`.wav` capture (own upload, a bundled benchmark sample from `/samples/`, or a committed real recording) with metadata.
2. `POST /api/analyze` streams the file to the local engine, which runs blind: detection → symbol-structure search → CFO estimation → structured FEC hypothesis search (rate × modulation × rotation × code × interleaver).
3. The decision is one of exactly three outcomes: **DECODED** (with payload), **SIGNAL_NO_CODE** (signal present, no provable code), **UNKNOWN** (no evidence). There is no "best guess" path — restraint is a feature.
4. The result lands in the **Signals** library. The detail view exposes the full evidence chain (presence → structure → parity → multiple-testing correction → structural consistency) and every individual hypothesis that was tested.
5. Signals that decode or warrant attention can be pushed to the **Review Queue** (human in the loop) and folded into **Incidents** for investigation.

### Flow C — Operator: live reception

1. **Live Monitor** lists the station catalogue (`GET /api/live/stations`): WWV, WWVB, DCF77, MSF, JJY, DDH47, AIR.
2. `POST /api/live/start?station=<key>` opens a KiwiSDR session; the browser subscribes to `GET /api/live/events?session=…` (SSE) and watches the same blind processor work incrementally: waterfall rows, one symbol per received second, time digits establishing, final blind analysis. The capture is saved as a recording.
3. **Replays:** committed recordings are re-processed by the same `LiveProcessor` (`server/export_live_replays.py` → `/live/*.json`), so the Monitor demonstrates identically offline — provenance-labelled, never passed off as live.

### Flow D — Intelligence views (clearly-labelled simulated layer)

Spectrum Map, Signal Genome, Intelligence and Command Center extend the real evidence records into monitoring-network visuals. Every such element carries a provenance tag — **BENCHMARK / LIVE / SIMULATED / EXPERIMENTAL / NOT ESTABLISHED** — visible in the session menu; the labelling is part of the product's honesty contract, not a footnote.

### Flow E — Evaluator: Experiment Lab

`/app/lab` surfaces the measured numbers (from `benchmark.json`, each figure linked to its source result file): sealed 30/30, train 63/100, null-set false-accept rates, real-transmission decodes with GPS verification, 3–4× performance results — plus tabs for Real transmissions, Performance and the Research Landscape.

---

## Part III — Workflows

### Runtime data flow

```
Public KiwiSDR receivers          Operator upload (.IQ/.wav)
        │ websocket (kiwi.py)              │ POST /api/analyze
        ▼                                  ▼
   server/live.py  ──SSE──►  Browser    server/app.py handler
        │                                    │
        ▼                                    ▼
   ┌──────────────────── src/ engine ────────────────────┐
   │ realsig.py → timecodes/fsk/broadcast   pipeline.py  │
   │   (real transmissions)                  (blind PSK  │
   │ live.LiveProcessor (incremental)         FEC search) │
   └──────────────────────┬──────────────────────────────┘
                          ▼
        decision (DECODED / SIGNAL_NO_CODE / UNKNOWN)
        + evidence pack (JSON) → recordings/, results/
                          │
                          ▼
        frontend/dist (React SPA) — evidence chain UI,
        hypotheses scatter, live monitor, experiment lab
```

### Offline data/export workflow (feeds the console)

`server/export_frontend_data.py` regenerates the console's real-data layer from engine outputs — no hand-typed numbers anywhere:

```
python src/generate.py sealed|train      # deterministic datasets from seed
pytest tests + sealed_test.py + eval/*   # measured results → results/
python server/export_frontend_data.py    # → frontend/public/evidence/<id>.json
                                         #   frontend/public/samples/*
                                         #   frontend/public/benchmark.json
python server/export_live_replays.py     # → frontend/public/live/*.json (replays)
cd frontend && npm run build             # dist/ with data baked in
python server/app.py                     # serve on 127.0.0.1:8765 (LAN: --host 0.0.0.0)
```

### Real-signal capture workflow (field → regression fixture)

```
python server/kiwi.py --freq-khz 40 --seconds 185 --near 37.37,140.85 --out jjy.npz
python server/make_recording.py jjy.npz --id my-jjy --station JJY --out-rate 1500
    # → recordings/real/my-jjy.wav + GPS sidecar
python -m pytest -q tests/test_realsig.py   # new recording joins CI regression
python server/record_band.py …              # waterfall census (e.g. AIR MW band)
```

### CI/release workflow

GitHub Actions on push: `pytest tests` (30) → regenerate sealed set (seed 99000) → `sealed_test.py` gate (must be 30/30, 0 false accepts) → frontend build. Branch history: work lands on `baseline-hardening`, CI-gated, then fast-forwarded to `main` (currently `d5c557f`); no force pushes, history is linear from `main`'s perspective.

### LAN demo workflow (as currently deployed)

`python server/app.py --host 0.0.0.0 --port 8765` (detached, PID logged) + one inbound firewall rule scoped to LocalSubnet; visitors use `http://<LAN-IP>:8765`. The API is authenticated, so visitors sign in with a demo account; set `ICHNOVA_SECRET_KEY` first so sessions survive a restart. There is still no TLS, so traffic is readable on the LAN — listed as a hardening item below.

---

## Part IV — Assessment

**Strengths**

- **Auditability is architectural:** with two dependencies and no framework magic, every decision the engine makes is traceable to code readable in an afternoon — which matches the project's "evidence-first" thesis (rejecting unprovable decodes).
- **Portability:** `pip install numpy scipy` + `npm run build` is the whole install story; runs on any machine with Python 3.11, no DB or services to host.
- **Performance where it matters:** the numpy-vectorised syndrome scan delivered 3–4× speedups without adding Cython/Rust complexity (`reports/PERFORMANCE_REPORT.md`).
- **Honesty by design:** three-outcome decision model, provenance tags on every visual, restraint (UNKNOWN) demonstrated as a feature in the walkthrough.

**Trade-offs / risks**

- `http.server` is fine for a demo console but not production-grade (no TLS, no HTTP/2, limited concurrency model) — a rewrite target (e.g. FastAPI) if this ever becomes a deployed product.
- Single-process, in-memory session state: one analysis at a time scales, many concurrent users will not.
- Strictly pinned numpy/scipy versions keep reproducibility but need deliberate bumps.
- No TLS — the API is authenticated server-side (scrypt passwords, signed session tokens, per-endpoint role permissions, rate limiting), but `http.server` terminates no TLS, so anything exposed beyond a trusted LAN needs a proxy in front. Google sign-in remains a prototype path: its token is decoded in the browser and is not verified server-side.

**Through-line:** the stack looks "small", but every choice serves the demo's core argument — a receiver that refuses to guess needs so little infrastructure that **absence of framework is itself the evidence** of a well-understood system.
