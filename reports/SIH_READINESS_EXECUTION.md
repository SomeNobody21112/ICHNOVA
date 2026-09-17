# SIH-readiness execution log (Constitution v2.5)

One section per phase: what changed, how it was tested, what was measured, what failed, and what was deferred. Numbers here come from commands that were actually run. Nothing is copied forward from plans.

Baseline before any change: `reports/AUTONOMOUS_EXECUTION_BASELINE.md`.

---

## Phase 0 — Reconnaissance

- Read the Constitution v2.4, the audit, `src/` (pipeline, blind_id, fec, modem, analyze), `server/evidence.py`, `server/app.py`, `eval/nullset.py`, `sealed_test.py`, the CI workflow and tests.
- Re-ran tests (30/30), sealed (30/30), train (63/100) and the full null set (0/900, 0/450). One count differs from v2.4 §19: uncoded QPSK → UNKNOWN 122 vs 121.

## Phase 1 — Governance and document conflicts

| Audit item | Resolution |
|---|---|
| C1 silent 1 MHz default | Recorded as a v2.5 rule (§10); code fix is Phase 2 |
| C2 withdrawn "93% held-out" still listed | `SIH26147_NOVELTY_AUDIT.md`: struck through with the reason; kept as history |
| C3 train called held-out | `PROGRESS.md`: wording changed and a dated historical note added (train became a development set from Session 3 on) |
| C4 "held-out split" | "evaluation split" in `frontend/src/pages/Lab.tsx`, `SIH26147_CURRENT_STATE.md`, `server/export_frontend_data.py`, `reports/RESEARCH_LANDSCAPE.md`; old changelog entries left as written |
| C5 roadmap vs SIH | Constitution §35 rewritten: explicit SIH capabilities are P0 |
| C6 wrong section cited in CRM plan | `ICHNOVA_CRM_UVP_PLAN.md` (outside repo): corrected to §13/§32, marked DEFERRED |
| C7 verification commit | Constitution header now cites `acf4201` and the re-measured baseline |
| C8 FSK overstated | `ICHNOVA_OPPORTUNITY_RESEARCH.md` (outside repo): E3/E6 FSK marked partial with the reason |
| C9 cloud vs air-gap | Constitution §9.2 cloud clause |

Pre-registered in Constitution v2.5 **before any code**:
- catalogue v1 (§12.1), each item citing its defining document;
- weighted acceptance families F1–F4 (§13.1);
- bench-v2 sealed policy (§18.1).

Normative sources were downloaded and read, not recalled:
- **CCSDS 131.0-B-5**: RS field and generator, dual-basis matrices and Annex F examples, ASM patterns, randomizer polynomials, seeds and first 40 bits.
- **CCSDS 231.0-B-4**: LDPC (128,64) H from §4.2.2 (read from the rendered page image) and generator from Table 4-1. Checked against each other: H·Gᵀ = 0, rank 64. The first construction attempt applied the circular shift across all 64 bits instead of per 16-bit circulant. It failed the check and was corrected.
- **3GPP TS 36.212 v10.0.0** Table 5.1.3-3: 188 QPP entries parsed. The K sequence matches the standard's block-size grid, and all 188 are verified permutations.

---

## Phase 2 — Sample-rate provenance (audit C1)

**Changed**
- `src/pipeline.py`:
  - `analyze_iq(iq, fs=None, fs_source=None)` and `analyze_file(fs=None)`; the old default `fs=1e6` is removed.
  - Every result carries `fs_hz` (None when unknown), `fs_source` ∈ {declared, wav_header, inferred, relative_only, unavailable}, and `symbol_rate_norm` (symbols per sample).
  - `symbol_rate_est` (Hz) is None without an absolute rate.
  - Invalid rates (≤ 0, NaN, ∞) and unknown sources raise errors.
- The raw symbol-rate estimate is now always computed in normalised units. Before, welch's Hz frequency grid rounded differently at band edges (the Nyquist bin), so the candidate set depended on the declared rate (next section).
- `server/app.py`:
  - `.iq` without `fs` → `fs_source = unavailable`; the silent 1 MHz default is gone.
  - Malformed `fs` → HTTP 400.
  - `.wav` → `wav_header`. An operator value that contradicts the header becomes `declared`, and the conflict is kept in `fs_note`.
  - Real-signal receivers run only when an absolute rate is known.
- `server/evidence.py`:
  - The pack's `capture` has `fs_hz`, `fs_source`, `fs_note` ("Absolute sample rate not established") and `duration_s` (None when unknown).
  - `views.units` is `hz` or `normalised`.
- `sealed_test.py`, `server/export_frontend_data.py`: bench-v1 rates are passed as `declared` (from the generator's ground-truth `fs`).
- Console:
  - "Sample rate" row with provenance in Characteristics, Data quality, the evidence chain and the report.
  - Symbol rate in sym/sample when Hz is unknown; the PSD axis is in cycles/sample for normalised packs.
  - The upload form no longer pre-fills 1,000,000 and says a raw `.iq` has no header.

**Tests**
- `tests/test_fs_provenance.py`, 12 tests:
  - missing fs → unavailable (never 1 MHz);
  - decision identical for fs ∈ {None, 1 MHz, 48 kHz};
  - invalid rates rejected;
  - pack says "not established";
  - live HTTP API: `.iq` without fs, with fs, malformed fs, WAV header, header conflict.
- Full suite: **42 passed**. Frontend build OK.

**Decision identity (measured)**

| Set | Comparison | Differences |
|---|---|---|
| bench-v1 sealed + train (130 files) | v2.4 engine (`acf4201`) vs Phase 2 engine at fs = 1 MHz: status, code, sps, n_hypotheses, log10 p | **0** |
| Null set (1,350 files) | v2.4 rows vs Phase 2 engine with fs unavailable | **0 status/code/payload changes**; 7 files changed their hypothesis count (e.g. `k7_060_008` 2,199 → 6,177; `noise_030_047` 3,843 → 3,060) because of the Nyquist-bin rounding described above. The null-set files had implicitly been analysed at fs = 1 MHz; the estimate is now fs-independent |

sealed 30/30, 0 FA; train 63/100, 0 FA (unchanged).

## Phases 5–9 (part 1) — Catalogue v1 primitives, not yet wired into the engine

Commits `adde168` (RS, LDPC, framing, interleavers) and `10e4156` (8PSK, 16-QAM). These add
verified building blocks; the engine's decisions were untouched, so bench-v1, the null set and every
status stayed exactly as in Phase 2.

**Added**
- `references/`: `ccsds_constants.json`, `lte_qpp_table.json` (188 QPP entries, each verified to be a
  permutation), `rs_ccsds_conventional_vectors.json` (generated with reedsolo 1.7.0), `README.md`.
- `src/rs.py` — CCSDS RS(255,223) E = 16 and RS(255,239) E = 8: GF(2⁸) in base β = α¹¹, dual basis
  (Annex F), depth I ∈ {1,2,3,4,5,8} and virtual fill Q, Berlekamp–Massey / Chien / Forney decoder,
  degenerate-codeword flag, and the exact random-decode probability V(n′,E)/256^{2E}
  (10⁻¹³·⁵⁸ for E = 16, 10⁻⁴·⁶⁸ for E = 8).
- `src/ldpc.py` — CCSDS TC LDPC (128,64): H from §4.2.2 a), G from Table 4-1; H·Gᵀ = 0 and rank 64
  checked at import; `satisfied_checks`; normalised min-sum decoder.
- `src/framing.py` — the three catalogue randomizers (each reproducing the published first 40 bits),
  both catalogue markers, exact-binomial `marker_search` / `blind_search`, domain counts, `frame_map`
  and `structural_rejection`.
- `src/interleavers.py` — block, diagonal, Forney convolutional and LTE QPP specs with
  `deinterleave_index` / `interleave` / `candidates` / `describe`.
- `src/constellations.py` — 8PSK and 16-QAM mapping, max-log LLRs, M-power phase, kurtosis-aware
  M2M4, and the two modulation gates (QPSK y⁴ signature, constant-modulus contradiction).
- `tests/test_catalogue.py`, 8 tests: RS against independent vectors, dual basis against Annex F,
  LDPC H/G consistency, randomizers against the standards, frame sync, QPP table, 8PSK/16-QAM BER
  (< 1e-3 at 20 dB) and gate separation.

## Phase 10 (step 1) — F1 generalised to interleaver specs (decision-identical refactor)

The burst family previously spoke only of block `(rows, cols)`. Before adding diagonal,
convolutional and QPP hypotheses, the plumbing was generalised **with the searched set unchanged**
(`pipeline.INTERLEAVER_TYPES = ('block',)`), so the change can be proven to alter no decision.

**Changed**
- `src/interleavers.py`: no longer imports `blind_id` (the cycle would break the new direction); it
  now owns `INTERLEAVER_ROWS` / `INTERLEAVER_COLS` and builds the block index from `fec`.
- `src/blind_id.py`:
  - `as_spec` accepts a spec tuple or a bare `(rows, cols)` pair, so every existing caller keeps working;
  - `syndrome_scan(th, specs)` takes specs, returns `spec` (an index into the `specs` it kept) instead
    of `rows`/`cols`, and drops specs whose index does not fit the observed stream;
  - `decode_hypothesis(llrs, code, interleaver)` works for any spec. Covered positions are scored in
    **stream order** (`argsort` of the index, stable), which for a block interleaver adds exactly the
    terms the old boolean mask added, in the same order, so the path metric is bit-identical;
  - `deinterleave_index(rows, cols)` is kept as the block-only helper.
- `src/pipeline.py`: hypotheses carry a global spec id (one interleaver is the same key across front
  ends); `INTERLEAVER_TYPES` declares which types are searched; results gain `interleaver_spec`
  (`interleavers.describe`), while `interleaver` stays `[rows, cols]` for block specs and is None for
  other types; `all_hypotheses` gains an `interleaver` label column (`rows`/`cols` stay for block and
  diagonal, 0 otherwise).
- `eval/identity.py` (new): decision-identity checker. Rows are matched by `file`; every key present
  in the BEFORE run must be equal in the AFTER run (recursively, exact), timing fields excluded.

**Decision identity (measured on this machine, commit `10e4156` vs this commit)**

| Set | Files | Differences |
|---|---|---|
| bench-v1 sealed | 30 | **0** |
| bench-v1 train | 100 | **0** |
| Null set | 1,350 | **0** |

The comparison covers every logged field, including each top hypothesis's `log10_p`, `path_metric`,
`consistency`, `covered_bits` and `mdl_savings_bits`, so the refactor is bit-identical, not merely
verdict-identical. sealed 30/30 0 FA; train 63/100 0 FA; null set 0/900 false accepts, K7/K5/K3
61/37/31, noise → SIGNAL_NO_CODE 21/500.

**Tests** — `tests/test_catalogue.py` gains `test_spec_scan_matches_per_pair_loop_and_decodes_every_type`:
on a 300-bit random stream the vectorised scan reproduces the per-pair `syndrome_checks` loop for all
four interleaver types (same counts, same positive counts, same order), and a noiseless K7 codeword
interleaved by block, diagonal, QPP and convolutional specs decodes back with consistency 1.0. Full
suite: **51 passed**.

**Baseline note (this machine)** — Python 3.11.16, numpy 2.4.2, scipy 1.17.0 on Windows 11 reproduce
the reference baseline exactly, except `uncoded_qpsk` → UNKNOWN 122/150 where the Constitution §19
table records 121/150 (one file also differs from the earlier run in the `.venv` baseline rows: the
pre-refactor and post-refactor runs here agree on all 1,350). Treated as a platform difference in a
single borderline file; it is not a decision change of this commit.

## Phase 10 (step 2) — F1 at the weighted bar with all four interleaver types, and F2 wired in

**Changed**
- `src/pipeline.py`:
  - `INTERLEAVER_TYPES = interleavers.TYPES` — block, diagonal, Forney convolutional and LTE QPP are
    now all searched (catalogue v1, §12.1);
  - `FAMILY_WEIGHTS` holds the pre-registered §13.1 weights; the F1 bar is now
    `α·0.50 / M₁` instead of `α / M₁`;
  - `accept.families` lists each family with its weight, tested hypotheses, bar, best p and verdict;
    `accept.interleaver_types` records what was searched;
  - family F2 runs after the burst family, and a file whose F1 family accepts nothing but whose F2
    family does is DECODED as a continuous stream (`result.stream_code` carries the evidence).
- `src/stream.py` (new) — family F2: the dual-code sign test applied directly to the stream, for pair
  offset × G2 inversion. Because g1 = 0o171 has odd weight, inverting every c2 bit negates every
  check, so the inverted hypothesis is the lower tail of the same count (no second pass) — both are
  counted in M₂. `decode` uses an unknown start state and resolves polarity by path metric.
- `src/fec.py`: `viterbi_decode(..., start='zero'|'any')`. The default is unchanged (`'zero'`);
  `'any'` initialises every start state at 0 for a continuous stream with no reset point.
- `eval/nullset.py`, `eval/acceptance.py`: a top hypothesis with a non-block interleaver has
  `interleaver = None`, which these comparisons now handle.

**Measured**

| Gate | Before (block only, α/M₁) | After (4 types, 0.5·α/M₁) |
|---|---|---|
| bench-v1 sealed | 30/30, 0 FA | **30/30, 0 FA** |
| bench-v1 train | 63/100, 0 FA | **63/100, 0 FA** |
| Null set false accepts | 0/900 | **0/900** |
| Null set correct K7/K5/K3 | 61/37/31 | **61/37/31** |
| Noise → SIGNAL_NO_CODE | 21/500 (4.2%) | 21/500 (4.2%) — Phase 11 |
| Mean hypotheses M₁ per file (null set) | 9,206–11,986 | 18,530–27,780 (≈2.4×) |
| Mean runtime per null file | 0.11–0.13 s | 0.18–0.26 s; whole null set 24 s → 35 s |

**The expected recall loss did not appear.** §13.1 note 3 predicted that halving the F1 budget and
growing M₁ would cost bench-v1 recall. It cost none: the accepted hypotheses on these files are far
below the bar (a 1-decade change in the bar is small next to their p-values), so no file crossed it.
Reported, not tuned — nothing was adjusted to obtain this.

**Wrong-structure null with the new interleaver types** (`eval/acceptance.py`, 1,350 null + 450
wrong-structure runs; the true interleaver is removed so any accept is wrong), evaluation split:

| Rule | Recall | Wrong-hypothesis | Null false accepts | Wrong-structure accepts |
|---|---|---|---|---|
| R0 (sign test only) | 0.311 | 4/225 | 1/450 | 37/225 |
| **R0+MC+BL+PM (adopted)** | **0.320** | **0/225** | **0/450** | **0/225 (≤1.7%)** |

Three more interleaver families therefore did **not** buy wrong-structure accepts (v2.5 measured
2/225 with block only; this run gives 0/225 at the same recall). The R0-only sweep on the null set is
also unchanged (τ = −2: 4 null accepts vs 6 before).

**Not adopted:** this run's calibration split recomputes the path-metric floor as 0.959 against the
shipped `PM_FLOOR = 0.926`. The shipped constant is left alone — changing it needs a Constitution
amendment (§13, §46), and re-fitting it here would tune on data the rule is being judged on.

**Tests** — `tests/test_families.py` (new, 4 tests): `start='any'` decodes a mid-stream cut that
`start='zero'` cannot; a continuous K7 stream is accepted and decoded at BER 0 with and without G2
inversion; noise and an uncoded stream are refused with the family bar shown; every family's bar
equals α·w/M with the pre-registered weights. Full suite: **55 passed**.

## Phase 10 (step 3) — F3 frame family wired in; two engine defects found and fixed

**Criteria, fixed before running anything** (§32): sealed ≥ 28/30 and 0 FA; train ≥ 63/100 and 0 FA;
null-set false accepts 0/900 and wrong decodes 0/450; noise → SIGNAL_NO_CODE not above 21/500;
wrong-structure accepts (adopted rule, evaluation split) not above 2/225; and on a 12-seed
concatenated sweep, ≥ 11/12 F2 accepts with BER < 0.01.

**Added**
- `pipeline._frame_family` / `_frame_streams` — family F3 over the streams described below.
  M₃ = Σ `framing.family_domain(n)` over every stream tested (the whole declared domain of periods,
  offsets, markers, widths and polarities, not only the hypotheses evaluated), bar α·0.20/M₃.
  Candidates are walked in p-value order and the first that passes `framing.structural_rejection` is
  accepted; the accepted frame carries `framing.frame_map`.
- Among candidates that clear the bar, a **catalogue marker is preferred** over a blind constant
  field. A blind window overlapping the same ASM can reach a smaller p-value merely by being wider,
  which hid a present ASM behind an anonymous "constant field" claim in 12 of 12 sweep runs.
- Verdict: an accepted F3 with no accepted code gives **SIGNAL_NO_CODE with the frame map**, as
  §13.1 note 6 requires. F3 never produces DECODED on its own.
- `result.frame` holds the family evidence: bar, best p, accepted hypothesis, map, the streams
  tested with their domains, the top candidates, and anything structurally rejected.

**Defect 1 — the front-end serial-dependence gate discarded the coherent front end of a framed
stream.** The gate rejected any front end whose neighbouring hard decisions agree significantly more
often than half the time. Its target is an oversampled front end (sps too small), which repeats every
symbol and so agrees on ≈75% of pairs (≈83% at 3×). But real framed data repeats a sync marker every
frame, which biases the rate to ≈0.515 — and over a 6,000-bit stream that is overwhelmingly
significant against ½. The gate therefore threw away the *coherent* front end and kept a front end
with a small carrier error, whose polarity flips in segments. Fix: the gate now tests against the
composite null "agreement ≤ `SERIAL_AGREEMENT_MAX` = 0.60", a declared receiver spec with a physical
basis (the 0.75 duplicate-symbol floor), not a fitted constant.

**Defect 2 — a tie at the p-value floor chose a segment-flipping front end.** `sign_test_log10p`
clips at 1e-300, so on a long stream every strong F2 hypothesis reports exactly −300 and the winner
was decided by list order. A front end with residual carrier offset satisfies the parity check inside
each polarity segment (the catalogue generators have odd weight, so a complemented codeword is a
codeword) and fails only at the boundaries, so it is accepted with p = −300 and a check agreement of
0.94, and it decodes to a segment-wise complemented, useless payload — a confident wrong decode. Fix:
`stream.rank` orders F2 hypotheses by (p-value, then check-agreement ratio), exactly as F1 breaks the
same tie with the syndrome z. The coherent front end (agreement > 0.999) now wins.

**Defect 3 — F3 stream selection by symbol SNR is not discriminating.** The M2M4 symbol SNR measures
power, not coherence, so the sps = 4 BPSK front ends at five different CFO candidates all measured
13.82 dB while only one carried a detectable ASM (p = 10⁻¹¹⁵·⁶ against 10⁻⁹·⁷ for its neighbours).
Taking "the 3 best front ends by SNR" therefore tested an arbitrary one. Fix: keep the
`F3_FRONT_ENDS` = 3 best (sps, modulation) **classes** and test every CFO/rotation front end within
them, capped at `F3_MAX_STREAMS` = 12 streams. Only streams actually tested enter M₃.

**Measured after the fixes**

| Gate | Before this step | After |
|---|---|---|
| bench-v1 sealed | 30/30, 0 FA | **30/30, 0 FA** |
| bench-v1 train | 63/100, 0 FA | **63/100, 0 FA** |
| Null set false accepts | 0/900 | **0/900** (≤ 0.43%) |
| Null set wrong decodes | 0/450 | **0/450** |
| Null set correct K7/K5/K3 | 61/37/31 | **61/36/31** (one K5 file lost) |
| Noise → SIGNAL_NO_CODE | 21/500 | **21/500** |
| Wrong-structure accepts (adopted rule) | 0/225 | **0/225** (≤ 1.7%) |
| Recall on the wrong-structure run | 0.320 | 0.316 |
| Concatenated 12-seed sweep | 11/12 accepted, 1 garbage payload | **12/12 accepted, 12/12 BER < 0.01, 12/12 ASM found** |
| Null-set runtime | 35 s | 37 s |

Every pre-fixed criterion holds. **The one-file losses are real and reported, not tuned away:** with
the relaxed serial gate more front ends survive, so M₁ grows and the F1 bar tightens; one K5 null
file (and 0.004 of wrong-structure recall) fell below it. Nothing was adjusted afterwards.

**Tests** — `tests/test_families.py` grows to 8: the ASM frame stream is SIGNAL_NO_CODE with a map
whose columns add up and which states how many frames a per-column proof would need; the
concatenated stream is DECODED via F2 with the frame found in the Viterbi output; noise and an idle
carrier are refused; the serial gate keeps the coherent front end of a framed stream; M₃ equals the
declared domain of the streams tested. Full suite: **59 passed**.

## Phase 10 (step 4) — F4 block-code family: CCSDS Reed-Solomon and TC LDPC (128,64)

**Added — `src/blockcode.py`**
- **Reed-Solomon behind an accepted catalogue marker.** The measured frame period fixes the
  codeblock: 8·(255·I − Q) = P − marker bits, so a 2,072-bit frame admits E = 16, I = 1, Q = 0.
  Hypotheses are (E, I, Q) × randomizer ∈ {none, TM 131071, TM 255}, derandomized from the first bit
  after the marker and restarted each frame. The statistic is the exact tail
  P(≥ D decodes of C codewords) with the per-codeword probability V(n′,E)/256^{2E}; a decoder success
  is never by itself the evidence, and a degenerate codeword (fewer than four distinct symbols)
  is refused however small the p-value.
- **TC LDPC (128,64)** by codeword offset ∈ [0,128) × randomizer ∈ {none, TC BTG preset per
  codeword}. The 64 rows of H are linearly independent, so the satisfied checks of F complete
  codewords are exactly Binomial(64F, ½). One pass computes each row's parity at every bit position;
  derandomizing flips a row's parity by a constant, so the randomized hypotheses come free from the
  same pass. Min-sum decoding runs only after acceptance.
- `pipeline._block_code_family` counts every RS and LDPC hypothesis in M₄ (bar α·0.20/M₄) and
  `pipeline._structure` now reports the accepted chain layer by layer (burst code / stream code /
  frame with its map / block code with its parameters).
- Verdict: an accepted F4 gives **DECODED**, above F2 alone, because it is the longer chain
  (§13.1 note 6). F1 still takes precedence, which keeps bench-v1 behaviour untouched.

**Defect 4 — LDPC polarity is unresolvable, and a segment-flipping front end exploited it.** Every
row of H has even weight 8, so the complement of a codeword is a codeword and the sign test is
polarity-invariant. An off-carrier front end whose polarity flips between segments therefore passed
with 1,457/1,536 satisfied checks and produced a payload that was correct in some segments and
complemented in others. Two fixes: `blockcode.rank` orders F4 hypotheses by (p-value, then agreement
fraction), so the coherent front end (1,536/1,536) wins, exactly as `stream.rank` does for F2; and the
accepted LDPC hypothesis now carries `polarity` / `polarity_resolved`, set from an accepted catalogue
marker on the same stream when there is one and reported as **unresolved** when there is not — a
CLTU start sequence appears once, so the periodic marker test cannot anchor it. Also fixed:
`ldpc_decode` returns the information bits of every codeword with a `converged_codewords` mask, so
the payload stays aligned with the transmission instead of silently dropping unconverged blocks.

**Measured (end-to-end, engine blind)**

| Signal | Result |
|---|---|
| RS(255,223) E=16 I=1 + TM 131071 randomizer + ASM (P = 2,072) + inner K7, BPSK at 8 dB | **DECODED** `ccsds_rs_255_223`; E, I, Q and randomizer all identified; 4/4 codewords, 0 symbol errors; payload BER **0.0**; layers stream_code → frame → block_code |
| TC LDPC CLTU: 64-bit start sequence + 24 BTG-randomized codewords, BPSK at 9 dB | **DECODED** `ccsds_tc_ldpc_128_64` at offset 64 (immediately after the start sequence), randomizer identified, 1,536/1,536 checks, 24/24 codewords converged, payload BER **0.0** (complement-tolerant; polarity reported unresolved) |
| ASM frames with random data | SIGNAL_NO_CODE, F3 accepted, F4 refused |
| ASM frames with constant fill | not DECODED; RS refused as degenerate |
| Noise, idle carrier | UNKNOWN / SIGNAL_NO_CODE, no F4 accept |

| Gate | Value |
|---|---|
| Tests | **63 passed** |
| bench-v1 sealed / train | 30/30, 0 FA / 63/100, 0 FA (unchanged) |
| Null set | 0/900 false accepts, 0/450 wrong decodes, K7/K5/K3 61/36/31, noise → SIGNAL_NO_CODE 21/500 (all unchanged: the null-set captures are ≤ 384 bits, so F4 has fewer than two codewords and is inert) |
| Null-set runtime | 37 s → 40 s |
| Runtime on the 66 k-sample CCSDS capture | 3.3 s, of which frame search 2.4 s and block-code search 0.3 s |

**Tests** — `tests/test_families.py` grows to 12: RS profiles follow the frame period (including
virtual fill and a rejection of non-byte-aligned periods); the full CCSDS chain decodes with every
parameter identified; the CLTU decodes and reports unresolved polarity; a framed stream with random
data and one with constant fill are both refused, the latter on the degenerate-codeword rule.
