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

---

## DEVELOPMENT MEASUREMENT — re-run after the ordering and hardening pass

**Not a validated benchmark.** A development machine under ordinary load, one run per dataset, no
pre-registration. It exists to answer one question — *did the ordering locks cost anything?* — and
nothing above it has been altered.

Environment: Python 3.11.14, numpy 2.4.2, psutil 7.2.2, Windows 11, single process, default engine
path (8PSK/16-QAM off). Command: `python eval/perf.py`.

| Dataset | Files | Mean s | Max s | Peak RSS | Earlier run (2026-09-18) |
|---|---|---|---|---|---|
| bench-v1 sealed | 30 | 0.15 | 0.22 | 118 MB | 0.12 s / 114 MB |
| bench-v1 train | 100 | 0.14 | 0.31 | 124 MB | 0.12 s / 123 MB |
| Null set (200-file sample) | 193 | 0.18 | 0.50 | 151 MB | 0.15 s / 144 MB |
| Long CCSDS chain | 1 | 4.11 | 4.11 | 147 MB | 3.47 s / 138 MB |
| Long TC LDPC CLTU | 1 | 0.43 | 0.43 | 148 MB | 0.37 s / 143 MB |

The two columns are **not** a controlled comparison: different machine state, a different Python
patch release, and a browser had just been driven through 120 pages on the same host. The stage
profile is unchanged (syndrome search 52–58% on short bursts, frame search 61–63% on long captures),
peak RSS still never exceeds 151 MB, and nothing in the ordering fix touches the analysis path.
**Conclusion: no regression of any consequence, and no performance claim is made from this table.**

### Where the ordering fix *does* cost something: the ledger append

`receipt.last_hash()` reads the ledger to find the head, so an append is one pass over the whole
file — and since the ordering fix that pass happens inside the writer lock. This was measured
directly, because an append-only file that is read in full on every append is a scaling limit worth
knowing before it is reached rather than after.

Synthetic receipts of about 440 bytes, 20 timed appends at each size, same environment:

| Ledger entries | File size | Mean append | p95 |
|---|---|---|---|
| 100 | 51 KB | 10.9 ms | 13.6 ms |
| 1,000 | 438 KB | 17.0 ms | 22.6 ms |
| 10,000 | 4.3 MB | 64.1 ms | 68.8 ms |
| 100,000 | 43 MB | 505 ms | 559 ms |

Linear in ledger size, as the implementation implies. Against a mean analysis of about 0.15 s the
append is noise at a few thousand receipts and becomes the dominant cost somewhere between 10,000
and 100,000. The deployed ledger currently holds **153** receipts, where the append costs about
11 ms.

Verification does not degrade the same way: reading and verifying a **100,020**-receipt chain end to
end took **1.8 s** (0.76 s read, 1.06 s verify), and reported `ok=True`.

**The upgrade path, deliberately not taken yet.** Because `server/store_lock.py` now gives a process
exclusive ownership of the results directory for its lifetime, that process can cache the head hash
after the first read and make the append O(1). That is sound *only* because of the single-writer
lock. It is not implemented, because 153 receipts do not justify it, and a cached head in a system
that did not own the directory would be a correctness bug rather than an optimisation.

## Console load (2026-09-22)

Same screens, same records, same numbers; less transferred.

| Change | Before | After |
|---|---|---|
| Evidence fetched at start-up to list the library | all six packs, ~14 MB | `evidence/index.json` with per-pack summaries, 14.7 kB; a full pack loads when its record opens |
| JavaScript on the first visit | one 786 kB bundle (249 kB gzip) | per-screen chunks, ~146 kB gzip; the rest prefetched when idle |
| Transfer of a 4.3 MB evidence pack | 4.3 MB | 228 kB (gzip from `server/app.py`) |
| Repeat visit, unchanged JSON/HTML | full re-download (`no-store`) | `304 Not Modified` (ETag + `no-cache`); hashed assets immutable |

Measured with `vite build` output and `curl` against `server/app.py`; not a browser timing study.
