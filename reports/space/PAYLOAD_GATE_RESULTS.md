# PAYLOAD_GATE_RESULTS

**ICHNOVA · SIH26147 — `SPACE-PAYLOAD-GATE-01`: request B measured. Can a wrong payload become a refusal without costing a decode that works?**

**Status: EXECUTED (2026-09-27). Read-only: the gate is applied as post-processing of the engine's own published result. No production file changed, no threshold in `src/` touched, no sealed dataset altered. Nothing is integrated.**

> **Headline — MEASURED FACT.** Yes, on this evidence base. A bar on `consistency` — a payload-side statistic the engine **already computes and publishes** — at **0.97427** loses **0 of 1,278** currently-correct decodes, converts **all 3** long-standing structural false accepts into refusals, and converts **52 of 54 (96.3 %)** sealed-Doppler wrong payloads into refusals while losing **0 of 91** correct ones.
>
> **Verdict by the pre-registered rules: SUPPORTED.** **Integration is a separate decision this experiment does not pre-approve** — the gate changes refusal behaviour, which every prior authorisation in this branch withheld.

**Labels:** **MEASURED FACT** · **ENGINEERING INTERPRETATION** · **LIMITATION OF THE EVIDENCE**

---

## 1. What request B was, and why it was blocked

`SPACE_IMPLEMENTATION_GATE.md` and `SPACE_ENGINEERING_STATUS.md` both carry request **B**: *downgrade `DECODED` → `SIGNAL_NO_CODE` on a pre-registered payload-side bar.* It has stood **BLOCKED** with one stated reason: *"may cost static-carrier recall, which must be measured first."*

That is the entire content of this experiment. It measures the cost. It does not integrate anything.

## 2. No new statistic was invented

**MEASURED FACT.** `stream_code.accepted_hypothesis.consistency` is the re-encode consistency of the payload F2 published. The engine already computes it and already publishes it; today it is used **only for polarity tie-breaking**, never as a gate. `path_metric` and `agreement` come from the same published hypothesis and are recorded alongside so that the *choice* of statistic is evidenced rather than asserted.

No score, confidence or composite was created. Nothing in `src/` was touched.

## 3. Scope — established before measuring

**MEASURED FACT.** The gate can only apply where a payload-side statistic exists, which is family **F2** (continuous stream). Of 2,002 captures analysed, **167** carry an F2-*supplied* claim:

| Population | Captures | F2-supplied claims | Outcomes |
|---|---:|---:|---|
| bench-v1 sealed | 30 | **0** | gate cannot touch this population |
| independent null set | 1,350 | **0** | gate cannot touch this population |
| bench-v2 sealed | 430 | **22** | 19 TP + **3 FALSE_ACCEPT** |
| sealed Doppler | 192 | **145** | 91 correct + **54 wrong payload** |

**Two consequences that decide the risk profile.** bench-v1's 30 decodes are all **F1 burst** claims (`conv_k7_r12_171_133`, no `_continuous` suffix) and the null set's 128 catalogue decodes carry no F2-supplied claim either — so **the gate cannot cost either population anything, by construction rather than by luck**. And every wrong payload in the sealed Doppler experiment was published by F2, so the failure this gate targets is entirely inside its scope.

**A definition that matters.** "F2-supplied" is stricter than "F2 accepted". The verdict order is F1 → F4 → F2, so F2 can accept a hypothesis that never becomes the published claim. `results/f4_margin_rows.jsonl` counts 40 captures where F2 accepted *something*; only **22** are captures where F2 actually supplied the published code. The gate is scoped to the 22, because those are the only claims it could change.

## 4. The bar, and why it is set this way

**The committed rule:** `bar = min(consistency)` over the bench-v2 F2 claims scored **correct today**. Measured: **0.97427** from 19 currently-correct claims.

**ENGINEERING INTERPRETATION — the direction is the whole point.** A bar fitted to the failures it is meant to catch is threshold tuning, and this branch rejected a carrier estimator for less. Setting the bar from the *no-regression constraint* instead means the **cost is zero by construction** on that population and the **benefit is whatever falls out**. Had the benefit been nil, the honest answer would have been that no useful bar exists.

**LIMITATION OF THE EVIDENCE, stated because it follows directly.** Because the bar is derived from the cost population, zero cost *on that population* is not an independent finding — it is arithmetic. It is an **empirical floor on the captures measured, not a guarantee for unseen captures**. The same caveat governs the F4 margin in `F4_MARGIN_RESULTS.md`.

**A declared peek.** Before this experiment was designed, the consistency distribution of the sealed Doppler set was inspected for feasibility (correct 0.9805–1.0000 vs wrong 0.8634–0.9808 on the shipped-engine arm of MECH-01). That peek is *why* the experiment was judged worth running. It means the **Doppler benefit figure below is not a blind estimate** and must not be presented as one. The bench-v2 consistency values — the ones that set the bar — were **not** inspected beforehand.

## 5. Cost — MEASURED FACT

| Population | Correct decodes today | Lost to the gate |
|---|---:|---:|
| bench-v2 sealed | 220 | **0** |
| bench-v1 sealed | 30 | **0** |
| independent null set | 1,028 | **0** |
| **Total** | **1,278** | **0** |

## 6. Benefit — MEASURED FACT

**The three long-standing structural false accepts, all F2 continuous claims, all converted to refusals:**

| Capture | `consistency` | Was | With the gate |
|---|---:|---|---|
| `burst_8PSK_k3_diag_0165` | 0.8310 | DECODED | **SIGNAL_NO_CODE** |
| `ccsds_concat_0260` | 0.9202 | DECODED | **SIGNAL_NO_CODE** |
| `stream_k7_0251` | 0.9718 | DECODED | **SIGNAL_NO_CODE** |

These three have been on record since bench-v2's first sealed run and were **not** what the gate was designed for. `SPACE_FINAL_AUDIT.md` §8 listed them as unexplained by the off-carrier mechanism; the gate catches all three.

**The sealed Doppler failure** (not a blind estimate — §4):

- wrong payloads: **52 of 54 converted to refusal (96.3 %)**
- correct payloads: **0 of 91 lost (0.0 %)**

**The two survivors, reported because they bound the claim:**

| Capture | Trajectory | Severity | `consistency` | vs bar 0.97427 |
|---|---|---:|---:|---|
| `linear_0104` | linear | 0.25 | 0.97427 | **exactly at the bar** |
| `linear_0108` | linear | 0.5 | 0.99540 | well above it |

`linear_0104` sitting *exactly* at the bar is not a coincidence to wave away: it shows the separation is tight at the top, and any bar that caught it would start costing bench-v2 decodes.

## 7. Separation on the three candidate statistics — MEASURED FACT

F2-supplied claims only, across all populations:

| Statistic | Correct (n=110) | Wrong (n=57) | Overlap |
|---|---|---|---|
| **`consistency`** | 0.9743 – 1.0000 (med 0.9976) | 0.8310 – **0.9954** (med 0.9073) | yes, at the top |
| `path_metric` | 0.9894 – 1.0000 (med 0.9998) | 0.8575 – 0.9934 (med 0.9105) | yes |
| `agreement` | 0.7950 – 1.0000 (med 0.9951) | 0.6249 – 0.9900 (med 0.7203) | wider |

**The distributions overlap.** Wrong payloads reach 0.9954, above the bar, which is exactly why two survive. This is not a clean classifier and must never be described as one.

## 8. What this does NOT establish

- **It does not fix Doppler.** It converts a wrong answer into a refusal. The payload is still not recovered; the capture still fails. What changes is that the engine stops asserting something untrue — which is what the three-outcome design exists for.
- **2 of 54 wrong payloads survive.** A gate at this bar leaves them published.
- **F1, F3 and F4 claims are untouched.** They publish no comparable payload-side statistic. Whether they need one is not addressed here.
- **Zero cost is an empirical floor**, and on the population that defined the bar it is arithmetic rather than evidence (§4).
- **The Doppler benefit is not blind** (§4).
- **Nothing here is integrated**, so no verdict the engine publishes today has changed.

## 9. A defect the tests caught, reported rather than quietly fixed

The first version of `gated()` guarded on `f2_supplied` and `consistency` but **not on the status**. `tests/test_payload_gate.py::test_the_gate_never_upgrades_a_refusal` failed: a refusal carrying a low consistency was rewritten to `SIGNAL_NO_CODE`, which would turn **UNKNOWN ("no evidence") into "a signal is there"** — the gate manufacturing a structural claim instead of withholding a payload. Real rows cannot reach that branch (`f2_supplied` already implies `DECODED`), so no measured number was affected, and the report was re-run to confirm that. The guard is now explicit and the reason is recorded in the code. **A gate that can upgrade a refusal must never reach production, and this is the kind of defect that has to surface before integration, not after.**

## 10. Recommendation

**The measurement that blocked request B is now done, and it came out in favour.** On 2,002 captures the gate costs nothing measured, removes three false accepts that have been on the books since the start, and converts 96.3 % of the Doppler failure from a wrong answer into an honest refusal.

**It is still not integrated, and this report does not integrate it.** Integration would change **refusal behaviour** in `src/`, which every authorisation in this branch has explicitly withheld, and it deserves its own decision with at least these conditions attached:

1. The bar must be a named production constant with this report cited, not an inline literal.
2. `SIGNAL_NO_CODE` must carry the reason, through the existing sufficiency mechanism, so a withheld payload is explained rather than silently dropped.
3. bench-v1, bench-v2 and the null set must be re-run **after** integration, because a post-hoc simulation of a gate is not the same artefact as the gate running inside the verdict path.
4. `SPACE_CLAIM_FIREWALL.md` §2a would need revisiting: with the gate in place, the measured limitation becomes "the engine refuses rather than publishing a wrong payload under a moving carrier" — a materially different and better sentence, which may not be claimed until the gate actually ships.

## Method note

`eval/payload_gate.py`, criteria `eval/payload_gate_criteria.json` (sha256 `5c2bb4eb8923d44e…`), committed before the harness existed. Reproduce with `python eval/payload_gate.py run` then `report`. Evidence: `results/payload_gate_rows.jsonl` (2,002 captures). Tests: `tests/test_payload_gate.py` (6). The engine's own verdict is recorded unchanged beside the gated one in every row. Sealed Doppler outcomes are read from `results/space_doppler_rows.jsonl`, never recomputed. No production file, threshold, dataset, manifest or prior report was altered.

**END OF PAYLOAD GATE RESULTS**
