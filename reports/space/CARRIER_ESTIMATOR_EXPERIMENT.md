# CARRIER_ESTIMATOR_EXPERIMENT
**ICHNOVA · SIH26147 — `SPACE-CARRIER-EST-01`: can the blind carrier estimator be integrated without unacceptable cost? (DESIGN ONLY)**
**Status: PRE-REGISTERED EXPERIMENT DESIGN (2026-09-26). Nothing implemented. No production file touched. Not executed.**

**The question this experiment answers.** `SPACE-DOPPLER-MECH-01` measured that a blind per-block carrier estimator, applied as an evaluation-side pre-correction, reduced wrong payloads from 57 of 96 to **3 of 96** on time-varying carriers (`DOPPLER_MECHANISM_RESULTS.md` §10). That says the *information* is recoverable. It does **not** say the estimator can live in ICHNOVA's analysis path. This experiment asks only: **what does adding it cost, on everything that already works?**

**What this experiment is not.** It is not an integration, and not a decision to integrate. A result in which arm B recovers payloads *and* damages static-carrier behaviour or structural safety is **not a success**, and is pre-registered as such (§6).

---

## 1. Immutability and independence (hard constraints)

| Constraint | Value |
|---|---|
| Experiment ID | `SPACE-CARRIER-EST-01` |
| New namespace | `data/space_bench/carrier_est/` — **never** `doppler/` or `doppler_mech/` |
| New criteria | `eval/carrier_estimator_criteria.json`, committed **before** the harness exists and before any vector |
| New harness | `eval/carrier_estimator.py` — the candidate estimator is **prototyped here only** |
| New rows | `results/carrier_est_rows.jsonl` |
| Seeds | `SEED0 = 700000`, capture seed = `700000 + index` over the pure-function job list; disjoint from 500000–500191 (SPACE-DOPPLER) and 600000–600143 (MECH-01) |
| **SPACE-DOPPLER (192 vectors, manifest `f9823ef5…`)** | **IMMUTABLE.** Not regenerated, not re-scored, not overwritten. Its harness already refuses to regenerate it |
| **SPACE-DOPPLER-MECH-01 (144 captures, manifest `a152d682…`)** | **IMMUTABLE.** Same rules. Its rows and F4-margin file stay as published |
| Existing benchmarks | bench-v1, bench-v2, the 1,350-file null set and the real-signal recordings are **read-only inputs**. No dataset, seed, criteria file or threshold of theirs may change |
| Production boundary | **No change** to `src/`, `server/`, `frontend/`, `deploy/`, `Dockerfile`, `requirements.txt`. The estimator is an evaluation-side pre-correction, exactly as in MECH-01 arm D |

## 2. Arms

| Arm | Definition | Role |
|---|---|---|
| **A — production engine** | `analyze_iq(iq)`, unmodified | The baseline every criterion is measured against |
| **B — candidate carrier estimator** | The capture is pre-corrected by the **candidate estimator** (§3), then analysed by the unmodified engine | The subject of the experiment |
| **C — ideal ground-truth correction** | The injected `f(t)` removed exactly, then the unmodified engine | **Diagnostic upper bound only.** An oracle; it cannot ship, and no criterion is written to be satisfied *by* it |

Arm C exists to answer "how much of the achievable gain did the candidate capture?" — it is a ceiling, never a target.

## 3. The candidate estimator — fixed before the run

Promoted from MECH-01 arm D **unchanged**, with every knob declared here so none can be tuned after a result is seen:

| Knob | Fixed value | Basis |
|---|---|---|
| Block count | `N_BLOCKS = 8` contiguous equal blocks | The value measured in MECH-01 arm D; changing it would make the two experiments incomparable |
| Per-block frequency | Most significant candidate of `pipeline._cfo_candidates(block)` (lowest log₁₀ p) | Uses the engine's own published carrier test — no new statistic is invented |
| Minimum block length | 32 samples; shorter blocks contribute no knot | As MECH-01 |
| Interpolation | Linear between block centres; constant extrapolation outside | As MECH-01 |
| De-rotation | `iq × exp(−2πj·cumsum(f̂))` | As MECH-01 |
| Failure handling | If no block yields a candidate, the capture passes through **uncorrected** and the row records `knots = 0` | As MECH-01 |

**No variant sweep.** If this candidate fails a criterion, the honest next step is a redesign with its own pre-registration — not a search over knobs on this dataset.

**What this arm does NOT test (stated so the result is not over-read).** A production estimator would have to be *inside* the analysis path, which means its front end is counted in every family's hypothesis multiplicity M, raising every family's bar. A pre-correction escapes that entirely. So arm B measures an **upper bound on the benefit** and a **lower bound on the cost** of integration. That asymmetry must appear in any sentence written about this experiment's result.

## 4. Test matrix — pre-registered

### 4.1 New vectors

| Factor | Levels | Note |
|---|---|---|
| Trajectory | `static`, `linear`, `pass` | Same definitions as `eval/space_doppler.py::trajectory` — the shared definition of the impairment |
| Severity (peak = severity × `CFO_MAX`) | 0.04, 0.1, 0.2, 0.4, 0.7, 1.0 | Identical to MECH-01, so the two are comparable; all in bound, so out-of-bound refusal is not a confound |
| Capture length | **412** and **1200** symbols | Straddles `TRACK_MIN_SYMBOLS = 512`; identical to MECH-01 |
| Es/N0 | **6** and **12** dB | Identical to MECH-01 |
| Repetitions | **4** | See §4.3 |
| Signal family | Continuous rate-½ K=7 convolutional stream, BPSK, sps ∈ {4,6,8}, β ~ U(0.2,0.5) | **The same family as both prior experiments** — the one with the strongest existing evidence (bench-v2 16/16 at Es/N0 ≥ 6 dB) |

**3 × 6 × 2 × 2 × 4 = 288 distinct captures**, analysed under three arms = **864 analyses**. Of the 288: **96 static controls** and **192 treated** (`linear` + `pass`).

### 4.2 Existing datasets re-analysed under arms A and B (the regression half)

| Dataset | n | Why it is in this experiment | Authorization |
|---|---|---|---|
| bench-v1 sealed (`data/sealed`) | 30 | The documented regression tripwire, explicitly designed for repeat runs | None needed |
| Independent null set (`data/nullset`) | 1,350 | The false-accept floor: 0/900 measured. A carrier pre-correction could plausibly turn noise into apparent structure — this is where that would show | None needed |
| Real-signal recordings (`tests/test_realsig.py` fixtures) | 6 transmitters | The only non-synthetic evidence in the project, and it includes the **WWVB refusal** — the most valuable refusal on record | None needed |
| bench-v2 sealed (`data/bench2/sealed`) | 430 | The 9-criteria capability statement | **REQUIRES EXPLICIT AUTHORIZATION.** bench-v2's discipline is one logged run per condition. Arm B is a *new condition*: it needs its own entry in `eval/bench2_access_log.jsonl`, must not overwrite the original result, and must be run **once** |

Because `eval/bench2.py` is inside the protected surface, the bench-v2 re-analysis is performed by the new harness **reading** `data/bench2/sealed` read-only and **importing** bench-v2's own scoring function, so no bench-v2 file is modified.

### 4.3 Why these sample sizes (derived, not chosen casually)

Two existing conventions fix the numbers:

1. **bench-v2's false-accept convention** requires a 95% **Wilson upper bound** on the observed rate, not just a point estimate (`eval/bench2_criteria.json`: null false accepts ≤ 1% with Wilson upper ≤ 5%; `eval/bench2.py::wilson_hi`). For **0 events in n**, the Wilson upper bound is ≈ z²/(n + z²) with z = 1.96, i.e. **3.84/(n + 3.84)**. So:
   - a "0 structural false accepts" claim with upper bound ≤ **5%** (bench-v2's null bar) needs **n ≥ 73**;
   - the same claim with upper bound ≤ **2%** (bench-v2's `wrong_structure_or_payload_is_rare` bar) needs **n ≥ 188**.
   **Therefore 96 static controls** (0/96 → upper bound 3.8%, inside the 5% bar) and **192 treated captures** (0/192 → upper bound 1.96%, inside the 2% bar). The §4.1 grid produces exactly these two numbers; they are the reason for 4 repetitions rather than 2.
2. **The prior experiments' cell convention** is 2 repetitions per cell (SPACE-DOPPLER: 192 = 4 × 4 × 3 × 2 × 2; MECH-01: 144 = 3 × 6 × 2 × 2 × 2). **4 repetitions doubles it**, so a per-cell difference between arms cannot be a single-sample artefact; each of the 72 cells is reported at n = 4 per arm, while the criteria are evaluated on the aggregates that §4.3(1) sizes.

**Runtime estimate** from MECH-01's measured 0.76 s mean: 864 × 0.8 s ≈ **12 minutes** for the new vectors; the null set adds ≈ 2 × 1,350 × 0.8 s ≈ **36 minutes**; bench-v1 and the real-signal suite are minutes. Under one hour, single logged run.

## 5. What each measurement records

Per analysis: arm, trajectory, severity, peak, achieved drift rate, capture length, symbol count, Es/N0, rep, seed; verdict, the four-way outcome (§6.0), payload BER, accepted code family, reported modulation, reported sps vs true sps; **estimator coverage** (knots obtained) and **estimator error** (RMSE against the true trajectory in cyc/sample — new vectors only, where truth exists); the F2 scores `agreement` / `path_metric` / `consistency`; **F4 `best_log10_p`, its bar, the margin between them, and the converged-codeword count of any accepted block-code hypothesis**; refusal status and its stated reason; runtime.

The F4 fields are mandatory because of what `DOPPLER_MECHANISM_RESULTS.md` §11.1 measured: in the shipped configuration one capture sat **0.116 log units** below the F4 bar, and the single F4 accept on record converged **0 of 18** codewords.

## 6. Acceptance criteria — six separate families, no aggregate score

**There is no single score, and none may be constructed.** Each family is reported and judged on its own. A result that satisfies some and fails others is reported exactly that way.

### 6.0 Outcome categories (as MECH-01, unchanged)

`CORRECT_STRUCTURE_CORRECT_PAYLOAD` · `CORRECT_STRUCTURE_WRONG_PAYLOAD` (the failure under study — **not** a structural false accept) · `WRONG_STRUCTURE` (a structural false accept) · `REFUSED`. BER via `bench2._ber`, imported verbatim.

### 6.1 Static-carrier regression — HARD

| Check | Bar | Basis |
|---|---|---|
| bench-v1 sealed under arm B | **30/30 decoded, 0 false accepts** — exact | The documented tripwire; any change is a regression by definition |
| bench-v2 sealed under arm B | **all 9 pre-registered criteria still pass** | The capability statement rests on them |
| Null set under arm B | **0 false accepts**, Wilson upper bound ≤ 5% | bench-v2's `no_false_accept_on_non_catalogue_signals`, inherited |
| Real-signal suite under arm B | JJY, DCF77, MSF, WWV still `DECODED` with digit agreement no worse than recorded; **WWVB still `SIGNAL_NO_CODE`** | A WWVB *decode* under arm B is an **automatic failure of the whole experiment**: that refusal is evidence the project has published |
| New static cells (n = 96) | **0 wrong payloads, 0 wrong structures**, and correct-payload rate ≥ (arm A's rate − 0.05) | The 0.05 is a **declared tolerance**, stated before any run, not inherited |

### 6.2 Time-varying-carrier payload reliability — PASS/FAIL, reported against both neighbours

| Check | Bar | Basis |
|---|---|---|
| Arm B wrong-payload rate, treated (n = 192) | **≤ 0.05** | **Declared tolerance**, anchored on MECH-01's measured prototype rate of 0.031 rounded up — explicitly *not* inherited from any prior benchmark |
| Arm B correct-payload rate, treated | **≥ 0.80** | **INHERITED**: bench-v2 `continuous_stream_code_recall` (≥ 80% of continuous K7 streams at Es/N0 ≥ 6 dB) |
| Reporting requirement | Arm B must appear beside **arm A** (the cost-free baseline) and **arm C** (the oracle ceiling) in every table | Prevents a mediocre gain from reading as a success |

### 6.3 Structural safety — HARD, and it outranks §6.2

| Check | Bar |
|---|---|
| Wrong structures, any arm, any dataset | **0.** **ANY** `WRONG_STRUCTURE` under arm B → **STOP**; the estimator is not a candidate, and the experiment reports failure regardless of payload gains |
| F4 block-code accepts | **Any accepted block-code hypothesis with 0 converged codewords is a structural-safety FAILURE**, whether or not its code matches the transmitted one |
| F4 margin | Reported per capture per arm (`best_log10_p` − bar). **Arm B must not reduce the minimum margin below arm A's** on the same captures |
| Null set | 0 accepts, as §6.1 |

The second and third rows are new, and they exist because of the STOP-bar analysis: a marginal block-code accept over a badly-decoded stream is how the one wrong structure on record was produced, and a pre-correction changes exactly the bits that search runs on.

### 6.4 Refusal behaviour — REPORTED, with two hard sub-bars

- **Reported, no bar:** refusal rate per arm, per trajectory, per severity, per length, per Es/N0 — always printed **next to** the correct-payload rate, so a safety gain bought with recall is visible in the same row. An increase in refusals under arm B is **not** a failure.
- **Hard:** refusals on the **null set** must not decrease (a pre-correction must not turn refusals into accepts).
- **Hard:** a refusal whose stated reason contradicts the injected trajectory (a drift-referenced reason on a `static` capture, for instance) is a failure.
- **Reported:** the DECODED→refusal migration direction across severity, as in the sealed experiment.

### 6.5 Estimator coverage and failure — one bar, the rest reported

| Check | Bar / treatment |
|---|---|
| Coverage: fraction of captures where all 8 knots are obtained | **≥ 0.95** (health bar; below it the estimator is not characterised and §6.2's result is uninterpretable) |
| Estimator error (RMSE vs the true trajectory, new vectors only) | **REPORTED, no bar — NOT ESTABLISHED.** No prior measurement of trajectory-estimation accuracy exists in this repository, so any figure would be invented |
| Where estimator failures land | **Reported as a 2×2 table** (estimator degraded or not × outcome). **Hard sub-bar:** no estimator failure may produce a `WRONG_STRUCTURE` |
| Behaviour on the null set and on static captures | Reported: the estimator must be shown *harmless* where there is nothing to correct |

### 6.6 Runtime — PASS/FAIL

| Check | Bar | Basis |
|---|---|---|
| Arm B mean per-file analysis time | **≤ 3 × arm A's mean on the same captures** | The same 3× convention as the sealed Doppler run's `runtime_guard` |
| Arm B maximum | **≤ 120 s** | Same convention |

### 6.7 The rule that governs interpretation

> **A carrier estimator that improves payload recovery but introduces a structural false accept is NOT an unconditional success — it is a failure of §6.3, and §6.3 outranks §6.2.**
> **A system that refuses more aggressively may be safer while recovering less; both numbers are reported, and neither alone decides the outcome.**
> **`INTEGRATION NOT SUPPORTED` is a pre-registered acceptable result**, as is `PARTIALLY SUPPORTED, WITH COSTS` — in which case every cost is named in the same sentence as every gain.

## 7. Pre-registered decision table

| Observation | Conclusion it licenses |
|---|---|
| §6.1 and §6.3 fully pass **and** §6.2 passes | **Integration is supportable in principle** — and still requires a separate production-change proposal, because arm B is a pre-correction, not a front end inside the hypothesis structure (§3) |
| §6.1 passes, §6.2 passes, §6.3 fails | **INTEGRATION NOT SUPPORTED.** Structural safety outranks payload recovery |
| §6.1 fails (any bench, null-set or real-signal regression) | **INTEGRATION NOT SUPPORTED.** The existing evidence base is the asset; nothing may be traded for it |
| §6.2 fails while §6.1 and §6.3 pass | The candidate does not deliver the MECH-01 prototype's benefit in this setting; **report and stop** — do not tune the estimator on this dataset |
| §6.5 coverage below 0.95 | The estimator is uncharacterised; §6.2 is **uninterpretable** and reported as such |
| Arm B ≈ arm C on treated captures **and** §6.1/§6.3 pass | The candidate captures most of the achievable benefit — the strongest possible outcome here, and still not an authorization |
| Arm B ≪ arm C | The gap is the estimator's, not the channel's; a redesign with a new pre-registration is the honest next step |
| Any WWVB decode, or any null-set false accept | **Immediate STOP**, whatever else passed |

## 8. What this experiment does not do

- It does **not** modify `src/`, `server/`, `frontend/`, `deploy/`, `Dockerfile` or `requirements.txt`.
- It does **not** change any threshold, bar, family weight, `ALPHA`, `CFO_MAX`, `TRACK_MIN_SYMBOLS` or `F2_AGREEMENT_FLOOR`.
- It does **not** implement a payload-reliability gate. That idea's basis was **weakened** by MECH-01 (score separation did not fully persist: 2 of 134 wrong payloads reached the lowest correct `path_metric`, 15 of 134 on `agreement`), and **no payload threshold is derived here**.
- It does **not** regenerate, re-score or overwrite the 192-vector or 144-capture datasets.
- It does **not** settle the F4 structural question. It *records* F4 margin and convergence data (§5, §6.3) and will show whether arm B makes that margin worse, but characterising the F4 family's exposure on **static** carriers cleanly needs a **dedicated study**, recommended separately in `DOPPLER_MECHANISM_RESULTS.md` §11.1.
- It does **not** authorise any space capability claim. `SPACE_CLAIM_FIREWALL.md` §2a stands unchanged.

## 9. Approval status

| Item | Status |
|---|---|
| This design | **Written. Not approved. Not implemented. Not executed.** |
| `eval/carrier_estimator_criteria.json` | Not written; must be committed before the first vector exists |
| `eval/carrier_estimator.py` | Not written |
| bench-v2 sealed re-analysis under arm B | **REQUIRES EXPLICIT AUTHORIZATION** (one logged run, new access-log entry, original result preserved) |
| Any production integration of the estimator | **BLOCKED** — and would remain blocked after a fully passing result, pending its own proposal and review |

**END OF CARRIER ESTIMATOR EXPERIMENT DESIGN**
