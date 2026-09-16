# SIH26147 — RESEARCH FRONTIER
**Date:** 2026-09-16 · **Version:** 2.0 (Research-Verified)

Ranked by **development priority** (MVP-relevance × feasibility × expected impact).

---

> **⚠ Baseline superseded (v2.1, 2026-09-16):** the code in this repo now scores **30/30** on the regenerated sealed set and **60/100** on the 100-file train set. The test_020/test_025 2 dB QPSK failures described below come from an earlier codebase/dataset and do not reproduce here (current test_020 = QPSK 8 dB, test_025 = QPSK 5 dB, both pass). See `SIH26147_CURRENT_STATE.md` and the v2.1 entry in `SIH26147_CONSTITUTION_CHANGELOG.md`. Kept for plan/history.

## Priority 1 — Cyclic-CAF Symbol-Rate Estimation

**Status:** LOCKED for immediate implementation

**Scientific basis:** Cyclostationary feature detection exploits periodicity in second-order statistics. Unlike energy detection, it has **no SNR wall** — noise (stationary) contributes nothing at nonzero cyclic frequencies. Given sufficient observation, detection is possible at arbitrarily low SNR (Tandra & Sahai, ~2005-2008).

**Verified references:**
- Gardner, *IEEE SPM* 8(2):14-36, 1991 — foundational tutorial
- Dandawate & Giannakis, *IEEE TSP* 42(9):2355-2369, 1994 — formal hypothesis tests
- Gardner/Napolitano/Paura, *Signal Processing* 86(4):639-697, 2006 — survey of 1500+ papers
- Oerder & Meyr, *IEEE T-Comm* COM-36:605-612, 1988 — square timing recovery

**Modern methods:** Kodithuwakkuge et al. (2021) — CNN on SCF surface for symbol rate; Socheleau, *IEEE J. Oceanic Eng.* 2022 — CAF for underwater acoustic; wavelet-based methods for very low SNR (Zhao et al. 2023, 2025).

**Open-source gap:** No turnkey CAF symbol-rate estimator exists. Closest: SSTGroup/Cyclostationary-Signal-Processing (MATLAB, detection only). Chad Spooner's CSP Blog provides theory guidance, no public code.

**Complexity:** Medium. **Expected value:** High — directly addresses bottleneck. **Promotion criterion:** ≤2% error on test_020/025 without regressing 28 passing files.

---

## Priority 2 — SAGE-Lite Decoding-Assisted Feedback

**Status:** LOCKED for implementation after CAF

**Scientific basis:** Code-aided synchronization / turbo synchronization — iterating between soft decoder and synchronization estimator, interpretable as EM (Noels et al. 2003).

**Verified references:**
- Fessler & Hero, *IEEE TSP* 42(10):2664-2677, 1994 — SAGE algorithm (853+ citations)
- Fleury et al., *IEEE JSAC* 17(3):434-450, 1999 — SAGE for radio channels
- Noels et al., *IEEE ICC '03*, pp. 2933-2937, 2003 — turbo sync as EM (~100 citations)
- **Herzet et al., *Proc. IEEE* 95(6):1255-1271, 2007 — landmark survey on code-aided turbo synchronization (87+ citations)**
- Herzet et al., *IEEE TSP* 55(5):1644-1658, 2007 — unified SP/EM framework
- Noels et al., *EURASIP JWCN* 2005 — soft-information sync framework (86+ citations)
- Mengali & D'Andrea, *Synchronization Techniques for Digital Receivers*, Plenum 1997

**CRITICAL LITERATURE GAP:** All turbo-sync literature assumes KNOWN FEC. All blind FEC literature assumes ACHIEVED sync. The combination is unexplored in open literature. This is the project's strongest novelty position.

**Open-source gap:** **No turbo sync implementations exist anywhere** — not GNU Radio, not AFF3CT, not CommPy, not any GitHub repository.

**Complexity:** Medium-high. **Expected value:** High if CAF provides reasonable initial estimate; UNKNOWN if initial estimate is grossly wrong. **Promotion criterion:** Rescue ≥1 failure with ablation showing FEC contribution.

---

## Priority 3 — Frame Synchronization / Bit-Stream Correlation

**Status:** FUTURE (P1)

**Basis:** Autocorrelation of decoded bit stream for periodic patterns; cross-correlation with known sync words. Standard in every digital receiver.

**Current status:** Stub only. System uses complement-tolerant BER as workaround.

**Complexity:** Low-medium. **Expected value:** Medium — removes hack, enables protocol analysis. **Promotion criterion:** Resolves phase ambiguity on ≥90% of decoded files.

---

## Priority 4 — FSK Demodulation

**Status:** FUTURE (P1)

**Basis:** Tone detection via Goertzel/FFT discriminators. Textbook (Proakis & Salehi). PS explicitly requests FSK.

**Complexity:** Low. **Promotion criterion:** ≥95% decode on FSK synthetic at ≥6 dB.

---

## Priority 5 — QAM Demodulation

**Status:** FUTURE (P1)

**Basis:** Requires amplitude + phase recovery, AGC. PS explicitly requests QAM.

**Complexity:** Medium. **Promotion criterion:** ≥90% decode on 16-QAM at ≥8 dB.

---

## Priority 6 — Reed-Solomon and Concatenated FEC

**Status:** FUTURE (P1)

**Basis:** RS(255,223) standard in CCSDS/DVB. AFF3CT (MIT, verified) supports RS, LDPC, Polar, Turbo, BCH — ideal reference/cross-check.

**Complexity:** Medium. **Promotion criterion:** Clean roundtrip + noisy decode.

---

## Priority 7 — Adversarial Synthetic Testing

**Status:** FUTURE (post-MVP)

**Basis:** Automated parameter-space search for failure boundaries. Analogous to fuzz testing.

**Complexity:** Medium. **Expected value:** Medium-high — discovers failures before judges.

---

## Priority 8 — Formal Uncertainty / UNKNOWN Classification

**Status:** FUTURE (Research)

**Basis:** Conformal prediction (Vovk et al. 2005) provides distribution-free prediction sets. Conformal risk control (Bates et al. 2021, JASA). No prior art found specifically for "conformal prediction signal classification" — this intersection appears unexplored.

**Complexity:** High. **Expected value:** Medium-long-term. **Promotion criterion:** Calibrated sets with empirical coverage ≥ 1−α on diverse benchmark.

---

## Priority 9 — Signal Genome Fingerprinting

**Status:** FUTURE (Research)

**Basis:** Persistent descriptor vector for recurring waveform recognition. Related to Specific Emitter Identification (SEI) literature.

**Complexity:** Medium. **Expected value:** Low for MVP, high for operations. **Promotion criterion:** Same-emitter fingerprints cluster while different emitters separate.

---

## Priority 10 — Full SAGE / BCJR / Factor-Graph Inference

**Status:** FUTURE (Research)

**Verified references:**
- Bahl et al., *IEEE T-IT* 20(2):284-287, 1974 — BCJR (9173+ citations)
- Kschischang, Frey & Loeliger, *IEEE T-IT* 47(2):498-519, 2001 — factor graphs + sum-product

**Complexity:** Very high. BCJR adds significant computation; factor-graph inference requires careful message scheduling. **Expected value:** High in principle, uncertain in practice on CPU. SAGE-Lite may capture most practical benefit.

---

## Priority 11 — Dandawate-Giannakis Statistical Testing

**Status:** FUTURE (may integrate with Priority 1)

**Verified reference:** Dandawate & Giannakis, *IEEE TSP* 42(9):2355-2369, 1994

Provides formal hypothesis testing for cyclostationarity with known asymptotic null distributions. Could replace heuristic peak-picking in CAF estimator.

**Complexity:** Medium. **Promotion criterion:** Lower false-positive rate while maintaining detection rate.

---

## Not Prioritized

| Item | Reason |
|---|---|
| BSS/ICA | Single-signal problem not solved |
| Deep learning modulation classifier | Cumulant C20 achieves 100%; no need demonstrated |
| Real-time SDR integration | Offline benchmark not stable; legality unclear |
| GUI-first development | DSP correctness first |
| Walsh-Hadamard Transform for code ID | Niche; catalogue working |
| NVIDIA Sionna integration | GPU-dependent; violates CPU constraint for MVP |

---

**RESEARCH FRONTIER COMPLETE**
