# F4_MARGIN_RESULTS
**ICHNOVA · SIH26147 — `SPACE-F4-MARGIN-01`: how close does the shipped engine run to an F4 block-code acceptance?**
**Status: EXECUTED AND PUBLISHED AS-IS (2026-09-26). Read-only characterisation. No production file changed, no threshold moved, no gate derived.**

> **Headline. MEASURED FACT.** Across **1,810** existing sealed captures analysed with the **unmodified shipped engine**, the F4 block-code family accepted **34** times. Every one of those 34 was on a capture that genuinely carries the claimed block code, and every one scored **correct** (32 TP + 2 TP_PARTIAL). **Zero** acceptances had zero converged codewords; all ten LDPC acceptances converged **24 of 24**. **Zero** acceptances supplied a wrong published structure, and **zero** occurred on any of the 900 true-null captures.

**Labels:** **MEASURED FACT** (read off this run) · **ENGINEERING INTERPRETATION** (inference beyond it).

---

## 0. A conflict in the authorising section, declared before measurement

`DOPPLER_MECHANISM_RESULTS.md` §11.1.9 pre-registered that *"any accept with zero converged codewords is a failure."* **That label was NOT applied here, and the reason is recorded in the protocol (`eval/f4_margin_protocol.json`, AMB-4) before any measurement was taken:**

- `src/blockcode.py` lines 175–177 state: *"Every codeword contributes its information bits, converged or not, so the payload stays aligned with the transmission; `converged_codewords` says which blocks are **proven consistent with H**."* Convergence is a per-block **provenance marker**, not an acceptance requirement.
- bench-v2's own scorer (`eval/bench2.py`, the `TP_PARTIAL` branch) treats an LDPC accept with only *some* codewords converged as **partial credit**, not as a false accept.

So the existing logic and specification establish the **opposite** reading, and §11.1.9's failure label is unsupported. Zero-convergence accepts are therefore **counted and characterised**, and judged only on whether the **published structure is wrong**. Four further ambiguities in §11.1.9 (existing data vs new vectors; the definition of "static"; vector counts; the margin's sign) are recorded with their declared resolutions as AMB-1, AMB-2, AMB-3 and AMB-5 in the same protocol file.

## 1. Objective

The exact question, from §11.1.9 and the authorising turn:

> Over the shipped engine's normal operating domain on static carriers: **how close does the F4 block-code family run to its acceptance boundary**, and does **acceptance with zero converged codewords** occur — and if it does, **is the published structure wrong**?

This exists because one F4 acceptance on record (`linear_0084`, in the **tracking-ablated** arm of `SPACE-DOPPLER-MECH-01`) cleared its bar by 0.066 log units with 0 of 18 codewords converged, and the shipped arm's nearest miss in that population was **+0.116 log units on a static capture** — proximity that is not drift-specific. It must be answered before any carrier estimator is permitted to change the samples the structural search consumes.

## 2. Population

**Arm: the shipped engine only** — `analyze_iq(iq)`, unmodified. No ablation, no pre-correction, no oracle. The tracking-ablated arm A of MECH-01 is **not** used as a substitute for the shipped engine anywhere in this experiment.

| Dataset | n | Role | Access |
|---|---:|---|---|
| bench-v2 sealed (`data/bench2/sealed`) | 430 | The catalogue families §11.1.9 names — burst, continuous stream, CCSDS concatenated, framed RS, TC-LDPC CLTU — across Es/N0 {3,6,9,12,15} and six channel classes | read-only |
| bench-v1 sealed (`data/sealed`) | 30 | The documented regression tripwire; static CFO by construction | read-only |
| Independent null set (`data/nullset`) | 1,350 | **Mixed by design** (`eval/nullset.py`:39–42): **900 true nulls** (noise, uncoded BPSK/QPSK, out-of-catalogue 8PSK-K7) where any decode is a false accept, plus **450 catalogue-coded** files (k7/k5/k3) where a correct decode exists | read-only |
| **Total** | **1,810** | | |

**Static vs non-static (protocol AMB-2).** Every capture in all three datasets carries a *static* CFO by construction. bench-v2 additionally applies one channel class per vector, so the two classes that move the carrier — `cfo_drift` (70) and `phase_noise` (52) — are labelled **non-static** and reported separately. **Primary static population: 1,688 captures.**

**Not in the population, and not touched:** `data/space_bench/doppler` (the sealed 192-vector experiment) and `data/space_bench/doppler_mech` (the 144-capture experiment). Neither was read, regenerated or re-scored. `data/bench2/calibration` and `data/bench2/train` are out of scope.

## 3. Method

- **Harness:** `eval/f4_margin.py`, driven by `eval/f4_margin_protocol.json` (sha256 `0235131beb3df7fa…`), committed before the harness existed.
- **Margin — the repository's own convention, not a new metric:** `eval/ladder.py:65` computes `log10p_margin = accept.log10_p − accept.log10_threshold`. This experiment uses the same form for F4: **margin = F4 `best_log10_p` − F4 bar**, so a **negative** margin means the bar was cleared (accepted) and a **positive** margin means the hypothesis fell short.
- **Extraction:** per capture, the engine's published `block_code` dict yields `best_log10_p`, `log10_threshold`, `accepted`, and — for an accepted hypothesis — its code, family (`rs` or `ldpc`), offset/randomizer, `n_codewords` and `converged_codewords`. `stream_code.accepted` is recorded too, so "which family supplied the published code" is answerable per capture.
- **Correctness, per dataset, using each dataset's own existing rule:** bench-v2 → `eval/bench2.py::_score` imported **verbatim**; bench-v1 → `sealed_test.py`'s rule (a conv-K7 claim whose payload matches at BER < 0.01); null set → `eval/nullset.py`'s rules, i.e. refusal is correct on the 900 true nulls, while the 450 k7/k5/k3 files require a matching code label, matching interleaver and BER < 0.01.
- **No bench-v2 file was written**, no criteria were evaluated, and **no entry was added to `eval/bench2_access_log.jsonl`**: this is a per-file diagnostic, not a criteria run.
- **A scoring error found and corrected before reporting.** The first pass applied the "any decode is a false accept" rule to all 1,350 null-set files, which produced 128 spurious FALSE_ACCEPTs — those 128 are *correct decodes* of the null set's catalogue-coded k7/k5/k3 subset. The rule was corrected to `eval/nullset.py`'s actual taxonomy, the sweep was re-run in full, and `tests/test_f4_margin.py` now pins the mixed-population rule. The F4 measurements were **identical** before and after (see determinism, below).
- **Determinism:** the two independent full sweeps produced **1,810/1,810 rows identical** on every field except `runtime` (and the re-defined correctness fields).
- **Machine-readable evidence:** `results/f4_margin_rows.jsonl`, one row per capture.

## 4. Results — MEASURED FACT

### 4.1 F4 evaluations and acceptances

| Quantity | Value |
|---|---|
| F4 evaluations (every capture receives one) | **1,810** |
| F4 **acceptances** | **34** — all in bench-v2 sealed; 0 in bench-v1 sealed, 0 in the null set |
| F4 rejections | **1,776** |
| Acceptances by hypothesis family | **24 RS**, **10 LDPC** |
| Acceptances by ground-truth class | `ccsds_concat` 18, `tc_ldpc_cltu` 10, `rs_framed` 6 — every one a capture that genuinely carries a block code |
| Acceptances by static label | 24 static, 10 non-static |
| Accepted-margin range | **−293.814 … −7.251** (the bar cleared by 7 to 294 orders of magnitude) |
| Outcome of the 34 acceptances | **32 TP + 2 TP_PARTIAL — all correct.** 0 incorrect |

### 4.2 Convergence — the specific condition under test

| Quantity | Value |
|---|---|
| Acceptances with **zero** converged codewords | **0** |
| LDPC acceptances (10): convergence | **24 of 24 in every single case** |
| RS acceptances (24) | `converged_codewords` does not apply — the RS path reports `n_decoded` and `symbol_errors` instead, so `n_converged` is recorded as null |
| F4 **structural rejections** that fired (degenerate-codeword guards, pre- and post-decode) | **0** in 1,810 captures |

The last row is itself a characterisation finding: in this population the F4 guards never had to fire — the p-value bar did all the work.

### 4.3 Margin distribution

| Population | n | F4 accepts | min margin | median | within 0.5 of the bar (rejected) | within 1.0 |
|---|---:|---:|---:|---:|---:|---:|
| bench-v2 sealed | 430 | 34 | −293.814 | +2.699 | 1 | 3 |
| bench-v1 sealed | 30 | 0 | **+2.074** | +2.699 | 0 | 0 |
| null set | 1,350 | 0 | **+0.399** | +2.699 | 2 | 6 |
| **static (primary)** | **1,688** | 24 | −293.814 | +2.699 | **2** | **8** |
| non-static (`cfo_drift`, `phase_noise`) | 122 | 10 | −293.814 | +2.699 | 1 | 1 |

The distribution is strongly bimodal: genuine block-code captures clear the bar by tens to hundreds of orders of magnitude, and everything else sits around +2.7. Only **3 of 1,776** rejected evaluations came within 0.5 log units of the bar, and only **9** within 1.0.

### 4.4 Ground-truth correctness across the run (context)

| Population | Outcomes |
|---|---|
| bench-v2 sealed (430) | TP 98, TP_PARTIAL 2, REFUSED_OK 120, FN 207, **FALSE_ACCEPT 3** |
| bench-v1 sealed (30) | **TP 30** — 30/30, reproducing the tripwire exactly |
| null set — 900 true nulls | **REFUSED_OK 900. Zero DECODED.** Reproduces the published 0/900 false accepts |
| null set — 450 catalogue-coded | correct decodes **k7 61 / k5 36 / k3 31**; **0** DECODED-but-wrong; the rest refusals |

**The 3 bench-v2 FALSE_ACCEPTs are the three already on record.** `SPACE_EVIDENCE_MATRIX.md` §0.1 documents that all three wrong claims in the 430-file sealed run fall in the `cfo_drift` channel class, in the classes `stream_k7`, `ccsds_concat` and `burst_8PSK_k3_diag`. This run found exactly those three files (`stream_k7_0251`, `ccsds_concat_0260`, `burst_8PSK_k3_diag_0165`), all on `cfo_drift` — an exact reproduction, and evidence that the engine is unchanged and the harness scores faithfully.

**MEASURED FACT, and directly on point: none of those three came from F4.** In all three the block-code family was **not accepted** (margins +2.699, +2.426, +2.821) and the published claim came from **F2**, the continuous-stream family. By claimed-versus-true code, one of the three is a genuine wrong structure (an 8PSK K3 burst published as BPSK continuous K7) and two are wrong payloads under a continuous-K7 claim. **The only wrong claims in bench-v2's sealed run are drift-related and F2-sourced; F4 supplied none of them.**

### 4.5 Runtime (characterisation, not a bar)

Mean **1.45 s**, max **123.6 s** — the maximum on `ccsds_concat_0275`, an 81,868-symbol concatenated capture. Reported because it exceeds the 120 s figure used as a *runtime guard in the Doppler experiments' own criteria*; that guard applies to those experiments' captures, not to this population, so this is an observation and not a failure.

## 5. Closest cases

### 5.1 Closest **rejected** evaluations in the shipped engine (smallest positive margin)

| Capture | Configuration | Margin | Ground truth | Channel | Es/N0 | Status | Final code | Correct |
|---|---|---:|---|---|---|---|---|---|
| `bench2_sealed/ccsds_concat_0268` | shipped | **+0.230** | `ccsds_concat` | `cfo_drift` — **non-static** | 12 | UNKNOWN | none | no (FN) |
| `nullset/uncoded_bpsk_240_012` | shipped | **+0.399** | `uncoded_bpsk` (true null) | static | 6 | SIGNAL_NO_CODE | none | **yes** |
| `nullset/noise_384_011` | shipped | **+0.401** | `noise` (true null) | static | 12 | UNKNOWN | none | **yes** |
| `bench2_sealed/burst_BPSK_k3_block_0042` | shipped | +0.666 | `burst_BPSK_k3_block` | `awgn` | 9 | SIGNAL_NO_CODE | none | no (FN) |
| `nullset/uncoded_qpsk_240_010` | shipped | +0.714 | `uncoded_qpsk` (true null) | static | 12 | SIGNAL_NO_CODE | none | **yes** |
| `nullset/k3_030_002` | shipped | +0.769 | `k3` | static | 3 | UNKNOWN | none | no (FN) |

**The closest static rejected margin in this population is +0.399, and it is a true null that the engine correctly refused.**

### 5.2 Closest **accepted** evaluations (the least emphatic acceptances)

| Capture | Configuration | Hypothesis | Margin | Converged | Final structure | Ground truth | Correct |
|---|---|---|---:|---|---|---|---|
| `bench2_sealed/ccsds_concat_0273` | shipped | `ccsds_rs_255_239` (rs) | **−7.251** | n/a (RS) | `ccsds_rs_255_239` / BPSK | `ccsds_concat` | **yes** (TP_PARTIAL) |
| `bench2_sealed/ccsds_concat_0270…0274` | shipped | `ccsds_rs_255_239` (rs) | −12.534 | n/a (RS) | `ccsds_rs_255_239` / BPSK | `ccsds_concat` | **yes** (TP) |
| `bench2_sealed/rs_framed_0287…0289` | shipped | `ccsds_rs_255_239` (rs) | −31.258 | n/a (RS) | `ccsds_rs_255_239` / BPSK | `rs_framed` | **yes** (TP) |
| `bench2_sealed/tc_ldpc_cltu_0290` | shipped | `ccsds_tc_ldpc_128_64` (ldpc) | −127.625 | **24/24** | `ccsds_tc_ldpc_128_64` / BPSK | `tc_ldpc_cltu` | **yes** (TP) |

Even the least emphatic acceptance cleared its bar by **7.25 orders of magnitude**. Full per-capture detail for all 34: `results/f4_margin_rows.jsonl`.

### 5.3 For comparison — the case that motivated this experiment (quoted, not recomputed)

| Capture | Configuration | Hypothesis | Margin | Converged | Final structure | Ground truth | Correct |
|---|---|---|---:|---|---|---|---|
| `linear_0084` (MECH-01) | **tracking ablated — not a shipped configuration** | `ccsds_tc_ldpc_128_64` | **−0.066** | **0/18** | `ccsds_tc_ldpc_128_64` / QPSK | conv K7 continuous / BPSK | **no** |
| `static_0009` (MECH-01) | shipped | — (rejected) | **+0.116** | n/a | conv K7 continuous | conv K7 continuous | yes |

`static_0009`'s **+0.116** remains the **tightest static F4 margin on record anywhere**, and it comes from the MECH-01 population, not this one. Nothing measured here displaces it.

## 6. STOP-BAR ANALYSIS

### **PARTIALLY RESOLVED.**

**What is now established (MEASURED FACT):**

1. **The specific feared condition does not occur in the shipped engine's normal operating domain.** In 1,810 sealed captures there is **no** F4 acceptance with zero converged codewords. All ten LDPC acceptances converged completely (24/24).
2. **No F4 acceptance published a wrong structure.** All 34 were on captures that genuinely carry the claimed block code, and all 34 scored correct.
3. **No F4 acceptance occurred on any of the 900 true nulls**, reproducing the published 0/900 false-accept result.
4. **F4 is not the source of the only wrong claims in bench-v2's sealed run.** All three came from F2 on the drifting channel class, with F4 rejected by 2.4–2.8 log units.
5. **The premise itself is unsupported.** "Acceptance with zero converged codewords is unsafe" is contradicted by the implementation's own documentation (`src/blockcode.py`: a provenance marker, not a requirement) and by bench-v2's scorer (partial credit). What made `linear_0084` a wrong structure was the **wrong code identity**, which arose only with the phase tracker ablated — a configuration that does not ship.
6. **The margin distribution is strongly bimodal**: genuine block codes clear by 7–294 orders of magnitude, everything else clusters near +2.7, and only 3 of 1,776 rejections came within 0.5 log units.

**What remains NOT established — why this is not RESOLVED:**

1. **The bound on the margin is empirical, not structural.** The shipped engine has been observed within **+0.116 log units** of an F4 acceptance on a *static* capture (`static_0009`, MECH-01). Nothing in the design bounds the margin away from zero; this experiment shows that on 1,810 existing captures it did not cross, not that it cannot.
2. **Adversarial structural conditions were never tested.** bench-v2's family I — captures engineered so a *plausible wrong hypothesis* scores strongly — is specified but **deferred** (`SPACE_BENCH_SPECIFICATION.md` §0). The question "can a legitimate-looking capture be constructed that pushes F4 over its bar with a wrong code?" is untouched by this run, by construction: the authorisation was to characterise the existing operating domain, not to search for a counterexample.
3. **This is one snapshot of existing sealed evidence.** No new vectors were generated (deliberately, per the authorisation), so the population contains no condition that was not already in the repository.
4. **The RS path's analogue of convergence was not characterised.** RS acceptances report `n_decoded` and `symbol_errors` rather than convergence; whether an RS acceptance can occur with *zero* codewords decoded is a separate question this run did not pose.

**ENGINEERING INTERPRETATION.** The structural-safety concern raised by `linear_0084` is, on this evidence, **specific to the ablated configuration and to a wrong code identity — not to the convergence count, and not to the shipped engine**. The residual risk is not a demonstrated defect; it is an unquantified tail, and the honest description is a characterised operating domain with an empirical margin floor rather than a guarantee.

## 7. Implication for the carrier estimator

**What this changes.** The F4 objection that justified sequencing `SPACE-F4-MARGIN-01` *ahead of* `SPACE-CARRIER-EST-01` is **substantially cleared**: on the shipped engine's existing operating domain, F4 does not accept on nulls, does not accept with zero convergence, and has never supplied a wrong published structure. There is now also a **measured baseline** for the estimator experiment's structural-safety control: static minimum rejected margin **+0.399** on this population, 34 acceptances all correct, and the full per-capture margin table in `results/f4_margin_rows.jsonl`.

**What this does not change. `SPACE-CARRIER-EST-01` remains BLOCKED pending authorisation**, for reasons this experiment did not address:

- The estimator's cost on static-carrier behaviour (bench-v1, bench-v2, the null set, the real-signal suite) is **unmeasured**.
- Arm D's benefit in MECH-01 came from an **evaluation-side pre-correction**, not a front end inside the engine's hypothesis structure — integration would raise every family's bar, which is unmeasured.
- The payload-reliability gate idea remains **weakened, not established** (MECH-01: score separation did not fully persist).
- The pre-registered control in `CARRIER_ESTIMATOR_EXPERIMENT.md` §6.3 — *arm B must not reduce the minimum F4 margin below arm A's* — is now the live guard, and it is the right one precisely because a pre-correction changes the bits the structural search consumes. Point 1 of §6 above is why that control matters: the margin floor is empirical.

**No production change is proposed or authorised by this report.** In particular, **no convergence requirement is added anywhere** — the evidence says the condition does not arise in the shipped engine, so adding a gate for it would be a change with cost and no measured benefit. No threshold was moved, no bar was introduced, and no space capability claim is created or strengthened: `SPACE_CLAIM_FIREWALL.md` §2a stands unchanged, and orbital Doppler, spacecraft RF, "space-ready" and "production estimator approved" remain exactly as forbidden as before.

## 8. Reproduction

```bash
cd C:/Users/WVF-D/Downloads/SIH26147/repo
python eval/f4_margin.py demo                    # harness self-check
python -m pytest tests/test_f4_margin.py -q      # 6 tests
python eval/f4_margin.py run                     # 1,810 read-only analyses -> results/f4_margin_rows.jsonl
python eval/f4_margin.py report                  # every table in this document
```

## 9. Minor discrepancy, recorded not resolved

The null set's catalogue-coded subset scored **k7 61 / k5 36 / k3 31** correct decodes here. `SPACE_EVIDENCE_MATRIX.md` records the published figures as **61 / 37 / 31**. The k7 and k3 figures reproduce exactly; k5 differs by **one file**. It was not investigated: it does not bear on the F4 question, and no null-set measurement was changed. Flagged so the difference is on the record rather than smoothed over.

**END OF F4 MARGIN RESULTS**
