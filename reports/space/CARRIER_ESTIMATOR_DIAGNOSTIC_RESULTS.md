# CARRIER_ESTIMATOR_DIAGNOSTIC_RESULTS
**ICHNOVA · SIH26147 — `SPACE-CARRIER-EST-DIAG-01`: why does carrier pre-correction help under drift and hurt when the carrier is static?**
**Status: EXECUTED AND PUBLISHED AS-IS (2026-09-26). Read-only over existing sealed captures. No production file changed, no estimator knob touched, no threshold moved, no dataset generated.**

> **Headline. MEASURED FACT.** The estimator's output on the failing static capture is **not spurious** — its constant term matches that capture's true CFO to 6×10⁻⁷ cyc/sample. What the correction changes is **whether the engine builds any front ends at all**: on the untouched capture the engine constructs **0 front ends and tests 0 F4 hypotheses**, and corrections flip that to 10–30 front ends and 2048–3072 F4 hypotheses. Every F4 false accept observed occurred in a cell where the correction had switched that search **on**. A **synthetic** correction never derived from estimator error reproduced the false accept, and the estimator's **time-varying component alone** reproduced it with a bit-identical margin, while a **pure constant** correction never did. **H-A is refuted as the cause of the static recall loss; H-B is supported.**

**Labels:** **MEASURED FACT** (read off this run) · **ENGINEERING HYPOTHESIS** (inference beyond it).

---

## Objective

Determine *why* carrier pre-correction improves time-varying payload recovery (`SPACE-CARRIER-EST-01`: wrong payloads 108 → 2 of 192) while degrading static-carrier behaviour (bench-v1 30/30 → 22/30; bench-v2 9/9 → 8/9; catalogue controls 128 → 87; one idle carrier decoded as CCSDS TC-LDPC) — by manipulating the correction trajectory **independently of the estimator**, so that **estimation error** and **correction-transformation effect** are separated rather than confounded.

## Hypotheses

- **H-A** — static-carrier regression is primarily caused by non-zero/spurious estimator output: the estimator invents a trajectory where none is warranted.
- **H-B** — static-carrier regression can occur with *controlled* corrections that do not correspond to estimator error, i.e. the correction transformation itself changes the structural evidence presented to F4 and can manufacture a plausible false hypothesis.

Not mutually exclusive. `NEITHER ESTABLISHED` was a pre-registered acceptable outcome.

## Pre-registration

`eval/carrier_est_diag_criteria.json`, committed **before any synthetic correction was applied** and before any F4 outcome under a synthetic correction was observed. It fixes: the primary case, five correction shapes, seven non-zero magnitude multipliers plus the zero control, the deterministic secondary-case selection rule, the measurements, the margin convention (`eval/ladder.py:65`, negative = accepted), the decision rules, and the stop conditions.

**One design input was measured before the grid was fixed** (an input property of the estimator, not an engine outcome): on `bench2_sealed/idle_carrier_0411` the estimator returns 8 knots with **mean 5.838611×10⁻³**, rms 5.838616×10⁻³, and a **time-varying part of rms 7.82×10⁻⁶** — against the capture's recorded **true static CFO of 5.840×10⁻³**. The grid was then sized in multiples `m` of that mean, `M_est`.

**MEASURED FACT, and it reframes H-A immediately:** the estimator did not invent a trajectory on this capture. It measured the real static offset to within 6×10⁻⁷ cyc/sample and removed it; its time-varying component is ~750× smaller than its constant one.

**Deviations from the pre-registration: none.** No grid value, shape, case or rule was changed after any outcome was seen. No new vectors were generated; no bench-v2 access-log entry was written (no bench-v2 criterion was evaluated), consistent with `SPACE-F4-MARGIN-01`'s precedent and stated in the criteria file in advance.

## Primary idle-carrier case

`data/bench2/sealed/idle_carrier_0411.iq` — ground truth `idle_carrier`, `expected: REFUSAL`, Rician channel, Es/N0 3 dB, 24,080 samples, true static CFO 0.005840. **Any DECODED verdict is a structural false accept.**

| Condition | front ends | M(F4) | F4 bar | F4 margin | verdict |
|---|---:|---:|---:|---:|---|
| **A — original, untouched** | **0** | **0** | −2.699 | +2.699 | `SIGNAL_NO_CODE` |
| **C — explicit zero correction, same code path** | **0** | **0** | −2.699 | +2.699 | `SIGNAL_NO_CODE` |
| **B — estimator's exact trajectory** | 18 | 2048 | −6.010 | **−0.112** | **DECODED `ccsds_tc_ldpc_128_64` / QPSK, 0 of 18 converged** |

**MEASURED FACT — the zero control is an exact identity.** Arm C matches arm A on every recorded field (F4 best, bar, accepted, status, code, front-end count, every family's M). `mech._derotate(iq, zeros)` multiplies by `exp(0) = 1`, and the test suite pins that. **The correction machinery does not perturb the analysis**, so every effect below comes from the correction's magnitude or shape, not from the act of calling the function.

**MEASURED FACT — and this is the finding that reframes the whole question.** On the untouched capture the engine builds **0 front ends** and therefore tests **0 F4 hypotheses**: the `+2.699` figure is the degenerate M = 0 bar, **not** an F4 near-miss. The original refusal happens at front-end construction, before any block-code search exists. Every correction that produced an F4 acceptance had first switched that search **on** (18 front ends, 2048 hypotheses).

## Correction trajectory grid

Five shapes, all applied through the same `mech._derotate`, at `m ∈ {0.01, 0.03, 0.1, 0.3, 0.5, 1.0, 2.0} × M_est`:

| Shape | Constant term | Time variation | Purpose |
|---|---|---|---|
| `constant` | m·M_est | **none** | At m = 1 this is, to 6×10⁻⁷, exact removal of the capture's **true** static CFO — a physically correct correction |
| `linear_mean` | m·M_est (mean) | ramp | controlled time variation, large |
| `pass_mean` | m·M_est (mean) | bounded S-curve | controlled time variation, **not** derived from the estimator |
| `estimator_scaled` | m·M_est | the estimator's own | m = 1 reproduces arm B exactly |
| `varying_only` | **zero** | the estimator's varying part × m | isolates "spurious variation" from "static-offset removal" |

## F4 margin vs correction

MEASURED FACT (`*` = F4 accepted, i.e. a structural false accept; front-end count in brackets):

| Shape | m=0.01 | m=0.03 | m=0.1 | m=0.3 | m=0.5 | m=1.0 | m=2.0 |
|---|---|---|---|---|---|---|---|
| `constant` | +2.699 [0] | +2.699 [0] | +2.699 [0] | +2.699 [0] | +2.699 [0] | +2.299 [18] | +2.039 [18] |
| `linear_mean` | +1.544 [10] | +2.265 [10] | +3.076 [18] | +2.634 [30] | +2.699 [0] | +2.699 [0] | +2.699 [0] |
| `pass_mean` | **−1.050\*** [18] | +2.036 [18] | +2.699 [0] | +2.699 [0] | +2.263 [18] | +2.699 [0] | +2.184 [20] |
| `estimator_scaled` | +2.699 [0] | +2.699 [0] | +2.699 [0] | +2.699 [0] | +2.699 [0] | **−0.112\*** [18] | +1.529 [18] |
| `varying_only` | +2.699 [0] | +2.699 [0] | +2.699 [0] | +2.699 [0] | +2.699 [0] | **−0.112\*** [18] | +2.181 [18] |

**Three MEASURED FACTS from this table:**

1. **A pure constant correction never produces an acceptance** — at any magnitude, including m = 1 where it is the physically correct removal of the true CFO. It does switch the search on at m ≥ 1 (0 → 18 front ends) but the best F4 hypothesis stays 2.0–2.3 log units short of the bar.
2. **`varying_only` at m = 1 — which carries *no constant term at all* — produces the *bit-identical* margin −0.112, the same accepted hypothesis and the same 0/18 convergence as the full estimator correction.** The constant half of the estimator's correction is therefore irrelevant to this outcome; the time-varying half accounts for all of it.
3. **A synthetic correction never derived from the estimator also does it:** `pass_mean` at m = 0.01 (mean 5.8×10⁻⁵, a bounded S-curve) accepts at margin −1.050, with the same code and the same 0/18 convergence.

**MEASURED FACT — front-end construction is the switch, and it is not monotonic.** Across the grid the front-end count flips between 0 and 10/18/20/30, in both directions, with no ordering in `m`: `linear_mean` builds front ends at m ≤ 0.3 and none at m ≥ 0.5; `pass_mean` alternates 18, 18, 0, 0, 18, 0, 20. Whenever front ends exist, M(F4) jumps from 0 to 2048–3072 and the F4 bar moves from −2.699 to about −6.0 to −6.2.

## Acceptance transition

**MEASURED FACT: there is no transition in the sense of a threshold.** Smallest accepting `m` per shape: `constant` **none**; `linear_mean` **none**; `pass_mean` **0.01** only; `estimator_scaled` **1.0** only; `varying_only` **1.0** only. Acceptance is **sporadic and non-monotonic** — it appears at isolated cells and disappears at both larger and smaller magnitudes. No monotonic relation between correction magnitude and F4 margin exists in this data, and **no threshold may be derived from it**.

**ENGINEERING HYPOTHESIS.** The pattern is what one would expect if acceptance depends on a *coincidence* at the front-end and codeword-offset level — which front ends survive, and whether some LDPC codeword offset happens to align with the de-rotated bits — rather than on a smooth function of correction magnitude. This experiment does not establish that; confirming it would require reading the engine's front-end construction internals, which is a production read-out and out of scope here.

## Codeword convergence

MEASURED FACT. All three accepting cells produced **the same hypothesis** — `ccsds_tc_ldpc_128_64` (LDPC family), **converged 0 of 18 codewords** — and each published it as the final structure with modulation QPSK:

| Shape | m | margin | accepted hypothesis | converged | published |
|---|---|---|---|---|---|
| `pass_mean` | 0.01 | −1.050 | `ccsds_tc_ldpc_128_64` | **0/18** | `ccsds_tc_ldpc_128_64` / QPSK |
| `estimator_scaled` | 1.0 | −0.112 | `ccsds_tc_ldpc_128_64` | **0/18** | `ccsds_tc_ldpc_128_64` / QPSK |
| `varying_only` | 1.0 | −0.112 | `ccsds_tc_ldpc_128_64` | **0/18** | `ccsds_tc_ldpc_128_64` / QPSK |

Zero convergence in every case. As `SPACE-F4-MARGIN-01` established from `src/blockcode.py`, convergence is a **provenance marker, not an acceptance requirement**, so this is not itself the defect — but it is a consistent signature of these manufactured accepts, and in the shipped engine's own 1,810-capture population **no** F4 acceptance ever had zero convergence.

## Secondary cases

Pre-declared deterministic selection (first two by filename per group), 5 conditions each:

| Group | Captures | A original | C zero | B estimator | scaled m=0.1 | scaled m=1.0 |
|---|---|---|---|---|---|---|
| **G1 bench-v1 failures** | `test_008`, `test_009` | DECODED (TP) | **DECODED (TP) — identical to A** | `SIGNAL_NO_CODE` (FN) | DECODED (TP) | `SIGNAL_NO_CODE` (FN) |
| **G2 bench-v2 failures** | `burst_BPSK_k3_block_0041`, `burst_BPSK_k3_diag_0046` | DECODED (TP) | **identical to A** | `SIGNAL_NO_CODE` (FN) | DECODED (TP) | `SIGNAL_NO_CODE` (FN) |
| **G3 catalogue controls** | `k3_120_005`, `k3_120_008` | DECODED (TP) | **identical to A** | refused (FN) | `k3_120_005` FN / `k3_120_008` TP | refused (FN) |
| **G4 static unaffected** | `static_0000`, `static_0001` | correct payload | **identical to A** | **correct payload** | correct payload | correct payload |
| **G5 time-varying success** | `linear_0096`, `linear_0100` | **wrong payload** | **identical to A** | **correct payload** | wrong payload | **correct payload** |

**MEASURED FACTS:**

1. **The zero control is identical to arm A in all ten secondary captures** — same status, same margin, same outcome. The machinery is transparent everywhere, not just on the primary.
2. **The harm and the benefit both appear at the same place: full correction magnitude.** At m = 0.1 little happens in either direction (G1/G2 still decode, G5 still has the wrong payload). At m = 1.0 the static captures break (G1, G2, G3) **and** the time-varying captures are fixed (G5).
3. **The harm is not universal:** G4's static captures decode correctly under every condition, including full correction.
4. **The harmed static captures carry a real static CFO**, and the correction removing it is physically correct — yet the decode is lost.

## H-A assessment

### **H-A: REFUTED as the cause of the static-carrier regression. Narrowly SUPPORTED for the false-accept phenomenon only.**

**Refuted for the recall loss (MEASURED FACT):** the estimator's output on the primary capture matches its true CFO to 6×10⁻⁷ cyc/sample — not spurious. In G1/G2/G3 the recall loss appears precisely at **full, physically-correct magnitude** (m = 1.0) and is *absent* at m = 0.1, which is the opposite of what "spurious output" predicts: a smaller, less committal correction would be the safer one if error were the mechanism. The harm tracks the **correct** component of the correction, not an erroneous one.

**Narrowly supported for the idle-carrier false accept (MEASURED FACT):** there, `varying_only` at m = 1 — the estimator's *time-varying* component alone, which on a static capture is pure estimation noise — reproduced the acceptance exactly, while `constant` at m = 1 did not. In that specific event the spurious part of the estimator's output is the active ingredient.

## H-B assessment

### **H-B: SUPPORTED.**

**MEASURED FACT — controlled corrections not derived from estimator error reproduce both phenomena:**

- `pass_mean` at m = 0.01, a synthetic bounded S-curve, manufactured the **same** LDPC false accept on the idle carrier (margin −1.050, 0/18 converged, same published structure).
- `estimator_scaled` at m = 1.0 — a controlled, declared magnitude — reproduced the bench-v1, bench-v2 and catalogue-control recall losses exactly, and at m = 0.1 did not.
- Across the primary grid, corrections **change the hypothesis space itself**: front ends 0 ↔ 10/18/20/30, M(F4) 0 ↔ 2048–3072, and every family's bar moves with M (F4's bar from −2.699 to ≈ −6.0).

**ENGINEERING HYPOTHESIS (labelled, not established).** The transformation acts *before* the engine's own carrier estimation and changes which front ends survive; the engine's structural search then runs on a different hypothesis set with different bars. On a capture with no real structure, a newly enabled search occasionally finds an LDPC codeword offset that clears its bar. On a capture whose real structure the engine was already finding, pre-removing the carrier it was about to estimate loses the decode. One mechanism, opposite consequences.

## Alternative explanations

Considered, and none excluded by this experiment:

1. **Double correction.** The engine estimates and removes a constant CFO itself; a pre-correction means the offset is removed twice, once approximately. This would explain why constant corrections are largely inert in the F4 margin (the engine re-centres anyway) while still changing front-end construction. **Not tested** — it needs the engine's per-front-end CFO values, a production read-out.
2. **Front-end coherence thresholds.** Front-end construction depends on detection p-values and coherence statistics; a correction changes those inputs. This would explain the non-monotonic 0 ↔ 18 flips. **Not tested** for the same reason.
3. **Noise-realisation coincidence.** The sporadic acceptances may be alignment accidents specific to these samples rather than a property of corrections in general. Only three accepting cells were observed, all on one capture.
4. **Interaction with the Rician channel of the primary capture.** `idle_carrier_0411` carries block-flat fading; the result may not generalise to an AWGN idle carrier. **Not tested.**

## Limitations

1. **One primary capture** for the false-accept phenomenon, and **ten** secondary captures in total. This is a diagnostic, deliberately small — not a benchmark.
2. **Three accepting cells** is a thin basis for any statement about how often corrections manufacture structure.
3. **No engine internals were read.** Every conclusion rests on published outputs (front-end counts, family M and bars, F4 fields). The *reason* front-end construction is so correction-sensitive is therefore hypothesis, not finding.
4. **The margin comparison across cells with different M is not apples-to-apples:** when front ends are 0, F4 tests nothing and its "margin" is the degenerate M = 0 bar. This is stated wherever those cells appear and must not be read as "F4 nearly accepted".
5. **`pass_mean`'s mean is only approximately m·M_est** (the S-curve's own mean is ~0 but not exactly), a ≤2% effect that does not bear on the conclusions.
6. **No causal claim about the estimator outside this population.** The manipulation licenses statements about *these corrections on these captures*, nothing wider.

## Conclusion

**MEASURED FACT.** The correction machinery is transparent (zero correction ≡ no correction, on all 11 captures). The estimator's output on the failing static capture is essentially *correct*, not spurious. What corrections do is change **whether and how the structural search runs at all** — front ends 0 ↔ 30, M(F4) 0 ↔ 3072 — and both the benefit under drift and the harm when static appear together at **full correction magnitude**. A pure constant correction never manufactured a false accept; the estimator's time-varying component alone did, with a bit-identical margin to the full correction; and a synthetic S-curve correction did too.

**Therefore: H-A REFUTED as the cause of the static regression (narrowly supported for the false accept alone); H-B SUPPORTED.**

**ENGINEERING HYPOTHESIS, offered as the leading explanation and not established:** pre-correction preempts the engine's own carrier estimation and reshapes its front-end set, which is why one operation both rescues drifting captures and damages static ones. Establishing that requires a read-out of front-end construction — a production change, which this experiment neither made nor requests.

**What this does not change.** `SPACE-CARRIER-EST-01` remains **INTEGRATION NOT SUPPORTED** and immutable. No threshold, bar or estimator parameter was altered. No space capability claim is created or strengthened: `SPACE_CLAIM_FIREWALL.md` §2a stands, and time-varying-carrier payload reliability remains a **measured limitation** of the shipped engine — now with a measured account of why correcting the carrier up front is not a safe remedy.

## Reproduction

```bash
cd C:/Users/WVF-D/Downloads/SIH26147/repo
python eval/carrier_est_diag.py demo
python -m pytest tests/test_carrier_est_diag.py -q
python eval/carrier_est_diag.py primary      # 38 analyses on idle_carrier_0411
python eval/carrier_est_diag.py secondary    # 50 analyses, 5 pre-declared groups
python eval/carrier_est_diag.py report
```

Determinism: the primary run was executed twice and produced **38/38 rows identical** on every field except runtime.

**END OF CARRIER ESTIMATOR DIAGNOSTIC RESULTS**
