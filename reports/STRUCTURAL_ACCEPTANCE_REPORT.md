# Structural Acceptance — Wrong-Structure Null Experiment

**Date:** 2026-09-17 · Follows `BASELINE_HARDENING_REPORT.md` ("Recommended next experiment")
**Code:** `eval/acceptance.py`, `src/pipeline.py` (`_structural_rejection`, `_front_end_evidence`)
**Raw evidence:** `reports/data/acceptance_rules.md`, `acceptance_params.json`, `nullset_report_structural.md`

## Question

The shipped rule (syndrome sign test + Bonferroni, "R0") accepted 11 wrong code/interleaver hypotheses on 450 coded null-set files. Can structural consistency checks remove them without losing true decodes?

## Diagnosis of the 17 false accepts under R0 (null set)

| Mechanism | Count | Example |
|---|---|---|
| Modulation × interleaver alias (BPSK read as QPSK with doubled rows, or QPSK as BPSK with halved rows) | 8 | true BPSK 3×20 accepted as QPSK 6×20 |
| Partial coverage of the transmitted block | 5 | true 16×24 accepted as 16×14 (224 of 394 bits) |
| Barely significant (log10 p within 0.2 of threshold): the nominal α | 4 | noise at −5.67 vs −5.64 |

## Candidate rules (all applied only to hypotheses already significant under R0)

| Rule | Statistic | How its constant was set |
|---|---|---|
| **MC** modulation consistency | Non-overlapping pairs v = y²(2m+1)·conj(y²(2m)): Re(v) > 0 for BPSK, a fair coin for QPSK. Exact binomial tests: "BPSK present" (rejects QPSK hypotheses) and "count too low for BPSK at the M2M4 SNR" (rejects BPSK hypotheses) | α = 0.01, **untuned** |
| **BL** block-length consistency | Transmission span from a two-level change-point fit to \|y\|²; reject if covered symbols < span − Δ | Δ = 99th percentile shortfall of correct hypotheses (calibration split) = **1.7 symbols** |
| **RM** runner-up margin | log10 p gap to the best different (code, interleaver) | Largest margin costing ≤ 2 recall points on calibration = 2.0 decades |
| **PM** soft path-metric floor | Zero-start Viterbi path metric | 99th percentile of top-1 path metric on calibration null files = **0.926** |

## Protocol

- Null-set runs (1,350 files) plus a **wrong-structure null**: every coded file re-run with its true interleaver removed from the candidates, so any acceptance is wrong (450 runs).
- Constants calibrated on even-indexed files; results reported on odd-indexed files.
- Success criteria fixed before the run: wrong-hypothesis accepts ≤ 1% of coded files, recall within 2 points of R0, null false-accept rate ≤ 1%.

## Results: evaluation split (odd file index, not used for calibration)

| Rule | Recall (coded) | Wrong-hypothesis accepts | Null false accepts | Wrong-structure accepts |
|---|---|---|---|---|
| R0 (previous) | 0.311 | 5/225 (2.2%) | 3/450 | **39/225 (17.3%)** |
| R0+MC | 0.320 | 1/225 | 3/450 | 34/225 |
| R0+BL | 0.311 | 4/225 | 2/450 | 12/225 |
| R0+RM | 0.311 | 3/225 | 3/450 | 26/225 |
| R0+PM | 0.324 | 0/225 | 0/450 | 4/225 |
| R0+MC+BL | 0.320 | 1/225 | 2/450 | 7/225 |
| R0+MC+BL+RM | 0.307 | 0/225 | 2/450 | 1/225 |
| **R0+MC+BL+PM (adopted)** | **0.320** | **0/225 (≤1.7%)** | **0/450 (≤0.8%)** | **2/225 (0.9%, ≤3.2%)** |

**All three success criteria were met.** The wrong-structure null exposed a larger weakness than the original 11 accepts suggested: with the true interleaver absent, R0 accepted a related wrong one on 17% of coded files.

## Implemented receiver, full null set (both splits)

| Metric | R0 | Adopted rule |
|---|---|---|
| False accepts, 900 non-catalogue files | 6 | **0** (95% upper bound 0.43%) |
| Wrong decodes, 450 coded files | 11 | **0** |
| Correct decodes K7 / K5 / K3 | 61 / 36 / 33 | 61 / 37 / 31 |
| bench-v1 sealed / train | 30/30, 63/100 | 30/30, 63/100 (0 false accepts) |

## Limitations

- BL assumes the burst starts at the capture start (end-only change point).
- The PM floor is empirically calibrated on this generator family; a different channel (fading, phase noise) needs recalibration.
- Low-SNR recall is unchanged (K7: 3/34 correct at 3 dB Es/N0); blocks ≤ 32 coded bits remain unprovable.
- Every significant-but-rejected hypothesis is reported with its reason (`accept.significant_but_rejected`), so an operator can see what the receiver declined to accept.
