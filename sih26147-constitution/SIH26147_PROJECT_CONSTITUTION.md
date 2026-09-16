# SIH26147 — PROJECT CONSTITUTION

## 1. Project Identity

**Problem Statement:** SIH26147
**Project:** SIH 2026
**Document:** Master Project Constitution
**Status:** Active — Single Source of Truth
**Version:** 2.0 (Research-Verified)
**Date:** 2026-09-16
**Basis:** Reconciliation of v1.0 Constitution, Engineering Handoff, Selection Rationale, and independent literature verification via web search (all references verified 2026-09-16)

---

## 2. Constitutional Purpose

This document defines the single source of truth for the technical, scientific, experimental, architectural, and strategic direction of SIH26147.

It defines what the project is solving, what has been experimentally demonstrated, what is partially demonstrated, what has been selected for implementation, what remains future work, what is currently unknown, what has been rejected, how new capabilities must be validated, and what constitutes project completion.

No major implementation, architecture, benchmark, presentation, or research claim may contradict this Constitution without explicitly updating it.

The project prioritizes **measurable scientific capability over feature count, marketing language, or unnecessary complexity.**

---

## 3. Project Mission

SIH26147 aims to recover communication structure from degraded, non-cooperative signal observations when important transmission parameters are unknown or uncertain.

The system investigates blind inference of parameters including modulation, symbol rate, carrier frequency offset, timing, Forward Error Correction, interleaving, framing, and related signal structure.

The immediate engineering objective is to overcome the demonstrated low-SNR symbol-rate estimation bottleneck in the existing system.

The long-term objective is to transform the receiver from a strictly sequential processing chain into a **cross-layer iterative inference system**, where decoding evidence can refine upstream physical-layer estimates.

---

## 4. Core Project Thesis

### DECODING AS A SENSOR

**Literature search result (verified 2026-09-16):** The exact phrase "Decoding as a Sensor" does not appear in IEEE Xplore, Google Scholar, arXiv, or CrossRef. It is a novel framing coined by this project. The underlying mechanism has established analogues in the **code-aided synchronization** and **turbo synchronization** literature (see §21), but the specific phrase and its use as a design principle for blind receivers appears original.

Conventional blind signal processing follows a feed-forward architecture:

```
Signal → Parameter Estimation → Demodulation → FEC / Decoding → Output
```

An error in an upstream parameter propagates through every downstream stage and can prevent decoding.

SIH26147 investigates a different principle:

```
Signal → Initial Inference → Demodulation → Soft Information → Decoding
→ Consistency / Residual Evidence → Parameter Refinement
→ Demodulation Again → Decoding Again
```

The decoder is not treated solely as the final stage. Its output becomes evidence that may be used to refine the physical-layer parameters responsible for decoding uncertainty.

The first implementation will be a deliberately constrained **SAGE-Lite / decoding-assisted feedback loop**.

SAGE-Lite must not be represented as a complete implementation of full SAGE, BCJR, or Bayesian factor-graph formulation unless those systems are actually implemented and experimentally validated.

---

## 5. Project Principles

### 5.1 Evidence Before Claims

A capability becomes **PROVEN** only after appropriate project experimentation — not because literature suggests it should work, mathematics permits it, a prototype has been written, or another system uses it.

### 5.2 Preserve the Baseline

The existing working system is an experimental reference and must remain reproducible. New algorithms must be compared against the baseline before adoption.

### 5.3 Solve the Demonstrated Bottleneck First

Existing evidence identifies low-SNR symbol-rate estimation as the principal demonstrated bottleneck. MVP engineering priority: (1) symbol-rate estimation, (2) decoding-assisted parameter refinement, (3) regression protection, (4) broader validation.

### 5.4 Scientific Ambition With Engineering Restraint

Each proposed capability must demonstrate measurable benefit, technical feasibility, acceptable computational cost, architectural compatibility, reproducibility, and relevance to the project bottleneck.

### 5.5 UNKNOWN Is a Valid Scientific Outcome

Where available evidence is insufficient, the correct output may be `UNKNOWN` or `INSUFFICIENT EVIDENCE`.

---

## 6. Evidence Classification

| Status | Meaning |
|---|---|
| **PROVEN** | Directly demonstrated by project experiments or supplied experimental artifacts |
| **PARTIALLY PROVEN** | Demonstrated under some conditions but known to degrade or remain incompletely validated |
| **LOCKED** | Formally selected for implementation — does NOT mean PROVEN |
| **FUTURE** | Technically relevant capability intentionally deferred |
| **UNKNOWN** | Insufficient evidence currently exists |
| **REJECTED** | Explicitly excluded based on project constraints |

---

## 7. Claim Discipline

Project documentation must distinguish between:

- **"The literature shows..."** — established knowledge
- **"Our hypothesis is..."** — untested project conjecture
- **"Our implementation does..."** — what the code computes
- **"Our experiment measured..."** — artifact-backed numerical result

These must never be treated as equivalent.

---

## 8. Non-Negotiable System Constraints

### 8.1 CPU-Oriented Execution
MVP must execute on restricted CPU hardware. GPU must not become a prerequisite.

### 8.2 Air-Gapped Compatibility
No unnecessary dependence on cloud, APIs, network, or heavyweight ML frameworks.

### 8.3 Reproducibility
Experiments record: input data, algorithm version, configuration, random seed, estimated parameters, output metrics, runtime, failure information.

### 8.4 Auditability
Decisions traceable through measurable intermediate evidence. Prefer interpretable evidence over opaque predictions.

### 8.5 No Feature-Count Competition
The central objective is to demonstrate one technically meaningful capability convincingly:

> **A degraded signal that fails under conventional feed-forward inference may provide enough decoding evidence to improve the upstream inference responsible for that failure.**

---

## 9. Existing System — Verified Baseline

### 9.1 Baseline Architecture

Sequential, feed-forward blind signal-analysis pipeline in pure NumPy/SciPy on CPU.

**Environment (verified):** Python 3.12.3; numpy 2.4.4, scipy 1.17.1, scikit-learn 1.8.0, matplotlib 3.10.8. Single CPU core, ~3.9 GB RAM, no GPU. No GNU Radio, no PyTorch, no commpy.

### 9.2 Source Files

| File | Purpose | Lines |
|---|---|---|
| `src/generate.py` | Ground-truth signal generator | ~120 |
| `src/modem.py` | BPSK/QPSK, RRC, channel, IQ/WAV I/O | ~104 |
| `src/fec.py` | Conv encoder, vectorized soft Viterbi, block interleaver | ~145 |
| `src/analyze.py` | Detection, symbol-rate, carrier, cumulant mod-ID, demod, soft bits | ~168 |
| `src/blind_id.py` | GF(2) rank code/interleaver ID + CODE_CATALOGUE | ~148 |
| `src/decode_search.py` | Rotation/offset search + sync resolver (stub) | ~73 |
| `src/pipeline.py` | Staged blind pipeline `analyze_file()` | ~115 |
| `sealed_test.py` | Sealed harness + funnel | ~85 |
| `baselines.py` | Genie/classical baselines + ablations | ~89 |
| `tests/test_core.py` | 6 automated tests | ~76 |

### 9.3 Current Verified Performance

**Baseline: 28/30 successful recoveries (~93%) on sealed held-out benchmark.**

**Genie experiment: 100% payload recovery** when correct upstream parameters are supplied.

> The core decoding chain is capable of successful recovery when required upstream parameters are known. The principal remaining limitation is concentrated in blind parameter estimation.

30/30 remains a **target**, not a currently achieved result.

### 9.4 Signal Generation Parameters (verified from generate.py)

- Modulations: BPSK, QPSK. Sample rate: fs = 1,000,000 Hz. Payload: 400 random info bits/file.
- FEC: K=7 rate-1/2 convolutional, generators 171/133 octal (NASA/CCSDS), zero-terminated.
- Interleaver: block, dimensions per split.
- Channel: RRC pulse shaping, random carrier offset (±0.01 cyc/sample), fractional timing offset (±0.5 sample), random static phase, AWGN.

**Train vs Sealed split:**

| Parameter | TRAIN (seed0=1000, n=100) | SEALED (seed0=99000, n=30) |
|---|---|---|
| SNR (dB) | {0, 3, 6, 10, 15} | {2, 5, 8, 12} — **unseen** |
| sps | {4, 8} | {6} — **unseen** |
| Interleaver | {(4,8),(8,8),(8,16)} | {(6,10),(10,12)} — **unseen** |
| RRC roll-off β | {0.35} | {0.25, 0.5} — **unseen** |

---

## 10. Known Failure Mode

### 10.1 Low-SNR Symbol-Rate Estimation

The existing estimator uses spectral/cyclostationary information from |x| and |x|². At sufficiently low SNR, noise-generated spectral features dominate the true signal feature.

### 10.2 Known 2 dB QPSK Failures (from sealed_results.json)

| File | GT Mod | GT SNR | GT Symbol Rate | EST Symbol Rate | Consistency | BER | Status |
|---|---|---|---|---|---|---|---|
| test_020 | QPSK | 2 dB | 166,667 Hz | **84,891 Hz** | 0.866 | 0.490 | FAIL |
| test_025 | QPSK | 2 dB | 166,667 Hz | **473,131 Hz** | 0.854 | 0.495 | FAIL |

### 10.3 Failure Chain

```
Low SNR → Incorrect symbol-rate estimate → Incorrect timing/demodulation
→ Corrupted soft information → Viterbi receives poor evidence
→ Consistency fails → Payload recovery fails
```

This exposes a structural weakness in purely feed-forward architecture and motivates the cross-layer inference hypothesis.

---

## 11. Existing Proven DSP Corrections

These must not be reintroduced.

### 11.1 Matched-Filter Delay
Total group delay: `delay = len(h) - 1` (NOT `(len(h)-1)//2`). Two convolutions, two half-delays.

### 11.2 QPSK Unsigned Integer Overflow
`1 - 2*b` on uint8: `1 - 2*1 = -1` wraps to 255. Fix: cast bits to float64 before signed arithmetic. Nastiest bug — produces plausible wrong output, not crash.

### 11.3 QPSK M-Power Phase Estimation
BPSK: `ph = angle(mean(s^2)) / 2`. QPSK: `ph = (angle(mean(s^4)) - π) / 4`. Residual 90° ambiguity intentionally left for decode search.

### 11.4 Symbol-Rate Estimation
Combined |x| and |x|² with 1%-of-fs guard. Improved but does not eliminate low-SNR failure.

### 11.5 Viterbi Vectorization
~50× faster using scatter-max with argsort-ascending trick. Verified bit-identical.

---

## 12. DSP and Implementation Conventions

| Convention | Rule | Consequence if broken |
|---|---|---|
| LLR sign | `LLR > 0` favors bit = 0 | Every decode inverts |
| Matched-filter delay | `len(h) - 1` total (TX+RX) | Appears as noise |
| QPSK phase offset | Subtract π before `/4` in M-power | No valid rotation |
| Bit dtype | Cast to float before `1 - 2*b` | Silent corruption |
| Trellis termination | Encoder zero-terminates; Viterbi trims K-1 bits | Length mismatch |
| Complement-tolerant BER | `min(BER, 1-BER) < 0.01` | Under-count recoveries |
| Consistency acceptance | Re-encode agreement ≥ ~0.98 | False accepts if lowered |

---

## 13. Consistency Principle

Re-encode consistency: decode → re-encode → compare against received evidence.

**Observed separation:** successes ≥ 0.984, failures ≤ 0.866. Threshold: `≥ 0.98`.

This is an engineering criterion, not a universal statistical guarantee.

**Competitor note (verified 2026-09-16):** PROCITEC go2signals uses a similar catalogue-based approach they call the **"revolver principle"** (introduced 2003) — cycling through known modem configurations and testing against the signal. Our catalogue + consistency approach follows the same industry-standard pattern.

---

## 14. Existing FEC Scope

**CODE_CATALOGUE:** conv_k7_r12_171_133, conv_k5, conv_k3, uncoded.

Rank-method collapse data:

| BER into rank identifier | n correct | K correct |
|---|---|---|
| 0.000 | 5/5 | 5/5 |
| 0.001 | 4/5 | 0/5 |
| ≥0.005 | 0/5 | 0/5 |

This is consistent with published literature. The DRDO paper (Tamakuwala, Defence Science Journal, Vol. 69(3), 2019, DOI: 10.14429/dsj.69.13370) reports probability of detection = 1 for BER ≤ 10⁻⁴. The Hanyang University group (Choi & Yoon 2017; Jang et al. 2020, IEEE Access) has published extensively on improved rank-based methods for scant/noisy data, but all require very low BER. Swaminathan & Madhukumar (IEEE Trans Broadcasting, 2017, 78+ citations) addresses noisy classification but remains limited.

**Conclusion:** Catalogue-based identification via decode + consistency is the practical engineering solution and is the same approach used by commercial tools.

---

## 15. Runtime & Resource Baseline

| Metric | Value |
|---|---|
| Mean runtime per file | ~8.6 seconds |
| Maximum observed runtime | ~21 seconds (low-confidence QPSK) |
| Full 30-file sealed run | ~4–5 minutes |
| Viterbi inner-loop per decode | ~13 ms |

---

## 16. Baseline Preservation Rule

Before introducing a new estimator or feedback mechanism: (1) baseline must be reproducible, (2) passing cases identifiable, (3) failure cases reproducible, (4) baseline metrics recorded, (5) new methods compared directly.

---

## 17. Baseline Status Summary

| Component | Status |
|---|---|
| Signal detection | **PROVEN** |
| SNR estimation (M2M4) | **PROVEN** (crude/biased but functional) |
| BPSK/QPSK support | **PROVEN** |
| Symbol-rate estimation (|x|+|x|² spectral) | **PARTIALLY PROVEN** (fails at 2 dB QPSK) |
| Carrier/phase estimation (M-power) | **PROVEN within validated scope** |
| Soft-bit generation (LLR) | **PROVEN** |
| Catalogue FEC identification | **PROVEN within catalogue** |
| Block interleaver identification | **PROVEN within validated scope** |
| Vectorized soft-decision Viterbi | **PROVEN** |
| Re-encode consistency | **PROVEN** |
| 28/30 sealed recovery | **PROVEN** |
| Genie 100% recovery | **PROVEN** (upper-bound diagnostic) |
| Modulation ID (cumulant C20) | **PROVEN** (100% on sealed set) |
| Rank-based blind FEC ID | **PARTIALLY PROVEN** (collapses ~0.1% BER) |
| Frame sync / bit-stream correlation | **PLANNED** (stub only) |
| SAGE-Lite feedback | **LOCKED — NOT YET PROVEN** |
| Cyclic-CAF estimator | **LOCKED — NOT YET PROVEN** |
| 30/30 sealed recovery | **TARGET — NOT YET PROVEN** |

---

## 18. Target Architecture — Three Tiers

### 18.1 Current Verified Architecture (PROVEN)

```
Raw IQ → Signal Detection (M2M4) → Symbol-Rate Estimation (|x|+|x|² spectral)
→ Modulation ID (cumulant C20) → Demodulation (RRC matched filter + M-power)
→ Soft Bits (LLR) → Catalogue FEC Hypothesis → Block Interleaver Hypothesis
→ Soft Viterbi Decode → Re-encode Consistency → Accept/Reject
```

### 18.2 Next Implementation Architecture (LOCKED)

```
Raw IQ → Signal Discovery → Initial Parameter Estimation (Cyclic-CAF)
→ Hypothesis Generation → Demodulation → Soft Bits / LLRs
→ FEC / Deinterleaving → Viterbi Decoding → Re-encode + Consistency
  ├── Sufficient evidence → ACCEPT
  └── Insufficient → SAGE-Lite Feedback → Parameter Refinement
      → Demodulation Again → Decode Again (max 1–3 iterations)
```

### 18.3 Future Research Architecture

Full factor-graph inference, BCJR soft decoding, conformal uncertainty, Signal Genome. **FUTURE** until experimentally validated.

---

## 19. Phase 1 — Baseline Preservation

Before modifying the pipeline: preserve benchmark results, protect DSP conventions (§12), maintain regression tests (6/6), retain FEC catalogue, protect consistency mechanism, record runtime, reproduce failure cases.

---

## 20. Phase 2 — Cyclic-CAF Symbol-Rate Estimation

### 20.1 Objective

Improve symbol-rate estimation at low SNR. Primary target: 2 dB QPSK failures.

### 20.2 Scientific Background (References Verified 2026-09-16)

Linearly modulated signals exhibit second-order cyclostationarity at the symbol rate and its harmonics. The Cyclic Autocorrelation Function (CAF):

```
R_x^α[τ] = lim(N→∞) (1/N) Σ_{n=0}^{N-1} x[n+τ] · x*[n] · exp(-j2πα·n)
```

where α is the cyclic frequency. For symbol rate f_s = 1/T_s, peaks appear at α = k/T_s.

**Key theoretical advantage (verified):** Unlike energy detection, cyclostationary detection has **no SNR wall** — noise is stationary and does not contribute at nonzero cyclic frequencies. Given sufficient observation time, detection is theoretically possible at arbitrarily low SNR. (Tandra & Sahai, ~2005-2008, established the SNR wall concept for energy detection and showed cyclostationary detectors avoid it.)

**Foundational references (all verified):**
- W.A. Gardner, "Exploitation of Spectral Redundancy in Cyclostationary Signals," *IEEE Signal Processing Magazine*, Vol. 8(2), pp. 14-36, April 1991
- A.V. Dandawate & G.B. Giannakis, "Statistical tests for presence of cyclostationarity," *IEEE Trans. Signal Processing*, Vol. 42(9), pp. 2355-2369, 1994
- W.A. Gardner, A. Napolitano, L. Paura, "Cyclostationarity: Half a century of research," *Signal Processing* (Elsevier), Vol. 86(4), pp. 639-697, April 2006
- M. Oerder & H. Meyr, "Digital filter and square timing recovery," *IEEE Trans. Comms.*, Vol. COM-36, pp. 605-612, May 1988

### 20.3 Proposed Implementation

**Phase 2a — Improved spectral estimation with proper windowing:**
Use Welch's method (segmented, windowed FFT averaging) on |x| and |x|² rather than raw FFT. This reduces spectral leakage and noise floor, improving peak detectability at low SNR.

**Phase 2b — Statistical peak validation:**
Apply Dandawate-Giannakis significance testing: compare peak magnitude against noise-floor distribution. Accept only statistically significant peaks rather than raw maximum.

**Phase 2c — Multi-method fusion:**
Combine evidence from |x|, |x|², and (if needed) conjugate products. Weight by estimated reliability.

**Phase 2d — Constrained search:**
Exploit known fs to constrain sps ∈ [2, 20], limiting the search to physically plausible rates.

Start with 2a+2d (simplest viable). Add 2b and 2c only if needed.

**Do NOT implement the full 2D Spectral Correlation Function** unless the 1D approaches prove insufficient — the full SCF is O(N · K_α · K_f) and may exceed the CPU budget.

### 20.4 Open-Source Landscape (verified 2026-09-16)

**No turnkey open-source CAF-based symbol-rate estimator exists.** The closest is SSTGroup/Cyclostationary-Signal-Processing (MATLAB, 37 stars) which implements detection but not parameter estimation. Chad Spooner's CSP Blog provides extensive implementation guidance but code is not public. SIH26147 would fill an actual open-source gap.

### 20.5 Evaluation

Compare using: symbol-rate absolute error, percentage error, within-2% rate, false peak rate, runtime, robustness across SNR, regression on passing cases.

**Target:** ≥95% within-2% at 2 dB QPSK. This is a TARGET, not a guaranteed outcome.

---

## 21. Phase 3 — SAGE-Lite / Decoding-Assisted Feedback

### 21.1 Objective

Determine whether FEC decoder output can improve upstream physical-layer parameter estimates.

### 21.2 Theoretical Foundation (References Verified 2026-09-16)

The established literature calls this **"code-aided synchronization"** or **"turbo synchronization"**:

- N. Noels et al., "Turbo synchronization: an EM algorithm interpretation," *IEEE ICC '03*, vol. 4, pp. 2933-2937, 2003 — showed turbo sync is an instance of EM
- C. Herzet, V. Ramon, L. Vandendorpe, "A theoretical framework for iterative synchronization based on the sum-product and the expectation-maximization algorithms," *IEEE Trans. Signal Processing*, vol. 55(5), pp. 1644-1658, May 2007 — unified framework
- **C. Herzet et al., "Code-aided turbo synchronization," *Proceedings of the IEEE*, vol. 95(6), pp. 1255-1271, June 2007** — landmark survey (87+ citations)
- N. Noels et al., "A theoretical framework for soft-information-based synchronization in iterative (turbo) receivers," *EURASIP J. Wireless Comms and Networking*, 2005 — foundational treatment (86+ citations)
- J.A. Fessler & A.O. Hero, "Space-alternating generalized expectation-maximization algorithm," *IEEE Trans. Signal Processing*, vol. 42(10), pp. 2664-2677, 1994 — the SAGE algorithm itself (853+ citations)
- B.H. Fleury et al., "Channel parameter estimation in mobile radio environments using the SAGE algorithm," *IEEE JSAC*, vol. 17(3), pp. 434-450, March 1999 — SAGE applied to radio channels
- U. Mengali & A.N. D'Andrea, *Synchronization Techniques for Digital Receivers*, Plenum Press, 1997 — textbook reference (ISBN: 0306457253)

### 21.3 Literature Gap (CRITICAL FINDING — verified 2026-09-16)

**The turbo synchronization literature uniformly assumes the FEC code is KNOWN a priori.** The blind FEC identification literature (Filiol, Cluzeau, Barbier, Tamakuwala) assumes synchronization is already achieved.

**The specific combination — blind FEC identification from a catalogue followed by decode-aided synchronization refinement — does not appear to have been explicitly treated in the open literature.**

This is SIH26147's strongest novelty claim: not the individual algorithms (all established), but the closed-loop architecture where:
1. The code is blindly identified via catalogue + consistency
2. The decoded output feeds back to refine synchronization
3. Both happen in a non-cooperative/blind context

### 21.4 SAGE-Lite Definition

For the MVP, SAGE-Lite is a constrained approximation. It is **NOT** a full SAGE/BCJR/factor-graph receiver.

More precisely, it is **decision-directed synchronization refinement using FEC-corrected symbols from a blindly-identified code** — a specific instance of code-aided synchronization applied in a non-cooperative context.

The MVP version: operates around the existing pipeline, reuses decoder outputs, makes bounded parameter updates, limits iterations (1–3), exposes measurements, remains CPU-compatible.

### 21.5 Feedback Procedure

For each candidate failing consistency:

1. Preserve initial parameter estimates
2. Demodulate with current estimates
3. Generate LLRs
4. Run Viterbi decode
5. Reconstruct candidate transmitted symbols from decoded bits (re-modulate)
6. **Estimate residual timing error:** cross-correlate received MF output with reconstructed symbol sequence; peak offset gives timing estimate
7. **Estimate residual phase:** angle of cross-correlation provides phase residual
8. **Estimate residual CFO:** linear phase slope across symbol sequence
9. Apply bounded updates: |Δτ| ≤ 1.0 symbol period, |Δφ| ≤ π/2, |ΔΔf| ≤ 0.005 cyc/sample
10. Re-demodulate and re-decode
11. Stop when: consistency ≥ 0.98, OR max iterations, OR convergence (ΔConsistency < 0.005), OR divergence

### 21.6 What SAGE-Lite Is NOT

- Not a full continuous-time ML estimator
- Not jointly optimizing all parameters simultaneously
- Not using BCJR/forward-backward soft decoding (uses Viterbi hard/quasi-hard output)
- Not implementing a factor graph
- Not providing formal convergence guarantees

### 21.7 Open-Source Landscape (verified 2026-09-16)

**No open-source implementation of turbo synchronization or code-aided synchronization exists anywhere.** Not in GNU Radio, not in AFF3CT, not in CommPy, not in any GitHub repository found via search. This is an implementation gap that SIH26147 would fill.

---

## 22. Feedback Safety Rules

- Feedback is conditional (only when consistency < 0.98)
- Iteration count bounded (initially 1–3)
- Parameter updates bounded (§21.5)
- Every iteration logged
- Consistency measured each iteration
- Degradation detectable
- Best-consistency iteration preserved

---

## 23. The 2 dB QPSK Rescue Experiment

The defining MVP experiment. Full specification in `SIH26147_2DB_QPSK_RESCUE_EXPERIMENT.md`.

**Primary success criteria (TARGETS, not guaranteed):**
```
Consistency ≥ 0.98
Payload BER < 0.01
```

**Required ablation:** Baseline vs. feedback-with-decoded-symbols vs. feedback-with-raw-demod-symbols. Isolates whether FEC decoding contributes to improvement.

---

## 24. Acceptance Gates

**Gate 1 — Symbol-Rate Estimator:** Compare against baseline on failures + passing cases + runtime.

**Gate 2 — SAGE-Lite:** Rescue ≥1 failure, no unexplained regression, bounded runtime, reproducible.

**Gate 3 — Sealed Regression:** Full 28/30 must not regress. 30/30 is the target.

---

## 25. MVP Definition

1. Existing verified baseline pipeline
2. Robust low-SNR symbol-rate estimation (Cyclic-CAF)
3. Consistency-based hypothesis search
4. SAGE-Lite decoding-assisted feedback
5. BPSK/QPSK capability
6. Convolutional FEC capability
7. Re-encode consistency verification
8. Reproducible benchmark + regression harness
9. CPU-oriented, air-gapped execution

---

## 26. Features Explicitly Outside MVP

Full SAGE, BCJR, factor-graph inference, conformal prediction, generalized blind FEC reconstruction, arbitrary LDPC/pseudo-random interleaver discovery, multi-signal BSS, full protocol reconstruction, GUI systems, real-time SDR integration, generic CNN/ResNet classifiers, FSK/QAM/8PSK demod (P1), RS/concatenated FEC (P1).

---

## 27. Core Evaluation Metrics

### 27.1 Parameter Estimation Accuracy
Absolute error, relative error, within-tolerance rate. Primary: ≤2% of true symbol rate.

### 27.2 Decode Success
Payload BER < 0.01 (complement-tolerant) AND consistency ≥ 0.98.

### 27.3 Runtime
Mean, median, maximum, total benchmark runtime.

### 27.4 Failure Taxonomy
F1 (Detection) through F12 (Runtime). Primary failure from logged evidence, not retrospective assignment.

---

## 28. Benchmark Framework

**Level 1 — Sealed Regression:** Original 30-file benchmark. Current: 28/30. Target: 30/30.

**Level 2 — Controlled Synthetic:** Systematic variation of SNR, CFO, timing, modulation, roll-off, sps, FEC, interleaver.

**Level 3 — Real-World Public IQ:** Legally accessible recordings. Required before any generalization claim. **NOT YET EXECUTED.**

---

## 29. Experimental Discipline

Every new algorithm must have: baseline, hypothesis, controlled variables, independent variable, ground truth, metrics, ablation, success criterion (defined BEFORE results), failure criterion, reproducible script, saved results, interpretation (SUPPORTED / NOT SUPPORTED / INCONCLUSIVE).

---

## 30. Regression Protection

No new algorithm may replace baseline based on one success. Test: original passing cases (28), original failures (test_020/025), edge cases, held-out. Net loss is unacceptable.

---

## 31. Competitor Context (Verified 2026-09-16)

| System | Type | Blind ID? | Full Decode? | License | Status |
|---|---|---|---|---|---|
| PROCITEC go2signals | Commercial SIGINT | Yes ("revolver principle") | Yes (250+ modes) | Proprietary | Active |
| R&S SIGINT products | Commercial SIGINT | Yes | Yes | Proprietary | Active |
| DeepSig OmniSIG | Commercial AI | Yes (classify) | No | Proprietary | Active |
| GNU Radio | Open-source toolkit | No (blocks only) | Partial | GPL-3.0 | Active |
| URH | Open-source tool | Partial (simple mods) | No | GPL-3.0 | **Archived March 2026** |
| gr-satellites | Open-source decoders | No (protocol-specific) | Yes (known sats) | GPL-3.0 | Active |
| liquid-dsp | Open-source C library | No (primitives) | No | MIT (without FFTW) | Active |
| AFF3CT | Open-source FEC | No | FEC only | MIT | Active |
| scikit-dsp-comm | Open-source Python | No (teaching) | No | BSD-2-Clause | Active |
| NVIDIA Sionna | Research platform | No (simulation) | Simulation | Apache-2.0 | Active |

**Confirmed gap:** No open-source tool performs the complete pipeline of blind IQ ingestion → automatic parameter identification → payload extraction. SIH26147 occupies this position.

**Our differentiation is NOT capability breadth.** It is: open, offline/air-gapped, auditable, catalogue-driven, indigenous, with the cross-layer feedback architecture as the technical differentiator.

---

## 32. Dependency & Licensing Discipline

| Dependency | License | Status |
|---|---|---|
| numpy | BSD | Core — required |
| scipy | BSD | Core — required |
| scikit-learn | BSD | Core — minor utilities |
| matplotlib | PSF/BSD | Core — visualization |
| AFF3CT | MIT | Optional cross-check |
| liquid-dsp | MIT (without FFTW!) | Optional C speed path |

**Rules:** verify license at integration; prefer MIT/BSD; pin versions; offline wheels for air-gap. **Never embed GPL code** in deliverable. FFTW (GPL-2) must be excluded from liquid-dsp builds.

---

## 33. Security, Ethics, and Authorized-Use Boundaries

Testing uses project-provided synthetic datasets, publicly released datasets with appropriate rights, signals with explicit authorization. No unauthorized live interception. No claims of: arbitrary decryption, universal recognition, real-time interception, guaranteed attribution.

---

## 34. India-First Application Framing

Potential application domains (NOT deployment claims): spectrum monitoring, interference analysis, disaster communications, satellite communication analysis, telecom diagnostics, authorized defence research.

**DRDO context (verified):** DLRL (Defence Electronics Research Laboratory), Hyderabad handles COMINT/ELINT. No publicly available DRDO signal analysis tools were found. SIH26147's problem space aligns with DLRL's mission.

---

## 35. Novelty Discipline (Research-Verified)

### 35.1 Established Methods (NOT our invention)
SAGE/EM estimation, cyclostationary analysis, Viterbi decoding, convolutional coding, FEC-based consistency checks, M-power carrier estimation, cumulant modulation classification, catalogue-based hypothesis testing ("revolver principle" — PROCITEC, 2003).

### 35.2 Engineering Combination (defensible position)
The constrained combination of blind catalogue-based FEC identification with decode-assisted synchronization refinement under CPU/air-gap constraints. Re-encode consistency as the blind selector.

### 35.3 Literature Gap (strongest claim — verified)
The specific combination of blind code identification + decode-aided synchronization refinement is not treated in open literature. Turbo-sync assumes known codes; blind FEC assumes achieved sync. SIH26147 bridges this gap.

### 35.4 Novel Framing (verified)
"Decoding as a Sensor" does not appear in IEEE/Scholar/arXiv. The closest established terms are "code-aided synchronization" and "turbo synchronization."

Full audit in `SIH26147_NOVELTY_AUDIT.md`.

---

## 36. Risk Register

| Risk | Consequence | Response |
|---|---|---|
| CAF fails at 2 dB | Core target not solved | Multi-method fusion; characterize limits |
| SAGE-Lite fails to rescue | Hypothesis weakened | Diagnose; retain baseline |
| Feedback diverges | Bad parameter refinement | Bounded updates and iterations |
| Regression | Net reliability loss | Gate before adoption |
| Runtime excessive | Impractical | Profile early; constrain search |
| CAF compute cost too high | Exceeds CPU budget | Start simplest; benchmark early |
| SAGE-Lite can't converge from 3× error | Only helps "approximately right" cases | CAF must provide reasonable initial estimate |

---

## 37. Open Technical Questions

1. **Sampling-frequency semantics** for real NTRO data
2. **Phase ambiguity** — frame-sync needed (currently complement-tolerant workaround)
3. **SAGE-Lite update rule** — starting-point equations in §21.5, must be validated experimentally
4. **Low-SNR estimator limits** — minimum viable SNR must be measured
5. **Generalization** — performance outside sealed corpus untested
6. **SAGE-Lite convergence radius** — can it recover from grossly wrong initial estimate (3× off in test_025)?

---

## 38. Immediate Execution Order

```
1. Freeze baseline → Reproduce 28/30
2. Reproduce and isolate test_020/test_025 failures
3. Implement Cyclic-CAF estimator (simplest viable)
4. Benchmark symbol-rate estimation (baseline vs CAF)
5. Implement SAGE-Lite feedback loop
6. Run 2 dB QPSK rescue experiment
7. Run regression gate (full sealed benchmark)
8. Build adversarial synthetic benchmark
9. Validate on public IQ
10. Add advanced features only if justified
```

---

## 39. Research Frontier Summary

Full details in `SIH26147_RESEARCH_FRONTIER.md`. Key directions:

- **Conformal prediction** for formal UNKNOWN (Vovk et al. 2005; Bates et al. 2021)
- **Signal Genome** fingerprinting (FUTURE)
- **Full SAGE / BCJR** (Fessler & Hero 1994; Bahl et al. 1974, 9173+ citations)
- **Factor-graph inference** (Kschischang, Frey & Loeliger 2001, IEEE Trans IT)
- **Adversarial testing** framework

---

## 40. Final Project Doctrine

> **Do not guess when structure can provide evidence.**
> **Do not claim what has not been measured.**
> **Do not add complexity before proving necessity.**
> **Do not discard a working baseline without comparison.**
> **Do not confuse research literature with project results.**
> **When evidence is insufficient, UNKNOWN is a valid scientific answer.**

The central organizing principle:

> **DECODING AS A SENSOR.**

The system is successful not when it produces an answer, but when it can demonstrate why that answer is consistent with the observed signal.

---

## 41. Constitutional Authority

This document is the project's Single Source of Truth. When implementation, presentation, or discussion conflicts with this Constitution, the Constitution governs until new evidence is produced and the Constitution is explicitly updated.

Only implementation plus reproducible evidence can promote a capability through the evidence-status system.

---

**SIH26147 PROJECT CONSTITUTION v2.0 (Research-Verified) — COMPLETE**
