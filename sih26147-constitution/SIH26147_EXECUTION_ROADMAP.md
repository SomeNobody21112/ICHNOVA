# SIH26147 — EXECUTION ROADMAP
**Date:** 2026-09-16 · **Version:** 2.0 (Research-Verified)

---

> **⚠ Baseline superseded (v2.1, 2026-09-16):** the code in this repo now scores **30/30** on the regenerated sealed set and **60/100** on the 100-file train set. The test_020/test_025 2 dB QPSK failures described below come from an earlier codebase/dataset and do not reproduce here (current test_020 = QPSK 8 dB, test_025 = QPSK 5 dB, both pass). See `SIH26147_CURRENT_STATE.md` and the v2.1 entry in `SIH26147_CONSTITUTION_CHANGELOG.md`. Kept for plan/history.

## Execution Philosophy

Fix the demonstrated bottleneck first. Do not add features until the core scientific capability is proven. Every step has an explicit acceptance criterion and regression gate.

---

## STEP 0 — Freeze Baseline

**Objective:** Ensure the existing 28/30 system is reproducible and protected.

**Actions:**
1. Reproduce the sealed benchmark: `python3 sealed_test.py` → confirm 28/30
2. Verify test_core.py: 6/6 passing
3. Record baseline metrics:
   - Per-file: symbol-rate estimate, modulation, interleaver, consistency, BER, runtime
   - Aggregate: 28/30 recovered, mean runtime, max runtime
4. Tag/snapshot the codebase as `baseline-v1`
5. Verify determinism: regenerate sealed data from seed0=99000, confirm byte-identical

**Acceptance:** 28/30 reproduced. 6/6 tests pass. Baseline metrics recorded.

**Regression gate:** N/A (this IS the baseline).

**Duration estimate:** 1 hour (includes environment setup + full run).

---

## STEP 1 — Reproduce and Isolate Failure Characteristics

**Objective:** Confirm the exact failure mechanism for test_020 and test_025.

**Actions:**
1. Run pipeline on test_020, capture verbose output:
   - GT symbol rate: 166,667 Hz
   - Estimated symbol rate: ~84,891 Hz (expected)
   - Consistency: ~0.866 (expected)
   - BER: ~0.49 (expected)
2. Run pipeline on test_025, capture verbose output:
   - GT symbol rate: 166,667 Hz
   - Estimated symbol rate: ~473,131 Hz (expected)
   - Consistency: ~0.854 (expected)
   - BER: ~0.495 (expected)
3. Run genie mode on both files (supply true sps) → confirm both decode successfully
4. Document: the failure is F4 (Symbol-Rate Estimation Failure) in both cases
5. Characterize the spectral evidence: plot |x| and |x|² spectra for both files, identify where the false peak appears vs the true symbol-rate line

**Acceptance:** Both failures reproduced with matching numbers. Genie confirms both are rescuable. Spectral analysis shows the false-peak mechanism.

**Regression gate:** Baseline unchanged.

**Duration estimate:** 2 hours.

---

## STEP 2 — Implement Cyclic-CAF Estimator

**Objective:** Build a symbol-rate estimator that can recover the correct rate at 2 dB QPSK.

**Actions:**

### 2a — Simplest viable implementation
1. Implement zero-lag CAF: `R_x^α[0] = (1/N) Σ x[n] · x*[n] · exp(-j2πα·n)`
2. This is equivalent to: take the FFT of `x[n] · x*[n]` ... wait, for the zero-lag case R_x^α[0], this simplifies to the Fourier transform of the instantaneous autocorrelation at lag 0, which is just the power spectral density — not useful alone.

   **Correct approach for symbol-rate detection:** compute the CAF at lag τ = 1 sample (or a few lags) as a function of cyclic frequency α:
   ```
   R_x^α[τ] = (1/N) Σ_{n=0}^{N-1} x[n+τ] · conj(x[n]) · exp(-j2πα·n)
   ```
   For each candidate α, this is one FFT evaluation. The symbol rate appears as a peak in |R_x^α[τ]| at α = 1/T_s.

   **Alternative (often more practical):** use the spectral coherence / cyclic periodogram:
   ```
   S_x^α(f) = Σ_τ R_x^α[τ] · exp(-j2πfτ)
   ```
   The symbol-rate manifests as non-zero spectral correlation at α = k·f_sym.

   **Simplest practical implementation:** compute cyclic autocorrelation magnitude profile:
   ```python
   def cyclic_caf_profile(x, fs, alpha_candidates):
       N = len(x)
       n = np.arange(N)
       magnitudes = []
       for alpha in alpha_candidates:
           # Zero-lag cyclic autocorrelation
           caf = np.abs(np.mean(x * np.conj(x) * np.exp(-1j * 2 * np.pi * alpha * n / fs)))
           magnitudes.append(caf)
       return np.array(magnitudes)
   ```
   Note: the zero-lag product x[n]·conj(x[n]) = |x[n]|² for a single signal, reducing this to the spectral analysis of |x|². This is NOT a useful improvement over the baseline.

   **The correct CAF-based approach for symbol rate** uses nonzero lag or conjugate products:
   - For **symbol-rate detection** specifically, use the **squared-magnitude** or **fourth-power** cyclostationary features:
     ```
     y[n] = |x[n]|² (or x[n]² for complex signals)
     ```
     Then compute:
     ```
     R_y^α[0] = (1/N) Σ y[n] · exp(-j2πα·n/fs)
     ```
     This IS the FFT of |x|² evaluated at frequency α — but with proper windowing, averaging, and statistical testing rather than raw peak-picking.

   **The actual improvement over the baseline** comes from:
   1. Proper windowing (Welch-style segmented averaging) to reduce spectral leakage
   2. Statistical testing (compare peak to noise floor) rather than raw peak selection
   3. Multi-method fusion (|x|, |x|², and conjugate-product approaches)
   4. Constrained search (only consider physically plausible rates)

3. Implement as `analyze.py::estimate_symbol_rate_caf(iq, fs, sps_range=(2,20))`:
   - Compute FFT of |x[n]|² using Welch's method (multiple segments, Hann window)
   - Compute FFT of |x[n]| using Welch's method
   - For each: normalize by median spectral level
   - Apply low-frequency guard (≥1% of fs)
   - Apply high-frequency guard (≤fs/2)
   - Combine both spectra (weighted sum or max)
   - Apply statistical peak test: peak must exceed median + k·MAD (k=5 initial)
   - If no significant peak: return UNCERTAIN flag
   - Return estimated symbol rate and confidence metric

### 2b — Test on failure cases
4. Run new estimator on test_020 and test_025
5. Compare: old estimate vs new estimate vs ground truth
6. If the new estimator returns the correct rate (within 2%): proceed
7. If not: investigate why. Options:
   - Increase FFT length / number of segments
   - Try |x|⁴ (fourth power) for QPSK
   - Add Gardner timing-error-detector energy metric
   - Try explicit cyclic autocorrelation at lag = estimated_sps

### 2c — Regression check
8. Run new estimator on ALL 30 sealed files
9. Verify: all 28 previously-passing files still get correct symbol rate
10. Record: per-file symbol-rate error, old vs new

**Acceptance:** New estimator achieves ≤2% error on test_020 AND test_025 without regressing the 28 passing cases.

**Regression gate:** All 28 previously correct symbol-rate estimates remain within 2%.

**Duration estimate:** 1–2 days.

**Fallback:** If CAF-style improvements don't rescue 2 dB, try:
1. Gardner/Oerder-Meyr timing-error-detector energy vs candidate rate
2. Oversampled autocorrelation of |x| with constrained peak-picking
3. Wider sps_try search (partial mitigation only)

---

## STEP 3 — Integrate Improved Estimator into Pipeline

**Objective:** Replace or augment the symbol-rate estimator in the full pipeline.

**Actions:**
1. Add `estimate_symbol_rate_caf` as primary estimator in `pipeline.py`
2. Keep existing `estimate_symbol_rate` as fallback (if CAF returns UNCERTAIN)
3. Run full sealed benchmark: `python3 sealed_test.py`
4. Record results: per-file comparison with baseline

**Acceptance:** ≥28/30 recovery (no regression). Ideally 29/30 or 30/30 from improved symbol-rate alone.

**Regression gate:** No previously passing file may fail.

**Duration estimate:** 0.5 days.

---

## STEP 4 — Implement SAGE-Lite Feedback Loop

**Objective:** Add decoding-assisted parameter refinement for cases that fail the consistency gate.

**Actions:**
1. Implement `sage_lite_refine(iq, initial_params, max_iter=3)` in new file `src/sage_lite.py`
2. The function:
   - Takes: IQ data, initial parameter estimates (sps, phase, cfo), pipeline configuration
   - For each iteration:
     a. Demodulate with current parameters
     b. Generate soft bits
     c. Run best-hypothesis FEC decode (Viterbi)
     d. If consistency < 0.98:
        - Re-modulate decoded bits to create pseudo-reference symbols
        - Cross-correlate received symbols with pseudo-reference to estimate timing residual
        - Compute correlation angle for phase residual
        - Fit linear phase slope for CFO residual
        - Apply bounded updates (Section 21.5 of Constitution)
        - Record iteration metrics
     e. If consistency ≥ 0.98: stop (success)
     f. If iteration limit reached: stop (report best)
     g. If consistency decreased from previous: stop (divergence)
   - Returns: best result across all iterations, iteration log

3. Integrate into `pipeline.py`:
   - After the existing hypothesis search produces a result with consistency < 0.98
   - Invoke SAGE-Lite on the best candidate
   - If SAGE-Lite improves consistency above threshold: accept
   - Otherwise: report the best result (may still be a failure)

4. Add logging: every iteration records (symbol_rate_est, timing_correction, phase_correction, cfo_correction, consistency, BER_if_available, runtime)

**Acceptance:** Implementation compiles, runs without error, and correctly invokes on failure cases.

**Regression gate:** SAGE-Lite only activates on failures; passing cases must not be affected.

**Duration estimate:** 2–3 days.

---

## STEP 5 — Run 2 dB QPSK Rescue Experiment

**Objective:** Determine whether the combined Cyclic-CAF + SAGE-Lite rescues the known failures.

**Actions:** Execute the full experiment as specified in `SIH26147_2DB_QPSK_RESCUE_EXPERIMENT.md`.

1. Pass A: Run baseline on test_020 and test_025 (reproduce known failure)
2. Pass B: Run improved system (CAF + SAGE-Lite) on both files
3. Pass C: Ablation — run SAGE-Lite with raw demod symbols (no FEC correction) as pseudo-reference
4. Record all metrics per the experiment specification
5. Generate comparison plots
6. Write experiment report

**Acceptance:** Defined in experiment specification. Primary: consistency ≥ 0.98 AND BER < 0.01 on at least one of the two failure cases.

**Regression gate:** Run full sealed benchmark to confirm ≥28/30.

**Duration estimate:** 1 day.

---

## STEP 6 — Full Regression Suite

**Objective:** Confirm the complete system (baseline + CAF + SAGE-Lite) on the sealed benchmark.

**Actions:**
1. Run `sealed_test.py` with the improved system
2. Record per-file results
3. Compare with baseline: file-by-file consistency, BER, runtime
4. Identify any regressions
5. Investigate and fix any regressions

**Acceptance:** ≥28/30 (no regression). Target: 30/30.

**Regression gate:** This IS the regression gate.

**Duration estimate:** 0.5 days (including investigation of any issues).

---

## STEP 7 — Expanded Synthetic Benchmark

**Objective:** Characterize system performance across a wider parameter space.

**Actions:**
1. Define benchmark matrix:
   - SNR: 0, 1, 2, 3, 4, 5, 6, 8, 10, 12, 15 dB
   - Modulation: BPSK, QPSK
   - sps: 4, 6, 8
   - Roll-off β: 0.25, 0.35, 0.5
   - CFO: 0, ±0.005, ±0.01 cycles/sample
   - Interleaver: (4,8), (6,10), (8,8), (8,16), (10,12)
   - 5 random seeds per configuration
2. Generate signals (new `generate_stress.py`)
3. Run full pipeline on all signals
4. Record: decode success rate vs SNR, symbol-rate error vs SNR, runtime distribution
5. Generate performance curves

**Acceptance:** Performance characterized. No unexpected failure modes discovered.

**Regression gate:** Sealed benchmark results unchanged.

**Duration estimate:** 2–3 days.

---

## STEP 8 — Validate on Public IQ (when possible)

**Objective:** Test against real receiver imperfections.

**Actions:**
1. Identify legally accessible public IQ recordings (SigMF, gr-satellites, KiwiSDR)
2. Select recordings with known modulation/FEC for ground-truth comparison
3. Run pipeline
4. Document: format handling, decode success, failure modes unique to real data

**Acceptance:** Documented performance on at least 3 real recordings.

**Prerequisite:** Network access to download recordings; SDR legality verification.

**Duration estimate:** 2–5 days (including data acquisition).

---

## STEP 9 — Decide on Advanced Features

**Objective:** Evidence-based decision on what to build next.

**Actions:**
1. Review rescue experiment results
2. Review synthetic benchmark results
3. Assess: is the core thesis validated?
4. If yes: proceed to P1 features (FSK, QAM, RS, frame-sync, GUI)
5. If no: diagnose and iterate on the core (better CAF, better SAGE-Lite, alternative approaches)

**Decision criteria:**
- If 30/30 achieved: core thesis supported → expand
- If 29/30: partial support → investigate remaining failure before expanding
- If 28/30 unchanged: thesis not yet validated → iterate on core
- If <28/30: regression → fix before anything else

---

## P1 Features (after MVP rescue validated)

| Feature | Effort | Dependency | Acceptance |
|---|---|---|---|
| Frame sync / bit-stream correlation | 2–3 days | Working decoder | Resolves 180° ambiguity on ≥90% of test files |
| FSK demodulation (2/4-FSK) | 2–3 days | None | ≥95% decode on FSK synthetic set |
| QAM demodulation (16-QAM) | 3–5 days | AGC, amplitude recovery | ≥90% decode on QAM synthetic set at ≥8 dB |
| Reed-Solomon (RS(255,223)) catalogue entry | 2–3 days | AFF3CT reference | Clean roundtrip + noisy decode |
| Concatenated FEC (conv+RS) | 2–3 days | RS above | Clean roundtrip + decode |
| GUI (waterfall/constellation/hypothesis tree) | 5–7 days | All of above | Interactive sealed-file demo |
| SigMF I/O | 1 day | None | Ingest SigMF recordings |
| PDF evidence report | 2–3 days | GUI/figures | Printable per-file analysis |

---

## P2 Features (after P1 validated)

| Feature | Effort | Dependency |
|---|---|---|
| Convolutional/diagonal interleavers | 3–5 days | Extended catalogue |
| Catalogue LDPC (DVB-S2, etc.) | 5–7 days | LDPC decoder |
| CNN modulation second-opinion | 3–5 days | RadioML dataset |
| Numba/Cython acceleration | 3–5 days | Profiling data |
| Adversarial benchmark automation | 3–5 days | Stress benchmark |

---

## Timeline Summary

| Week | Focus | Deliverable |
|---|---|---|
| Week 1 | Steps 0–2 (Baseline + CAF estimator) | Working improved symbol-rate estimator |
| Week 2 | Steps 3–5 (Integration + SAGE-Lite + Rescue) | Rescue experiment results |
| Week 3 | Steps 6–7 (Regression + Synthetic benchmark) | Full performance characterization |
| Week 4+ | Step 8–9 + P1 features | Public IQ validation + expanded capabilities |

---

**EXECUTION ROADMAP COMPLETE**
