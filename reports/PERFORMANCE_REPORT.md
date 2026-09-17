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

---

## Cost of acceptance families F1–F4 (measured 2026-09-18, `eval/perf.py`)

Single process, Python 3.11.16, numpy 2.4.2, Windows 11. Interpreter baseline RSS 99 MB. Default
engine path (8PSK/16-QAM off, §24 row 34).

| Dataset | Files | Mean samples | Mean s | Max s | Peak RSS | ΔRSS | Front ends | Mean M₁ | M₂ | M₃ | M₄ |
|---|---|---|---|---|---|---|---|---|---|---|---|
| bench-v1 sealed | 30 | 462 | 0.12 | 0.18 | 114 MB | 15 MB | 51 | 29,365 | 123 | 26,663 | 19 |
| bench-v1 train | 100 | 460 | 0.12 | 0.24 | 123 MB | 10 MB | 51 | 27,444 | 114 | 25,569 | 70 |
| Null set (200-file sample) | 193 | 1,072 | 0.15 | 0.38 | 144 MB | 22 MB | 56 | 25,665 | 142 | 284,101 | 734 |
| Long CCSDS chain (4 frames, 66 k samples) | 1 | 66,392 | 3.47 | 3.47 | 138 MB | 3 MB | 30 | 0 | 80 | 1.38×10⁹ | 3,090 |
| Long TC LDPC CLTU (24 codewords) | 1 | 12,584 | 0.37 | 0.37 | 143 MB | 5 MB | 15 | 0 | 40 | 9.87×10⁷ | 3,072 |

Time by stage:

| Dataset | CFO | sps | MF | syndrome | Viterbi | scoring | stream | frame | block code |
|---|---|---|---|---|---|---|---|---|---|
| bench-v1 sealed | 1% | 2% | 1% | 63% | 8% | 16% | 2% | 4% | 4% |
| Null set sample | 2% | 2% | 2% | 58% | 9% | 13% | 2% | 5% | 8% |
| Long CCSDS chain | 16% | 3% | 1% | 1% | 0% | 0% | 0% | **69%** | 10% |
| Long TC LDPC CLTU | 10% | 5% | 2% | 1% | 0% | 0% | 0% | **64%** | 18% |

**Reading it.**
- Short bursts are unchanged in character: the syndrome search still dominates, and adding three
  interleaver types took the mean from 0.06 s to 0.12 s per bench-v1 file.
- On long captures the **frame search dominates** (about 70%). M₃ is large because it is the whole
  declared domain (every byte-aligned period 64–16,384 bits × offset × marker/width × polarity) over
  every stream tested, which is the honest denominator; the cost is the blind constant-field pass over
  all periods, not the domain count.
- M₁ is 0 on long captures because no single block interleaver of ≤ 384 bits can cover them, so the
  burst family has nothing to test — as declared in §12.
- **Peak RSS never exceeds 144 MB**, and the growth over baseline is 3–22 MB, so the demo machine's
  memory is not a constraint on the default path.
- The EXPERIMENTAL higher-modulation path costs about 20× on the null set (mean 2–3 s per file, max
  19 s) and is off by default; `eval/perf.py --higher` measures it.
