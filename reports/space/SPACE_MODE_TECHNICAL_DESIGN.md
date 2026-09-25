# SPACE_MODE_TECHNICAL_DESIGN
**ICHNOVA · SIH26147 — SPACE COMMUNICATIONS MODE (design only, nothing implemented)**
**Status: DESIGN PROPOSAL (2026-09-25). No production code is modified by this document.**
SPACE MODE is an **optional operating profile** over the existing engine — not a redesign. Every step below is tagged `EXISTING` (verified in source this session) / `EXTENSION` (adapt existing code) / `NEW` (new engineering) / `EXPERIMENTAL` / `SIMULATED` / `NOT ESTABLISHED`.

---

## 1. The flow, step by step

```
SPACE LINK CAPTURE → 1. SIGNAL QUALIFICATION → 2. CARRIER/FREQUENCY ANALYSIS
→ 3. MODULATION HYPOTHESES → 4. SYMBOL-RATE/TIMING ANALYSIS → 5. DOPPLER/CFO ANALYSIS
→ 6. FEC/CODING HYPOTHESES → 7. INTERLEAVER ANALYSIS → 8. FRAME SYNCHRONIZATION
→ 9. TELEMETRY STRUCTURE → 10. EVIDENCE VERIFICATION → 11. DECISION → 12. EVIDENCE RECEIPT
```

| # | Step | Current implementation | Required work | Test required | Risk | Build? |
|---|---|---|---|---|---|---|
| 0 | Space-link capture ingestion | `EXISTING` — raw interleaved float32 .iq, `load_iq`; fs provenance tracked (`FS_SOURCES`) | None for synthetic; real SDR captures already flow through (§22 live capture — FACT) | existing suite | none | — |
| 1 | Signal qualification | `EXISTING` — capture-quality gate (`src/quality.py`): clipping, DC, dropouts, I/Q balance; quality is reported **beside** the verdict, never part of it | None | existing | none | — |
| 2 | Carrier/frequency analysis | `EXISTING` — x²/x⁴ spectral-line detection with exact exponential-periodogram null (`pipeline._cfo_candidates`) | None | existing | none | — |
| 3 | Modulation hypotheses | `EXISTING` — BPSK/QPSK searched by default; 8PSK/16-QAM `EXPERIMENTAL`, gated OFF (`SEARCH_HIGHER_MODULATIONS=False`, `_modulation_gates`) | None in Phase 1. Space telemetry at higher orders stays honestly out of scope until the Constitution path (§critical-path: classifier before gate) exists | existing + modulation-aliasing tests | low | Phase 2+ |
| 4 | Symbol-rate/timing | `EXISTING` — y⁴ lag-1 scan over sps 2–20, divisors tested, serial-dependence gate | None | existing | none | — |
| 5 | Doppler/CFO analysis | `PARTIAL EXISTING` — static CFO bounded ±1.25% fs; **linear drift** handled by coherence-adaptive phase tracking `_track_phase` (block chosen by data coherence, ≥512 symbols) — FACT from code; **measured-trajectory reporting is `NEW`** | Extend: report the estimated per-block phase/frequency trajectory as first-class evidence (it already exists internally); feed DOPPLER experiment | new unit tests on trajectory extraction; D1–D7 experiment | drift beyond linear unmeasured — `NOT ESTABLISHED` | **P0** |
| 6 | FEC/coding hypotheses | `EXISTING` — K3/K5/K7 conv via dual-code syndrome sign test; RS; CCSDS concatenated; TC-LDPC — all sealed-validated (bench-v2 9/9; CCSDS chain 10/12; LDPC 8/8 — FACT) | None | existing sealed | none | — |
| 7 | Interleaver analysis | `EXISTING` — all four types (block, diagonal, Forney convolutional, LTE QPP) searched (`INTERLEAVER_TYPES`) | None | existing | none | — |
| 8 | Frame synchronization | `EXISTING` — CCSDS ASM 1ACFFC1D + 64-bit LDPC marker + **blind** constant-field sync detection (exact binomial, Bonferroni over periods) — FACT from `framing.py` | None | existing (`test_catalogue.py`, `test_families.py`) | none | — |
| 9 | Telemetry structure | `PARTIAL EXISTING` — frame map: header columns proven constant/alternating, undetermined columns reported with the frames a decision would need (FACT from framing.py); **randomizer de-whitening exists** (`RANDOMIZERS` standards-verified) | `EXTENSION`: a CCSDS *profile view* that interprets an accepted frame map in 132.0 transfer-frame terms — presentation only, no new inference | new: profile-view unit test (pure function over accepted frame map) | mislabeling risk → CCSDS profile must use the four-level honesty labels | **P1** |
| 10 | Evidence verification | `EXISTING` — structural checks (modulation consistency, block length, soft path floor), multi-hypothesis correction reported (p·M ≤ α), runner-up margin | None | existing | none | — |
| 11 | Decision | `EXISTING` — DECODED / SIGNAL_NO_CODE / UNKNOWN + refusal reasons + sufficiency (ACHIEVABLE / IMPOSSIBLE_IN_DOMAIN) | None | existing | none | — |
| 12 | Evidence receipt | `EXISTING` — SHA-256 hash-chained receipt, CLI + browser verifiers | `EXTENSION`: add space-domain fields (capture provenance = station/antenna/SDR metadata when real; `SIMULATED` marker when synthetic) — small, additive, does not alter chain semantics | existing receipt tests + one new field test | low | **P1** |

## 2. What is deliberately NOT in SPACE MODE

- No orbital mechanics / TLE integration in Phase 1 (Doppler enters as a **measured RF phenomenon**, not an orbit model — the orbital pass model is deferred until the Doppler experiment passes; DOPPLER_EXPERIMENT_DESIGN.md §8).
- No new modulations enabled (8PSK/16-QAM stay EXPERIMENTAL/OFF — Constitution rule).
- No LLM/AI interpretation layer (prohibited — SPACE_CLAIM_FIREWALL.md).
- No autopilot "mission control" behaviour: the operator reads evidence; the system refuses.

## 3. How SPACE MODE is selected

DESIGN PROPOSAL: a capture-level profile flag (like the existing fs-provenance and provenance tags), surfaced in the evidence pack and receipt. It changes **only**: (a) which profile view renders (CCSDS terms), (b) which benchmark domain claims apply. It does **not** change engine constants, thresholds, or family weights — those are Constitution-governed and identical.

## 4. Consistency check against the constitution invariants

SPACE MODE introduces no new hypothesis family (F1–F4 unchanged), no threshold change, no tuning target. SPACE-BENCH results can only *fail* against existing rules, never be tuned into passing — the acceptance policy is pre-registered before any sealed run (SPACE_BENCH_SPECIFICATION.md §3).

**END OF SPACE MODE DESIGN**
