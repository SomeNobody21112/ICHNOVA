# SPACE_IMPLEMENTATION_GATE
**ICHNOVA · SIH26147 — the gate that must be satisfied before any production code changes for the space extension**
**Status: GATE DOCUMENT (2026-09-25). Until every §7 condition holds, no production file is modified.**
Companion documents: SPACE_ENGINEERING_ROADMAP.md (what/when), SPACE_BENCH_SPECIFICATION.md (how it will be judged), SPACE_CLAIM_FIREWALL.md (what may be said).

---

## 1. What should be built (and why)

**P0 sequence only, in order:**
1. **Doppler trajectory generator** (`pass` impairment class) — because no space claim is testable without the defining space impairment; all neighbouring channel machinery is validated and reused (FACT).
2. **SPACE-BENCH generator + criteria file + sealed run** — because the entire space positioning is *conditional on benchmark validation* (POSITIONING §2); the criteria are already pre-registered in the spec, before any vector exists.
3. **Carrier-trajectory evidence extraction** (read-out of the existing tracked front end's per-block state) + **static-vs-time-varying classification** (declared rule) — because D1–D8 must be answered with measurements, and the receipt must carry them.

Why in this order: each step's output is the next step's input; nothing in the sequence changes engine decision logic; everything else (profile view, replay, forensics, receipts UI) consumes P0 evidence and is gated behind it.

## 2. Exact files likely affected (P0)

| File | Change | Nature |
|---|---|---|
| `eval/bench2_gen.py` (or a sibling `eval/spacebench_gen.py`) | add `pass` trajectory class / new generator reusing validated classes | additive; existing classes untouched |
| `eval/spacebench.py` + `eval/spacebench_criteria.json` (new) | SPACE-BENCH runner + pre-registered criteria | new files; bench2.py and its criteria untouched |
| `src/pipeline.py` | expose per-block phase/frequency from `_track_phase` in `diagnostics` (read-out only) | additive key; **no threshold, family, or gate changes** |
| `src/sufficiency.py` (or sibling) | classify trajectory; report in sufficiency output | additive |
| `src/receipt.py` / `server/evidence.py` | LINK EVIDENCE section in pack/receipt (namespaced) | additive; chain semantics unchanged |
| `tests/test_spacebench.py`, `tests/test_trajectory.py` (new) | generator + read-out + classification tests | new files |

Frontend files are **not** in P0. (P1 touches `frontend/src/components/evidence.tsx` renderers and one new page; that is a separate gate review.)

## 3. Tests required before merge

1. Trajectory generator: continuity, bounds vs sourced magnitudes, determinism under seed; static/linear regressions unchanged (existing bench2 outputs byte-stable).
2. Trajectory read-out: extracted trajectory vs injected truth within declared tolerance on clean controls; no behaviour change when tracking is inactive (< TRACK_MIN_SYMBOLS).
3. Classification: 100% on static/linear/pass synthetic controls (it is a declared rule, tested as such).
4. Receipt: existing receipt tests pass byte-for-byte; new section round-trips; tamper on trajectory fails verification.
5. Full suite: `python -m pytest -q tests` → **178 passing, plus the new tests** — the existing 178 must not change count or outcome.

## 4. Benchmark required

- SPACE-BENCH sealed run per the pre-registered spec (one run, logged, results published whatever they say) — *before* any space capability sentence enters UI or documents.
- Existing sealed benchmark evidence must remain **unchanged**, and the two sealed benchmarks must not be conflated:
  - **bench-v1** provides the documented **30/30** result — `data/sealed`, 30 files, run by `sealed_test.py`, 0 false accepts, a *regression tripwire and not a held-out set* (Constitution §18, `SIH26147_CURRENT_STATE.md` — FACT).
  - **bench-v2** provides the **430-file sealed run with 9/9 pre-registered criteria passed** — `data/bench2/sealed`, seeds 400000–400429, criteria `eval/bench2_criteria.json`, the single logged run in `eval/bench2_access_log.jsonl` (`reports/BENCH2_SEALED_REPORT.md` — FACT).
  - Both are re-run as regressions. Neither dataset, its seeds, its criteria nor its thresholds may change. There is no such measurement as "bench-v2 30/30".

## 5. What existing behaviour must remain unchanged (invariants)

1. Three-outcome model semantics (DECODED / SIGNAL_NO_CODE / UNKNOWN) — unchanged.
2. Family-wise error control: ALPHA 0.01, family weights, Bonferroni bars — unchanged.
3. Structural checks and their calibrated constants (BL_DELTA_SYMBOLS 1.7, PM_FLOOR 0.926, F2_AGREEMENT_FLOOR 0.61, SERIAL_AGREEMENT_MAX 0.60) — unchanged.
4. `SEARCH_HIGHER_MODULATIONS = False` — unchanged.
5. bench-v2 data, seeds, criteria, results — untouched.
6. Receipt chain semantics and verifier compatibility — unchanged (additive sections only).
7. One-writer results protection; source freshness; auth/RBAC — untouched.
8. Quality-beside-verdict rule ("a bad capture explains a refusal, it does not create one") — unchanged.
9. Historical documents — untouched.

## 6. Rollback strategy

- All P0 changes are additive new files or additive keys/sections; rollback = revert the merge commit; no data migration, no state to unwind.
- SPACE-BENCH lives in its own directory; deleting it cannot affect bench-v2.
- Diagnostics additions are ignored by all existing consumers (unknown keys), verified by the unchanged frontend build.
- If the sealed run fails: the results are published as they are (firewall §3.10); engineering reopens only per the Constitution STOP rule; no partial rollbacks that leave tuned remnants.

## 7. Gate conditions (all must hold before code)

- [ ] This document reviewed alongside ROADMAP and BENCH spec.
- [ ] SPACE-BENCH criteria committed **before** vector generation (pre-registration).
- [ ] §2 file list confirmed against the then-current tree (no file renamed/moved).
- [ ] §3 test plan agreed; §5 invariants copied into the PR template/checklist.
- [ ] Claim wording for any pre-merge demo approved against SPACE_CLAIM_FIREWALL.md.

## 8. Risks

| Risk | Mitigation |
|---|---|
| Bench criteria quietly adjusted after seeing results | Pre-registration discipline + dated criteria-file revisions only before SEALED exists (bench-v2 precedent — FACT) |
| Trajectory read-out subtly perturbs analyses | Read-out is side-effect-free; regression suite proves byte-stable engine output |
| Space labels drift from reality in UI | Labels render from data (firewall §5); one source of truth |
| Scope creep into "mission control" aesthetics | ROADMAP DO-NOT-BUILD list + this gate's file scope |
| Overclaim in excitement post-results | Demo script's hard requirements + firewall one-sentence test |

## 9. GATE REVIEW — 2026-09-25 (recorded, not retro-fitted)

First reviewed against branch `sih-readiness`, commit `3919546`, clean working tree, `python -m pytest -q` → **178 passed**. Re-verified 2026-09-27: **252 passed**, clean tree, the one approved production change delivered (see 9.3).

### 9.1 §7 conditions, as assessed

| Condition | State |
|---|---|
| Reviewed alongside ROADMAP and BENCH spec | **MET** — all three read in full, plus SPACE_EVIDENCE_MATRIX.md (now written; it was the package's one missing mandatory artefact). |
| Criteria committed **before** vector generation | **MET for the Doppler experiment** — `eval/space_doppler_criteria.json` is written and committed before any vector exists. **NOT MET for SPACE-BENCH families A–J**, which are therefore not generated. |
| §2 file list confirmed against the current tree | **MET** — `eval/bench2_gen.py`, `eval/bench2.py`, `eval/bench2_criteria.json`, `src/pipeline.py`, `src/sufficiency.py`, `src/receipt.py`, `server/evidence.py` all present, none renamed or moved. |
| §3 test plan agreed; §5 invariants in the checklist | **MET for the subset being built** (see §9.2); the full §3 plan applies only to the blocked portion. |
| Demo claim wording approved | **N/A** — no demo material is produced by this phase. |

### 9.2 Decision: the P0 experiment is **split**, and only the production-free half proceeds

The experiment's eight questions do not all cost the same. They divide cleanly:

**PROCEEDS — no production file is touched.** D3–D7 (modulation, symbol-rate and code consistency under trajectory; false decodes; refusal migration) are answered entirely by *calling the existing engine on new synthetic vectors and scoring its published output*. This needs a new isolated generator + runner + pre-registered criteria + tests, and nothing else. Q8 of the measurement plan ("does the existing tracking help?") is answerable **behaviourally** — by comparing captures below and above `TRACK_MIN_SYMBOLS = 512` — with no read-out of internal state.

**BLOCKED — requires a production change, therefore STOPPED and documented here rather than made.** D1 (trajectory RMSE), D2 (static-vs-time-varying classification) and D8 (trajectory in the receipt) all depend on reading per-block phase estimates out of `pipeline._track_phase`, which today discards them after equalisation. Per the file-scope rule, that change is **not** made silently. It is recorded in §9.3 for a separate, explicit review.

Rationale for splitting rather than waiting: D6 (false decodes) is the criterion that can *falsify* the space positioning, and it is exactly the half that needs no production change. Deferring the whole experiment until a production edit is approved would delay the only measurement capable of stopping the project — which is the wrong way round.

### 9.3 PRODUCTION CHANGE REQUESTED (not made) — trajectory read-out

| Field | Content |
|---|---|
| **File** | `src/pipeline.py`, function `_track_phase` (and the `diagnostics` dict assembled in `analyze_file`). |
| **Change** | Return, alongside the equalised symbol stream, the per-block unwrapped phase estimates and the chosen block length; surface them under a new `diagnostics` key (e.g. `carrier_trajectory`). Read-out only. **As delivered the key is `phase_tracking_validity`, not `carrier_trajectory`** — `TRACK_READOUT_RESULTS.md` measured that the tracker estimates a piecewise-constant phase with no trajectory model, so naming it a trajectory would have implied a capability that does not exist. |
| **Why it is needed** | D1, D2 and D8 are unanswerable without it. The data already exists inside the function; it is thrown away. |
| **Why it is not being made now** | It touches a production engine file. The file-scope rule requires a STOP and an explicit record rather than a quiet edit bundled into an experiment. |
| **Risk assessment** | Low but **not zero**. `_track_phase`'s return value is consumed as a symbol stream; changing its signature touches the hypothesis-enumeration path. The safe form is a separate accessor or an out-parameter, never a changed return type. |
| **Invariants it must preserve** | All of §5. Specifically: identical verdicts on BENCH-V1 (30/30) and on the existing 178 tests, byte-stable diagnostics for every key that exists today, and no change to M in any family (a read-out adds no hypotheses). |
| **Test required before merge** | Extracted trajectory vs injected truth within a declared tolerance on clean controls; no behavioural change when tracking is inactive (< `TRACK_MIN_SYMBOLS`); full suite unchanged at 178 + new tests. |
| **Status** | **APPROVED AND DELIVERED 2026-09-27** (`SPACE-TRACK-READOUT-01`, `SPACE-TRACK-VALIDITY-01`). Implemented as an optional write-only `_trace` on `_track_phase` plus two `diagnostics` keys — `src/pipeline.py` +61/−3, no change to tracking, unwrap, thresholds, F4, candidate generation, acceptance or refusal. Invariants held: verdicts identical on all 192 sealed Doppler captures, full suite green (247), read-out deterministic, and corrupting it leaves status, code, payload, M and front count identical. **D1, D2 and D8 nevertheless remain NOT ESTABLISHED**, now on measurement rather than on a missing read-out: the tracker was measured to be a piecewise-constant phase estimator with **no trajectory model**. **The rule stands unchanged — no document may imply ICHNOVA measures or reports a carrier trajectory.** What is published is a scalar unwrap margin, which is not a trajectory. |

### 9.4 What this phase does not do

SPACE-BENCH families A–J are **not** generated: family A–E criteria are specified in prose in SPACE_BENCH_SPECIFICATION.md but have never been committed as a machine-checkable criteria file, and pre-registration means the file comes first. The Doppler experiment below is the narrower, fully pre-registered thing that can be run honestly today. Whether SPACE-BENCH proceeds is a decision for after its results.

Also not done, deliberately: no UI, no replay, no forensics view, no orbital mechanics, no tracker, no new modulation, no threshold change, no dependency added.

## 10. RESULT — 2026-09-25, the same day (the gate's decision, executed)

§9.2's PROCEEDS half was built and run: `eval/space_doppler.py` (harness), `tests/test_space_doppler.py` (7 additive tests), 192 vectors in `data/space_bench/doppler`, one run, published in **`reports/space/DOPPLER_EXPERIMENT_RESULTS.md`**.

**Criterion 1 failed: 54 false decodes in 192 captures (54 of 96 treated, 0 of 96 controls).** The STOP rule is in force — SPACE-BENCH families D/E do not proceed, the orbital pass model stays deferred, and no threshold was touched. §5's invariants all held: 185 tests passed (178 + 7 additive, none changed), bench-v1 sealed 30/30 with 0 false accepts, no file under `src/` or `server/` edited, and the dataset regenerates byte-identically.

Two production changes are now **requested and unapproved** (DOPPLER_EXPERIMENT_RESULTS.md §8): **R1** a payload-reliability gate that would downgrade an untrustworthy payload to `SIGNAL_NO_CODE`, and **R2** a drift-aware front end. They join §9.3's trajectory read-out in the queue. R1 is the one worth approving first — it converts wrong answers into refusals, which is what the design exists to do — and it is also the one that could cost static-carrier recall, so it is measured against bench-v1, bench-v2 and the full suite before it is considered, not after.

**END OF IMPLEMENTATION GATE**
