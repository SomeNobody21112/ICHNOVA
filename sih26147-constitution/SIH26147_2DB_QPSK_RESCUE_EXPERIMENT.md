# SIH26147 — 2 dB QPSK RESCUE EXPERIMENT SPECIFICATION

**Document:** Experiment Protocol
**Status:** LOCKED — Ready for execution
**Date:** 2026-09-16
**Version:** 2.0 (Research-Verified)
**Theoretical basis:** Code-aided synchronization / turbo synchronization (Herzet et al., *Proc. IEEE* 95(6):1255-1271, 2007; Noels et al., *IEEE ICC '03*, 2003). Applied in a novel context where the FEC code is blindly identified rather than known a priori.

---

> **⚠ Baseline superseded (v2.1, 2026-09-16):** the code in this repo now scores **30/30** on the regenerated sealed set and **60/100** on the 100-file train set. The test_020/test_025 2 dB QPSK failures described below come from an earlier codebase/dataset and do not reproduce here (current test_020 = QPSK 8 dB, test_025 = QPSK 5 dB, both pass). See `SIH26147_CURRENT_STATE.md` and the v2.1 entry in `SIH26147_CONSTITUTION_CHANGELOG.md`. Kept for plan/history.

## 1. Objective

Determine whether the combination of an improved symbol-rate estimator (Cyclic-CAF) and decoding-assisted parameter refinement (SAGE-Lite) can recover QPSK signals at ~2 dB SNR that fail under the existing feed-forward baseline pipeline.

This is the defining experiment for the SIH26147 MVP and the primary test of the "Decoding as a Sensor" thesis.

---

## 2. Hypothesis

### Primary Hypothesis

Decoding-assisted feedback can improve upstream parameter estimation sufficiently to recover signals that fail under the current feed-forward estimator, specifically by using FEC-corrected decoded symbols as a pseudo-reference for residual synchronization error estimation.

### Null Hypothesis

The feedback mechanism provides no statistically meaningful improvement over the feed-forward baseline, either because:
- The initial parameter estimates are too far from correct for the decoder to produce useful output, OR
- The decoder output at low SNR is insufficiently reliable to serve as a useful pseudo-reference, OR
- The residual estimation from the pseudo-reference is too noisy to improve parameters meaningfully.

---

## 3. Test Data

### Primary test files

| File | Modulation | SNR (dB) | True Symbol Rate (Hz) | True sps | Interleaver | Roll-off β |
|---|---|---|---|---|---|---|
| test_020 | QPSK | 2 | 166,667 | 6 | (6,10) | varies |
| test_025 | QPSK | 2 | 166,667 | 6 | (10,12) | varies |

Both are from the sealed set (seed0=99000). Both are confirmed failures under the baseline.

### Secondary test files (regression)

All 30 sealed files. The 28 passing files serve as the regression set.

### Tertiary test files (stress)

Generate a supplementary QPSK-heavy stress set:
- SNR: {0, 1, 2, 3, 4} dB
- Modulation: QPSK only
- sps: {4, 6, 8}
- Roll-off β: {0.25, 0.35, 0.5}
- 10 random seeds per configuration
- Total: 5 × 3 × 3 × 10 = 450 files
- Seed formula: `seed = 200000 + snr_idx*1000 + sps_idx*100 + beta_idx*10 + trial`

---

## 4. Baseline Parameters (Pass A — Feed-Forward)

Run the existing `pipeline.py::analyze_file()` without any modifications.

Record per file:
```
file_id
ground_truth_symbol_rate
estimated_symbol_rate
symbol_rate_error_percent = |est - true| / true * 100
ground_truth_modulation
estimated_modulation
carrier_offset_estimate
consistency_score
payload_BER (complement-tolerant)
decode_status (OK / FAIL)
runtime_seconds
failure_category (F1-F12 per taxonomy)
```

### Expected baseline results for primary files

| File | Expected EST symbol rate | Expected consistency | Expected BER | Expected status |
|---|---|---|---|---|
| test_020 | ~84,891 Hz | ~0.866 | ~0.490 | FAIL |
| test_025 | ~473,131 Hz | ~0.854 | ~0.495 | FAIL |

If the baseline results differ significantly from these, STOP and investigate before proceeding. The baseline must reproduce the known failure.

---

## 5. Improved System Parameters (Pass B — CAF + SAGE-Lite)

### Symbol-rate estimator configuration

```
estimator = "cyclic_caf"
sps_search_range = (2, 20)
fft_method = "welch"
window = "hann"
n_segments = 8 (or auto based on signal length)
low_freq_guard = 0.01 * fs
significance_threshold = 5.0 (MAD units above median)
methods = ["|x|", "|x|²"]  # fuse both
```

### SAGE-Lite configuration

```
max_iterations = 3
consistency_threshold = 0.98
convergence_threshold = 0.005  # min consistency improvement per iteration
timing_update_bound = 1.0  # symbol periods
phase_update_bound = pi/2  # radians
cfo_update_bound = 0.005  # cycles/sample
pseudo_reference = "viterbi_decoded"  # FEC-corrected symbols
```

### FEC/decode configuration (unchanged from baseline)

```
code_catalogue = [conv_k7_r12_171_133, conv_k5, conv_k3, uncoded]
interleaver_search = factor_pairs with 2≤r≤16, 4≤c≤24
consistency_accept = 0.98
ber_threshold = 0.01 (complement-tolerant)
```

Record per file, per iteration:
```
file_id
iteration_number (0 = initial, 1+ = feedback)
symbol_rate_estimate (may change if SAGE-Lite refines timing)
timing_correction_applied
phase_correction_applied
cfo_correction_applied
consistency_score
payload_BER
decode_status
termination_reason (success / max_iter / convergence / divergence / bounds)
iteration_runtime_seconds
total_runtime_seconds
```

---

## 6. Ablation (Pass C — Raw Demod Pseudo-Reference)

Run the same SAGE-Lite loop but replace the pseudo-reference:

Instead of: decoded bits → re-modulated symbols (FEC-corrected)
Use: hard-decided demodulated symbols (no FEC correction)

```
pseudo_reference = "hard_demod"  # NOT FEC-corrected
```

All other parameters identical to Pass B.

### Purpose

Isolate the contribution of FEC decoding to the feedback improvement. If Pass C performs as well as Pass B, then the improvement comes from iterative refinement itself, not from the decoded information — which would weaken the "Decoding as a Sensor" thesis. If Pass B significantly outperforms Pass C, the FEC correction is providing essential information, supporting the thesis.

---

## 7. Metrics

### Primary metrics

| Metric | Definition | Success criterion |
|---|---|---|
| **Rescue rate** | Fraction of previously-failing files now decoded successfully | ≥ 1/2 (at least one of the two primary failures rescued) |
| **Final consistency** | Re-encode agreement of the best iteration | ≥ 0.98 for rescued files |
| **Payload BER** | Complement-tolerant bit error rate | < 0.01 for rescued files |

### Secondary metrics

| Metric | Definition | Target |
|---|---|---|
| Symbol-rate error | |est - true| / true × 100 | ≤ 2% after feedback |
| Iterations to converge | Number of SAGE-Lite iterations before termination | ≤ 3 |
| Total runtime | End-to-end pipeline time including feedback | < 30 seconds per file |
| Regression count | Files that passed baseline but fail improved system | 0 |
| Ablation gap | Pass B consistency − Pass C consistency | > 0 (positive = FEC helps) |

### Diagnostic metrics (per iteration)

| Metric | Purpose |
|---|---|
| Consistency trajectory | Does consistency monotonically improve? |
| Parameter update magnitude | Are updates decreasing (convergence) or oscillating (instability)? |
| Pseudo-reference quality | Correlation between pseudo-reference and true symbols (if ground truth available) |

---

## 8. Procedure

### Step 1 — Reproduce baseline failures (Pass A)

```bash
# Run baseline on primary files
python3 -c "
import sys, json, numpy as np
sys.path.insert(0, 'src')
from pipeline import analyze_file

for f in ['test_020', 'test_025']:
    gt = json.load(open(f'data/sealed/{f}.iq.gt.json'))
    r = analyze_file(f'data/sealed/{f}.iq', verbose=True)
    
    d = np.asarray(r['payload_bits'])
    o = np.array(gt['original_bits'])
    L = min(len(d), len(o))
    ber = min(np.mean(d[:L] != o[:L]), np.mean((1-d[:L]) != o[:L]))
    
    print(f'=== {f} BASELINE ===')
    print(f'GT symrate: {gt[\"symbol_rate\"]} Hz')
    print(f'EST symrate: {r[\"symbol_rate_est\"]} Hz')
    print(f'Error: {abs(r[\"symbol_rate_est\"] - gt[\"symbol_rate\"]) / gt[\"symbol_rate\"] * 100:.1f}%')
    print(f'Consistency: {r[\"consistency\"]:.4f}')
    print(f'BER: {ber:.4f}')
    print(f'Status: {\"OK\" if ber < 0.01 else \"FAIL\"}')
    print()
"
```

**Gate:** Both files must fail (BER > 0.01). If either passes under baseline, investigate — the experiment premise is invalid.

### Step 2 — Run improved system (Pass B)

```bash
# Run improved system with CAF + SAGE-Lite
python3 -c "
import sys, json, numpy as np
sys.path.insert(0, 'src')
from pipeline_improved import analyze_file_improved  # new entry point

for f in ['test_020', 'test_025']:
    gt = json.load(open(f'data/sealed/{f}.iq.gt.json'))
    r = analyze_file_improved(f'data/sealed/{f}.iq', verbose=True,
                               sage_lite=True, max_iter=3)
    
    # ... same BER calculation and reporting ...
    # Additionally report per-iteration metrics from r['iteration_log']
    for it in r.get('iteration_log', []):
        print(f'  Iter {it[\"iteration\"]}: cons={it[\"consistency\"]:.4f} '
              f'dt={it.get(\"timing_correction\",0):.4f} '
              f'dphi={it.get(\"phase_correction\",0):.4f}')
"
```

### Step 3 — Run ablation (Pass C)

Same as Step 2 but with `pseudo_reference='hard_demod'`.

### Step 4 — Full regression

```bash
python3 sealed_test_improved.py  # must report ≥28/30
```

### Step 5 — Stress benchmark (if primary files rescued)

Run on the 450-file QPSK stress set. Record decode success rate vs SNR curve.

---

## 9. Logging Requirements

Every run must produce a structured JSON log:

```json
{
  "experiment_id": "2db_qpsk_rescue_v1",
  "timestamp": "2026-09-XX",
  "system_version": "baseline-v1+caf+sage-lite",
  "pass": "B",
  "file": "test_020",
  "ground_truth": {
    "modulation": "QPSK",
    "snr_db": 2,
    "symbol_rate": 166667,
    "sps": 6,
    "interleaver": [6, 10],
    "carrier_offset": 0.00XX
  },
  "result": {
    "symbol_rate_est": 166667,
    "modulation_est": "QPSK",
    "consistency": 0.991,
    "ber": 0.000,
    "decode_status": "OK",
    "total_runtime_s": 12.3,
    "termination_reason": "consistency_achieved",
    "n_iterations": 2
  },
  "iteration_log": [
    {
      "iteration": 0,
      "consistency": 0.866,
      "symbol_rate_est": 166667,
      "timing_correction": 0.0,
      "phase_correction": 0.0,
      "cfo_correction": 0.0,
      "runtime_s": 8.5
    },
    {
      "iteration": 1,
      "consistency": 0.972,
      "timing_correction": 0.23,
      "phase_correction": 0.15,
      "cfo_correction": 0.001,
      "runtime_s": 3.1
    },
    {
      "iteration": 2,
      "consistency": 0.991,
      "timing_correction": 0.04,
      "phase_correction": 0.02,
      "cfo_correction": 0.000,
      "runtime_s": 3.0
    }
  ]
}
```

Note: the above is an EXAMPLE of the desired format, NOT a predicted result.

---

## 10. Required Plots

1. **Consistency trajectory:** Plot consistency vs iteration for each primary file (Pass A, B, C overlaid)
2. **Parameter convergence:** Plot timing/phase/CFO corrections vs iteration
3. **Before/after constellation:** Demodulated constellation at iteration 0 vs final iteration
4. **Symbol-rate estimation comparison:** Bar chart of baseline estimate vs CAF estimate vs ground truth
5. **SNR performance curve:** Decode success rate vs SNR from the stress benchmark (baseline vs improved)
6. **Ablation comparison:** Side-by-side consistency for Pass B vs Pass C

---

## 11. Interpretation Rules

### Outcome A — Full Rescue

Both test_020 AND test_025 achieve consistency ≥ 0.98 and BER < 0.01 under Pass B.

**Interpretation:** Strong support for the "Decoding as a Sensor" hypothesis. The cross-layer feedback architecture demonstrably rescues signals that fail under feed-forward processing.

**Required additional check:** Pass C (ablation) must perform worse than Pass B to confirm that FEC decoding contributes to the improvement. If Pass C performs equally well, the improvement is from iterative refinement alone (still valuable, but weakens the "decoding as sensor" claim).

### Outcome B — Partial Rescue

One of the two files is rescued; the other improves (higher consistency) but does not reach the success threshold.

**Interpretation:** Partial support. Document which file was rescued and why the other was not. Investigate: is the un-rescued file's initial estimate too far off for SAGE-Lite to converge?

### Outcome C — Improvement Without Rescue

Both files show improved consistency or parameter estimates but neither reaches the success threshold.

**Interpretation:** The feedback mechanism produces measurable benefit but is insufficient for full rescue at this SNR. Investigate: is the decoder output at 2 dB too unreliable? Would more iterations help? Is the update step size appropriate?

### Outcome D — No Improvement

Neither file shows meaningful improvement under Pass B relative to Pass A.

**Interpretation:** The hypothesis is not supported by this experiment. Possible causes:
- Decoder output at 2 dB is pure noise (insufficient FEC correction to create a useful pseudo-reference)
- Symbol-rate estimate is too far off for demodulation to produce anything useful (SAGE-Lite needs a reasonable starting point)
- Update equations are incorrect or poorly scaled
- The feedback mechanism itself is flawed

**Required action:** Detailed failure analysis before expanding scope.

### Outcome E — Regression

Previously passing files fail under the improved system.

**Interpretation:** The modification has introduced a bug or an inappropriate parameter change. STOP. Fix the regression before reporting any rescue results.

---

## 12. What This Experiment Does NOT Prove (Even If Successful)

- It does not prove the system works on real-world signals (only synthetic AWGN)
- It does not prove the system works below 2 dB (untested regime)
- It does not prove the system works for FSK/QAM/other modulations (only QPSK tested)
- It does not prove the system works for non-convolutional FEC (only K=7 r1/2 tested)
- It does not prove convergence in general (only tested on two specific cases)
- It does not prove the feedback provides formal statistical guarantees
- It does not prove commercial competitiveness

It proves (if successful):

> On the specific demonstrated failure mode (low-SNR QPSK symbol-rate estimation), decoding-assisted feedback measurably improves recovery compared to the feed-forward baseline.

This is a significant result. It is also a precisely bounded one.

---

## 13. Experiment Record Template

After execution, create `results/2db_qpsk_rescue_report.md` with:

```
Experiment ID: 2db_qpsk_rescue_v1
Date: YYYY-MM-DD
Code version: [git hash or tag]
Configuration: [exact params used]

PASS A — BASELINE
  test_020: symrate_est=___ cons=___ BER=___ status=___
  test_025: symrate_est=___ cons=___ BER=___ status=___

PASS B — CAF + SAGE-LITE
  test_020: symrate_est=___ cons=___ BER=___ status=___ iters=___ termination=___
  test_025: symrate_est=___ cons=___ BER=___ status=___ iters=___ termination=___

PASS C — ABLATION (raw demod pseudo-reference)
  test_020: cons=___ BER=___ status=___
  test_025: cons=___ BER=___ status=___

REGRESSION: ___/30 (must be ≥28)

OUTCOME: [A / B / C / D / E]

INTERPRETATION: [1-3 sentences]

CONCLUSION: [SUPPORTED / PARTIALLY SUPPORTED / NOT SUPPORTED / INCONCLUSIVE]
```

---

**EXPERIMENT SPECIFICATION COMPLETE**
