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
- bench-v2 re-run as regression: sealed 30/30 and the bench-v2 criteria must be **unchanged** (no tuning, no drift).

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

**END OF IMPLEMENTATION GATE**
