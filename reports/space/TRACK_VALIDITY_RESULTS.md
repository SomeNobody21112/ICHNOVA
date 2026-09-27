# TRACK_VALIDITY_RESULTS

**ICHNOVA · SIH26147 — `SPACE-TRACK-VALIDITY-01`: making the phase tracker's validity boundary observable as evidence**

**Status: EXECUTED (2026-09-27). Additive write-only diagnostic only. Verdicts verified unchanged on all 192 sealed Doppler captures; read-out verified deterministic and verified never consulted by any decision. Full suite 247 passed.**

> **Headline — MEASURED FACT.** The engine can now report the condition its own phase tracker depends on, and the number is the tracker's own arithmetic: **π minus the largest wrapped block-to-block change its `np.unwrap` actually had to accept.** π is not a chosen threshold — it is the exact discriminant of `np.unwrap`. Read at the front end that produced the published claim, it **separates cleanly and without overlap**: static controls **1.623 – 2.712 rad**, claims that slipped **0.0001 – 0.0422**, claims that did not **0.0900 – 2.712**. **No threshold is compiled into the engine**; it publishes the number and the bound.
>
> **One negative result is load-bearing: the whole-search aggregate does NOT work** (static controls reach 0.0106) and is documented as not being a warning signal. The candidate "count of unwrap corrections" was **tested and rejected** — it fires on 10 of 48 static controls.

**Labels:** **MEASURED FACT** · **ENGINEERING INTERPRETATION** · **HYPOTHESIS**

---

## 1. What validity condition was exposed

Per tracked front end, two numbers derived from quantities `_track_phase` already computed:

| field | meaning |
|---|---|
| `max_wrapped_advance_rad` | max over blocks of \|wrap(diff(`ang`))\| — the largest block-to-block M-power phase change the unwrap had to accept |
| `unwrap_margin_rad` | `π − max_wrapped_advance_rad` — the headroom remaining before the unwrap's ambiguity |

Published in `result['diagnostics']`:

- **`phase_tracking_validity`** = `{bound_rad, n_tracked_front_ends, min_unwrap_margin_rad, max_unwrap_margin_rad}`, or **`null`** when no tracked front end exists at all.
- **`unwrap_margin_by_front_end`** — a list aligned with the **same front-end index the engine already publishes** in `stream_code.accepted_hypothesis.front`, so the validity of the tracker *behind a reported claim* is directly readable. `None` where that front end is not the tracked variant.

**The three required states, all computed rather than assumed:**

| state | how it is determined |
|---|---|
| **within the assumption** | claim's `unwrap_margin_rad` far from 0 (measured: statics ≥ 1.62; correct time-varying claims ≥ 0.090) |
| **beyond the assumption** | claim's `unwrap_margin_rad` at the ambiguity (measured: all 24 slipping claims ≤ 0.0422) |
| **indeterminate** | the field is `null` (no tracked front end ran), or the claim's front end is not the tracked variant — **153 of 192 captures** |

## 2. Why it is the tracker's actual assumption

**MEASURED FACT, from `src/pipeline.py::_track_phase`.** It computes per-block M-power angles `ang` and calls `np.unwrap(ang)`. `np.unwrap` keeps the **wrapped** block-to-block change and assumes it is the true one. That is correct **if and only if** |true change| < π. So:

- **π is not a tuning parameter.** It is the discriminant of the operation the shipped tracker performs. Nothing was chosen.
- **The quantity is not a new statistic.** `ang` is already computed; the margin is one `diff`, one wrap and one `max` over it.
- **It is not a confidence score.** It is a phase in radians with a physical meaning and a hard bound.

`tests/test_track_validity.py::test_the_margin_is_exactly_the_trackers_own_arithmetic` pins this: the published value equals `π − max|wrap(diff(block_angles))|` recomputed from the tracker's own trace.

## 3. How it behaves on the sealed evidence — MEASURED FACT

192 sealed Doppler captures, shipped engine, no correction.

**At the claim's front end — the representation that works:**

| trajectory | n | min | median | max |
|---|---:|---:|---:|---:|
| zero (control) | 2 | 2.1590 | 2.3585 | 2.5580 |
| static (control) | 2 | **1.6233** | 2.1676 | 2.7118 |
| linear | 18 | 0.0001 | 0.0144 | 0.8134 |
| pass | 17 | 0.0012 | 0.0123 | 0.6184 |

**Time-varying max 0.8134 < static min 1.6233 → NON-OVERLAPPING.**

**Against slips measured independently from the KNOWN trajectory (`SPACE-TRACK-READOUT-01`):**

| | n | min | median | max |
|---|---:|---:|---:|---:|
| no slip measured | 15 | **0.0900** | 0.5097 | 2.7118 |
| slips measured | 24 | 0.0001 | 0.0052 | **0.0422** |

**Non-overlapping, with a clear gap (0.0422 → 0.0900).** The same 24/15 split is exactly the wrong-payload / correct-payload partition, which is the independent result READOUT-01 measured against ground truth.

**Coverage:** the aggregate field is published on 150/192 and `null` on 42. At claim level, 39 captures have a claim from a tracked front end; the other 153 are honestly **INDETERMINATE**.

## 4. Does it identify the known slip regime?

**Yes — MEASURED FACT.** Every capture whose claim slipped has a claim margin ≤ 0.0422 rad; every capture whose claim did not slip has ≥ 0.0900 rad. Static controls sit an order of magnitude further away (≥ 1.62). So the read-out finds the regime that `SPACE-TRACK-READOUT-01` established, using **only** what the tracker computes and **without** access to the true trajectory.

**Two things it got wrong, and they are reported rather than hidden:**

1. **The whole-search aggregate does not separate.** `max_unwrap_margin_rad` over all tracked front ends: statics **0.0106 – 2.712**, time-varying **0.0152 – 1.640** — **OVERLAPPING**. `min_unwrap_margin_rad` is worse (statics reach 0.0000). **ENGINEERING INTERPRETATION:** `fronts` holds only front ends that passed the serial gate, and the search deliberately includes wrong-cfo and wrong-sps candidates whose trackers *should* be beyond the bound; a capture can be left with only those. So the aggregate is a fact about the search, not a warning about the result. Both aggregates are still published because both are true, and this report states plainly that neither is the indicator.
2. **A rejected candidate.** "Number of times `np.unwrap` inserted a 2π correction" looked like the natural parameter-free condition. **Measured: it fires on 10 of 48 static controls, up to 146 corrections**, because a benign crossing of the ±π boundary also triggers a branch while the wrapped change stays tiny. It was **tested and rejected**, and no proxy was substituted for it.

## 5. What it does NOT tell us

- **It measures proximity to the ambiguity, not the violation.** Aliasing is intrinsic: a true advance of exactly 2π wraps to 0 and is indistinguishable from no advance. A margin near 0 means the unwrap ran at its limit, where its branch *may* be wrong — **not** that it was.
- **It is not a verdict, and must never be read as one.** 28 REFUSED time-varying captures also sit near the bound (0.0210 – 0.2772). The engine refused those on its own bars, for its own reasons. "Beyond the bound" ≠ "decode failed".
- **It says nothing about the 30 untracked-claim failures** from `SPACE-TRACK-READOUT-01`. Where the claim came from an untracked front end, the tracker was not involved and this field is `INDETERMINATE` by construction.
- **BPSK only** (the sealed Doppler set is BPSK, M = 2). For QPSK the ambiguity step is 2π/4, so the bound should be reached at half the drift rate — **untested HYPOTHESIS**.
- **It is not a sufficiency or quality metric** and has no calibrated relationship to payload BER.
- **No threshold exists in the engine.** The banding in §3 describes measured populations on one synthetic sealed set; it is not a rule the engine applies, and nothing in `src/` compares the margin to anything.

## 6. Should it remain diagnostic-only?

**Yes — MEASURED, not argued.** `tests/test_track_validity.py::test_the_diagnostic_is_never_consulted_by_any_decision` replaces `_tracking_validity` with a function returning nonsense (`bound_rad = −1`, margins = −99) and asserts that `status`, `code`, `payload_bits`, `accept.n_hypotheses` and `n_front_ends` are all identical. Nothing in `src/` reads either field.

**ENGINEERING INTERPRETATION — it should stay diagnostic-only for a specific reason, not out of caution.** The condition is *necessary but not sufficient*: it is at the bound on 24 wrong claims **and** on 28 correct refusals. Wiring it into acceptance would reject refusals the engine already gets right, and would convert an honest "this assumption was stressed" into a false "this signal is bad". It is evidence for a human or a downstream report, and that is the whole of its value.

## 7. Can the Space engineering branch be frozen?

**Yes, on the current evidence — with the open items recorded rather than closed.**

What is settled and reproducible: the Doppler limitation is measured and published as a failure; the mechanism is characterised end to end (H1 dominant, H3 measured as a partial mechanism); carrier-estimator integration is **NOT SUPPORTED** with the reason understood; off-carrier front-end admission is a measured normal operating state that F4 rejects; and the tracker's validity boundary is now observable, validated and inert.

What stays open, and none of it is a new blocker: the 30 untracked-claim Doppler failures (an H1 question already characterised); QPSK/higher-order behaviour of the bound; the absence of any real spacecraft capture anywhere in this branch; and `SPACE_CLAIM_FIREWALL.md` §2a, **unchanged** — nothing in this branch licenses a space capability claim.

**No new research branch is opened by this result.** No remediation is proposed: not a change to the unwrap, not to the block rule, not to `TRACK_MIN_SYMBOLS`, not a tracker replacement.

## 8. Production change, in full

`src/pipeline.py` only — **61 insertions, 3 deletions**, all additive and write-only:

1. `_track_phase`'s existing optional `_trace` gains `unwrap_bound_rad`, `max_wrapped_advance_rad`, `unwrap_margin_rad`.
2. The front-end loop passes a trace and stores `unwrap_margin_rad` on each front-end record (`None` for the untracked variant).
3. New helper `_tracking_validity(fronts)` returning the aggregate or `None`.
4. `diagnostics` gains `phase_tracking_validity` and `unwrap_margin_by_front_end`.

**No** change to tracking, phase estimation, unwrap behaviour, thresholds, F4, serial independence, sps ranking, candidate generation, acceptance or refusal. No new estimator, no remediation, no new dataset.

**One collateral fix, no behaviour change:** `eval/space_doppler_mech.py:259` stubbed the tracker as `lambda y, mod: None` for its arm-A ablation; the stub now mirrors the real signature (`lambda y, mod, _trace=None: None`). Ablation semantics are identical — arm A still produces no tracked front end. This was caught by the existing `tests/test_space_doppler_mech.py`, and MECH-01's sealed data and row files were re-verified byte-identical afterwards.

## Method note

`eval/track_validity.py`, criteria `eval/track_validity_criteria.json` (sha256 `ecdc240c74f1beee…`). Reproduce with `python eval/track_validity.py run` then `report`; two consecutive runs produced **byte-identical** row files. Evidence: `results/track_validity_rows.jsonl` (192). Validation: verdicts unchanged on all 192 sealed Doppler captures; sealed datasets byte-identical (192/192, 144/144, 288/288); no previous rows, manifests, criteria or reports altered; full suite **247 passed**. This report adds forward evidence only — no earlier report was edited to agree with it.

**END OF TRACK VALIDITY RESULTS**
