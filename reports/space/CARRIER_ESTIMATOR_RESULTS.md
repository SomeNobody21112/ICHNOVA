# CARRIER_ESTIMATOR_RESULTS
**ICHNOVA · SIH26147 — `SPACE-CARRIER-EST-01`: does the blind carrier estimator survive contact with the rest of ICHNOVA?**
**Status: EXECUTED AND PUBLISHED AS-IS (2026-09-26). DECISION: INTEGRATION NOT SUPPORTED. No production file changed, no estimator knob tuned, no threshold moved.**

---

## Executive result

The candidate estimator does almost exactly what `SPACE-DOPPLER-MECH-01` predicted on time-varying carriers — on 192 treated captures it cut wrong payloads from **108 to 2** and raised correct payloads from **0.292 to 0.932**, within 0.011 of the ideal-correction ceiling — and it **damages the existing evidence base at the same time**. Under arm B, bench-v1 sealed falls from **30/30 to 22/30**, bench-v2 sealed drops from **9/9 to 8/9** pre-registered criteria (`burst_block_interleaver_recall` 4/12 = 33% against a 50% bar), the null set's catalogue-coded controls fall from **128 to 87** correct decodes, and — decisively — an **idle carrier that the production engine refuses was DECODED as `ccsds_tc_ldpc_128_64`/QPSK**, an F4 block-code acceptance the pre-correction pushed from a margin of **+2.699 to −0.112** with **0 of 18 codewords converged**. Real-signal behaviour was untouched, including the WWVB refusal. Two independent pre-registered rules therefore fire — C1 (static-carrier regression) and C3 (structural safety) — and the pre-registered immediate-stop condition (a false accept on a null class) fires with them. **The improvement does not survive contact with the rest of the system.**

## Experimental design

| Field | Value |
|---|---|
| Experiment ID | `SPACE-CARRIER-EST-01` |
| Pre-registration | `eval/carrier_estimator_criteria.json`, sha256 `9c70e0e4a10cb246…`, committed **before** the harness existed and before any vector was generated |
| Source design | `reports/space/CARRIER_ESTIMATOR_EXPERIMENT.md` |
| Arms | **A** production engine (`analyze_iq`, unmodified) · **B** candidate estimator as a pre-correction · **C** ideal ground-truth correction (**diagnostic ceiling only — it cannot ship and is never an implementation target**) |
| Estimator identity | **Imported**, not reimplemented: `space_doppler_mech.estimate_trajectory` — the exact MECH-01 arm-D function, 8 blocks, most-significant `pipeline._cfo_candidates` per block, linear interpolation between block centres, `exp(−2πj·cumsum(f̂))`. `tests/test_carrier_estimator.py` asserts the function *object* identity, so no knob can have drifted |
| Production boundary | Estimator prototyped only in `eval/carrier_estimator.py`. Nothing under `src/`, `server/`, `frontend/`, `deploy/`, `Dockerfile`, `requirements.txt` was modified |
| Margin convention | F4 `best_log10_p` − bar (`eval/ladder.py:65`); **negative = accepted** |

**Deviations from the pre-registration: none in arms, grid, seeds, scoring, bars or populations.** Three tensions were identified and resolved *before* measurement, in the criteria file:

- **T1** — `CARRIER_ESTIMATOR_EXPERIMENT.md` §6.3 pre-registers "any accepted block-code hypothesis with 0 converged codewords is a structural-safety FAILURE", while `SPACE-F4-MARGIN-01` established that convergence is a **provenance marker, not an acceptance requirement** (`src/blockcode.py`:175–177; bench-v2's TP_PARTIAL rule). **The bar was applied exactly as pre-registered.** It fired (§ Structural safety), and it fired on a capture that is *also* a false accept on a null class — so the C3 failure does not depend on the convergence question at all.
- **T2** — C4's "refusal reason contradicts the injected trajectory" sub-bar assumes drift-referenced refusal reasons, which the engine does not emit. Reported **NOT APPLICABLE**, not silently passed.
- **T3** — the C3 margin comparison is strictly paired (arm B vs arm A on identical captures), never against a historical figure.

One reporting addition traceable to the authorising turn, declared in the criteria file before the run: **per-family hypothesis multiplicity M and each family's bar are recorded per arm**, so the integration cost is measured rather than assumed.

## Dataset

| Field | Value |
|---|---|
| Namespace | `data/space_bench/carrier_est/` |
| Captures | **288** distinct — 3 trajectories (`static`, `linear`, `pass`) × 6 severities {0.04, 0.1, 0.2, 0.4, 0.7, 1.0} × `CFO_MAX` × 2 lengths (**412**, **1200** symbols) × 2 Es/N0 (**12**, **6** dB) × **4 repetitions** |
| Composition | **96 static** controls, **192 treated** (`linear` + `pass`) |
| Analyses | **864** = 288 × 3 arms (all arms see byte-identical samples — the comparison is paired) |
| Seeds | **700000–700287**, disjoint from SPACE-DOPPLER (500000–500191) and MECH-01 (600000–600143) |
| Manifest | `eval/carrier_estimator_manifest.json`, manifest sha256 `8af0c83dd5151758…`, 288 files |
| Determinism | **288/288 byte-identical** on regeneration; overwrite refused by the harness |
| Transmitter | Continuous rate-½ K=7 convolutional stream, BPSK, sps ∈ {4,6,8}, β ~ U(0.2,0.5) — generator **imported** from MECH-01, so the signal family is identical across all three experiments |
| Sample-size basis | bench-v2's Wilson convention: for 0 events in n the 95% upper bound is 3.84/(n+3.84), so 96 static captures give ≤3.8% (inside bench-v2's 5% null bar) and 192 treated give ≤1.96% (inside its 2% catalogue-wrong bar) |

## Arm comparison

**Treated captures (`linear` + `pass`), n = 192 per arm:**

| Arm | correct structure + correct payload | correct structure + **wrong payload** | wrong structure | refusal | wrong-payload rate |
|---|---:|---:|---:|---:|---:|
| **A — production** | 56 | **108** | 0 | 28 | **0.562** |
| **B — candidate** | 179 | **2** | 0 | 11 | **0.010** |
| **C — ideal (ceiling)** | 181 | **0** | 0 | 11 | **0.000** |

**Static captures, n = 96 per arm:**

| Arm | correct + correct | correct + wrong payload | wrong structure | refusal | correct rate |
|---|---:|---:|---:|---:|---:|
| A | 91 | 0 | 0 | 5 | 0.948 |
| B | 89 | 0 | 0 | 7 | 0.927 |
| C | 90 | 0 | 0 | 6 | 0.938 |

On the **new** static cells arm B costs 0.021 of correct-payload rate — inside the declared 0.05 tolerance. That sub-check passes; the damage appears only on the **existing** benchmarks, which is the strongest argument in this report for having run the regression half at all.

## Time-varying performance

**By trajectory (n = 96 per cell):** `linear` wrong-payload **A 0.469 → B 0.000** (C 0.000); `pass` **A 0.656 → B 0.021** (C 0.000).

**By severity (treated, n = 32 per arm per row) — wrong-payload / correct-payload:**

| Severity | A | B | C |
|---|---|---|---|
| 0.04 | 0.219 / 0.750 | **0.000 / 0.969** | 0.000 / 0.969 |
| 0.10 | 0.469 / 0.469 | **0.000 / 0.938** | 0.000 / 0.938 |
| 0.20 | 0.562 / 0.406 | **0.000 / 1.000** | 0.000 / 1.000 |
| 0.40 | 0.719 / 0.125 | **0.000 / 0.938** | 0.000 / 0.938 |
| 0.70 | 0.688 / 0.000 | **0.031 / 0.844** | 0.000 / 0.875 |
| 1.00 | 0.719 / 0.000 | **0.031 / 0.906** | 0.000 / 0.938 |

**By length:** short (412 sym) wrong-payload A 0.667 → B 0.021 (C 0.000); long (1200 sym) A 0.458 → B 0.000 (C 0.000).
**By Es/N0:** 12 dB A 0.615 → B 0.000 (C 0.000); 6 dB A 0.510 → B 0.021 (C 0.000).

Both of arm B's two wrong payloads are `pass` captures at the two steepest severities. Arm B tracks the oracle ceiling within 0.011–0.032 everywhere.

## Structural safety

**On the new 288-capture matrix — no failure:**

| Arm | wrong structures | F4 accepts | zero-convergence accepts | min F4 margin | median |
|---|---:|---:|---:|---:|---:|
| A | **0** | 0 | 0 | +0.443 | +2.673 |
| B | **0** | 0 | 0 | **+0.862** | +2.729 |
| C | **0** | 0 | 0 | +0.765 | +2.795 |

On these captures arm B's minimum F4 margin is *further* from the bar than arm A's (+0.862 vs +0.443), so the paired margin sub-check **passes here**.

**On the regression populations — C3 fails, decisively:**

| Capture | Arm A | Arm B |
|---|---|---|
| `bench2_sealed/idle_carrier_0411` (**null class**, `expected: REFUSAL`) | `SIGNAL_NO_CODE`, F4 margin **+2.699**, not accepted | **`DECODED` as `ccsds_tc_ldpc_128_64` / QPSK**, F4 margin **−0.112**, accepted, **converged 0 of 18** |

An idle carrier — a signal with no catalogue structure at all — was published as a CCSDS TC-LDPC codeword stream because the pre-correction moved the F4 statistic across its bar. This is a **structural false accept in a legitimate operating population**, and it independently trips: C3's "0 wrong structures" bar, C3's zero-convergence bar (T1), and the pre-registered **immediate-stop** condition ("any null-set false accept").

It also settles a question `SPACE-F4-MARGIN-01` left open. That study found the F4 margin floor to be **empirical, not structural** (+0.116 the tightest static margin then on record). This experiment demonstrates the crossing: a pre-correction can push a null capture from +2.699 to −0.112.

bench-v2 catalogue-side wrong claims also rose from **3 to 6** under arm B — `burst_QPSK_k3_qpp_0116`, `ccsds_concat_0268`, `ccsds_concat_0275`, `stream_k7_0252`, `stream_k7_0255` (wrong structure or payload under a continuous-K7 claim), plus the `idle_carrier_0411` event above. Arm A's three are the three already documented in `SPACE_EVIDENCE_MATRIX.md` §0.1, reproduced exactly.

## Payload reliability

Structural and payload correctness are scored separately throughout (categories in the criteria file). Treated captures: arm A published **108 wrong payloads beneath correct structural claims**; arm B published **2**; arm C **0**. Refusals: A 28, B 11, C 11 — arm B refuses *less* than arm A while being far more often right, so its gain is not bought with recall on this matrix. **No arm produced a wrong structure on the new vectors.**

## Estimator

| Metric | Value |
|---|---|
| Coverage (full 8-knot set) | **1.000** — 288/288 captures, knots distribution `{8: 288}` |
| RMSE vs the true trajectory | median **7.88×10⁻⁵**, min 1.73×10⁻¹⁸, max 3.16×10⁻³ cyc/sample — **REPORTED, no bar (NOT ESTABLISHED)** |
| RMSE by trajectory (median) | static 3.16×10⁻⁵ · linear 1.40×10⁻⁴ · pass 1.27×10⁻⁴ |
| RMSE by severity (median) | 3.44×10⁻⁵ → 4.72×10⁻⁵ → 7.00×10⁻⁵ → 1.40×10⁻⁴ → 2.59×10⁻⁴ → 3.95×10⁻⁴ — error grows monotonically with severity, and the only two wrong payloads sit at the top two severities |
| Estimator failures (degraded coverage) | **0** — so C5's "no estimator failure may produce a wrong structure" sub-bar is satisfied vacuously, not demonstrated |
| Behaviour where there is nothing to correct | 8 knots produced on every static capture and on all 7 real-signal recordings; static-cell cost 0.021 correct-payload rate; **but `idle_carrier_0411` shows the estimator is not harmless on a null** |

Coverage is **not** described as validated outside this experiment, per the criteria file.

## Static regression

| Population | Arm A | Arm B | Verdict |
|---|---|---|---|
| **bench-v1 sealed** (30) | **30/30 TP**, 0 false accepts | **22 TP + 8 FN** — `test_008`, `009`, `011`, `014`, `017`, `018`, `025`, `027`, all refusals (3 × `SIGNAL_NO_CODE`, 5 × `UNKNOWN`), each with full 8-knot coverage | **FAIL** (bar: 30/30 exact) |
| **bench-v2 sealed** (430) | TP 98, TP_PARTIAL 2, REFUSED_OK 120, FN 207, FALSE_ACCEPT 3 → **9/9 criteria PASS** | TP 76, TP_PARTIAL 2, REFUSED_OK 119, FN 227, FALSE_ACCEPT 6 → **8/9**: `burst_block_interleaver_recall` **FAIL 4/12 = 33%** (bar 50%) | **FAIL** (bar: all 9 pass) |
| **Null set** (1,350 = 900 true nulls + 450 catalogue-coded) | true nulls **900/900 refused, 0 false accepts**; catalogue correct **128** (k7 61 / k5 36 / k3 31) | true nulls **900/900 refused, 0 false accepts**; catalogue correct **87** (k7 42 / k5 20 / k3 25) | true nulls **PASS**; catalogue controls **FAIL** (−41 files, tolerance 5) |
| **Real signals** (7 recordings) | JJY/DCF77/MSF/WWV `DECODED` with correct protocols; **WWVB `SIGNAL_NO_CODE`**; DDH47 ITA2 50 Bd; AIR AM carrier | **identical on all seven**, WWVB still `SIGNAL_NO_CODE` | **PASS** |
| **New static cells** (96) | correct 0.948, 0 wrong payloads, 0 wrong structures | correct 0.927, 0 wrong payloads, 0 wrong structures | **PASS** (Δ 0.021 ≤ 0.05) |

bench-v2's own null-class criterion is worth stating precisely: `no_false_accept_on_non_catalogue_signals` allows ≤1% with a Wilson upper bound ≤5%, so arm B's **1/120 = 0.83%** technically **passes that bench-v2 bar**. It does **not** pass this experiment's C3, which requires zero wrong structures. Both facts are reported; the stricter bar governs the decision.

## Integration cost (REPORTED, no bar)

Mean per capture over the 288-vector matrix:

| Arm | M(F1) | M(F2) | M(F3) | M(F4) | front ends | tracked front ends | bar(F1) |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 5607 | 179.3 | 7.477×10⁶ | 2958 | 67.2 | 23.0 | −4.821 |
| B | 5074 | 170.7 | 7.458×10⁶ | 2954 | 64.0 | 22.1 | −4.739 |
| C | 4933 | 166.5 | 7.409×10⁶ | 2949 | 62.5 | 21.5 | −4.743 |

A pre-correction slightly *reduces* the hypothesis burden (cleaner samples yield fewer surviving front ends), so the multiplicity cost measured here is mildly favourable. **This is exactly where the measurement must not be over-read:** arm B is a **pre-correction**, not a front end inside the enumeration. A real integration would *add* a front end counted in every family's M, raising every bar — which this experiment does not measure. Arm B is therefore an **upper bound on the benefit and a lower bound on the cost** of integration, and the structural failure above occurred even at that lower bound.

## Runtime

| Arm | mean | max |
|---|---:|---:|
| A | 0.549 s | 0.98 s |
| B | 0.535 s | 0.95 s |
| C | 0.531 s | 0.99 s |

Ratio **B/A = 0.97×** (bar ≤ 3×); max 0.95 s (bar ≤ 120 s).

## Decision

| Criterion | Verdict | Evidence |
|---|---|---|
| **C1 — static-carrier regression** (HARD) | **FAIL** | bench-v1 22/30 (bar 30/30); bench-v2 8/9 criteria (bar 9/9); null-set catalogue controls 128 → 87 (tolerance 5). Real signals PASS, new static cells PASS |
| **C2 — time-varying payload reliability** | **PASS** | treated wrong-payload **0.010** (bar ≤ 0.05); correct-payload **0.932** (bar ≥ 0.80); reported beside A (0.562) and C (0.000) |
| **C3 — structural safety** (HARD, outranks C2) | **FAIL** | `idle_carrier_0411` DECODED under arm B as `ccsds_tc_ldpc_128_64`/QPSK — a structural false accept on a null class, F4 margin +2.699 → **−0.112**, **0/18 converged** (also fails the pre-registered zero-convergence bar, T1). New-vector sub-checks pass: 0 wrong structures, min margin B +0.862 > A +0.443 |
| **C4 — refusal behaviour** | **REPORTED; one hard sub-bar FAIL** | Independent null set refusals held 900 → 900 (**PASS**); bench-v2 null-class refusals 120 → **119** (**FAIL** — the same idle-carrier event). Contradictory-reason sub-bar **NOT APPLICABLE** (T2). Recall and refusal reported separately throughout |
| **C5 — estimator coverage and failure** | **PASS** | coverage **1.000** (bar ≥ 0.95); RMSE reported, NOT ESTABLISHED; 0 degraded captures, so the wrong-structure sub-bar holds vacuously |
| **C6 — runtime** | **PASS** | 0.97× (bar ≤ 3×); max 0.95 s (bar ≤ 120 s) |

No aggregate score is computed, and none may be.

### **INTEGRATION NOT SUPPORTED**

Chosen by the pre-registered rules, not by preference, and by two independent routes: *"C1 fails on any bench, null-set or real-signal population → INTEGRATION NOT SUPPORTED"* and *"C1 passes, C2 passes, C3 fails → INTEGRATION NOT SUPPORTED; structural safety outranks payload recovery."* The immediate-stop condition (a false accept on a null class) fired as well.

**What the evidence does establish.** Within the tested conditions, blind per-block carrier pre-correction **recovers nearly all of the payload reliability lost to a time-varying carrier** — 0.010 wrong-payload against the oracle's 0.000 and the production engine's 0.562, at no runtime cost and with full estimator coverage. That is a real, measured finding, and it survives publication.

**What the evidence does not establish, and now positively contradicts.** That this estimator can be placed in front of ICHNOVA's structural search as it stands. It costs 8 of 30 bench-v1 decodes, one of bench-v2's nine criteria, 41 of 128 null-set catalogue decodes, and — the finding that ends the question — it manufactured a CCSDS LDPC claim out of an idle carrier.

**Claim discipline.** Nothing here supports: orbital Doppler validated, spacecraft RF validated, real-world space deployment, space-ready, universal blind decoding, or production deployment approved. `SPACE_CLAIM_FIREWALL.md` §2a stands unchanged, and the measured limitation in `SPACE_EVIDENCE_MATRIX.md` row 6 is **not** retired: time-varying-carrier payload reliability remains a measured limitation of the shipped engine, now with a measured reason why the obvious fix is not the fix.

## Reproduction

```bash
cd C:/Users/WVF-D/Downloads/SIH26147/repo
python eval/carrier_estimator.py demo
python -m pytest tests/test_carrier_estimator.py -q
python eval/carrier_estimator.py generate         # 288 captures, seeds 700000-700287 (guarded)
python eval/carrier_estimator.py run              # 864 analyses (arms A/B/C)
python eval/carrier_estimator.py regress bench1
python eval/carrier_estimator.py regress nullset
python eval/carrier_estimator.py regress bench2   # also evaluates bench-v2's 9 criteria + logs the access
python eval/carrier_estimator.py regress realsig
python eval/carrier_estimator.py report
python eval/carrier_estimator.py verify           # 288/288 byte-identical
```

## bench-v2 access

One entry was appended to `eval/bench2_access_log.jsonl` using bench-v2's own writer (`bench2._log_access`), in its exact format, extended with `experiment`, `purpose`, `arms` and `read_only: true`. bench-v2's vectors, manifest, criteria file, rows file, original result and historical report were **not** modified; its nine criteria were evaluated **in memory** from arm-A and arm-B rows via `bench2._evaluate_criterion`, imported verbatim. Arm A's in-memory evaluation reproduced **9/9 PASS** and its three documented wrong claims exactly, which is the check that the harness scores bench-v2 faithfully.

## What was not done, deliberately

- The estimator was **not** modified, re-tuned or re-run after the failures. Per the criteria file's no-optimization clause, a remediation must be separately pre-registered.
- No threshold, bar, family weight, `ALPHA`, `CFO_MAX`, `TRACK_MIN_SYMBOLS` or `F2_AGREEMENT_FLOOR` was changed; hypothesis enumeration and the F1 → F4 → F2 resolution order are untouched.
- No payload-reliability gate and no convergence requirement was added anywhere.
- No vector was excluded and no smaller sample substituted: all 30 bench-v1, all 430 bench-v2, all 1,350 null-set and all 7 real-signal captures were run under both arms.
- The SPACE-DOPPLER (192) and SPACE-DOPPLER-MECH-01 (144) datasets were not read, regenerated or re-scored.

**END OF CARRIER ESTIMATOR RESULTS**
