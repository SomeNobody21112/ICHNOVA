# SPACE_TECH_RESEARCH_GAP
**ICHNOVA · SIH26147 — gap analysis: is the space extension technically meaningful?**
**Status: RESEARCH (2026-09-25). Implements nothing.**
Question under test: *"An evidence-first ground-segment layer that can analyze partially unknown spacecraft RF recordings, progressively infer signal structure, test candidate communication hypotheses, and explicitly refuse to decode when evidence is insufficient."*

---

## 1. What is already established technology (so NOT novel)

| Capability | Established by | Label |
|---|---|---|
| CCSDS TM sync + channel coding (ASM, RS, conv, concatenated, LDPC, randomizers) | CCSDS 131.0-B-5; MathWorks reference chains | FACT |
| Known-parameter satellite telemetry decoding at scale | gr-satellites (hundreds of SatYAML decoders), SatNOGS network | FACT |
| Doppler prediction/correction in ground terminals | TLE-based, 10 s steps, standard practice (SmallSat papers) | FACT |
| Generic blind modulation/parameter estimation | URH autofocus; large AMR literature | FACT |
| Discrete tools for every individual step ICHNOVA chains together | GNU Radio ecosystem | FACT |

**Conclusion:** nothing in the *ingredients* is novel. Any document claiming a "novel algorithm" here would be false.

## 2. What is ordinary engineering integration (feasible, unremarkable)

- Ingesting space-shaped IQ (no change — raw float32 already the format).
- Adding CCSDS-shaped synthetic generators (existing `bench2_gen.py` channel machinery covers awgn / phase_noise / cfo_drift / rician / amplitude / timing — FACT from code).
- Exposing the CCSDS profile as an operator-facing view over existing evidence structures (server + frontend already render evidence packs — FACT).
- A SIMULATED pass-replay UI over an existing analysis run (progressive masking of one real engine result — DESIGN PROPOSAL, cheap).

## 3. What is technically difficult (the real engineering)

| Difficulty | Why it is hard | Existing anchor |
|---|---|---|
| Time-varying Doppler **without** TLE/a-priori knowledge | Static-CFO front ends fail; phase must be tracked adaptively | `_track_phase` coherence-adaptive tracking exists (FACT); its limits are unmeasured on true trajectories (GAP) |
| Distinguishing "signal with no catalogue structure" from "structure below the evidence floor" | Semantics of SIGNAL_NO_CODE vs UNKNOWN under low SNR | sufficiency.py ACHIEVABLE/IMPOSSIBLE_IN_DOMAIN (FACT); space-domain calibration missing |
| Adversarial/aliasing risk under new impairment classes | Every new channel class re-opens the false-accept question | bench-v2 null sets exist for exactly this discipline (FACT); space null sets not built |
| Pass-geometry realism vs honesty | Simulating an 8-min pass must not become "fake mission control" | SIMULATED labelling regime (DESIGN PROPOSAL in firewall) |

## 4. What is potentially distinctive about ICHNOVA (and what merely sounds distinctive)

**Distinctive (defensible if SPACE-BENCH validates it):**
- Family-wise-error-controlled *blind* inference over a bounded catalogue with **pre-registered acceptance rules** (bench2_criteria.json records revisions made **before** SEALED existed — FACT).
- Explicit refusal + sufficiency reporting ("more of this signal would settle it: ACHIEVABLE in N s" / "IMPOSSIBLE_IN_DOMAIN") — FACT from sufficiency.py docstring and tests.
- Portable cryptographic evidence receipts verifiable without trusting the system (FACT — receipt.py, verified against a real tamper).
- The **combination**: blind + refusing + auditable + standards-aligned (ASMs/randomizers verified against 131.0-B-5 constants) — INFERENCE.

**Sounds distinctive but is not (do not claim):**
- "Blind decoding" per se (URH does autofocus; the literature is old) — FACT.
- "CCSDS support" per se (every serious ground system has it — ours is *blind identification of CCSDS-shaped structure*, a narrower and honestly describable thing) — INFERENCE.
- "AI/ML-powered space signal intelligence" (the project has no ML by design; claiming it would be false and indefensible) — FACT about the repo.

## 5. What cannot honestly be claimed

- First-of-kind, novel algorithm, patented, superior to commercial/defence ground systems — **never claimed** (those systems are not inspectable).
- Validated on operational spacecraft telemetry — **no real spacecraft capture exists in the project** (FACT).
- "Space-ready" before SPACE-BENCH runs — the entire claim is conditional on the benchmark defined in SPACE_BENCH_SPECIFICATION.md.
- Any live/fake ISRO data, ground-station network, or mission-control pretence — prohibited (SPACE_CLAIM_FIREWALL.md).

## 6. Experiments required before stronger claims

| # | Experiment | Unlocks | Defined in |
|---|---|---|---|
| E1 | Sealed SPACE-BENCH (families A–J) | The space-relevant capability statement itself | SPACE_BENCH_SPECIFICATION.md |
| E2 | Doppler trajectory experiment (E1-D/E as controlled study) | "Tracks time-varying CFO without a-priori knowledge" | DOPPLER_EXPERIMENT_DESIGN.md |
| E3 | Adversarial wrong-hypothesis family (E1-I) | "A plausible wrong space-link hypothesis does not produce a false decode" | SPACE_BENCH_SPECIFICATION.md §I |
| E4 | Simulated Mission Replay with honest labels | A judge-demonstrable progressive-evidence story | SATELLITE_PASS_REPLAY_DESIGN.md |
| E5 | One real RF capture of spacecraft-resembling telemetry (e.g. an amateur LEO downlink recorded legally at a local station) | The single strongest honest upgrade over pure synthesis | SPACE_ENGINEERING_ROADMAP.md P2 |

**Verdict on the research question:** the direction is **technically meaningful** — not because the ingredients are new, but because the *epistemic product* (verified blind inference with refusals and receipts) is unserved in the surveyed space-tooling landscape, and ICHNOVA's architecture already embodies it. The extension is a **validation and adaptation problem** (space channels, space-relevant null sets, honest labelling), not a redesign — INFERENCE, conditional on E1–E3.

**END OF GAP ANALYSIS**
