# SIH26147 — CURRENT PROJECT STATE
**Date:** 2026-09-16 · **Version:** 2.0 (Research-Verified)

---

## Component Status Table

| # | Component | Status | Evidence | Next Action |
|---|---|---|---|---|
| 1 | .IQ ingestion (float32 interleaved) | **PROVEN** | `modem.py::load_iq`; test_core.py | Maintain |
| 2 | .WAV ingestion (int16 stereo I/Q) | **PROVEN** | `test_core.py::test_wav_stereo_iq` | Maintain |
| 3 | Signal detection (energy/power) | **PROVEN** | `analyze.py::detect_signal` | Maintain |
| 4 | SNR estimation (M2M4) | **PROVEN** | Functional across test set | Known crude/biased at extremes |
| 5 | Symbol-rate estimation (|x|+|x|²) | **PARTIALLY PROVEN** | 28/30 within 2%; fails test_020 (84,891 Hz) and test_025 (473,131 Hz) vs true 166,667 Hz | **P0 — Replace with Cyclic-CAF** |
| 6 | Modulation ID (cumulant C20) | **PROVEN** | 100% on sealed set | Extend to FSK/QAM (P1) |
| 7 | Carrier/phase estimation (M-power) | **PROVEN** | Within validated scope (AWGN + small CFO) | Extend later |
| 8 | Demodulation (RRC MF + timing) | **PROVEN** | Genie 100% confirms correctness | Maintain |
| 9 | Soft-bit generation (LLR) | **PROVEN** | Convention verified: LLR>0 → bit 0 | Maintain |
| 10 | Catalogue FEC identification | **PROVEN** | 3 conv codes + uncoded; consistency selection | Expand catalogue (P1) |
| 11 | Block interleaver identification | **PROVEN** | Factor-pair sweep; 28/30 correct | Expand types (P2) |
| 12 | Vectorized soft Viterbi (K=7) | **PROVEN** | Bit-identical to reference; ~13 ms/decode | Maintain |
| 13 | Re-encode consistency | **PROVEN** | Separates success (≥0.984) from failure (≤0.866) | Maintain |
| 14 | Sealed benchmark (28/30) | **PROVEN** | `sealed_results.json` | Target: 30/30 |
| 15 | Genie upper bound (100%) | **PROVEN** | `baselines.json` | Diagnostic reference |
| 16 | Rank-based blind FEC ID | **PARTIALLY PROVEN** | Collapses at 0.1% BER (consistent with DRDO paper: works at ≤10⁻⁴) | Clean-signal tool only |
| 17 | Regression tests | **PROVEN** | 6/6 passing | Extend with new components |
| 18 | Deterministic data generation | **PROVEN** | Byte-identical from seed0 | Maintain |
| 19 | Cyclic-CAF estimator | **LOCKED** | Not yet implemented; no open-source CAF estimator exists (verified) | **P0 — Implement** |
| 20 | SAGE-Lite feedback | **LOCKED** | Not yet implemented; no turbo-sync implementation exists anywhere (verified) | **P0 — After CAF** |
| 21 | 2 dB QPSK rescue experiment | **LOCKED** | Not yet executed | **P0 — After SAGE-Lite** |
| 22 | 30/30 sealed recovery | **TARGET** | Not achieved | Depends on 19-21 |
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
#19 (Cyclic-CAF) → #20 (SAGE-Lite) → #21 (Rescue Experiment) → #22 (30/30 target)
```

All are **P0**. Everything else is P1 or later.

---

## Key Research Findings Affecting State

| Finding | Impact on Project |
|---|---|
| No SNR wall for cyclostationary detection | CAF approach at 2 dB is theoretically sound |
| "Decoding as a Sensor" phrase is novel | Unique branding; defensible framing |
| Blind FEC + turbo-sync combination is literature gap | Strongest novelty claim |
| No open-source CAF or turbo-sync exists | SIH26147 fills real gaps |
| PROCITEC "revolver principle" = our catalogue approach | Industry validation; cannot claim catalogue novelty |
| URH archived March 2026 | One less open-source competitor |
| Rank methods collapse at 10⁻³-10⁻⁴ BER (consistent with DRDO paper) | Confirms catalogue strategy is correct |

---

## Verification Commands

```bash
# After ANY change to fec.py, modem.py, or analyze.py:
python3 tests/test_core.py          # must be 6/6

# Spot-check regression + known failures:
python3 - <<'PY'
import sys,json,numpy as np; sys.path.insert(0,'src')
from pipeline import analyze_file
def pber(d,o): d=np.asarray(d);o=np.asarray(o);L=min(len(d),len(o)); return min(np.mean(d[:L]!=o[:L]),np.mean((1-d[:L])!=o[:L]))
for f,exp in [('test_000','OK'),('test_007','OK'),('test_020','FAIL'),('test_025','FAIL')]:
    gt=json.load(open(f'data/sealed/{f}.iq.gt.json')); r=analyze_file(f'data/sealed/{f}.iq')
    ber=pber(r['payload_bits'],np.array(gt['original_bits']))
    got='OK' if ber<0.01 else 'FAIL'
    print(f, got, 'MATCH' if got==exp else '*** REGRESSION ***', 'cons',r['consistency'])
PY

# Full sealed (if ~5 min available):
python3 sealed_test.py              # must be 28/30
```

---

**CURRENT STATE COMPLETE**
