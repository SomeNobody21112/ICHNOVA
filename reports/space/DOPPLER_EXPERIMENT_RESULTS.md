# DOPPLER_EXPERIMENT_RESULTS
**ICHNOVA · SIH26147 — SPACE-DOPPLER, the controlled time-varying-carrier experiment: measured result**
**Status: RUN AND PUBLISHED AS-IS (2026-09-25). The headline criterion FAILED. The STOP rule is in force.**

> **The result in one sentence.** On a carrier whose frequency varies during the capture, the engine published a **wrong payload under a true structural claim in 54 of 96 treated captures (56.3%)**, while the same engine on a static or zero carrier was wrong **0 times in 96** — so ICHNOVA's decode verdict is **bounded to a carrier that is static within the capture**, and no document may state or imply otherwise.

No threshold, family weight or engine constant was changed in response to this result. No production file was edited. Every threshold in the pre-registered criteria file is exactly what it was before the first vector existed; the only post-run edit to that file is a `revision_history` entry (see §1 for both hashes).

---

## 1. Provenance

| Field | Value |
|---|---|
| Commit | `3919546` (branch `sih-readiness`; working tree also carried the uncommitted space-report edits listed in §9) |
| Pre-registered criteria | `eval/space_doppler_criteria.json` — written **before** the generator existed. Sha256 **as run**: `7e287774fc40b28c0621d46bce3e194ac7654873b9695772718dbbf78104e446`. Sha256 **now**: `8bebb4dd5dabe7c01c8ea4957fae4c8d51d8fcef48ff1e7ca4cbb9efb6cd2e5e` — the file was appended to *after* the run with one `revision_history` entry recording the run and the §4.1 correction, and re-serialised (2-space indent). **Every criterion, metric and threshold is unchanged**; the two hashes differ by that entry and the whitespace alone, and both are recorded here so the change is auditable rather than invisible |
| Harness | `eval/space_doppler.py` (generator + runner + report; no production file touched) |
| Dataset | `data/space_bench/doppler`, 192 files, 1.6 M samples, seeds 500000–500191 |
| Manifest | `eval/space_doppler_manifest.json`, manifest sha256 `f9823ef5a45c97f106825ac51768b9412db5c65460d3574cd06b813627fe50ea` |
| Rows | `results/space_doppler_rows.jsonl` (192 rows, one per vector) |
| Run | 2026-09-25T16:34Z, single run, 192 files in 45 s, mean 1.35 s/file, max 3.02 s |
| Tests | `python -m pytest -q` → **185 passed** (178 before + 7 new, additive; no existing test changed outcome) |
| bench-v1 tripwire | `python sealed_test.py` → **30/30, 0 false accepts**, unchanged |
| Determinism | `python eval/space_doppler.py verify` → **192/192 files byte-identical** on regeneration |

Independence: bench-v1 (`data/sealed`) and bench-v2 (`data/bench2`) datasets, seeds, criteria and thresholds were neither read nor written by this experiment. It lives in its own namespace.

## 2. What was varied, and what it cost

One transmitter throughout: continuous rate-½ K=7 convolutional stream, BPSK, `sps ∈ {4,6,8}`, `β ∈ [0.2,0.5]`, chosen because it is the best-evidenced family in bench-v2 (continuous K7 stream recall measured 16/16 at Es/N0 ≥ 6 dB), so a degradation is attributable to the trajectory and not to a weak baseline.

Four frequency trajectories, `peak = severity × CFO_MAX` where `CFO_MAX = 0.0125` cyc/sample is the **engine's own** static search bound:

| Class | f(t) | Role |
|---|---|---|
| `zero` | 0 | control |
| `static` | peak | control — the validated static-CFO case |
| `linear` | −peak → +peak | control 2 — bench-v2's `cfo_drift` shape |
| `pass` | peak·(2/π)·arctan(4·(2t/T−1)) | **treatment** — bounded S-curve, **CONTROLLED SYNTHETIC**, never a satellite pass |

Grid: severity ∈ {0.25, 0.5, 1.0, 2.0} × Es/N0 ∈ {12, 9, 6} dB × length ∈ {long 1200 info bits (**2412 symbols**, above `TRACK_MIN_SYMBOLS = 512`), short 200 info bits (412 symbols, below it)} × 2 reps = **192 vectors**. Severity 2.0 places the peak outside `CFO_MAX` and was pre-registered as an expected-refusal condition for every class.

**Severity context, stated so the numbers are not read as harsher or softer than they are.** The sweep is scaled to the engine's *static* search bound, not to bench-v2's drift class. The mildest treated cell (`linear`, severity 0.25) has a maximum drift rate of 3.7×10⁻⁶ cyc/sample² — about **18× bench-v2's largest `cfo_drift` rate** (±2×10⁻⁷ cyc/sample², `bench2_gen.apply_channel`). The harshest (`pass`, severity 2.0) reaches 7.5×10⁻⁵ cyc/sample². So this experiment probes a region the tracked front end was never measured in; that is the point of it, and it is also why the result is a **boundary**, not a contradiction of bench-v2.

## 3. Outcome by trajectory

`DECODED_CORRECT` = DECODED, true code family, true modulation, payload BER < 0.01. `FALSE_DECODE` = DECODED while the structure, modulation or payload is not the transmitted one (bench-v2's FALSE_ACCEPT semantics, scoring function imported verbatim). `REFUSED` = `SIGNAL_NO_CODE` or `UNKNOWN`.

| Trajectory | n | decoded correctly | refused | **false decodes** | false-decode BER range |
|---|---:|---:|---:|---:|---|
| `zero` (control) | 48 | 48 | 0 | **0** | — |
| `static` (control) | 48 | 32 | 16 | **0** | — |
| `linear` (treatment) | 48 | 6 | 15 | **27** | 0.027 – 0.490 |
| `pass` (treatment) | 48 | 5 | 16 | **27** | 0.212 – 0.495 |
| **controls** | **96** | **80** | **16** | **0** | — |
| **treatments** | **96** | **11** | **31** | **54 (56.3%)** | 0.027 – 0.495 |

All 16 control refusals are severity-2.0 `static` cells — the peak is outside the engine's declared search bound, which is the pre-registered expected-refusal condition, and the engine refused every one of them. Noise was **not** the driver: false decodes are flat across SNR (18 at 12 dB, 17 at 9 dB, 19 at 6 dB).

Full per-cell table: `python eval/space_doppler.py report`. Raw rows: `results/space_doppler_rows.jsonl`.

## 4. The nine pre-registered criteria, as measured

| # | Criterion | Required | Measured | Verdict |
|---|---|---|---|---|
| 1 | `no_false_decode_under_trajectory` | 0 | **54 of 192 (28.1% overall; 54 of 96 treated)** | **FAIL** |
| 2 | `payload_correctness_on_control_cells` | ≥ 0.80 | **24/24 (1.00)** | PASS |
| 3 | `refusal_migration_direction` | direction only (no bar) | 16 series; **54 DECODED→wrong transitions**; 10 non-monotonic cells | REPORTED |
| 4 | `modulation_consistency` | 0 wrong on DECODED | **0 of 145** (refusal-side: 40 × none, 6 × BPSK, 1 × QPSK) | PASS |
| 5 | `symbol_rate_consistency` | NOT ESTABLISHED | true sps in candidates **180/192**; accepted front end used true sps **146/192**; control reference 24/24 | REPORTED |
| 6 | `code_consistency` | NOT ESTABLISHED | true code family accepted on **145/192** | REPORTED |
| 7 | `runtime_guard` | mean ≤ 7.14 s, max ≤ 120 s | mean **1.35 s**, max **3.02 s** | PASS |
| 8 | `determinism` | exact | **192/192 byte-identical** | PASS |
| 9 | `existing_regression_unchanged` | 178 + additive; bench-v1 30/30 | **185 passed** (178 + 7 new); bench-v1 **30/30, 0 false accepts** | PASS |

Criterion 2 passing at 24/24 is what makes criterion 1's failure interpretable: the harness's own signal is a signal this engine reads perfectly when the carrier holds still, so the treated cells are measuring the trajectory and not a generator bug.

### 4.1 An error in the pre-registration, disclosed rather than corrected

Criterion 1's `basis` field claimed the bar of **0** was "INHERITED, not invented" from bench-v2. That is **not accurate**. bench-v2 has two distinct bars: `no_false_accept_on_non_catalogue_signals` (≤ 1% of *null-class* files DECODED, Wilson upper bound ≤ 5%) and `wrong_structure_or_payload_is_rare` (**≤ 2%** of *catalogue-class* files DECODED with a wrong structure or payload). These captures are catalogue-class, so the inherited bar was **≤ 2%**, not 0. The pre-registration conflated the two.

The bar was **not** changed, and the verdict does not depend on the error: 28.1% overall (56.3% on treated cells) fails the stricter bar and the true inherited ≤ 2% bar by more than an order of magnitude. The mistake is recorded here and in the criteria file's revision history — nowhere silently.

## 5. Failure record (required by `on_failure`)

The failure is systematic, not a handful of outliers, so three representative captures are recorded in full. Every figure below is the engine's own published output.

| Field | `pass_0147` | `linear_0098` | `pass_0146` |
|---|---|---|---|
| **Capture** | `data/space_bench/doppler/pass_0147.iq`, 412 symbols, seed 500147 | `linear_0098.iq`, 412 symbols, seed 500098 | `pass_0146.iq`, 412 symbols, seed 500146 |
| **Ground truth** | BPSK, sps 8, β 0.41, conv K7 continuous, Es/N0 12 dB, `pass` severity 0.25, peak 0.00313 cyc/sample, max drift 4.7×10⁻⁶ | BPSK, sps 4, β 0.30, conv K7 continuous, Es/N0 12 dB, `linear` severity 0.25, peak 0.00313, max drift 3.7×10⁻⁶ | BPSK, sps 4, β 0.45, conv K7 continuous, Es/N0 12 dB, `pass` severity 0.25, peak 0.00313, max drift 9.4×10⁻⁶ |
| **Decision** | **DECODED** `conv_k7_r12_171_133_continuous`, BPSK, sps 8, CFO −0.00175 | **DECODED** same code, BPSK, sps 4, CFO −0.00155 | **DECODED** same code, BPSK, sps 4, CFO 0.00118 |
| **Payload** | **BER 0.495** | **BER 0.365** | **BER 0.460** |
| **Wrong hypothesis** | None at the structure level — **the accepted structure is the true one.** What is wrong is the payload carried under it | same | same |
| **Evidence score** | F2 stream code **log₁₀p = −14.81** against a bar of −4.68, M = 48 | F2 **−28.04** vs bar −5.08, M = 120 | F2 **−29.71** vs bar −5.28, M = 192 |
| **Which gate failed** | **None of the four acceptance families failed.** F1/F3/F4 each fell short of their own bars and were correctly not accepted; F2 cleared its bar by 10–24 orders of magnitude. **No gate acts on payload reliability** — that is the gap; the engine computes payload-side scores and uses them only to break the polarity tie (see §10) | same | same |
| **Was refusal possible?** | **Not with today's gates.** The syndrome sign test is a statement about *code presence*, and the code genuinely is present; nothing in the accept path tests whether the Viterbi output is trustworthy. Tracked front ends: 0 (capture is below `TRACK_MIN_SYMBOLS`) | Tracked front ends: 15 of 45 — **tracking was active and did not prevent it** | Tracked front ends: 18 of 72 — same |

**This is not a misalignment artefact.** Every false-decode payload checked was re-tested against the transmitted bits over all bit offsets ±64 and both polarities: the best achievable BER equals the scored BER (at offset 0) in every case. The bits are genuinely wrong, not merely out of phase.

**The precise shape of the defect.** The structural claim is *true* and overwhelmingly supported; the payload published beneath it is *unreliable*, and the verdict carries no indication of that. The three-outcome guarantee is stated in terms of never claiming a structure that is not there — which held, **0 wrong structures out of 192** — but a reader of "DECODED, conv K7 continuous" reasonably takes the payload to be decoded too. Under a carrier that moves within the capture, it is not.

## 6. Q8 — does the existing tracking materially help? (measured behaviourally; no engine internals read)

| length | trajectory | n | decoded | refused | false | tracked front ends present |
|---|---|---:|---:|---:|---:|---|
| long (2412 sym, above 512) | `zero` | 24 | 24 | 0 | 0 | 24/24 |
| long | `static` | 24 | 18 | 6 | 0 | 24/24 |
| long | `linear` | 24 | 6 | 6 | **12** | 24/24 |
| long | `pass` | 24 | 5 | 6 | **13** | 24/24 |
| short (412 sym, below 512) | `zero` | 24 | 24 | 0 | 0 | 15/24 |
| short | `static` | 24 | 14 | 10 | 0 | 10/24 |
| short | `linear` | 24 | 0 | 9 | **15** | 14/24 |
| short | `pass` | 24 | 0 | 10 | **14** | 15/24 |

**Answer: it helps, and not enough.** Above `TRACK_MIN_SYMBOLS` the engine still decodes 11 of 48 treated captures correctly and commits 25 false decodes; below it, 0 of 48 correct and 29 false. Tracking buys back correct decodes; it does not buy back refusals, which is the property that matters. At these drift rates — 18× to 375× bench-v2's `cfo_drift` — the coherence-block front end is outside its measured envelope, exactly as §2 sets out.

## 7. What this changes in what ICHNOVA may claim

**Now measured, and it must be said in these terms:**

> ICHNOVA's decode verdict is validated for a carrier that is **static within the capture** (bench-v2, 430 files, 9/9 pre-registered criteria; bench-v1 30/30; 0/900 on an independent 1,350-file null set). Under a **time-varying carrier** — measured 2026-09-25 on 192 controlled synthetic vectors — it published a **wrong payload under a true structural claim in 54 of 96 treated captures**, with no refusal available from today's gates. Time-varying-carrier operation is therefore a **measured limitation, not an open question**.

**Forbidden from this date, in any deck, document, UI string or conversation:**
- any sentence implying ICHNOVA handles Doppler, drift, LEO passes or spacecraft links;
- any presentation of the three-outcome guarantee that lets a reader infer the *payload* is guaranteed when the verdict is DECODED, without the static-carrier qualifier;
- any use of the word "pass" for these vectors that does not carry **CONTROLLED SYNTHETIC**.

**Still true and unchanged:** every static-carrier result in the repository. This experiment did not weaken them; it found their edge. 0 wrong *structures* in 192 captures under conditions up to 375× the drift the engine was hardened for is itself a measured property of the structural test, and it is why this failure is diagnosable at all.

## 8. Decision, per the design's §4 rule

`DOPPLER_EXPERIMENT_DESIGN.md` §4: *"D6 false decode or D7 non-monotonic → STOP, document in `reports/space/DOPPLER_EXPERIMENT_RESULTS.md`, treat as the discovery it is."* Both triggered (54 false decodes; 10 non-monotonic cells). Therefore, and until an explicit decision says otherwise:

1. **SPACE-BENCH families D/E do not proceed.** The orbital pass model (`SATELLITE_PASS_REPLAY_DESIGN.md`) stays deferred — "no exceptions" is the design's own wording.
2. **No threshold is tuned.** Not `ALPHA`, not a family weight, not `CFO_MAX`, not `TRACK_MIN_SYMBOLS`.
3. **No production change is made here.** Two are now *requested* and await explicit approval, alongside the trajectory read-out already pending in `SPACE_IMPLEMENTATION_GATE.md` §9.3:

| # | Proposed change | Why | Risk |
|---|---|---|---|
| R1 | **A payload-reliability gate**: when the accepted hypothesis is a continuous stream and a re-encode consistency check on the Viterbi output (or the tracked residual phase) indicates the payload cannot be trusted, downgrade to `SIGNAL_NO_CODE` with the structure reported and the payload withheld. | This is the missing gate the failure record names. It converts a wrong answer into a refusal, which is the behaviour the whole design exists to produce. | **Not low.** It can turn currently-correct decodes into refusals. Must be measured against bench-v1 (30/30), bench-v2 (all 9 criteria) and the full suite before it is considered, and abandoned if it costs static-carrier recall. |
| R2 | **A drift-aware front end** (per-block CFO re-estimation rather than phase-only tracking). | Would recover correct decodes rather than merely refusing them. | Higher — it changes hypothesis enumeration and therefore M in every family. Strictly after R1, and only if R1's measurements are clean. |

R1 before R2, deliberately: a refusal is the honest answer and the cheap one; a correct decode under drift is the ambitious one. Neither is built today.

4. **The claim documents are updated to match this result** (§9), because the STOP rule is "documented, never tuned away" — and a limitation that is measured but not written down is the same failure as tuning it away.

## 9. Files this run created or changed

**Created:** `eval/space_doppler.py`, `eval/space_doppler_manifest.json`, `tests/test_space_doppler.py` (7 tests, additive), `data/space_bench/doppler/` (192 vectors + ground truth), `results/space_doppler_rows.jsonl`, this report.

**Changed:** `reports/space/SPACE_EVIDENCE_MATRIX.md` (row 6 and §19: time-varying CFO moves from NOT ESTABLISHED to **MEASURED LIMITATION**), `reports/space/SPACE_CLAIM_FIREWALL.md` and `reports/space/SPACE_IMPLEMENTATION_GATE.md` (pointer to this result), `eval/space_doppler_criteria.json` (revision-history entry recording §4.1 — **no threshold altered**).

**Not touched:** every file under `src/` and `server/`; bench-v1 and bench-v2 data, seeds, criteria, thresholds and manifests; every engine constant.


## 10. ADDENDUM 2026-09-25 (post-run audit; the sealed measurements above are unchanged)

An audit of the inference code after this report was written found one statement in §5 imprecise. The correction sharpens the finding rather than softening it, and it is recorded here instead of being edited away. No measured figure above changes.

**What §5 said:** "There is no gate on payload reliability."

**What is accurate:** the F2 path *does* carry payload-adjacent guards — `F2_AGREEMENT_FLOOR = 0.61` on syndrome check agreement, a decoy-tap-pattern control, and the degenerate-stream rule — and `stream.decode` *already computes* two payload-side scores: the soft `path_metric` and the hard re-encode `consistency`. **They are used only to break the polarity tie. Neither gates the verdict, and neither is published as a reliability statement.** The accurate form is therefore: *the engine already measures its own payload reliability and does not act on it.*

**Post-hoc diagnostic (not pre-registered; `results/space_doppler_diagnostic_scores.jsonl`).** Over the 145 DECODED captures — 91 correct payloads against 54 wrong:

| Score | correct: min / median | wrong: median / max | overlap |
|---|---|---|---|
| `path_metric` | 0.9983 / 0.9998 | 0.9099 / 0.9934 | **none** |
| `consistency` | 0.9878 / 0.9975 | 0.9073 / 0.9954 | 1 of 54 |
| `agreement` | 0.9444 / 0.9925 | 0.7211 / 0.9900 | 1 of 54 |

The 54 wrong payloads have agreement 0.6249–0.9900 — entirely above the existing 0.61 floor, which is why it never fired on them. The existing guards fired on 6 of 47 refusals and on 0 of 54 wrong payloads.

**This is an observation, not a result, and it licenses nothing.** It was not pre-registered; separation on one code family and 192 vectors is not a calibrated threshold; choosing a cut from this data would be the tuning the Constitution forbids; and the cost in static-carrier recall is unmeasured. What it does is make the remediation question concrete: not "invent a reliability signal" but "test, on a new pre-registered dataset, whether the signal the engine already computes generalises". That test is `DOPPLER_REMEDIATION_EXPERIMENT.md`.

Full analysis: `reports/space/DOPPLER_FAILURE_ANALYSIS.md`.

**END OF ADDENDUM**

**END OF DOPPLER EXPERIMENT RESULTS**
