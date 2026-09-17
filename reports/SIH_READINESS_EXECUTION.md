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
