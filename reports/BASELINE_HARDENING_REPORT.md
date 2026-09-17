# SIH26147 — Evidence-First Baseline Hardening Report

**Date:** 2026-09-16 · **Branch:** `baseline-hardening` · **Commits:** `7a74986`, `0f71803` (on top of `4c8188b`)
**Environment:** Windows 11, Python 3.11.14, NumPy 2.4.2, SciPy 1.17.0, 8 logical cores
**Raw evidence:** `reports/data/` (benchmark JSON, oracle ladders, null-set report, scoring comparison)

Reproduce:

```bash
python src/generate.py sealed && python src/generate.py train
python -m pytest -q tests/test_core.py
python sealed_test.py data/sealed 30 && python sealed_test.py data/train 100
python eval/snr.py
python eval/nullset.py generate && python eval/nullset.py run && python eval/nullset.py report && python eval/nullset.py compare
python eval/ladder.py data/sealed 30 data/train 100
```

---

## IMPLEMENTED

| File | Change | Why |
|---|---|---|
| `src/pipeline.py` | Rewritten receiver: documented search domain; sps candidates = best 3 by lag-1 y⁴ quality + integer divisors + raw spectral estimate; both modulations tested; x²/x⁴ CFO candidates with p-values; syndrome hypothesis search; Bonferroni acceptance; DECODED / SIGNAL_NO_CODE / UNKNOWN; serial-independence front-end check; payload tie-break over equivalent front-ends and both polarities; full diagnostics; evaluation-only `_oracle` | Remove sps=6 / β / bonus leakage; add a calibrated reject path |
| `src/blind_id.py` | Dual-code syndrome sign test (exact Binomial null), interleaver domain, `decode_hypothesis` with consistency / path metric / MDL inputs. Removed `blind_identify`, `_CODED_BONUS`, K7-only restriction | Replace the 0.12 bonus with a statistic that has a known null |
| `src/analyze.py` | Kept symbol-rate spectrum (documented as single-segment periodogram), matched filter, M-power phase. Added lag-1 correlation, symbol-domain M2M4, calibrated PSK LLRs. Removed per-sample "SNR", `identify_modulation` (hid its statistic), `detect_signal`, `estimate_noise_variance` | LLRs were scaled by a meaningless per-sample SNR; the modulation statistic is now logged per sps candidate |
| `src/fec.py` | Terminated traceback starts from state 0 (was argmax — not ML, caught by the brute-force test); per-step metric renormalization | Correctness; long-block numerics |
| `src/decode_search.py` | Deleted | Superseded |
| `sealed_test.py` | Pass = DECODED and BER < 0.01; false accepts counted; per-file diagnostics JSONL; run metadata; Es/N0 columns; `--min-pass` / `--max-false-accept` | Harness no longer gates on consistency ≥ 0.98 |
| `eval/snr.py` | Per-sample SNR → Es/N0, Ec/N0, Eb/N0 formulas + independent genie measurement | SNR terminology |
| `eval/ladder.py` | Oracle ladder O0–O7 with O0 blind-diagnostic ranks | Failure attribution |
| `eval/nullset.py` | 1,350-file null / other-code set, outcome + false-accept tables, confusion matrix, threshold sweep, runtime profile, scoring comparison | Calibration |
| `tests/test_core.py` | 9 tests: textbook encoder vs `conv_encode`; Viterbi = exhaustive ML (K7/K5/K3, terminated/truncated); truncated decode; syndrome true vs wrong interleaver; syndrome null calibration; CFO tone; sps 4/6/8/10/12 aliases; noise → UNKNOWN, uncoded → SIGNAL_NO_CODE; guard against reintroducing dataset constants | Independent verification + regression protection |
| `.github/workflows/ci.yml`, `requirements.txt` | CI: pytest + regenerate bench-v1 + `--min-pass 28 --max-false-accept 0` | A 4/30 commit reached main before |

`src/generate.py` and the bench-v1 datasets were **not** modified.

---

## PROVEN

- **SPS=6 leakage is gone from inference** and guarded by a test. On bench-v1 train, BPSK files at sps 4/8 that the forced sps=6 modulation filter broke now decode (16 files gained vs baseline).
- **Viterbi equals exhaustive maximum likelihood** for K7, K5 and K3, terminated and truncated, on 150 noisy random frames against an independently written textbook encoder. This found and fixed a real defect: terminated traceback started from the best final state rather than state 0.
- **Encoder convention documented and tested:** bit *i* of the octal generator taps the input delayed by *i* (LSB = current input), i.e. impulse response of "171" is `1,0,0,1,1,1,1`. This is the bit-reversal of the MATLAB `poly2trellis` convention (where it would be 117/155).
- **The reject path works:** pure noise → UNKNOWN 475/500; uncoded BPSK → SIGNAL_NO_CODE 134/150; no file is forced to "K7".
- **Code acceptance is calibrated on this null set:** 6/900 false accepts on files with no catalogue code (0.67%, 95% upper bound 1.45%) against a 1% design target.
- **K5 and K3 are distinguishable from K7:** accepted coded files are labelled with the correct code in 61/61 (K7), 38/38 (K5), 40/42 (K3).
- **bench-v1 sealed unchanged at 30/30 with 0 false accepts**, about 5× faster.
- **Es/N0 definition verified:** formula Es/N0 = SNR_per_sample · L / n_sym matches a genie measurement to a median −0.64 dB (sealed) and −0.31 dB (train); the difference is implementation loss (fractional timing, filter mismatch), not a formula error.

## PARTIALLY PROVEN

- **Blind sps estimation.** True sps is in the candidate list for 30/30 sealed and 91/100 train files; 5 train failures pass only with the sps oracle (true sps ranked 4th–15th by q4).
- **Multiplicity control.** Bonferroni over all tested hypotheses holds on noise/uncoded/8PSK nulls, but **not** for wrong interleavers on genuinely coded data (below).
- **Coverage.** Evidence grows with covered bits, so full-coverage correct hypotheses dominate; but uncovered LLRs are not explicitly charged, and wrong partial-coverage interleavers are among the remaining false accepts.
- **Signal-presence test.** The exponential-periodogram null is anti-conservative: noise gets SIGNAL_NO_CODE on 21/500 files (4.2%) against a 1% target.
- **Standard compatibility.** CANNOT DETERMINE WITHOUT INSPECTING/GENERATING THE REQUIRED ARTIFACT (no MATLAB, GNU Radio or commpy reference vectors on this machine). Only the internal convention is proven.
- **CI.** Workflow written and the same commands pass locally; it has not run on GitHub because the branch is not pushed. CANNOT DETERMINE the Linux CI result until it runs.

## REMAINING FAILURES

1. **Wrong-interleaver false accepts on coded data:** 11/450 coded null-set files decoded with the wrong interleaver or code (9 K3, 2 K5); still 5 at τ = −6. Examples: true K3 16×24 accepted as 16×14; true K5 3×20 accepted as 6×20. The Binomial null assumes independent bits; a related interleaver on real codewords violates it. Precision at the shipped threshold: 0.884.
2. **Short blocks are unprovable:** L = 30 coded bits → 0/90 decoded; bench-v1 train 4×8 (32 bits) → 0/24. Ten parity checks give p ≥ 10⁻³, above the ≈10⁻⁶ Bonferroni bar.
3. **Low Es/N0 recall:** K7 correct decodes 3/34 at 3 dB, 13/40 at 6 dB, 20/40 at 9 dB, 25/36 at 12 dB.
4. **Uncoded QPSK detection is weak:** 121/150 UNKNOWN (x⁴ line too weak at these lengths).
5. **Signal detection is anti-conservative** (4.2% vs 1%).
6. **sps candidate misses** (5 train files) and **CFO candidate misses** (4 QPSK train files at 6.7–9.7 dB with no candidate within one x⁴ bin).
7. **Payload rotation ambiguity** is resolved only by assuming a zero encoder start state; real mid-stream captures need frame sync.
8. **The sign test is not the most powerful score measured** (see SCORING RESULTS).

---

## BENCHMARK RESULTS

### Baseline freeze (`4c8188b`)

| Item | Result | Runtime |
|---|---|---|
| tests | 4/4 | — |
| bench-v1 sealed | 30/30 | 86.7 s on a quiet machine (earlier session); 109.2 s in this session's re-run with overlapping load |
| bench-v1 train | 60/100 | 624.7 s quiet; 1326.2 s in the re-run with overlapping load |

### Hardened receiver (`0f71803`) — blind: no forced sps=6, no dataset sps/β lists, no 0.12 bonus, no ground truth

| Dataset | Pass | False accept | UNKNOWN | SIGNAL_NO_CODE | Runtime |
|---|---|---|---|---|---|
| bench-v1 sealed (30) | **30** | **0** | 0 | 0 | 16.6 s (0.55 s/file) |
| bench-v1 train (100) | **63** | **0** | 17 | 20 | 37.8 s (0.38 s/file) |

Train by transmitted block size:

| Coded bits | Pass | Refused (UNKNOWN / SIGNAL_NO_CODE) |
|---|---|---|
| 32 (4×8) | 0/24 | 24 — structurally unprovable at α = 1% |
| 64 (8×8) | 37/41 | 4 |
| 128 (8×16) | 26/35 | 9 |

### Oracle ladder (`reports/data/*_ladder.json`)

| Stage | Sealed first passes | Train first passes |
|---|---|---|
| O0 blind | 30 | 63 |
| O1 +modulation | 0 | 0 |
| O2 +sps | 0 | 5 |
| O3 +CFO | 0 | 6 |
| O4 +β | 0 | 0 |
| O5 +fractional timing | 0 | 1 |
| O6 +phase/rotation | 0 | 0 |
| O7 +interleaver | 0 | 24 |
| never | 0 | 1 (test_052: 32-bit, 8.1 dB, insufficient evidence even with all oracles) |

**Confound (measured):** 23 of the 24 O7 first passes are 32-bit files. Supplying the interleaver collapses the hypothesis count and lowers the Bonferroni bar; it does not indicate an interleaver-identification error. Blind modulation identification is no longer a failure cause (0 files at O1).

---

## LEAKAGE REMOVED

| Dataset-derived assumption | Status |
|---|---|
| sps fallback list `[4, 6, 8]` | **Removed** → integer sps domain 2–20 with ≥16 symbols (receiver spec) |
| `force_include=6` | **Removed** |
| Modulation ID at sps=6 (`_mod_sps`) | **Removed** → statistic q2/q4 logged at every sps candidate; both modulations tested |
| β candidates `[0.25, 0.5, 0.35]` | **Removed** → single `RX_BETA = 0.3`; the O4 oracle shows 0 files waiting on β |
| `_CODED_BONUS = 0.12`, accept at consistency ≥ 0.98 | **Removed** → syndrome sign test + Bonferroni α = 0.01 |
| K7-only search | **Removed** → K7, K5, K3 searched |
| CFO top-3 of x⁴ only; DC bin zeroed | **Replaced** → x² and x⁴ peaks with p-values (still a compute budget of 3 per order); DC no longer zeroed |
| CFO bound \|Δf\| ≤ 0.0125 fs (from generator ±0.01) | **Kept, declared** as a front-end spec; out-of-range behaviour untested |
| Single-block interleaver, r∈[2,16], c∈[4,24] | **Kept, declared**; repeated blocks / >384 bits not supported |
| Zero encoder start state, integer sps, fixed matched-filter delay, QPSK I-then-Q bit order, RRC pulse | **Kept, declared** in code comments; real captures violate several |
| `n_info_bits=400` passed into search | **Removed** (dead parameter) |
| bench-v1 sealed as "held-out" | **Renamed in docs** as a development-contaminated regression tripwire |

---

## NULL / FALSE-ALARM RESULTS

1,350 files (`eval/nullset.py`, seed0 500000): sps ∈ {3,4,5,6,7,8,10,12}, β ~ U(0.2,0.5), CFO ~ U(±0.01), timing ~ U(±0.5), Es/N0 ∈ {3,6,9,12} dB, coded lengths {30,60,120,240,384}.

| Class | n | UNKNOWN | SIGNAL_NO_CODE | DECODED |
|---|---|---|---|---|
| noise | 500 | 475 | 21 | 4 |
| uncoded BPSK | 150 | 16 | 134 | 0 |
| uncoded QPSK | 150 | 121 | 28 | 1 |
| 8PSK + K7 (out of family) | 100 | 94 | 5 | 1 |
| K7 | 150 | 51 | 38 | 61 (61 correct) |
| K5 | 150 | 63 | 49 | 38 (36 correct) |
| K3 | 150 | 59 | 49 | 42 (33 correct) |

**False accepts on null classes: 6/900 = 0.67% (95% Wilson upper bound 1.45%).** By class: noise 4/500 (≤2.0%), uncoded BPSK 0/150 (≤2.5%), uncoded QPSK 1/150 (≤3.7%), 8PSK 1/100 (≤5.4%). No length shows systematic failure (noise: L30 0, L60 2, L120 1, L240 0, L384 1).

Confusion matrix (rows truth, columns output):

| truth | UNKNOWN | SIGNAL_NO_CODE | K7 | K5 | K3 |
|---|---|---|---|---|---|
| noise | 475 | 21 | 1 | 2 | 1 |
| uncoded BPSK | 16 | 134 | 0 | 0 | 0 |
| uncoded QPSK | 121 | 28 | 1 | 0 | 0 |
| K7 | 51 | 38 | 61 | 0 | 0 |
| K5 | 63 | 49 | 0 | 38 | 0 |
| K3 | 59 | 49 | 1 | 1 | 40 |
| 8PSK+K7 | 94 | 5 | 1 | 0 | 0 |

Threshold sweep (evidence e = log10 p + log10 M; accept if e ≤ τ; a true positive requires the true code and interleaver):

| τ | Recall | FPR (nulls) | FNR | Precision | False accepts |
|---|---|---|---|---|---|
| −1 | 0.291 | 0.0433 | 0.709 | 0.645 | 39 null + 33 wrong-hypothesis |
| **−2 (shipped)** | **0.289** | **0.0067** | **0.711** | **0.884** | **6 null + 11 wrong-hypothesis** |
| −3 | 0.287 | 0.0011 | 0.713 | 0.942 | 1 null + 7 wrong-hypothesis |
| −4 | 0.256 | 0.0000 | 0.744 | 0.943 | 0 null + 7 wrong-hypothesis |
| −6 | 0.238 | 0.0000 | 0.762 | 0.955 | 0 null + 5 wrong-hypothesis |

Null evidence distribution: min −3.08, 1% quantile −1.78, median 0.04 — consistent with the analytic rule (−2). No universal guarantee is claimed; this is calibration on this generator family only.

---

## SCORING RESULTS

`python eval/nullset.py compare`: every (code × interleaver) hypothesis decoded at the **true** front-end, 180 coded vs 180 null files, L ∈ 60/120/240, ~270 hypotheses per file. File score = max over hypotheses.

| Method | AUC | TPR at 0 null FP | Identification accuracy | Null score range |
|---|---|---|---|---|
| Hard re-encode consistency (old) | 0.834 | **0.000** | 0.967 | [0.86, 1.00] |
| Soft path metric (Phase 2) | **0.994** | **0.939** | **0.989** | [0.00, 0.95] |
| MDL savings (length- and multiplicity-aware) | 0.800 | **0.000** | 0.972 | [−1042, +115] bits |
| Sign test evidence (shipped) | 0.960 | 0.844 | 0.900 | [−2.47, 2.18] |
| Syndrome soft z | 0.966 | 0.889 | 0.944 | [0.00, 3.62] |

- Hard consistency cannot reject noise: noise reaches 1.00 (short, near-zero-LLR hypotheses).
- MDL, as formulated, fails on noise: with near-zero LLRs a coded hypothesis appears to save bits for free. It would need an explicit "no signal" model.
- **The soft path metric is the most powerful separator measured**, but it has no analytic null; its threshold would have to be calibrated empirically at the blind receiver's ~10⁴ hypotheses per file. The sign test was kept for acceptance because its false-accept rate is known and was confirmed above.

---

## NEW UNKNOWN/REJECT BEHAVIOR

- **DECODED**: the best hypothesis passes p · M ≤ 0.01; payload from zero-start Viterbi.
- **SIGNAL_NO_CODE**: no hypothesis passes, but an x² or x⁴ spectral line is significant; hard-decision bits are returned, explicitly not decoded.
- **UNKNOWN**: neither; empty payload.
- Every result carries `accept{log10_p, log10_threshold, n_hypotheses}` and diagnostics: all CFO candidates (order, peak-to-floor dB, p), full sps table (q4, q2), sps candidates, modulation statistic per sps candidate with margin, top-5 hypotheses (code, interleaver, sps, CFO, modulation, rotation, checks, positives, log10 p, z, covered bits, total bits, coverage ratio, consistency, path metric, MDL savings, uncoded MDL = 0), runner-up margin, front-ends searched / rejected for serial dependence, per-stage timers.
- bench-v1 train refusals: 17 UNKNOWN + 20 SIGNAL_NO_CODE, all on files the old receiver either failed or "passed" only by assuming K7.

---

## RUNTIME

| Benchmark | Baseline `4c8188b` | Hardened `0f71803` | Change |
|---|---|---|---|
| bench-v1 sealed | 86.7 s (2.9 s/file, quiet) | 16.6 s (0.55 s/file) | 5.2× faster |
| bench-v1 train | 624.7 s (6.2 s/file, quiet) | 37.8 s (0.38 s/file) | 16.5× faster |
| null set (1,350 files) | — | mean 0.75–1.10 s/file by class, max 3.73 s | — |

Stage profile (bench-v1 train): syndrome search 81.5%, Viterbi 6.0%, matched filter 4.3%, sps table 4.0%, scoring 3.7%, CFO 0.6%. Mean 8,591 hypotheses per file (max 21,916); 38.7 front-ends searched and 61.5 rejected for serial dependence per file.

Scaling: cost ∝ CFO candidates (≤6) × sps candidates (typically 3–8) × modulation/rotation (3) × interleaver candidates (grows with stream length, capped by the 384-bit domain) × 3 codes. No catastrophic scaling was observed up to 384-bit blocks. **Functional ceiling:** a stream longer than ~768 LLRs has no interleaver candidates in the domain, so the receiver can only refuse. Full-payload (812-bit) captures will need a multi-block interleaver search before they can decode.

---

## REGRESSIONS

- **bench-v1 sealed:** 0 lost, 0 gained (30 → 30).
- **bench-v1 train:** 60 → 63; **13 lost, 16 gained.**
  - Lost: all 13 are 32-bit (4×8) blocks, now UNKNOWN (5) or SIGNAL_NO_CODE (8). These cannot reach significance at α = 1%; the baseline's passes there depended on assuming K7. This is an intended, scientifically positive regression.
  - Gained: 16 BPSK files at sps 4 or 8 (64 or 128 bits) previously broken by the sps=6 modulation filter.
- **Payload correctness:** no file on bench-v1 is DECODED with BER ≥ 0.01 (0 false accepts on both sets).
- Defects found and fixed during this work, each covered by a test: terminated Viterbi traceback; BPSK π and QPSK π/2 payload ambiguity (zero-start tie-break over both polarities); oversampled front-ends biasing short parity checks (train test_098 false accept → 0).

---

## BLOCKERS BEFORE CYCLIC-CAF

Stop-condition check:

| # | Condition | Status |
|---|---|---|
| 1 | SPS=6 hard-coded in inference | **Resolved** (removed; test guard) |
| 2 | Uncoded systematically reported as K7 | **Resolved** (uncoded BPSK 0/150, QPSK 1/150 decoded) |
| 3 | Noise systematically reported as K7 | **Resolved** (4/500 decoded, spread over K7/K5/K3) |
| 4 | No meaningful REJECT/UNKNOWN | **Resolved** |
| 5 | Acceptance has no null calibration | **Resolved for code acceptance** (0.67%, UB 1.45%); **unresolved for signal detection** (4.2% vs 1%) |
| 6 | Benchmark depends on hidden generator constants | **Partially resolved**: CFO bound, single-block interleaver domain, zero start state, integer sps and fixed MF delay remain as declared receiver specs |
| 7 | Scoring ignores multiplicity | **Resolved for independent-bit nulls; unresolved for wrong interleavers on coded data** (11 wrong-hypothesis accepts) |
| 8 | Partial coverage unpenalized | **Partially resolved**: evidence scales with coverage; uncovered LLRs are not charged |

Specific blockers for Cyclic-CAF: (a) conditions 5 (detection), 6, 7 and 8 above; (b) blind sps misses are 5/100 on train, and the remaining failures are dominated by short blocks and low Es/N0, not the symbol-rate estimator; (c) there is no Es/N0-swept, decoy-sps benchmark yet to measure an estimator gain against.

## BLOCKERS BEFORE SAGE-LITE

- Wrong-interleaver false accepts: feedback would refine parameters toward an accepted wrong hypothesis and raise its apparent evidence.
- The most powerful score (soft path metric) has no calibrated threshold at blind hypothesis counts; the calibrated score (sign test) has about 9 points lower identification accuracy.
- Payload rotation/polarity is resolved only by the zero-start-state assumption; there is no frame sync or CRC to verify a refined decode.
- bench-v1 transmits 30–60 payload bits; there is no full-payload benchmark on which to show a feedback gain.

## RECOMMENDED NEXT EXPERIMENT

**Wrong-structure null and coverage-consistent acceptance.**

- *Hypothesis:* wrong-interleaver accepts come from interleavers that share row or column structure with the true one and cover only part of the transmitted block; requiring the accepted hypothesis to also explain the measured transmission length removes them without losing true decodes.
- *Input:* the 450 coded null-set files, plus a re-run of each with the true interleaver excluded from the candidate list (a pure wrong-structure null).
- *Independent variables:* acceptance rule: (1) shipped sign test; (2) sign test + block-length consistency (r·c vs the symbol-energy span of the capture); (3) sign test + best-vs-related-runner-up margin; (4) empirically calibrated soft path metric.
- *Controlled:* front-end candidates, α = 0.01, generator.
- *Measurement:* wrong-hypothesis accepts, null false accepts, recall and precision per rule, with Wilson intervals.
- *Success:* wrong-hypothesis accepts ≤ 1% of coded files, recall within 2 points of the shipped rule, null FPR ≤ 1%.
- *Failure:* no rule reduces wrong-hypothesis accepts below 5 without losing more than 5 points of recall. In that case short-block identification claims must be withdrawn and bench-v2 (full payload) becomes the only valid evaluation.
- *Why first:* it is the only remaining mechanism by which the receiver confidently returns a wrong payload, and every later feature (CAF, SAGE-Lite, bench-v2) inherits it.
