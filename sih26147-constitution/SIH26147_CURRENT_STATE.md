# SIH26147 — CURRENT PROJECT STATE
**Date:** 2026-09-16 · **Version:** 2.1 (code-verified)

---

## Component Status Table

| # | Component | Status | Evidence | Next Action |
|---|---|---|---|---|
| 1 | .IQ ingestion (float32 interleaved) | **PROVEN** | `modem.py::load_iq`; test_core.py | Maintain |
| 2 | .WAV ingestion (int16 stereo I/Q) | **IMPLEMENTED, UNTESTED** | `modem.py::load_wav`; no test in repo | Add test |
| 3 | Signal detection (energy/power) | **PROVEN** | `analyze.py::detect_signal` | Maintain |
| 4 | SNR estimation (kurtosis) | **FUNCTIONAL** | Only scales LLRs; Viterbi decisions are scale-invariant | Known crude/biased |
| 5 | Symbol-rate estimation (|x|+|x|² Welch) | **WEAK, COMPENSATED** | Raw estimate often wrong; pipeline ranks {est±1, 4, 6, 8} by M4 quality and lets decode pick. **sps=6 is force-included** (sealed-set bias) | P0 — remove sps=6 bias; Cyclic-CAF candidate |
| 6 | Modulation ID (lag-1 autocorr of s²) | **PROVEN on sealed** | 30/30; CFO-invariant. Uses sps=6 matched filter — suspect on sps 4/8 at low SNR | Extend to FSK/QAM (P1) |
| 7 | CFO (x⁴ raw IQ, 16× zero-pad, top-3 decoded) + M-power phase | **PROVEN on sealed** | True CFO in top-3 on 30/30; decode consistency selects | Maintain |
| 8 | Demodulation (RRC MF, fixed delay) | **PROVEN on sealed** | Genie decode = 1.000 consistency on every failure investigated | No fractional timing recovery |
| 9 | Soft-bit generation (LLR) | **PROVEN** | Convention verified: LLR>0 → bit 0 | Maintain |
| 10 | Catalogue FEC identification | **PROVEN (K7 only)** | K7 + uncoded searched; K5/K3 in catalogue but disabled | Re-enable K5/K3 and re-measure (P1) |
| 11 | Block interleaver identification | **PROVEN on sealed** | Factor-pair sweep; 30/30 correct | Expand types (P2) |
| 12 | Vectorized soft Viterbi (K=7) | **PROVEN** | `terminated=False` mode for truncated codewords; `tests/test_core.py` | Maintain |
| 13 | Re-encode consistency | **PROVEN** | Correct hypothesis = 1.000 on 30/30 sealed; wrong ≤0.942 (genie sweep). Accept threshold 0.98 | Maintain |
| 14 | Sealed benchmark | **30/30** | `python sealed_test.py`. ⚠ Session-2 fixes were diagnosed on this set, so it is no longer truly held-out | Use train set + fresh seeds as held-out |
| 15 | Train set (held-out for session-2 fixes) | **60/100** | `python sealed_test.py data/train 100`; Phase 1 code: 35/100 (BER-only). Failures: 27 BPSK (incl. 10–15 dB at sps 4/8) + 13 QPSK at 0–3 dB | **P0 — next target** |
| 16 | Rank-based blind FEC ID | **PARTIALLY PROVEN** | Collapses at 0.1% BER (consistent with DRDO paper: works at ≤10⁻⁴) | Clean-signal tool only |
| 17 | Regression tests | **PROVEN** | `python tests/test_core.py` → 4/4 | Extend with new components |
| 18 | Deterministic data generation | **PROVEN** | Byte-identical from seed0 | Maintain |
| 19 | Cyclic-CAF estimator | **DEFERRED** | Not needed for 30/30; may help train-set sps 4/8 failures | P1 — measure on train set first |
| 20 | SAGE-Lite feedback | **PARTIAL (candidate selection)** | Decode consistency selects among CFO/sps/β/rotation candidates; iterative refinement not implemented | P1 |
| 21 | 2 dB QPSK rescue experiment | **PREMISE CHANGED** | Sealed 2 dB QPSK (003, 015, 018) now pass; spec's test_020/025 failures don't reproduce | Re-target at the 450-file stress set |
| 22 | 30/30 sealed recovery | **ACHIEVED** | 2026-09-16, consistency 1.000 on all 30 | Guard against regression |
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
Train set (60/100) → remove sps=6 bias (#5, #6) → 450-file QPSK stress set (#21) → re-enable K5/K3 (#10)
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

python tests/test_core.py            # must be 4/4
python sealed_test.py                # must be 30/30 (~2 min)
python sealed_test.py data/train 100 # currently 60/100 (~10 min)
```

---

**CURRENT STATE COMPLETE**
