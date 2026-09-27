# SPACE_EVIDENCE_MATRIX
**ICHNOVA · SIH26147 — requirement-by-requirement evidence ledger for the space-ground extension**
**Status: AUDIT ARTEFACT (2026-09-25). Verified against the working tree at branch `sih-readiness`, commit `3919546`, working tree clean, `python -m pytest -q` → 178 passed.**

This file is the answer to one question, asked eighteen times: **"what exactly entitles ICHNOVA to say anything about this, and what does not?"** It is the reviewer's checklist for every space claim, and it is deliberately unflattering where the evidence is thin.

Every row carries exactly one status from the mandated taxonomy:

**EXISTING** · **EXTENSION** · **NEW** · **EXPERIMENTAL** · **SIMULATED** · **NOT ESTABLISHED**

A capability may be EXISTING *as a terrestrial/bench capability* and simultaneously NOT ESTABLISHED *as a space-link capability*. That distinction is the entire point of this document, and collapsing it is the single most likely way this project would come to make a false claim.

---

## 0. Evidence sources cited below (all verified in-tree this session)

| Tag | Artefact | What it is | Scale |
|---|---|---|---|
| **BENCH-V1** | `data/sealed`, `sealed_test.py` | Regression **tripwire**, *not* held-out — 30/30, 0 false accepts | 30 files |
| **BENCH-V2** | `data/bench2/sealed`, `eval/bench2.py`, `eval/bench2_criteria.json` | Pre-registered sealed benchmark, one logged run (`eval/bench2_access_log.jsonl`, 2026-09-17, engine `d790e99`) — **9/9 criteria passed** | 430 files |
| **NULLSET** | `eval/nullset.py`, `data/nullset` (seed 500000) | Independent null/other-code set — **0/900** false accepts, **0/450** wrong decodes | 1,350 files |
| **REALSIG** | `reports/REAL_SIGNAL_VALIDATION.md`, `recordings/real/`, `tests/test_realsig.py` | Real over-the-air captures — **terrestrial only** | 8 captures |
| **CODE** | `src/*.py` | Constants and logic read directly this session | — |

**BENCH-V1 and BENCH-V2 are different benchmarks with different numbers.** "bench-v2 30/30" is not a measurement that exists anywhere in this repository.

### 0.0 SPACE STATUS SUMMARY (read this first)

| Condition | Status as of 2026-09-25 |
|---|---|
| **Static carrier** (zero or constant offset within `CFO_MAX = 0.0125` cyc/sample) | **ESTABLISHED WITHIN DOCUMENTED BENCHMARK SCOPE** — blind inference and refusal discipline validated: bench-v2 430 sealed files 9/9 pre-registered criteria; bench-v1 30/30 with 0 false accepts; 0/900 false accepts on the independent 1,350-file null set; and 0 wrong payloads in this experiment's 96 static controls |
| **Time-varying carrier** (frequency moves during the capture) | **EXPERIMENT COMPLETED — PAYLOAD-RELIABILITY LIMITATION MEASURED.** 54 of 96 treated captures returned a wrong payload beneath a *true* structural claim; 0 wrong structures across all 192 captures. Result: `DOPPLER_EXPERIMENT_RESULTS.md`; analysis: `DOPPLER_FAILURE_ANALYSIS.md`. **ROOT CAUSE NOT ESTABLISHED**; diagnostic designed in `DOPPLER_REMEDIATION_EXPERIMENT.md` |
| **Orbital Doppler** (TLE / geometry-driven pass trajectory) | **NOT ESTABLISHED** — no orbit model exists in this project; deferred by the STOP rule |
| **Real spacecraft RF** | **NOT ESTABLISHED** — no real spacecraft capture exists in this project; all real-signal validation to date is terrestrial |

Neither "Doppler supported" nor "space-link ready" is a permitted sentence anywhere in this project. The boundary in one line: a `DECODED` verdict may be relied on for *what the signal is*; for *what the signal says* only when the carrier is static within the capture.

### 0.1 The single most Doppler-relevant fact in the repository

BENCH-V2's per-channel breakdown (`reports/BENCH2_SEALED_REPORT.md`, "By channel"):

| channel | N | wrong structure/payload | rate |
|---|---|---|---|
| `awgn` | 88 | **0** | 0.0% |
| `phase_noise` | 52 | **0** | 0.0% |
| **`cfo_drift`** (linear frequency ramp) | **70** | **3** | **4.3%** |
| `rician` | 46 | **0** | 0.0% |
| `amplitude` | 76 | **0** | 0.0% |
| `timing` | 88 | **0** | 0.0% |

**All three wrong claims in the entire 430-file sealed run fall in the one channel class whose impairment is a time-varying carrier frequency** — and they fall in three *different* signal classes (`stream_k7`, `ccsds_concat`, `burst_8PSK_k3_diag`), so this is a property of the impairment, not of one family. FACT.

This is the strongest available justification for the Doppler experiment and simultaneously the strongest available warning about it: the project's only measured false-decode mode is already carrier-drift-shaped, and `cfo_drift` is merely a **linear** ramp (rate ~ U(−2e-7, +2e-7) cycles/sample per sample, applied as a quadratic phase — `bench2_gen.apply_channel`). A pass-shaped trajectory is strictly harder. Nothing in the repository establishes what happens there. This is not a prediction of failure; it is the reason the experiment is worth running rather than assumed.

---

## 1. RF capture

| Field | Content |
|---|---|
| **SPACE REQUIREMENT** | Ingest an IQ recording of a spacecraft downlink with known provenance and sample rate. |
| **CURRENT CAPABILITY** | Raw interleaved-float32 `.iq` ingestion (`modem.load_iq`); `.wav` with header parsing; sample-rate provenance tracked as a first-class enum `FS_SOURCES = ('declared','wav_header','inferred','relative_only','unavailable')` — CODE. Real SDR captures flow the whole chain — REALSIG. |
| **SPACE EXTENSION** | None required for synthetic vectors. For real space captures: station/antenna/SDR metadata fields in the capture provenance record. |
| **STATUS** | **EXISTING** (format-agnostic — a spacecraft IQ file is not structurally different from any other IQ file). |
| **EXPERIMENT REQUIRED** | None. |
| **EVIDENCE REQUIRED** | Already satisfied — REALSIG captures ingested through the identical path. |
| **FALSE-CLAIM RISK** | **Low**, with one trap: "ICHNOVA ingests spacecraft telemetry" is true of the *file format* and false of the *validation*. Never let ingestion capability imply space validation. |

## 2. Signal qualification

| Field | Content |
|---|---|
| **SPACE REQUIREMENT** | Decide whether a capture is fit to analyse at all, and say why when it is not — without letting that judgement contaminate the verdict. |
| **CURRENT CAPABILITY** | `src/quality.py` — clipping, DC offset, dropouts/zero-runs, I/Q balance; GOOD/FAIR/POOR reported **beside** the verdict. Governing rule, verified in code and docs: *"a bad capture explains a refusal, it does not create one."* — CODE. |
| **SPACE EXTENSION** | None. Space-link degradation (deep fade, low elevation) shows up as evidence decay on the existing axes. |
| **STATUS** | **EXISTING**. |
| **EXPERIMENT REQUIRED** | None of its own; the quality axis is *recorded* in every SPACE-BENCH family as a covariate. |
| **EVIDENCE REQUIRED** | Satisfied. Quality-vs-verdict independence must be re-verified as an invariant in any space run (SPACE_IMPLEMENTATION_GATE.md §5.8). |
| **FALSE-CLAIM RISK** | **Low.** |

## 3. Modulation inference

| Field | Content |
|---|---|
| **SPACE REQUIREMENT** | Infer the modulation of a spacecraft carrier without being told it. Real missions use BPSK, QPSK, OQPSK, 8PSK, 16-APSK, GMSK, PCM/PSK/PM. |
| **CURRENT CAPABILITY** | Blind BPSK/QPSK inference with a *modulation consistency* structural check (y² data-free for BPSK / random for QPSK, two exact binomial tests per candidate) — CODE, `tests/test_modulation_aliasing.py`. 8PSK/16-QAM implemented but **gated OFF**: `SEARCH_HIGHER_MODULATIONS = False`. |
| **SPACE EXTENSION** | None permitted in Phase 1. Higher-order and continuous-phase modulations stay out of scope. |
| **STATUS** | **EXISTING** for BPSK/QPSK · **EXPERIMENTAL, OFF** for 8PSK/16-QAM · **NOT ESTABLISHED** (not implemented) for GMSK, OQPSK, PCM/PSK/PM. |
| **EXPERIMENT REQUIRED** | D3 (modulation consistency under a frequency trajectory). Enabling higher orders requires a Constitution amendment (F1 sub-weight split + power-condition gate) and is explicitly **not** part of this work. |
| **EVIDENCE REQUIRED** | D3 measurement: modulation-gate statistics and inferred modulation vs static control across the severity sweep. |
| **FALSE-CLAIM RISK** | **HIGH — the sharpest overclaim edge in the space story.** Most real spacecraft telemetry is outside the enabled modulation set. Enabling 8PSK/16-QAM was *measured harmful*: it cost BENCH-V1 5/30 files, produced 1/900 null false accepts and 1 wrong K5 decode (`reports/HIGHER_MODULATION_EXPERIMENT.md`). Any sentence implying general spacecraft-modulation coverage is false. |

## 4. Symbol-rate inference

| Field | Content |
|---|---|
| **SPACE REQUIREMENT** | Recover the symbol rate blindly across the mission-plausible range. |
| **CURRENT CAPABILITY** | y⁴ lag-1 correlation scan over `SPS_RANGE = (2, 20)` integer samples/symbol with divisors added, `MIN_SYMBOLS = 16` per candidate, `N_SPS_RANKED = 3`; front-end serial-dependence gate `SERIAL_AGREEMENT_MAX = 0.60` rejects oversampled repeated-symbol aliases — CODE. True sps in the candidate list 30/30 BENCH-V1 sealed, 91/100 train. |
| **SPACE EXTENSION** | None structurally. Note the domain is *integer* sps 2–20, i.e. symbol rate ∈ [fs/20, fs/2] — a real downlink at an arbitrary non-integer sps ratio is out of domain. |
| **STATUS** | **EXISTING** (within the integer-sps domain). |
| **EXPERIMENT REQUIRED** | D4 (sps-candidate stability under trajectory). |
| **EVIDENCE REQUIRED** | D4: sps error rate and candidate-rank stability per severity cell vs static control. |
| **FALSE-CLAIM RISK** | **Medium.** The integer-sps restriction is a real domain bound and is rarely stated. It must appear in the assumption ledger, not only in code comments. |

## 5. Static carrier frequency offset

| Field | Content |
|---|---|
| **SPACE REQUIREMENT** | Acquire a carrier whose frequency is offset from nominal by oscillator error and coarse tuning. |
| **CURRENT CAPABILITY** | x²/x⁴ spectral-line detection against an **exact** exponential-periodogram null, Bonferroni-corrected over spectra; search bound `CFO_MAX = 0.0125` (±1.25% fs); `N_CFO_PER_ORDER = 3` — CODE. |
| **SPACE EXTENSION** | None. |
| **STATUS** | **EXISTING**, and broadly exercised: **every** BENCH-V2 sealed vector carries a static CFO drawn U(−0.008, +0.008) cyc/sample (±0.8% fs) on top of its channel class (`bench2_gen.apply_channel` — CODE), so static CFO is exercised across all 430 sealed files rather than by a dedicated family. The `awgn` class (88 files, **0** wrong claims) is the cleanest static-CFO-only evidence. |
| **EXPERIMENT REQUIRED** | None of its own. Serves as the **control group** for the Doppler experiment (trajectory class `static`). |
| **EVIDENCE REQUIRED** | Satisfied — BENCH-V2. SPACE-BENCH family C re-measures it in the space namespace with hidden-truth CFO comparison. |
| **FALSE-CLAIM RISK** | **Low**, with one boundary to state: ±1.25% fs is an *assumed front-end tuning accuracy*. A real downlink beyond that bound is out of domain, and the system must refuse rather than alias. |

## 6. Time-varying CFO / Doppler — **THE HEADLINE GAP, NOW MEASURED AND FAILED**

| Field | Content |
|---|---|
| **SPACE REQUIREMENT** | Analyse a carrier whose frequency **moves during the capture**: LEO residual Doppler of order ±5 kHz at S-band with rates to ~32 Hz/s (sourced magnitudes, SPACE_RESEARCH_LANDSCAPE.md §1), i.e. a non-linear S-curve over a pass. |
| **CURRENT CAPABILITY** | A **generic** coherence-adaptive block phase tracker, `pipeline._track_phase`: applied when a capture reaches `TRACK_MIN_SYMBOLS = 512`; block length chosen **by the data** from {64, 32, 16, 8} symbols (`TRACK_BLOCK = 64` is the maximum, not a fixed value) by maximising block coherence \|mean(y^M)\| / mean(\|y^M\|), requiring ≥ 8 blocks; per-block M-power phase estimates unwrapped across blocks. It is not data-aided and adds no hypotheses of its own — it is one more front end, counted in every family's M. — CODE. Its existence is *itself* measured evidence: it was added because BENCH-V2 calibration found 13 of 15 wrong payloads came from `phase_noise` / `cfo_drift` / `amplitude`. Validated impairment reached: **linear** ramp only (`cfo_drift`). |
| **SPACE EXTENSION** | (a) A **pass-shaped (S-curve) trajectory generator** — NEW, small pure function, seeded, unit-tested. (b) **Trajectory read-out**: the per-block phase/frequency estimates already computed inside `_track_phase` are currently **discarded after equalisation** — surfacing them is an additive, side-effect-free read-out. (c) A **declared static-vs-time-varying classification rule** over the extracted trajectory. |
| **MEASURED RESULT (2026-09-25)** | **THE EXPERIMENT HAS RUN AND IT FAILED ITS HEADLINE CRITERION.** SPACE-DOPPLER, 192 controlled synthetic vectors, pre-registered criteria `eval/space_doppler_criteria.json` committed before the first vector existed; full record in `reports/space/DOPPLER_EXPERIMENT_RESULTS.md`. Under a time-varying carrier the engine published a **wrong payload beneath a *true* structural claim in 54 of 96 treated captures (56.3%)**, false-decode BER 0.027–0.495, flat across Es/N0 12/9/6 dB; on the `zero` and `static` controls it was wrong **0 of 96** (80 correct, 16 refusals, all of them severity-2.0 cells outside `CFO_MAX` where refusal was the pre-registered expectation). **0 wrong structures in 192** — the structural test held; the payload did not, and no gate flagged it (accepted F2 log₁₀p −14.8 to −29.7 against bars near −5). Tracking helps and is not sufficient: above `TRACK_MIN_SYMBOLS`, 25 false decodes remain. — FACT |
| **STATUS** | **MEASURED LIMITATION** (was NOT ESTABLISHED; the experiment has now been run). The decode verdict is validated **only for a carrier that is static within the capture**. Under a carrier that moves during the capture the payload is unreliable and **is published anyway**, with no refusal available from today's gates. A generic phase tracker exists and helps on a *linear* ramp; it does **not** make Doppler operation supportable. **Doppler support must not be claimed — not on the tracker's existence, and no longer as an open question either: it is a measured failure.** |
| **REMEDIATION TESTED AND REJECTED (2026-09-26)** | The obvious fix was measured and does **not** hold. `SPACE-CARRIER-EST-01` (`CARRIER_ESTIMATOR_RESULTS.md`): a blind per-block carrier pre-correction recovers most of the lost payload reliability within the tested conditions (wrong payloads 108 → 2 of 192 treated captures) **but** costs bench-v1 8 of 30 decodes, one of bench-v2's nine criteria, 41 of 128 null-set catalogue decodes, and produced a **structural false accept on an idle carrier**. **INTEGRATION NOT SUPPORTED.** The limitation in this row is therefore **not retired** — it now also has a measured reason why the obvious remedy is not the remedy. |
| **ANALYSIS** | `DOPPLER_FAILURE_ANALYSIS.md` — what failed, what did not, where in the chain the failure appears, why tracking is insufficient, the safe operating boundary, and six candidate mechanisms under **ROOT CAUSE NOT ESTABLISHED**. |
| **EXPERIMENT REQUIRED** | **DONE for D3–D7** (the half answerable without a production change): run 2026-09-25, 192 vectors, result above. **STILL REQUIRED: D1** (trajectory RMSE), **D2** (static-vs-time-varying classification) and **D8** (trajectory in the receipt) — all three blocked on the `_track_phase` read-out that awaits approval (SPACE_IMPLEMENTATION_GATE.md §9.3). Next after that is not a new experiment but a **remediation measurement**: whether a payload-reliability gate (R1, DOPPLER_EXPERIMENT_RESULTS.md §8) converts these wrong answers into refusals without costing static-carrier recall. |
| **EVIDENCE REQUIRED** | A **sealed** experiment with: injected trajectory ground truth; measured trajectory RMSE (D1); static-vs-time-varying classification accuracy (D2); modulation/sps/code consistency vs control (D3–D5); **false-decode count (D6 — any false decode is a failure condition, STOP-and-document, never tuned)**; verdict-migration monotonicity (D7); trajectory preserved in the evidence receipt (D8). Acceptance criteria written **before** the sealed vectors exist. |
| **FALSE-CLAIM RISK** | **HIGHEST IN THE PACKAGE.** Three specific traps: (1) claiming Doppler support because a phase tracker exists — prohibited; that is a generic carrier-tracking capability, not a validated space-link one; (2) treating the linear `cfo_drift` result as a Doppler result — it is a linear ramp, and a pass is not linear; (3) forgetting §0.1 — the *only* channel in which this engine had ever produced a wrong claim was the carrier-drift channel, at 3/70. **That warning is now confirmed at scale: 54 of 96 on time-varying carriers.** The risk has changed shape — it is no longer overclaiming an unmeasured capability but **failing to state a measured limitation**, and a fourth trap is now the live one: (4) presenting the three-outcome guarantee without the static-carrier qualifier, which lets a reader infer a payload guarantee the measurement contradicts. |

## 7. FEC identification

| Field | Content |
|---|---|
| **SPACE REQUIREMENT** | Identify the channel code blindly: CCSDS convolutional r=1/2 K=7 (G2-first), Reed-Solomon, concatenated RS+conv, LDPC (TC and TM families), turbo on legacy links. |
| **CURRENT CAPABILITY** | Dual-code syndrome sign test over `blind_id.CODE_CATALOGUE` with exact binomial p-values; RS (DVB 204/188 tables); CCSDS concatenated chain; TC-LDPC (128,64) with H·Gᵀ = 0 and rank verified at import — CODE. BENCH-V2 sealed: continuous **K7 16/16** at Es/N0 ≥ 6 dB; **CCSDS concatenated 10/12** full decodes at ≥ 9 dB (11/12 answered without a wrong claim); **TC-LDPC CLTU 8/8** at ≥ 6 dB; **framed RS 5/6** at ≥ 9 dB. K3/K5 are exercised only in **burst** families at recall **0.00–0.60** by interleaver type — there is no continuous K3/K5 criterion. NULLSET: correct K7/K5/K3 = 61/37/31 of 150 each. |
| **SPACE EXTENSION** | None to the inference. A CCSDS *profile view* interpreting the accepted structure in standards terms is presentation-only. |
| **STATUS** | **EXISTING** for K7 / RS / concatenated / TC-LDPC at bench conditions · **PARTIALLY SUPPORTED** for K3/K5 (burst, recall 0.00–0.60) · **NOT ESTABLISHED** (not implemented) for TM block-LDPC (8161/8144, k=1024 family) and turbo. |
| **EXPERIMENT REQUIRED** | D5 — does a frequency trajectory push the true (code, interleaver) hypothesis out of the significant set? |
| **EVIDENCE REQUIRED** | D5: rank and corrected p-value of the true hypothesis vs severity; count of cells where truth leaves the significant set. |
| **FALSE-CLAIM RISK** | **Medium.** "CCSDS coding supported" is defensible *within the searched catalogue* and indefensible as a general statement — TM block-LDPC and turbo are simply absent. The out-of-domain ledger must always ship with the claim. |

## 8. Interleaver identification

| Field | Content |
|---|---|
| **SPACE REQUIREMENT** | Recover the interleaver blindly, since a wrong interleaver destroys the payload while potentially satisfying parity checks. |
| **CURRENT CAPABILITY** | All four types searched by default: block, diagonal, Forney convolutional, LTE QPP (`interleavers.TYPES`, `QPP_MAX_K = 384`, `MIN_CODED = 32`) — CODE. Structural coverage rule (`BL_DELTA_SYMBOLS = 1.7`) rejects hypotheses explaining too few symbols. Adding all four types moved wrong-structure accepts from 2/225 (block only) to **0/225**, with BENCH-V1 30/30 and train 63/100 unchanged. BENCH-V2: burst block-interleaver recall 6/12 at Es/N0 ≥ 12 dB (criterion PASS). |
| **SPACE EXTENSION** | None. CCSDS interleaving depth I is already a parameter of the concatenated generator. |
| **STATUS** | **EXISTING**. |
| **EXPERIMENT REQUIRED** | Covered inside D5 (the hypothesis is the (code, interleaver) pair). |
| **EVIDENCE REQUIRED** | D5, plus SPACE-BENCH family I (adversarial): a plausible wrong interleaver must be refused, and any escape documented as a gate failure with a proposed corrective gate. |
| **FALSE-CLAIM RISK** | **Low-Medium.** Bound to state: ≤ 384-bit QPP, and blocks ≤ 32 bits are *unprovable in domain* (~10 checks ⇒ best attainable p ≥ 2⁻¹⁰, above the bar) — which is a correctness property, not a defect. |

## 9. Frame synchronization

| Field | Content |
|---|---|
| **SPACE REQUIREMENT** | Find frame boundaries via CCSDS ASMs, or blindly when the frame format is unknown. |
| **CURRENT CAPABILITY** | CCSDS ASM `0x1ACFFC1D` (32-bit) and `0x034776C7272895B0` (64-bit LDPC stream) from `references/ccsds_constants.json`; **plus blind** constant-field sync over `BLIND_WIDTHS = (16, 24, 32, 48, 64)`, exact binomial with Bonferroni over the declared period domain; `MIN_FRAMES = 2`, structural check `FRAME_PRESENT = 0.75` (marker visible in ≥ 75% of frames); polarity and runner-up margin reported — CODE, `tests/test_catalogue.py`, `tests/test_families.py`. BENCH-V2: non-catalogue framed streams reported SIGNAL_NO_CODE **with the true frame period** 5/10 (criterion PASS). |
| **SPACE EXTENSION** | None to inference. |
| **STATUS** | **EXISTING** — and the blind path is an ICHNOVA capability rather than a CCSDS one, which is the more interesting claim. |
| **EXPERIMENT REQUIRED** | None of its own; observed throughout families A–E. |
| **EVIDENCE REQUIRED** | Satisfied — BENCH-V2 F3 family. |
| **FALSE-CLAIM RISK** | **Low.** |

## 10. Telemetry structure

| Field | Content |
|---|---|
| **SPACE REQUIREMENT** | Interpret frame contents: transfer-frame fields (CCSDS 132.0), space packets (133.0), counters, de-randomization. |
| **CURRENT CAPABILITY** | Frame **map**: header columns proven constant or alternating across frames by exact binomial test with Bonferroni over columns; counter-field detection; undetermined columns reported **together with the number of frames a decision would need** — CODE, `framing.py`. De-randomization for `tm_255`, `tm_131071`, `tc_btg`, each reproducing the standards-printed first 40 bits (`tests/test_catalogue.py`). |
| **SPACE EXTENSION** | **EXTENSION**: a CCSDS profile view interpreting an accepted frame map in 132.0 terms — presentation only, a pure function over the evidence pack, **no new inference**. |
| **STATUS** | **PARTIAL EXISTING** (structural frame map + randomizers) · **NOT SUPPORTED** for 132.0 *semantic* field interpretation and 133.0 space-packet parsing — no packet parsing exists anywhere in the code. |
| **EXPERIMENT REQUIRED** | None (it is a presentation function). Its test is that the ledger matches as-run diagnostics and that the out-of-domain list is complete. |
| **EVIDENCE REQUIRED** | Unit test: the profile view over an accepted frame map claims nothing the frame map does not establish. |
| **FALSE-CLAIM RISK** | **HIGH — the subtlest row here.** A structural frame map rendered in CCSDS vocabulary *looks* like semantic telemetry decoding and is not. The mandatory disclaimer ("not a CCSDS-certified implementation"; fields named, not interpreted) is load-bearing, not boilerplate. |

## 11. Low-SNR robustness

| Field | Content |
|---|---|
| **SPACE REQUIREMENT** | Behave honestly as Es/N0 falls — space links are routinely near threshold. |
| **CURRENT CAPABILITY** | Family-wise error control: per-hypothesis bar p ≤ ALPHA·weight/M with `ALPHA = 0.01` and `FAMILY_WEIGHTS = {F1 0.50, F2 0.10, F3 0.20, F4 0.20}` summing to 1, so P(any false structural claim on a file) ≤ α by the union bound. Evidence-strength floors: `PM_FLOOR = 0.926` (soft Viterbi path metric), `F2_AGREEMENT_FLOOR = 0.61` (parity-check agreement — an idle carrier reaching p = 10⁻¹¹ at 59% agreement is correctly refused) — CODE. BENCH-V2: 207 refusals of 430; **0/120** false accepts (95% Wilson UB 3.10%); wrong structure/payload **3/310 = 0.97%** (UB 2.81%). NULLSET **0/900**, **0/450**. |
| **SPACE EXTENSION** | None to the mechanism. SPACE-BENCH family B sweeps *below* the sealed coded-family floor (4–6 dB). |
| **STATUS** | **EXISTING** — this is the project's best-evidenced property. |
| **EXPERIMENT REQUIRED** | SPACE-BENCH family B; and D6/D7 in combination with a trajectory (family E). |
| **EVIDENCE REQUIRED** | 0 false decodes across the sweep, with every refusal carrying a measured sufficiency reason. |
| **FALSE-CLAIM RISK** | **Low.** One discipline note: the 0/120 and 0/900 figures are *dataset-bounded* and must always be quoted with their n and their Wilson bound, never as "zero false accepts" unqualified. |

## 12. Fading

| Field | Content |
|---|---|
| **SPACE REQUIREMENT** | Survive or honestly refuse under fading — ionospheric scintillation, multipath at low elevation, polarization mismatch. |
| **CURRENT CAPABILITY** | `rician` block-flat-fading channel class, K ∈ [6, 14] dB, fade block ∈ {64, 128, 256} samples — CODE, `bench2_gen.apply_channel`. BENCH-V2 `rician`: 46 files, **0** wrong claims, recall 9/27 on catalogue classes. |
| **SPACE EXTENSION** | SPACE-BENCH family F re-runs it in the space namespace with fade-block metadata preserved in evidence. |
| **STATUS** | **EXISTING** as a bench impairment · **NOT ESTABLISHED** as a model of real space-link fading (block-flat Rician is not scintillation; no ionospheric model exists in this project). |
| **EXPERIMENT REQUIRED** | Family F — a re-measurement, not new physics. Lower priority than D. |
| **EVIDENCE REQUIRED** | 0 false decodes during fade blocks; fade metadata in the evidence pack. |
| **FALSE-CLAIM RISK** | **Medium.** "Validated under fading" would imply a physical channel model this project does not have. The honest phrasing is "under the bench Rician block-flat class". |

## 13. Timing error

| Field | Content |
|---|---|
| **SPACE REQUIREMENT** | Tolerate symbol-timing offset and clock drift. |
| **CURRENT CAPABILITY** | `timing` channel class, fractional delay τ ~ U(−0.5, +0.5) symbol; matched-filter front ends per sps candidate; serial-dependence gate `SERIAL_AGREEMENT_MAX = 0.60` (a 2× oversampled front end agrees on ~75% of neighbouring pairs, 3× on ~83%, while genuinely framed data biases the rate by only a few percent — a declared receiver spec with a physical basis, not a fitted value) — CODE. BENCH-V2 `timing`: 88 files, **0** wrong claims, recall 20/65. |
| **SPACE EXTENSION** | SPACE-BENCH family G. |
| **STATUS** | **EXISTING** for static fractional offset · **NOT ESTABLISHED** for *time-varying* timing (clock drift over a pass — the timing analogue of Doppler, and genuinely unmeasured). |
| **EXPERIMENT REQUIRED** | Family G (static, ≥ 90% decodes expected). Time-varying timing is **deliberately out of scope** for this phase. |
| **EVIDENCE REQUIRED** | Family G recall; 0 wrong payloads. |
| **FALSE-CLAIM RISK** | **Low-Medium.** Do not let "timing offset handled" imply symbol-clock drift over a pass. |

## 14. Evidence receipts

| Field | Content |
|---|---|
| **SPACE REQUIREMENT** | A third party must be able to re-derive the decision without trusting the system that produced it. |
| **CURRENT CAPABILITY** | SHA-256 **hash-chained** receipts (`src/receipt.py`): each entry carries `prev_hash`, canonical JSON serialisation, `verify_receipt` / `verify_chain` recomputing every hash independently of the module's own bookkeeping; chain-lock against forked ledgers. Verified by CLI (`server/verify_receipt.py`) **and** in-browser (`frontend/src/lib/receipt.ts`), demonstrated against a real tamper — CODE. Honest limitation stated in the source: receipts are **not signed** (no safe key custody in a prototype), so they are tamper-**evident**, not tamper-**proof** against a party who can rewrite the whole chain. |
| **SPACE EXTENSION** | **EXTENSION**: a namespaced **LINK EVIDENCE** section carrying the measured carrier trajectory (per-block estimates, or fitted parameters *plus residuals*), the static-vs-time-varying classification with its declared rule, and `SIMULATED` provenance **inside** the hashed content. Additive only; chain semantics unchanged. |
| **STATUS** | **EXISTING** for the chain and verifiers · **NEW** for the LINK EVIDENCE section (D8 — nothing carries a trajectory today). |
| **EXPERIMENT REQUIRED** | D8: does the receipt preserve enough for an independent party to re-derive D1/D2? |
| **EVIDENCE REQUIRED** | Chain regression (existing receipts verify byte-for-byte); round-trip through the CLI verifier; tamper test on a trajectory value fails verification; a SIMULATED run mechanically distinguishable from a live one. |
| **FALSE-CLAIM RISK** | **Low-Medium.** Never upgrade "tamper-evident, unsigned" to "cryptographically signed". Store measurements and residuals, not fitted curves — a fitted trajectory the reader cannot check is decoration. |

## 15. Operator workflow

| Field | Content |
|---|---|
| **SPACE REQUIREMENT** | An analyst must be able to read the evidence, see what was refused and why, and export the package. |
| **CURRENT CAPABILITY** | A working operator console — `frontend/src/pages/` (Analysis, Command, Monitor, Review, Reports, Lab, Incidents, Intelligence, Genome) with `components/evidence.tsx` renderers, capture-gate and data-quality components, verdict-first layout, quality-beside-verdict, provenance tags, receipt panel — CODE. Sufficiency reporting converts a failing statistic into what capture would settle it: `ACHIEVABLE` (with how much more signal) or `IMPOSSIBLE_IN_DOMAIN` (`src/sufficiency.py`). |
| **SPACE EXTENSION** | **EXTENSION (P1, gated)**: a Telemetry Forensics view (CAPTURE / LINK / CODING / FRAME / DECISION / WHY) reusing existing evidence components and adding the LINK section. |
| **STATUS** | **EXISTING** for the general workflow · **NOT BUILT** for any space-specific screen. |
| **EXPERIMENT REQUIRED** | None — but it is **gated behind P0**: no space screen may exist before the evidence it would display exists. |
| **EVIDENCE REQUIRED** | Every value on a space screen traceable to a field in the evidence pack; no arbitrary confidence percentages anywhere. |
| **FALSE-CLAIM RISK** | **Medium.** A polished space console reads as operational maturity. Labels must render **from data** (provenance flags), never from copy that can drift out of sync with the evidence. |

## 16. Mission replay

| Field | Content |
|---|---|
| **SPACE REQUIREMENT** | Show a pass unfolding: evidence accumulating, a verdict forming or being refused. |
| **CURRENT CAPABILITY** | **None.** No replay exists. The *raw material* exists: the evidence pack already orders detection → sps → modulation → CFO → FEC → frame → verdict, which is the engine's own pipeline order, so a projection onto simulated wall-clock is a pure function over an existing result. |
| **SPACE EXTENSION** | **SIMULATED** replay of one real engine run, with progressive masking. P1, gated. |
| **STATUS** | **NOT BUILT · SIMULATED when built.** |
| **EXPERIMENT REQUIRED** | None (it displays, it does not infer). Explicitly **not** to be built in this phase. |
| **EVIDENCE REQUIRED** | Projection unit tests; two runs replayed — one success **and one degradation/refusal**, the refusal shown as prominently as a decode. |
| **FALSE-CLAIM RISK** | **HIGH.** This is the feature most likely to become a lie: a replaying timeline over a map reads as live satellite tracking. Mandatory on-screen `SIMULATED` banner and in-package provenance. No orbital mechanics, no tracker, no 3D globe — deliberately deferred until D1–D8 pass. |

## 17. CCSDS-related capabilities (summary — full ledger in CCSDS_TELEMETRY_PROFILE.md)

| Field | Content |
|---|---|
| **SPACE REQUIREMENT** | Alignment with CCSDS 131.0-B-5 (TM sync and channel coding) and neighbours (132.0, 133.0, 231.0, 401.0). |
| **CURRENT CAPABILITY** | **SUPPORTED**: ASM 32/64-bit; conv r=1/2 K=7 G2-first (16/16); RS; concatenated RS+conv (10/12 full, 11/12 not-wrong); TC-LDPC CLTU (8/8); TM 255 / TM 131071 / TC BTG randomizers, each standards-verified. **PARTIALLY SUPPORTED**: transfer-frame *structure* (map, not semantics); CLTU/TC framing (chain decoded, full 231.0 start-sequence/tail semantics not claimed); modulation assumptions (BPSK/QPSK only); conv K3/K5 (burst, 0.00–0.60). **NOT SUPPORTED**: TM block-LDPC (8161/8144, k=1024 family); turbo; space-packet protocol 133.0; GMSK; PCM/PSK/PM carriers. |
| **SPACE EXTENSION** | The assumption ledger + profile view (presentation). |
| **STATUS** | **EXISTING within the searched domain · NOT SUPPORTED outside it.** Never a bare "CCSDS support". |
| **EXPERIMENT REQUIRED** | None new; the honest framing is that the searched subset is *already* sealed-validated at bench conditions, and the rest is printed as out-of-domain. |
| **EVIDENCE REQUIRED** | The out-of-domain ledger ships with every CCSDS claim, showing the operator what the decode did **not** rule out. |
| **FALSE-CLAIM RISK** | **HIGH.** "CCSDS-compliant" and "CCSDS-certified" are both false. The defensible sentence is: *blind identification of CCSDS-shaped structure within a bounded, published catalogue* — narrower, and actually true. |

## 18. Real spacecraft signal validation

| Field | Content |
|---|---|
| **SPACE REQUIREMENT** | At least one genuine spacecraft downlink analysed end-to-end. |
| **CURRENT CAPABILITY** | **None for spacecraft.** Real-signal validation to date is entirely **terrestrial** and genuinely strong on its own terms — REALSIG, `tests/test_realsig.py`: JJY 40 kHz DECODED (0/120 symbols disagree, p = 10⁻³²·³, GPS agreement +1.9 ms), DCF77 (+4.7 ms), MSF (+3.6 ms), WWV (+23.4 ms); **WWVB SIGNAL_NO_CODE — WWVB structure significant at p = 10⁻⁴·⁷ but the time refused** because no digit reached 100:1 (the most-likely frame read "2066-09-17", and the digit test is what prevented a false time); DDH47 RTTY decoded to text stating its own callsign and frequency (p = 10⁻²⁴¹); AIR Chennai 720 kHz SIGNAL_NO_CODE with 5/5 carriers matched to the official transmitter list. |
| **SPACE EXTENSION** | P2: one legal amateur LEO downlink capture through the whole chain, published as-is whatever the outcome. |
| **STATUS** | **NOT ESTABLISHED.** No real spacecraft recording exists in this project. |
| **EXPERIMENT REQUIRED** | A real capture attempt — hardware/logistics-bound, explicitly **not** part of this phase. |
| **EVIDENCE REQUIRED** | Full pipeline + receipt on a real capture, with conservative framing: **one capture is not validation**. |
| **FALSE-CLAIM RISK** | **HIGHEST, and the easiest to commit by accident.** "Validated on spacecraft telemetry" is forbidden outright. The WWVB refusal is the most valuable single item in the real-signal record and should be presented as such: the system had a significant signal, formed a most-likely answer, and refused to state it. |

---

## 19. Reviewer summary

**Established and space-relevant (EXISTING, bench- or real-signal-evidenced):** RF capture, signal qualification, BPSK/QPSK modulation inference, integer-sps symbol-rate inference, static CFO, FEC identification for K7/RS/concatenated/TC-LDPC, all four interleaver types, frame synchronization (ASM + blind), low-SNR refusal discipline, hash-chained receipts, operator workflow.

**Measured and failed (the one item that has moved):** time-varying CFO / Doppler *(row 6)* — no longer an open question but a **measured limitation**: 54 wrong payloads in 96 treated captures, 0 in 96 controls, `reports/space/DOPPLER_EXPERIMENT_RESULTS.md`.

**Not established as a space-link capability (the honest gaps):** trajectory measurement, static-vs-time-varying classification and trajectory-in-receipt *(row 6, D1/D2/D8 — no longer blocked on a read-out: it was approved and delivered 2026-09-27, and `TRACK_READOUT_RESULTS.md` measured the shipped tracker as a piecewise-constant phase estimator with no trajectory model, which **confirms** these three as NOT ESTABLISHED. The engine publishes a scalar unwrap margin, never a trajectory)*, real spacecraft validation *(row 18)*, TM block-LDPC and turbo, 132.0/133.0 semantics, higher-order and continuous-phase modulations, fading as a physical channel model, time-varying timing.

**Not built:** space-specific UI, mission replay, telemetry forensics view, CCSDS profile view, assumption ledger, trajectory read-out and the LINK EVIDENCE receipt section.

**The one sentence this matrix authorises today:**

> ICHNOVA is an evidence-first ground-segment RF analysis layer whose blind-inference core and refusal discipline are sealed-benchmark validated at bench conditions (430-file BENCH-V2, 9/9 pre-registered criteria, 0/120 false accepts on non-catalogue classes; 0/900 on an independent 1,350-file null set), and whose decode verdict is **bounded to a carrier that is static within the capture** — measured 2026-09-25 on 192 controlled synthetic vectors, it publishes a wrong payload beneath a true structural claim in **54 of 96 time-varying-carrier captures** and in **0 of 96 static ones** (DOPPLER_EXPERIMENT_RESULTS.md), so **spacecraft-link Doppler operation is a measured limitation, not an open question**.

Anything stronger fails the firewall's one-sentence test: *"would this still be true if the reader re-ran every measurement it rests on?"*

**END OF SPACE EVIDENCE MATRIX**
