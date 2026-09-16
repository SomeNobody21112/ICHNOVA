# SIH26147 — CURRENT PROJECT STATE
**Date:** 2026-09-16 · **Version:** 2.2 (baseline hardening, `0f71803`; evidence in `reports/BASELINE_HARDENING_REPORT.md`)

---

## Component Status Table

| # | Component | Status | Evidence | Next Action |
|---|---|---|---|---|
| 1 | .IQ ingestion (float32 interleaved) | **PROVEN** | `modem.py::load_iq`; test_core.py | Maintain |
| 2 | .WAV ingestion (int16 stereo I/Q) | **IMPLEMENTED, UNTESTED** | `modem.py::load_wav`; no test in repo | Add test |
| 3 | Signal detection (x²/x⁴ spectral line vs exponential null) | **PARTIAL** | Noise → SIGNAL_NO_CODE 21/500 (4.2% vs 1% target); uncoded QPSK often undetected (121/150) | Calibrate empirically |
| 4 | SNR / LLR scaling (symbol-domain M2M4) | **FUNCTIONAL** | Replaces per-sample kurtosis; Es/N0 definitions in `eval/snr.py` (formula vs measured median −0.6 dB sealed) | Validate estimator error |
| 5 | Symbol rate: sps domain 2–20, top-3 by lag-1 y⁴ + divisors + raw spectral estimate, code test resolves aliases | **PARTIALLY PROVEN** | No dataset constants. True sps in candidates 30/30 sealed, 91/100 train; oracle ladder: 5 train files wait on sps | Improve ranking |
| 6 | Modulation ID (both tested; q2/q4 statistic logged per sps candidate) | **PROVEN on bench-v1** | Oracle ladder: 0 train files wait on modulation (was 27 failures with the sps=6 filter) | Out-of-family class |
| 7 | CFO (x² and x⁴ lines, p-values) + M-power phase | **PARTIALLY PROVEN** | Oracle ladder: 6 train files wait on CFO (low-Es/N0 QPSK) | CFAR candidates, interpolation |
| 8 | Demodulation (RRC MF, fixed delay) | **PROVEN on sealed** | Genie decode = 1.000 consistency on every failure investigated | No fractional timing recovery |
| 9 | Soft-bit generation (LLR) | **PROVEN** | Convention verified: LLR>0 → bit 0 | Maintain |
| 10 | Catalogue FEC identification (K7, K5, K3, dual-code syndrome sign test, Bonferroni α=1%) | **PARTIALLY PROVEN** | Null set: 6/900 false accepts (≤1.45%); accepted codes labelled correctly 139/141; 11/450 wrong-interleaver accepts on coded data | Wrong-structure null (next experiment) |
| 11 | Block interleaver identification (single block ≤384 bits) | **PARTIALLY PROVEN** | 30/30 sealed; wrong related interleavers can be accepted (see #10); ≤32-bit blocks unprovable | Multi-block search for bench-v2 |
| 12 | Vectorized soft Viterbi (K7/K5/K3) | **PROVEN (self-consistent)** | Equals exhaustive ML vs an independent textbook encoder, terminated and truncated; terminated-traceback bug fixed. Standard (CCSDS/MATLAB) conformance not verified — convention is bit-reversed vs poly2trellis | Reference test vectors |
| 13 | Re-encode consistency | **RETIRED as acceptance** | Scoring comparison: noise reaches 1.00, AUC 0.834, TPR 0 at zero null FP. Kept as a diagnostic | — |
| 14 | bench-v1 sealed (regression tripwire) | **30/30, 0 false accepts** | Development-contaminated; 30–60 payload bits; CI gate ≥28 and 0 false accepts | bench-v2 full payload |
| 15 | bench-v1 train | **63/100, 0 false accepts** | 17 UNKNOWN + 20 SIGNAL_NO_CODE; all 24 32-bit files refused (unprovable); 64-bit 37/41, 128-bit 26/35 | Low Es/N0 recall |
| 16 | Rank-based blind FEC ID | **PARTIALLY PROVEN** | Collapses at 0.1% BER (consistent with DRDO paper: works at ≤10⁻⁴) | Clean-signal tool only |
| 17 | Regression tests + CI | **PROVEN locally** | 9/9 tests; `.github/workflows/ci.yml` not yet run on GitHub | Push and confirm CI |
| 18 | Deterministic data generation | **PROVEN** | Byte-identical from seed0 | Maintain |
| 19 | Cyclic-CAF estimator | **BLOCKED** | Stop conditions 5 (detection), 6, 7, 8 not fully resolved; only 5/100 train failures wait on sps | After wrong-structure null |
| 20 | SAGE-Lite feedback | **BLOCKED** | Wrong-interleaver accepts would be reinforced; no calibrated soft score; no frame sync/CRC | After wrong-structure null + bench-v2 |
| 21 | 2 dB QPSK rescue experiment | **PREMISE CHANGED** | Sealed 2 dB QPSK (003, 015, 018) now pass; spec's test_020/025 failures don't reproduce | Re-target at the 450-file stress set |
| 22 | Reject path (DECODED / SIGNAL_NO_CODE / UNKNOWN) | **PROVEN** | Noise UNKNOWN 475/500; uncoded BPSK SIGNAL_NO_CODE 134/150 | Maintain |
| 23 | Frame sync / bit-stream correlation | **FUTURE** | Stub only | P1 |
| 24 | FSK demodulation | **FUTURE** | Not implemented | P1 |
| 25 | QAM demodulation | **FUTURE** | Not implemented | P1 |
| 26 | Reed-Solomon decode | **FUTURE** | Not implemented; AFF3CT (MIT) available as reference | P1 |
| 27 | Concatenated FEC | **FUTURE** | Not implemented | P1 |
| 28 | GUI | **FUTURE** | Figures exist; no interactive GUI | P1 |
| 29 | Conv/diagonal interleavers | **FUTURE** | Not implemented | P2 |
| 30 | Catalogue LDPC | **FUTURE** | Not implemented | P2 |
| 31 | Conformal prediction | **FUTURE** | No prior art found for signal classification application | Research |
| 32 | Signal Genome | **FUTURE** | Not implemented | Research |
| 33 | Adversarial benchmark | **FUTURE** | Not implemented | Post-MVP |
| 34 | Real public IQ validation | **FUTURE** | Not run (external hosts blocked) | Required before claims |
| 35 | Arbitrary blind LDPC | **REJECTED** | Rank collapse demonstrated | Not for MVP |
| 36 | Arbitrary pseudo-random interleaver | **REJECTED** | Same collapse | Not for MVP |
| 37 | Generic CNN/ResNet classifier | **REJECTED** | Cumulant 100%; no need | Not for MVP |
| 38 | BSS/ICA | **REJECTED** | Single-signal unsolved | Not for MVP |
| 39 | Real-time SDR capture | **REJECTED** | Offline unstable; legality unclear | Not for MVP |
| 40 | Full SAGE/BCJR/factor-graph | **FUTURE** | Research-grade | After MVP |

---

## Critical Path

```
Wrong-structure null / coverage-consistent acceptance → detection-test calibration → bench-v2 (full payload, CRC) → Es/N0 waterfall → only then Cyclic-CAF / SAGE-Lite
```

---

## Session-2 Findings (2026-09-16)

| Finding | Impact |
|---|---|
| Interleaver keeps only rows×cols of the 812 coded bits → **codeword is never zero-terminated** | Tail-trimming Viterbi + zero-tail re-encode capped correct consistency at ~0.9; fixed with `terminated=False`. Caused the test_012/019 "genie failures" |
| Unpadded x⁴ FFT too coarse for ~40-symbol QPSK; true tone not always the top peak at 2 dB | 16× zero-padding + top-3 candidates decoded; fixed test_015/018 |
| Commit 677241f (Phase 2) was pushed unverified and scores **4/30** | Reverted. Path metric alone: 28/30; `_refine_cfo` alone: 3/30 (M4 lag-1 metric is nearly CFO-invariant) |

---

## Verification Commands

```bash
# Data is not committed; regenerate deterministically from repo root:
python src/generate.py sealed        # data/sealed, seed0=99000
python src/generate.py train         # data/train,  seed0=1000

python -m pytest -q tests/test_core.py   # must be 9/9
python sealed_test.py                    # must be 30/30, 0 false accepts (~20 s)
python sealed_test.py data/train 100     # currently 63/100, 0 false accepts (~40 s)
```

---

**CURRENT STATE COMPLETE**
