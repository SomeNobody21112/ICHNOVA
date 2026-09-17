# Performance — Same Decisions, 3–4× Faster

**Date:** 2026-09-17 · **Code:** `src/blind_id.py::syndrome_scan`, `src/pipeline.py`

## Where the time went

On 100 train captures the syndrome search over code × interleaver hypotheses was 81 % of analysis time (`reports/data` runtime breakdown). Each capture tests ~20 000 hypotheses, and each was a separate Python-level call on arrays of ≤ 384 values, plus four list appends; root-raised-cosine taps were recomputed in a Python loop for every front end.

## Changes

1. **Vectorised syndrome scan.** All interleaver candidates of one front end are gathered into a padded matrix with one fancy-index operation (indices cached per candidate set); each code's parity products are formed column-wise with the **same factor order** as the scalar version, so every check sign — and therefore every sign-test p-value — is bit-identical.
2. Hypothesis table built from arrays (no per-hypothesis appends); ordering preserved, so stable sorts break ties exactly as before.
3. Root-raised-cosine filters cached (read-only arrays).

## Verification (not assumed)

| Set | Files | Before | After | Speed-up | Decision differences |
|---|---|---|---|---|---|
| bench-v1 sealed | 30 | 5.6 s | 1.5 s | 3.7× | 0 (all 21 result fields per file) |
| bench-v1 train | 100 | 16.9 s | 4.4 s | 3.8× | 0 |
| null set | 1350 | 734.6 s | 241.2 s | 3.0× | 0 (status, code, interleaver, BER, n_hypotheses, log10_p); `syndrome_z` differs below 1e-9 from summation order |

Evidence: `reports/data/v2_sealed_results_vectorised.json`, `reports/data/v2_train_results_vectorised.json`, `reports/data/v2_nullset_runtime.json`. `src/generate.py` and the datasets are unchanged.

## Also fast in the new receivers

- FSK tone-pair search: one STFT per shift class instead of a filter per candidate pair (30 s → 2.5 s on a 125-s capture); framings screened on 20 s before full runs.
- Live processing keeps an amortised growing buffer (no per-row concatenation) and refits the second epoch every 5 s until locked.
