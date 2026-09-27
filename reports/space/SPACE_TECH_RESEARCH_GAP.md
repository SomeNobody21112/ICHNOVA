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
| Time-varying Doppler **without** TLE/a-priori knowledge | Static-CFO front ends fail; phase must be tracked adaptively — and, as now measured, tracking alone is not sufficient | `_track_phase` coherence-adaptive tracking exists (FACT); **its limits are now MEASURED rather than unmeasured**: 54 wrong payloads in 96 time-varying-carrier captures — §3a and `DOPPLER_FAILURE_ANALYSIS.md` |
| Distinguishing "signal with no catalogue structure" from "structure below the evidence floor" | Semantics of SIGNAL_NO_CODE vs UNKNOWN under low SNR | sufficiency.py ACHIEVABLE/IMPOSSIBLE_IN_DOMAIN (FACT); space-domain calibration missing |
| Adversarial/aliasing risk under new impairment classes | Every new channel class re-opens the false-accept question | bench-v2 null sets exist for exactly this discipline (FACT); space null sets not built |
| Pass-geometry realism vs honesty | Simulating an 8-min pass must not become "fake mission control" | SIMULATED labelling regime (DESIGN PROPOSAL in firewall) |

## 3a. THE PROJECT'S STRONGEST RESEARCH FINDING (measured 2026-09-25)

The gap named in §3 row 1 was hypothetical when this document was written. It is no longer hypothetical. It is measured, and it is the most transferable result the space extension has produced:

> **Static-carrier blind inference does not automatically generalize to time-varying-carrier conditions.**

**The measurement** (`DOPPLER_EXPERIMENT_RESULTS.md`, 192 pre-registered deterministic vectors): a signal family with 16/16 sealed recall under a static carrier produced, under a carrier that moves during the capture, **54 wrong payloads in 96 captures** — while making **0 wrong structural claims in all 192**. Controls: 0 wrong payloads in 96.

**Why this matters technically, beyond this project:**

1. **It separates two properties that are routinely conflated.** "Can the system identify the code?" and "can the system be trusted with the bits?" are different questions with different failure modes. A parity/syndrome structural test is *invariant* to the very error a moving carrier introduces: for a code whose generators have odd weight the complement of a codeword is a codeword, so a segment-wise polarity pattern satisfies the test inside each segment. Structural evidence can therefore stay overwhelming (log10 p −14.8 to −29.7 against bars near −5) while the payload becomes unusable. **Any** blind-inference system that accepts on a structural statistic and then publishes a decoded payload inherits this gap, whether or not its authors have measured it.
2. **It shows where a validated benchmark stops validating.** bench-v2's `cfo_drift` class reaches 2×10⁻⁷ cyc/sample². The mildest *treated* cell in the Doppler experiment is 3.7×10⁻⁶ — about 18× that — and the harshest is 375×. A benchmark is a statement about the conditions it contains; generalising past them is an assumption, and here the assumption was wrong in a specific, reproducible way.
3. **It identifies a missing evidence channel, not just a missing feature.** The engine already computes payload-side scores (soft path metric, hard re-encode consistency) and uses them only to break a polarity tie. The failure is not that the system lacks the information — it is that the information never reaches the verdict. That is an architectural observation with a cheap first remedy (publish the reliability) and an expensive second one (gate on it).
4. **It is a falsification result produced by the project's own discipline.** Criteria pre-registered before the first vector, one run, published as-is, no threshold moved. The finding exists *because* the method was set up to allow a negative answer.

**KNOWN (MEASURED FACT):**
- A time-varying carrier causes measured payload-reliability failures in the tested setup: 54/96 treated, 0/96 control, flat across Es/N0 12/9/6 dB, at drift rates 18×–375× the previously benchmarked class.
- Structural identification, modulation inference and out-of-bound refusal all survive those same conditions.
- Phase tracking helps materially (11 correct decodes above `TRACK_MIN_SYMBOLS` against 0 below it) and does **not** convert wrong answers into refusals (25 wrong payloads remain above the threshold).

**UNKNOWN (explicitly NOT established):**
- **The exact minimal algorithmic change required to eliminate those failures.** Whether it is per-block CFO re-estimation, piecewise-linear phase correction, LLR re-scaling, a payload-reliability gate, or a combination — unknown.
- Which of the six candidate mechanisms (`DOPPLER_FAILURE_ANALYSIS.md` §7) is operating. **ROOT CAUSE NOT ESTABLISHED.**
- Where the boundary lies between 2×10⁻⁷ and 3.7×10⁻⁶ cyc/sample² — an 18× span never measured.
- Whether any remediation can be had without costing static-carrier recall, which is the property the project's existing evidence rests on.

The decisive next measurement — ideal ground-truth carrier correction vs estimated correction vs none — is designed in `DOPPLER_REMEDIATION_EXPERIMENT.md` and has not been run.

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
- "Space-ready" — never claimable, and since 2026-09-25 **contradicted by measurement** for the payload half of the claim (SPACE_CLAIM_FIREWALL.md §2a).
- "Doppler robust", "handles satellite Doppler", "decodes telemetry during a pass" — forbidden on **measured** grounds, not merely for want of validation.
- Any live/fake ISRO data, ground-station network, or mission-control pretence — prohibited (SPACE_CLAIM_FIREWALL.md).

## 6. Experiments required before stronger claims

| # | Experiment | Unlocks | Defined in |
|---|---|---|---|
| E1 | Sealed SPACE-BENCH (families A–J) | The space-relevant capability statement itself | SPACE_BENCH_SPECIFICATION.md |
| E2 | Doppler trajectory experiment — **RUN 2026-09-25, FAILED its headline criterion** | Unlocks **nothing**: the claim "tracks time-varying CFO without a-priori knowledge" is now **forbidden**; what it established is a boundary | DOPPLER_EXPERIMENT_RESULTS.md, DOPPLER_FAILURE_ANALYSIS.md |
| E2b | **Mechanism diagnostic** `SPACE-DOPPLER-MECH-01` (ideal vs estimated vs no carrier correction) | Identifies the mechanism — a precondition for any remediation. **Not yet run** | DOPPLER_REMEDIATION_EXPERIMENT.md |
| E3 | Adversarial wrong-hypothesis family (E1-I) | "A plausible wrong space-link hypothesis does not produce a false decode" | SPACE_BENCH_SPECIFICATION.md §I |
| E4 | Simulated Mission Replay with honest labels | A judge-demonstrable progressive-evidence story | SATELLITE_PASS_REPLAY_DESIGN.md |
| E5 | One real RF capture of spacecraft-resembling telemetry (e.g. an amateur LEO downlink recorded legally at a local station) | The single strongest honest upgrade over pure synthesis | SPACE_ENGINEERING_ROADMAP.md P2 |

**Verdict on the research question:** the direction is **technically meaningful** — not because the ingredients are new, but because the *epistemic product* (verified blind inference with refusals and receipts) is unserved in the surveyed space-tooling landscape, and ICHNOVA's architecture already embodies it. The extension is a **validation and adaptation problem** (space channels, space-relevant null sets, honest labelling), not a redesign — INFERENCE, conditional on E1–E3.

**END OF GAP ANALYSIS**
