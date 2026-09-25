# SPACE_ENGINEERING_ROADMAP
**ICHNOVA · SIH26147 — prioritized engineering roadmap for the space extension**
**Status: ROADMAP (2026-09-25). Nothing here is implemented; execution is gated by SPACE_IMPLEMENTATION_GATE.md.**

---

## 1. Feature table

| # | FEATURE | WHY IT MATTERS FOR SPACE | CURRENT STATE | TECHNICAL DIFFICULTY | DEPENDENCIES | TEST STRATEGY | EXPECTED EVIDENCE | RISK OF FALSE CLAIM | SIH DEMO VALUE |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Doppler trajectory generator (pass-shaped class) | The defining space-channel impairment; without it no space claim is testable | NEW — small pure function; neighbours exist (`cfo_drift`, FACT) | Low | none | Unit tests: trajectory continuity, magnitude/rate bounds vs sourced LEO values | Severity-swept vectors for families D/E | Low (it generates test data, makes no claims) | Medium (enables the headline experiment) |
| 2 | SPACE-BENCH generator + criteria + sealed run | The entire space capability statement rests on it | SPECIFIED (SPACE_BENCH_SPECIFICATION.md), not built | Medium | #1; existing bench2 machinery | Pre-registered criteria; calibration split; one sealed run | `SPACE_BENCH_RESULTS.md` — whatever it says | High if shortcuts taken → mitigated by pre-registration discipline | **Very high** (judges can verify) |
| 3 | Carrier-trajectory evidence extraction + reporting | D1–D8 answers; receipt LINK EVIDENCE section; makes drift a *measured* fact | NEW read-out of internal tracked-front-end state (`_track_phase` runs today, output discarded — FACT) | Low-Medium | none (engine touch is additive read-out only) | Unit tests on trajectory extraction; consistency vs injected truth | D1/D2 answers; receipt upgrade | Medium — must be labelled measurement, not oracle | High ("it measures the drift and shows you") |
| 4 | Static-vs-time-varying classification | Distinguishes residual oscillator offset from Doppler — operationally meaningful | NEW (declared model-comparison rule, DOPPLER §D2) | Low | #3 | Unit tests on synthetic static/linear/pass trajectories | D2 answer | Medium (a heuristic — must state its declared rule) | High (one slide: "static vs S-curve") |
| 5 | CCSDS profile view + assumption ledger | "Which assumptions were required" — the honesty centerpiece, space-flavoured | PARTIAL: frame map + randomizers + hypothesis domains all exist (FACT); ledger is a new presentation function | Low | none (pure function over evidence pack) | Unit tests: ledger matches as-run diagnostics; out-of-domain list completeness | Every decode ships its assumption ledger | Low | **Very high** (the trust story) |
| 6 | Space receipt extension (LINK EVIDENCE + SIMULATED provenance) | Third-party verification of space analyses | RECEIPTS EXIST (FACT); additive section | Low | #3, #5 | Chain regression + round-trip + tamper tests (existing patterns) | Verifiable space package | Low | High (tamper demo generalises) |
| 7 | Mission Replay view (SIMULATED) | The 5–7 minute judge narrative; progressive evidence | DESIGN ONLY (SATELLITE_PASS_REPLAY_DESIGN.md) | Medium (UI work) | #1 (capture), #3 (trajectory), existing evidence components | Projection unit tests; two real-run replays (success + degradation) | Judge-demo artifact | High if labels dropped → mandatory SIMULATED banner + provenance | **Very high** |
| 8 | Telemetry Forensics view | Operator-facing space evidence screen (CAPTURE/LINK/CODING/FRAME/DECISION/WHY) | DESIGN ONLY (TELEMETRY_FORENSICS_DESIGN.md) | Medium | #5 | UI tests; measured-numbers-only check | Honest space UX | Low | High |
| 9 | Real spacecraft-resembling RF capture (legal amateur LEO downlink, local station) | The single strongest honest upgrade: one real capture through the whole chain | NOT ESTABLISHED (real-signal validation to date is terrestrial — FACT) | Medium-High (hardware/logistics) | #2 | Full pipeline + receipt on the real capture; published as-is whatever the outcome | §22-style real-signal evidence for space | **High** — needs conservative framing (one capture ≠ validation) | Very high if achieved |
| 10 | Higher-order space modulations (8PSK/16QAM path, GMSK, PCM/PSK/PM) | Real missions use them | GATED EXPERIMENTAL, measured harmful when enabled (Constitution §24 — FACT); classifier-before-gate is the documented critical path | High | Constitution amendment path first | Existing higher-mod sweep harness | Only after F1 sub-weight split + power-condition gate | **Very high** — leave OFF | Medium (judges don't need it) |
| 11 | Orbital pass model (TLE/elevation-aware replay) | Realism for pass geometry | NOT ESTABLISHED — deferred until D1–D8 pass | Medium | #2, #3, experiment success | Geometry unit tests vs MathWorks reference model (S14) | Richer replay realism | Medium (must stay SIMULATED-labelled) | Medium |
| 12 | Packet/transfer-frame semantic parsing (132.0/133.0 fields) | Deeper CCSDS interpretation | NOT SUPPORTED — frame-map layer only today (FACT) | Medium-High | #5 | Semantic unit tests against standards examples | Field-level decode claims | Medium (scope discipline: only if frames support it) | Medium |

## 2. Classification

**P0 — essential (build first):**
- #1 trajectory generator → #2 SPACE-BENCH (spec already pre-registered) → #3 trajectory evidence → #4 classification.
- Rationale: this sequence *produces the evidence* the space claim stands on. Nothing else on this list can be honestly claimed without it.

**P1 — strong extension:**
- #5 CCSDS profile + ledger, #6 receipt extension, #7 Mission Replay, #8 Telemetry Forensics.
- Rationale: presentation and packaging of evidence that P0 generates; large demo value, contained risk, no engine-constant changes.

**P2 — optional:**
- #9 real capture attempt, #11 orbital model, #12 semantic parsing.
- Rationale: valuable but hardware/scope-dependent; each carries specific framing risks that its own row names.

**DO NOT BUILD (feature creep, prohibited, or measured harmful):**
- Enabling 8PSK/16-QAM in the default path (#10) — measured harm on record; Constitution path exists, not ours to shortcut.
- Generic CNN/ResNets, LLM interpretation, "AI space classifier" — prohibited (firewall), and epistemically wrong for this project.
- Fake tracking, fake ISRO data, fake ground-station networks, mission-control aesthetics, government branding.
- Confidence sliders/percentages not derived from exact statistics.
- A "universal space protocol decoder" — the catalogue-bounded refusal behaviour *is* the product.

## 3. Sequencing and gates

```
GATE (SPACE_IMPLEMENTATION_GATE.md approved)
  └→ P0: #1 → #2 → #3 → #4        [produces SPACE_BENCH_RESULTS.md + D1–D8 answers]
        └→ P1: #5, #6, #7, #8       [parallelizable; UI + presentation over P0 evidence]
              └→ P2: #9 → #11/#12   [only if scope + hardware allow; framing rules in row]
```

Every P0/P1 row lists its test strategy — no feature ships without the tests in its row, and the invariants in SPACE_IMPLEMENTATION_GATE.md §5 hold throughout.

**END OF ROADMAP**
