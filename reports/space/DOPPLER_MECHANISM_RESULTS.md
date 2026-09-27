# DOPPLER_MECHANISM_RESULTS
**ICHNOVA · SIH26147 — `SPACE-DOPPLER-MECH-01`: mechanism diagnostic, measured result**
**Status: EXECUTED AND PUBLISHED AS-IS (2026-09-25). One pre-registered STOP bar fired (§11). No production file was changed.**

> **The result in one sentence. MEASURED FACT.** Removing the injected carrier trajectory exactly, before analysis, eliminated the wrong-payload failure completely — **0 of 96 treated captures** wrong under ideal correction, against **57 of 96** with today's engine and **77 of 96** with tracking ablated — and a **blind** per-block estimator built only from the engine's own published carrier test came within 3 of 96. **ENGINEERING INTERPRETATION:** the failure is dominated by **residual carrier-frequency error that the front end does not model**, not by decoding under non-stationary conditions.

Labels used throughout: **MEASURED FACT** (read off this run) and **ENGINEERING INTERPRETATION / HYPOTHESIS** (inference beyond what was measured).

---

## 1. Objective

Determine *which* mechanism produced the failure measured in `DOPPLER_EXPERIMENT_RESULTS.md` — 54 wrong payloads beneath **correct structural claims** in 96 time-varying-carrier captures, 0 in 96 static controls, 0 wrong structures in 192 — and distinguish carrier-drift/estimation explanations (H1, H2, H3) from decoding-side explanations (H4, H6) and from observation length (H5). The objective was **not** to improve the Doppler result, and `MECHANISM NOT ESTABLISHED` was a pre-registered acceptable outcome.

## 2. Pre-registration reference

| Field | Value |
|---|---|
| Experiment ID | `SPACE-DOPPLER-MECH-01` |
| Design | `reports/space/DOPPLER_REMEDIATION_EXPERIMENT.md` |
| Criteria | `eval/space_doppler_mech_criteria.json`, sha256 `f5f21560aa564bdb…`, committed **before** `eval/space_doppler_mech.py` existed and before any vector was generated |
| Hypotheses under test | H1–H6 of `DOPPLER_FAILURE_ANALYSIS.md` §7 |
| Sealed predecessor | `SPACE-DOPPLER`, manifest `f9823ef5…` — **read-only; not re-run, not re-scored, not overwritten** (§14, §16) |

**Four deviations from the design document, each declared in the criteria file before generation, not chosen afterwards:**

- **DEV-1 — symbol counts.** The design lists {256, 412, 1200, 2400} in its factor table but fixes "2 lengths (412, 1200)" in the sentence that sets the vector count. The count sentence governs: **412 and 1200 symbols**. (An internal inconsistency in the design, reported rather than silently reconciled.)
- **DEV-2 — drift-rate levels.** The design asks for six levels spanning 2×10⁻⁷ → 7.5×10⁻⁵ cyc/sample². **That span is unreachable while the peak offset stays inside the engine's declared search bound**: drift rate ≈ peak × shape constant ÷ N samples, so with peak ≤ `CFO_MAX` the maximum is ≈1.5×10⁻⁵ (linear, 412 symbols) and ≈3.7×10⁻⁵ (pass, 412 symbols). The design's 7.5×10⁻⁵ came from the sealed run's severity-2.0 cell, whose peak lay **outside** the bound and which the engine correctly refused. Holding rates that high would have measured refusal-at-the-bound instead of the mechanism. Resolution: sweep **peak** at six declared severities {0.04, 0.1, 0.2, 0.4, 0.7, 1.0} × `CFO_MAX`, all in bound, and **report the achieved drift rate** (§8). The achieved span, 1.0×10⁻⁷ → 3.8×10⁻⁵, covers the whole previously unmeasured gap between bench-v2's largest `cfo_drift` (2×10⁻⁷) and the sealed run's mildest treated cell (3.7×10⁻⁶).
- **DEV-3 — static under a rate factor.** A static carrier has drift rate 0, so the static class carries the **same peak offset** as its matched treated cell with no variation: a control for peak magnitude, not for rate.
- **DEV-4 — paired design.** 144 distinct captures × 4 arms = the pre-registered **576 analyses**. Every arm sees byte-identical samples, which is what makes the comparison attributable.

## 3. Experiment arms

| Arm | What the receiver got | Implementation (all evaluation-side) |
|---|---|---|
| **A — no tracking** | Today's engine with the tracked front end ablated | `pipeline._track_phase` rebound to return `None` **inside the worker process only**, restored under `finally` with an assert. No file under `src/` modified; a test verifies the ablation bites (0 tracked front ends) and does not leak |
| **B — existing** | Today's engine, unmodified | `analyze_iq(iq)` |
| **C — ideal ground-truth correction** | The injected `f(t)` removed before analysis | `iq × exp(−2πj·cumsum(f_true))`, then the unmodified engine. An evaluation-only oracle; it corrects the **samples**, never the acceptance decision |
| **D — estimated correction (blind)** | A declared estimator using no ground truth | Capture split into `D_BLOCKS = 8` equal blocks; per block, the most significant candidate of the engine's own `pipeline._cfo_candidates`; frequencies assigned to block centres, linearly interpolated, held constant outside; de-rotated. All 144 captures yielded 8 knots |
| **E — correction granularity** | Ideal correction at declared granularities | True trajectory quantised piecewise-**constant** at 64/32/16/8-symbol blocks (the same form `_track_phase` applies to phase) and piecewise-**linear** at 64 |

## 4. Dataset composition

| Field | Value |
|---|---|
| Captures | **144** distinct, `data/space_bench/doppler_mech/` |
| Analyses | **606** = 576 (144 × arms A–D) + 30 (arm E) |
| Manifest | `eval/space_doppler_mech_manifest.json`, manifest sha256 `a152d682a811f973…`, 144 files |
| Grid | 3 trajectories (`static`, `linear`, `pass`) × 6 severities × 2 lengths (412, 1200 symbols) × 2 Es/N0 (12, 6 dB) × 2 reps |
| Transmitter | Continuous rate-½ K=7 convolutional stream, BPSK, sps ∈ {4,6,8}, β ~ U(0.2,0.5) — **identical** to the sealed experiment, so the two are comparable |
| Arm E sub-study | `pass`, long, 12 dB, severities {0.1, 0.4, 1.0}, 2 reps × 5 granularities = 30 |
| Run | 606 analyses in **80 s**; runtime mean **0.76 s**, max **1.58 s** |
| Determinism | **144/144 byte-identical** on regeneration |

## 5. Seeds

`SEED0 = 600000`; each capture's seed is `600000 + index` over the pure-function job list (trajectory × severity × length × Es/N0 × rep). Seeds **600000–600143**. The arm is *not* part of the seed — all arms analyse the same bytes. The namespace is disjoint from the sealed experiment's 500000–500191.

## 6. Scoring definitions (pre-registered)

| Category | Definition |
|---|---|
| `CORRECT_STRUCTURE_CORRECT_PAYLOAD` | DECODED, true code family, true modulation, payload BER < 0.01 |
| `CORRECT_STRUCTURE_WRONG_PAYLOAD` | DECODED, true code family, true modulation, payload BER ≥ 0.01 — **the failure under study; NOT a structural false accept** |
| `WRONG_STRUCTURE` | DECODED with a code family or modulation that is not the transmitted one — a structural false accept, separate and more serious |
| `REFUSED` | `SIGNAL_NO_CODE` or `UNKNOWN` |

BER is `bench2._ber`, imported verbatim — the same function that scored bench-v2's 430-file sealed run and the sealed SPACE-DOPPLER run. The sealed experiment merged wrong structure and wrong payload into one category; this experiment separates them, as its criteria require.

## 7. Results by arm — MEASURED FACT

**Treated captures (`linear` + `pass`), n = 96 per arm:**

| Arm | correct payload | **wrong payload** | wrong structure | refused | wrong-payload rate |
|---|---:|---:|---:|---:|---:|
| **A — no tracking** | 4 | **77** | 1 | 14 | **0.802** |
| **B — existing engine** | 27 | **57** | 0 | 12 | **0.594** |
| **C — ideal correction** | 90 | **0** | 0 | 6 | **0.000** |
| **D — estimated correction** | 88 | **3** | 0 | 5 | **0.031** |

**Static controls (matched peak offset, zero drift), n = 48 per arm:**

| Arm | correct payload | wrong payload | refused |
|---|---:|---:|---:|
| A | 46 | **0** | 2 |
| B | 46 | **0** | 2 |
| C | 45 | **0** | 3 |
| D | 45 | **0** | 3 |

**MEASURED FACT.** A constant carrier offset of the *same magnitude* — up to the full `CFO_MAX` — produces **zero** wrong payloads in every arm. The failure requires the carrier to *move*; peak magnitude alone is harmless. This reproduces the sealed experiment's control result independently, and it is what licenses attributing everything below to drift.

Refusal composition: C and D refuse only as `SIGNAL_NO_CODE` (9 and 8); A and B also produce `UNKNOWN` (10 and 8).

## 8. Results by trajectory and drift condition — MEASURED FACT

**By trajectory (treated, n = 48 per cell):**

| Trajectory | A | B | C | D |
|---|---:|---:|---:|---:|
| `linear` wrong-payload rate | 0.792 | 0.562 | **0.000** | **0.000** |
| `pass` wrong-payload rate | 0.812 | 0.625 | **0.000** | 0.062 |

**By severity, with the achieved drift rate (treated, n = 16 per arm per row):**

| Severity | peak (cyc/sample) | achieved drift rate (cyc/sample²) | A | B | C | D |
|---|---|---|---:|---:|---:|---:|
| 0.04 | 0.00050 | 1.03×10⁻⁷ – 1.51×10⁻⁶ | 0.625 | **0.188** | 0.000 | 0.000 |
| 0.10 | 0.00125 | 3.44×10⁻⁷ – 3.77×10⁻⁶ | 0.938 | 0.438 | 0.000 | 0.000 |
| 0.20 | 0.00250 | 5.17×10⁻⁷ – 7.55×10⁻⁶ | 1.000 | 0.562 | 0.000 | 0.000 |
| 0.40 | 0.00500 | 1.03×10⁻⁶ – 1.51×10⁻⁵ | 1.000 | 0.938 | 0.000 | 0.000 |
| 0.70 | 0.00875 | 2.41×10⁻⁶ – 1.76×10⁻⁵ | 0.625 | 0.750 | 0.000 | 0.000 |
| 1.00 | 0.01250 | 2.58×10⁻⁶ – 3.77×10⁻⁵ | 0.625 | 0.688 | 0.000 | 0.188 |

**MEASURED FACT — the boundary is now mapped, and it starts inside the previously unmeasured gap.** At the mildest level, whose drift rates *include* bench-v2's largest `cfo_drift` (2×10⁻⁷), today's engine already produces **3 wrong payloads in 16** (0.188). The failure does not begin at the 18× point the sealed experiment happened to sample first; it is already present an order of magnitude lower, and rises to 0.938 by severity 0.40. Ideal correction is 0.000 at every level.

## 9. Results by Es/N0 and by capture length — MEASURED FACT

| Condition | A | B | C | D |
|---|---:|---:|---:|---:|
| Es/N0 12 dB (n = 48) | 0.875 | 0.625 | **0.000** | 0.021 |
| Es/N0 6 dB (n = 48) | 0.729 | 0.562 | **0.000** | 0.042 |
| short, 412 symbols — below `TRACK_MIN_SYMBOLS` (n = 48) | 0.729 | 0.729 | **0.000** | 0.042 |
| long, 1200 symbols — above it (n = 48) | 0.875 | 0.458 | **0.000** | 0.021 |

**MEASURED FACT.** Noise is not the driver: the wrong-payload rate is *higher* at 12 dB than at 6 dB in three of four arms. **MEASURED FACT and an internal consistency check:** below `TRACK_MIN_SYMBOLS` arms A and B are identical (0.729 both) — exactly as expected, since no tracked front end exists there to ablate. Above it, ablation costs 0.875 against 0.458, i.e. **tracking roughly halves the failure rate and does not remove it**.

## 10. Ideal vs estimated vs no correction — the critical comparison

| | no correction (A) | existing correction (B) | **estimated, blind (D)** | **ideal, oracle (C)** |
|---|---:|---:|---:|---:|
| wrong-payload rate, treated | 0.802 | 0.594 | **0.031** | **0.000** |
| correct-payload rate, treated | 0.042 | 0.281 | 0.917 | 0.938 |
| refusals | 14 | 12 | 5 | 6 |

**Pre-registered bars, as measured:**

| Bar | Verdict | Measured |
|---|---|---|
| `C_restores` (C wrong ≤ 0.05 **and** C correct ≥ 0.90) | **YES** | wrong 0.000, correct 0.938 |
| `C_does_not_restore` (≥ 0.25) | no | 0.000 |
| `C_partial` (0.05–0.25) | no | 0.000 |
| `D_approaches_C` (abs(D − C) ≤ 0.10) | **YES** | 0.031 − 0.000 = 0.031 |
| `D_far_from_C` (≥ 0.20) | no | 0.031 |
| `A_equals_B` (abs(A − B) ≤ 0.10) | **no** | 0.208 — tracking's contribution is *not* incidental |
| `H2_confirmed` | no | see §13 |
| `H2_killed` (granularity spread ≤ 0.10) | **YES** | spread 0.000 |
| `wrong_structure_stop` (any wrong structure) | **YES — FIRED** | 1, in arm A only (§11) |

**Arm E — ideal correction at declared granularities (`pass`, long, 12 dB, n = 6 each):**

| Granularity | correct | wrong payload |
|---|---:|---:|
| piecewise-constant, 64-symbol blocks | 6 | **0** |
| piecewise-constant, 32 | 6 | **0** |
| piecewise-constant, 16 | 6 | **0** |
| piecewise-constant, 8 | 6 | **0** |
| piecewise-linear, 64 | 6 | **0** |

**MEASURED FACT.** Once the frequency *values* are right, the correction's **form does not matter**: a coarse 64-symbol staircase is as good as per-sample correction. The three arm-D failures are all `pass`, all at severity 1.0 (the steepest drift, up to 3.8×10⁻⁵), each with 8 estimator knots: `pass_0136` (12 dB, short, BER 0.410), `pass_0139` (6 dB, short, BER 0.205), `pass_0143` (6 dB, long, BER 0.024).

## 11. Structural versus payload breakdown — and the STOP bar that fired

**MEASURED FACT.** Across all 606 analyses there was **exactly one** `WRONG_STRUCTURE` outcome, and it occurred **only in the ablation arm**:

| Field | Value |
|---|---|
| Capture | `linear_0084` — `linear`, severity 0.7, 12 dB, long (1200 symbols), true sps 4 |
| Arm | **A — no tracking** (tracked front end ablated) |
| Verdict | DECODED as **`ccsds_tc_ldpc_128_64`, QPSK** — neither is what was transmitted |
| Payload BER | 0.488 |
| Evidence it cleared | F2 log₁₀p −32.4 against a bar of −4.94; agreement 0.740, path_metric 0.879, consistency 0.875; 0 tracked front ends |
| The **same capture** under the other arms | **B**: correct structure, wrong payload (BER 0.061) · **C**: correct structure, correct payload · **D**: correct structure, correct payload |

**The pre-registered bar `wrong_structure_stop` says: any `WRONG_STRUCTURE` in any arm → STOP and re-scope. It fired, and it is reported as fired.** Three facts bound what it means, and none of them cancels it:

1. **MEASURED FACT.** It did **not** occur in any shipped configuration: arm B (today's engine) produced **0 wrong structures in 144** captures, as did C and D.
2. **MEASURED FACT.** It occurred in a configuration that exists only inside this harness — the tracker ablated — and the same capture is handled correctly by the shipped engine and perfectly by both corrections.
3. **ENGINEERING INTERPRETATION.** This is evidence that the phase tracker **also protects the structural claim**, not only the payload: removing it let a wrong code family *and* a wrong modulation through the acceptance path at a strongly significant p-value. Arm A is therefore disqualified as any kind of remediation direction — which is useful to have measured — but a single occurrence is one capture, not a characterised failure mode.

**Consequence, per the STOP rule:** this finding is documented here and no further step is taken on it. Whether it warrants its own experiment (a structural-integrity study of the untracked front end) is a decision for the project owner, not something to be folded silently into this diagnostic.

**The four-way breakdown, all arms pooled (606 analyses):** 391 correct-structure/correct-payload, 137 correct-structure/wrong-payload, **1** wrong structure, 77 refusals.

## 11.1 ADDENDUM 2026-09-26 — forensic analysis of the STOP-bar case (post-hoc, read-only)

Requested follow-up on `linear_0084`. **Nothing was regenerated, re-scored or modified**: §11's measurements and the original scored rows stand exactly as published. Two post-hoc artefacts were produced, both read-only over the existing capture set: a per-arm forensic dump of this capture, and `results/space_doppler_mech_f4_margins.jsonl` (F4 margins for all 144 captures under arms A and B).

### 11.1.1 Ground truth of the capture (from its own `.gt.json`)

| Field | Value |
|---|---|
| Trajectory | `linear`, −0.00875 → +0.00875 cyc/sample (severity 0.7 × `CFO_MAX`), **max drift rate 3.62×10⁻⁶ cyc/sample²**, 4840 samples |
| Peak inside the search bound? | **Yes** — `outside_search_bound` false |
| Symbol length | **1200 symbols** (594 info bits, rate-½ K=7), above `TRACK_MIN_SYMBOLS = 512` |
| Es/N0 | **12 dB** (the cleanest noise level in the grid) |
| Modulation / code / interleaver | **BPSK / `k7_continuous` / none** (continuous stream), sps 4, β 0.2334 |
| Seed | 600084 |

### 11.1.2 What arm A actually saw — MEASURED FACT

| Family | M | best log₁₀ p | bar | accepted |
|---|---:|---:|---:|---|
| F1 burst code | 210 | −2.10 | −4.62 | no |
| **F2 stream code** | 88 | **−32.37** | −4.94 | **YES — and it accepted the TRUE code**: `conv_k7_r12_171_133_continuous`, BPSK, sps 4, offset 0, g2 not inverted, agreement 0.7396 |
| F3 frame | 12,748,780 | −6.03 | −9.80 | no |
| **F4 block code** | 3,072 | **−6.252** | **−6.19** | **YES** — `ccsds_tc_ldpc_128_64`, offset 63, 18 codewords, **converged codewords 0 of 18** |

Front end: 33 front ends, **0 tracked** (the ablation), CFO −0.00579, rotation π/2. `structure.layers` = [`stream_code` `conv_k7_r12_171_133_continuous` (agreement 0.7396), `block_code` `ccsds_tc_ldpc_128_64` (offset 63)].

### 11.1.3 Why the one-line verdict said `ccsds_tc_ldpc_128_64` / QPSK — MEASURED FACT (from `src/pipeline.py`)

The verdict resolution order is F1 → **F4** → F2: when the block-code family accepts, `result['code']`, `result['payload_bits']` and the reported modulation / sps / cfo are taken from **F4 and its front end**. So the summary fields reported the *deepest accepted layer* (LDPC, on a QPSK front end) while `structure.layers[0]` still named the **true** stream code. The scorer reads the summary `code`, which is why the capture scored `WRONG_STRUCTURE`.

**This refines §11 without softening it.** The published verdict *was* a wrong structure — a reader of `code` and `modulation` would have been told LDPC/QPSK, which is false. What the forensic detail adds is that the engine's layer stack simultaneously recorded the correct stream code, so the failure is a **marginal second-layer accept plus a summary-field convention**, not a wholesale misidentification.

### 11.1.4 The three contributing facts — none of them inferred beyond the measurement

1. **Tracking-dependent trigger.** Without tracking the F2 payload is garbage: agreement 0.7396 / `path_metric` 0.8787 / `consistency` 0.8748, against 0.8965 / 0.9672 / 0.9808 in arm B and 0.9967 / 0.9999 / 0.9975 in arm C. The bits handed to the frame and block searches are largely wrong.
2. **A razor-thin F4 accept.** −6.252 against a bar of −6.19: cleared by **0.066 log units** (a factor of 1.16).
3. **No convergence requirement in the F4 accept path.** `pipeline._block_code_family` guards against degenerate codewords (before and after decoding) and anchors polarity against an accepted marker, but **nothing requires any codeword to converge**. An accept with **0 of 18** converged codewords is publishable today.

### 11.1.5 Intermediate evidence on the same capture in arms B, C, D — MEASURED FACT

| Arm | Outcome | F2 log₁₀ p / agreement | F4 best vs bar | Final code |
|---|---|---|---|---|
| B (shipped) | correct structure, **wrong payload** (BER 0.061) | −94.98 / 0.8965 | −3.18 vs −6.19 — not accepted | `conv_k7_…_continuous` |
| C (ideal) | correct structure, correct payload (BER 0.000) | −175.06 / 0.9967 | −4.05 — not accepted | `conv_k7_…_continuous` |
| D (blind estimator) | correct structure, correct payload (BER 0.000) | −170.59 / 0.9933 | −3.27 — not accepted | `conv_k7_…_continuous` |

The F4 near-accept exists **only** in the arm whose stream bits are degraded. No suspicious intermediate evidence appears in B, C or D on this capture.

### 11.1.6 The F4 margin distribution across all 144 captures — MEASURED FACT (post-hoc)

From `results/space_doppler_mech_f4_margins.jsonl` (margin = `best_log10_p` − bar; negative means the bar was cleared):

| Arm | F4 accepts | smallest margin | median margin | captures within 0.5 log of the bar |
|---|---:|---:|---:|---:|
| A (ablated) | **1** — `linear_0084`, margin **−0.066**, 0/18 converged | −0.066 | +2.63 | 2 of 144 |
| **B (shipped)** | **0** | **+0.116** | +2.63 | **1 of 144** |

**The shipped arm's nearest miss is `static_0009` — a *static*-carrier capture** (severity 0.1, 412 symbols, 12 dB) that decodes correctly in every arm, sitting **0.116 log units** below the F4 bar. Then a gap to +1.25. **So the proximity to an F4 accept is present in the shipped configuration and is not drift-specific.**

### 11.1.7 Classification

- **The instance — `linear_0084`: EXPLAINED WITH EXISTING EVIDENCE.** The chain is fully measured: ablation degrades the F2 stream → the LDPC scan clears its bar by 0.066 log units on those degraded bits with 0 of 18 codewords converging → the F4-over-F2 resolution order surfaces the LDPC layer in the summary fields. No step of that chain is inferred.
- **The generalisation — is the shipped engine exposed? REQUIRES TARGETED FOLLOW-UP.** Three reasons, each measured: (a) the nearest shipped-arm miss is on a **static** capture, so the proximity is **not** an artefact of drift or of the ablation; (b) the missing convergence requirement is a property of the **shipped** F4 path, not of the ablation; (c) n = 144, one code family, one modulation, in-bound peaks only — far too narrow to characterise an acceptance margin. **Nothing here establishes that the shipped engine can be pushed over that edge, and nothing here establishes that it cannot.**

### 11.1.8 What this does and does not license

- The STOP bar **remains fired**, and §11 is unchanged. The mechanism experiment is **not** declared unconditionally passed.
- Arm A (removing tracking) remains **disqualified** as a remediation direction.
- **No production change is proposed here**, and none may be inferred from this addendum. In particular, adding a convergence requirement to the F4 accept path would be a production change to `src/pipeline.py` affecting every block-code claim the engine can make, including bench-v2's RS and TC-LDPC families — it is **not** made, **not** authorised, and would need its own pre-registered measurement against bench-v1, bench-v2, the null set and the real-signal suite.

### 11.1.9 Recommended follow-up (not designed yet, not authorised)

`SPACE-F4-MARGIN-01` — a **static-carrier** structural-margin study: sweep the existing catalogue families (RS, concatenated, TC-LDPC, burst, continuous stream) on static carriers across SNR and length, recording per capture the F4 `best_log10_p`, its bar, the margin, and the converged-codeword count of any accepted hypothesis; pre-register that **any accept with zero converged codewords is a failure**. Its purpose is to characterise how close the shipped engine runs to an F4 accept when nothing is drifting. It is **separate** from `CARRIER_ESTIMATOR_EXPERIMENT.md`, which records the same F4 fields (§5, §6.3) but only over one signal family.

**END OF ADDENDUM 11.1**

## 12. Mechanism conclusion

### **MECHANISM: SUPPORTED — carrier-estimation error.**

**The measured evidence, and only it:**

1. Exactly removing the injected trajectory eliminated the failure entirely: **0 of 96** treated captures wrong, against 57 of 96 for the unmodified engine on the **same bytes** (arm C vs B, paired). `C_restores` YES.
2. A **blind** estimator — no ground truth, built only from the engine's own published carrier test applied per block — reached **3 of 96** (0.031). `D_approaches_C` YES. The information needed is therefore *present in the samples*, not only in the oracle.
3. A constant offset of the same magnitude produced **0 of 48** wrong payloads in every arm, so the cause is the carrier *moving*, not its size.
4. Ablating the tracker made things worse (0.802 against 0.594) and, once, broke the structural claim — so the tracker is net protective and is not itself the cause.
5. Correction *granularity* is irrelevant once the values are right: 0 wrong payloads at every granularity from a 64-symbol staircase to per-sample.

**ENGINEERING INTERPRETATION (the inference, stated as such).** The failing stage is the **estimation of the time-varying carrier**, not the decoder and not the soft-metric scaling. The engine's front end removes one *constant* frequency per front end and then tracks *phase* piecewise; what it never does is estimate a *changing frequency*. When the true frequency is supplied — or estimated per block — the existing Viterbi decoder, the existing LLR scaling and the existing acceptance path all produce correct payloads at the rates they achieve on a static carrier. H4 and H6 predicted the opposite.

**What this conclusion does NOT license.** It does not authorise a production change; it does not establish that a production estimator can match arm D inside the engine's hypothesis-enumeration and family-bar structure; and it does not measure what such an estimator would cost on static-carrier recall. Arm D is an evaluation-side pre-correction applied to the samples before the engine runs — a much easier setting than adding a front end that must be counted in every family's M.

### A second measured result that cuts the other way

**MEASURED FACT.** The payload-side scores, recorded here on **new** data (pooled arms A + B: 123 correct against 134 wrong payloads):

| Score | correct: min / median | wrong: median / max | wrong at or above the lowest correct value |
|---|---|---|---|
| `path_metric` | 0.9963 / 0.9995 | 0.9193 / 0.9968 | **2 of 134** |
| `consistency` | 0.9805 / 0.9958 | 0.9077 / 0.9808 | **3 of 134** |
| `agreement` | 0.9073 / 0.9883 | 0.7553 / 0.9561 | **15 of 134** |

The sealed run's post-hoc observation was *complete* separation on `path_metric` (0 of 54 overlapping). **On new data the separation is no longer complete.** The populations still differ strongly, but they touch. **ENGINEERING INTERPRETATION:** a verdict gate built on these scores would not be a clean separator — it would misclassify in both directions, and its price in static-carrier recall is still unmeasured. The design's precondition for the payload-reliability gate is therefore **partially met at best**, and this experiment deliberately derives **no threshold** from either dataset.

## 13. Alternative hypotheses affected

| # | Hypothesis | Status after this run | Evidence |
|---|---|---|---|
| **H1** | Residual frequency error the front end does not model | **SUPPORTED — the leading explanation** | Ideal correction 0/96; blind per-block estimation 3/96; same bytes, same engine |
| **H2** | Staircase (piecewise-constant) correction error | **KILLED** (pre-registered bar `H2_killed`) | Arm E: 0 wrong payloads at every granularity, spread 0.000. The form of the correction is irrelevant when its values are right |
| **H3** | Unwrap slip near the M-power ambiguity | **NOT SUPPORTED as necessary; not directly tested** | H1 alone accounts for the whole effect, and no slip-specific signature was needed to explain it. Confirming or excluding slip still needs the trajectory read-out (unapproved) |
| **H4** | Soft-metric (LLR) miscalibration under non-stationary SNR | **LARGELY EXCLUDED** | Arm C changes *only* the carrier; LLR scaling is untouched, yet payloads are correct 90/96. If miscalibration were driving it, C would still fail |
| **H5** | Insufficient observation length | **REFINED, not a cause** | Below `TRACK_MIN_SYMBOLS` arms A and B are identical (0.729) — length governs whether tracking exists, but ideal correction is 0.000 at *both* lengths, so length is not the mechanism |
| **H6** | Tracking × code-decoding interaction (tracking leaves a stream that looks more significant and decodes worse) | **WEAKENED** | Tracking *helps*: 0.594 with it against 0.802 without, and ablation also produced the single wrong structure. Tracking is net protective, not the source |

## 14. Limitations

1. **One signal family.** Continuous K7, BPSK only — chosen for comparability with the sealed run. Nothing here speaks to burst codes, RS, concatenated chains, TC-LDPC, QPSK or any interleaved family.
2. **Arm C is an oracle.** It cannot exist in production. Its value is diagnostic: it bounds what carrier knowledge is worth.
3. **Arm D is a pre-correction, not a front end.** It runs before the engine, with the whole capture in hand and no obligation to be counted in any family's M. A production equivalent is a materially harder problem, and its recall cost is unmeasured.
4. **In-bound peaks only.** Every cell keeps peak ≤ `CFO_MAX` (DEV-2), so this run says nothing about out-of-bound behaviour; the sealed run covered that separately (refusal).
5. **Two Es/N0 levels and two lengths.** The sealed run's third SNR (9 dB) is absent by design.
6. **The `pass` shape is CONTROLLED SYNTHETIC.** It is not a satellite pass, and no orbital geometry was involved.
7. **The wrong-structure event is a single observation** in an ablated configuration; it is not a characterised failure mode.
8. **Arm E is small** (30 analyses, one trajectory, one length, one SNR). Its `H2_killed` verdict is clean at 0.000 spread but narrow in scope.
9. **The payload-score comparison is observational.** It was recorded, not pre-registered with a bar in this experiment's criteria, and may not be used to choose a threshold.

## 15. Reproduction commands

```bash
cd C:/Users/WVF-D/Downloads/SIH26147/repo
python eval/space_doppler_mech.py demo        # harness self-checks
python -m pytest tests/test_space_doppler_mech.py -q
python eval/space_doppler_mech.py generate    # 144 captures, seeds 600000-600143 (guarded against overwrite)
python eval/space_doppler_mech.py run         # 576 + 30 analyses -> results/space_doppler_mech_rows.jsonl
python eval/space_doppler_mech.py report      # the tables and pre-registered bars in this document
python eval/space_doppler_mech.py verify      # 144/144 byte-identical regeneration
```

## 16. What remains NOT ESTABLISHED

- **That any production change will work.** No remediation was implemented, and none is authorised. Arm D's 0.031 is an evaluation-side pre-correction, not a front end inside the engine's hypothesis structure.
- **The cost of remediation on what already works.** Untested against bench-v1 (30/30), bench-v2 (9/9 criteria), the 1,350-file null set (0/900) and the real-signal suite. Until that is measured, no direction is preferable on evidence.
- **The payload-reliability gate's basis.** Weakened, not established: separation is no longer complete on new data (§12). No threshold derived.
- **H3 (unwrap slip).** Neither confirmed nor excluded; it needs the `_track_phase` read-out, which remains **AWAITING EXPLICIT APPROVAL** (`SPACE_IMPLEMENTATION_GATE.md` §9.3).
- **The structural false accept under ablation.** One occurrence, mechanism unknown, no experiment run on it. The STOP bar it fired is recorded in §11 and left to the project owner.
- **Generalisation beyond one code family, one modulation, and in-bound peaks.** See §14.
- **Every space-capability claim.** Unchanged and still forbidden: this is a diagnostic. `SPACE_CLAIM_FIREWALL.md` §2a stands as written, and the measured limitation in `SPACE_EVIDENCE_MATRIX.md` row 6 is **not** retired by this result — it is explained, not fixed.

**END OF DOPPLER MECHANISM RESULTS**
