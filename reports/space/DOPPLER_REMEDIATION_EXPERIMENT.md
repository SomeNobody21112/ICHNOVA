# DOPPLER_REMEDIATION_EXPERIMENT
**ICHNOVA · SIH26147 — `SPACE-DOPPLER-MECH-01`: the mechanism-identification experiment (DESIGN ONLY)**
**Status: EXPERIMENT DESIGN (2026-09-25). Nothing implemented. No production file touched. No correction written.**

**The purpose of this experiment is NOT to make a benchmark pass.** It is to determine *which* mechanism produced the failure measured in `DOPPLER_EXPERIMENT_RESULTS.md`, so that any later remediation is aimed at a cause rather than a symptom. A design that could only ever confirm the fix its author already wants is not a diagnostic — this one is written to be able to conclude "the mechanism is still not established".

Prior result being diagnosed (sealed, never re-scored): 54 wrong payloads beneath true structural claims in 96 time-varying-carrier captures; 0 in 96 static controls; 0 wrong structures in 192. Candidate mechanisms **H1–H6** are defined in `DOPPLER_FAILURE_ANALYSIS.md` §7 and referenced here by number.

---

## 1. Independence and preservation (hard constraints)

| Constraint | Value |
|---|---|
| Experiment ID | `SPACE-DOPPLER-MECH-01` |
| New dataset namespace | `data/space_bench/doppler_mech/` — **never** `data/space_bench/doppler/` |
| New criteria file | `eval/space_doppler_mech_criteria.json`, committed **before** the first vector exists |
| New runner | `eval/space_doppler_mech.py` (may import the sealed experiment's *trajectory function* — that function is the shared definition of the impairment and must not be redefined) |
| New rows | `results/space_doppler_mech_rows.jsonl` |
| Sealed predecessor | `SPACE-DOPPLER` (192 vectors, manifest `f9823ef5…`): **read-only, never regenerated, never re-scored, never overwritten.** Its failure is the evidence this experiment exists to explain |
| Production files | **Unchanged.** `src/`, `server/`, thresholds, acceptance bars, bench-v1, bench-v2, frontend, deployment — all untouched by this experiment |
| Oracle discipline | The ideal-correction arms are **evaluation-only**, passed the way `eval/ladder.py` already passes ground truth (`_oracle`), and must never be reachable from a production path |

## 2. Factors

The sealed experiment varied one thing (the trajectory) and measured the verdict. This one varies **what the receiver is allowed to know and do about the carrier**, holding the signal fixed.

### 2.1 Correction arm — the factor that carries the experiment

| Arm | What the receiver gets | Hypotheses it addresses |
|---|---|---|
| **A — no tracking** | Tracked front ends suppressed; static CFO estimation only | Baseline: how much failure exists before tracking is involved at all (H5, and the floor for H1) |
| **B — existing tracking** | Exactly today's engine, unmodified | The condition already measured; reproduces the sealed result in the new namespace as a sanity anchor |
| **C — ideal ground-truth carrier correction** | The injected `f(t)` removed from the capture *before* analysis (oracle) | **THE DECISIVE ARM.** If payloads come back correct, the failure is carrier estimation (H1/H2/H3). If they do not, it is decoding under non-stationary conditions (H4/H6) |
| **D — estimated carrier correction** | A declared estimator (per-block CFO from the x²/x⁴ line, no ground truth) applied as a pre-correction | Separates "the information is recoverable from the samples" from "ideal knowledge was required" |
| **E — piecewise correction granularity** | Ideal correction applied piecewise-constant at block lengths {64, 32, 16, 8}, and piecewise-linear | **H2** directly: is the staircase itself the error source? |

**The decisive comparison, fixed before any data exists: A vs B vs C vs D.** Everything else in this design is subordinate to it.

### 2.2 Stress factors (crossed with the correction arm, kept deliberately small)

| Factor | Levels | Why this factor |
|---|---|---|
| Trajectory class | `static`, `linear`, `pass` | `zero` is dropped: the sealed run measured 48/48 correct, so it carries no information here |
| Drift rate | 6 levels spanning **2×10⁻⁷ → 7.5×10⁻⁵** cyc/sample², logarithmically | **Maps the unmeasured gap** between bench-v2's largest `cfo_drift` and the sealed experiment's mildest treated cell — an 18× hole in the evidence |
| Symbol count | 256, 412, 1200, 2400 | Straddles `TRACK_MIN_SYMBOLS = 512` twice, so the tracking threshold's effect is separable from length itself (**H5**) |
| Es/N0 | 12, 9, 6 dB | Confirms or kills a noise interaction; the sealed run found none |
| Block length | as in arm E | **H2** |
| Reps | 2 | Deterministic, seed-derived |

Scale: the full cross is deliberately not run. The pre-registered grid is **arms A–D × 3 trajectories × 6 drift rates × 2 lengths (412, 1200) × 2 Es/N0 (12, 6) × 2 reps = 576 vectors**, plus arm E as a **focused sub-study** (ideal correction only, 5 granularities × 3 drift rates × 2 reps = 30). Runtime estimate from the sealed run's 1.35 s/file: ~15 minutes.

## 3. What each measurement must record

Per vector, beyond the sealed experiment's fields: correction arm, injected trajectory and drift rate, applied correction and its granularity, verdict, payload BER, `agreement`, `path_metric`, `consistency`, F2 `log10_p` and its bar, accepted sps vs true sps, whether a tracked front end was present, and runtime. The three payload-side scores are recorded **as observations on a new dataset** — which is what would make them usable evidence, unlike their post-hoc appearance in `DOPPLER_FAILURE_ANALYSIS.md` §4.1.

## 4. Pre-registered decision table (the point of the design)

Each row is written before the data exists and names what the outcome *means*, so the result cannot be re-narrated afterwards.

| Observation | Conclusion it licenses | Mechanism verdict |
|---|---|---|
| Arm **C** restores correct payloads at essentially all drift rates; arm B does not | The information survives the channel; the engine's **carrier estimation** is the failing stage | H1/H2/H3 supported; H4/H6 weakened |
| Arm **C** does *not* restore correct payloads | Removing the carrier exactly is insufficient — the failure is in **decoding / soft-metric behaviour**, not estimation | H4/H6 supported; H1/H2/H3 largely excluded |
| Arm **D** ≈ arm **C** | A realisable estimator closes the gap; remediation becomes a front-end change with a measurable target | Analysis §9 option C/D becomes the candidate |
| Arm **D** ≪ arm **C** | The gap is estimation *accuracy*, not estimation *form*; a better estimator is required and refusal (option B) is the honest interim | Option B first |
| Arm **A** ≈ arm **B** | Tracking contributes nothing at these rates; its role in the failure is incidental | H5 reframed; tracker not the culprit |
| Piecewise-**linear** (arm E) markedly better than piecewise-constant at the same block length | The staircase is a real error source | **H2 confirmed** |
| No block-length dependence in arm E | The staircase is not the error source | **H2 killed** |
| Failure rate rising sharply where per-block phase advance approaches the M-power ambiguity | Consistent with unwrap slip; still needs the trajectory read-out to confirm directly | H3 supported, not proven |
| `path_metric` / `consistency` separation between correct and wrong payloads **persists on this new dataset** | A payload-reliability signal generalises beyond the sealed dataset — a *precondition* for option B, not a validation of it | Option B becomes designable |
| Separation **does not** persist | The §4.1 observation was dataset-specific; option B loses its basis and must not be built | Option B dropped |
| Any wrong **structure** in any arm | A new and more serious failure than the one under study | STOP; re-scope entirely |

**Explicitly pre-registered as an acceptable outcome:** *the mechanism is not established by this experiment.* If arms C and D both partially restore payloads with no clean pattern across drift rate or block length, the honest conclusion is a further-narrowed unknown, published as such — not a remediation.

## 5. What this experiment does NOT do

- It does **not** implement a payload-reliability gate, a piecewise-linear corrector, or a drift-aware front end. Corrections exist only as **evaluation-side pre-corrections and oracles**, to identify the mechanism.
- It does **not** change any threshold, bar, family weight, `CFO_MAX`, `TRACK_MIN_SYMBOLS` or `F2_AGREEMENT_FLOOR`.
- It does **not** touch bench-v1, bench-v2, the null set, or the real-signal suite. Those are the regression floor any later remediation must clear and must stay uncontaminated.
- It does **not** re-run or re-score the sealed `SPACE-DOPPLER` dataset.
- It does **not** license any space capability claim. A diagnostic produces understanding, not capability.

## 6. Sequencing after the diagnostic

```
SPACE-DOPPLER (done, failed, sealed)
   └→ SPACE-DOPPLER-MECH-01  [this design — diagnostic, no production change]
         └→ mechanism named?
               ├─ NO  → publish the narrowed unknown; remediation stays BLOCKED
               └─ YES → design the remediation, pre-register its criteria, and only then
                        propose the production change for explicit approval, measured against
                        bench-v1 (30/30), bench-v2 (9/9), the null set (0/900) and the
                        real-signal suite — abandoned if it costs static-carrier recall
                          └→ SPACE-DOPPLER-FIX-01: a NEW sealed validation on a NEW namespace
```

No step may be skipped, and no remediation may be validated on the dataset that motivated it.

## 7. Approval status

| Item | Status |
|---|---|
| This design | **Written. Not approved. Not implemented.** |
| `eval/space_doppler_mech.py` + criteria file | Not written; criteria must be committed before the first vector |
| Trajectory read-out in `pipeline._track_phase` (needed to *prove* H3, not to run arms A–E) | **AWAITING EXPLICIT APPROVAL** — SPACE_IMPLEMENTATION_GATE.md §9.3 |
| Any production change | **BLOCKED** pending this experiment's result |

**END OF DOPPLER REMEDIATION EXPERIMENT DESIGN**
